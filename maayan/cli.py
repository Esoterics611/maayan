"""maayan CLI entrypoint (typer).

Each subcommand is wired up in its own prompt/module as the build progresses.
This file stays a thin layer: it parses args, builds the concrete services
(embedder, qdrant client, generation backend, clock) and injects them into the
library code. No business logic lives here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import typer

from maayan import __version__
from maayan.clock import Clock, SystemClock
from maayan.config import Settings, get_settings
from maayan.corpus.ingest import IngestResult
from maayan.corpus.models import Lang

if TYPE_CHECKING:
    from maayan.graph.models import ConceptEndpoint, RefEndpoint, Relation
    from maayan.graph.store import GraphStore
    from maayan.users.models import Role, UserOut
    from maayan.users.service import UserService

app = typer.Typer(
    name="maayan",
    help="Esoteric Torah RAG — ingest, index, retrieve, ask, and capture expert knowledge.",
    no_args_is_help=True,
    add_completion=False,
)


# --- runtime mode -----------------------------------------------------------
# Default: talk to a RUNNING Qdrant (start it with `make up`). `--mock` swaps in an
# embedded (no-Docker) Qdrant + the hashing embedder so the flow runs offline.
_MOCK = False
_MOCK_QDRANT_PATH = "data/qdrant-mock"


@app.callback()
def main(
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Run on an embedded (no-Docker) Qdrant + hashing embedder. Offline demo of "
        "the flow — NOT real retrieval quality.",
    ),
) -> None:
    """maayan — see `maayan --help`.

    By default the commands talk to a RUNNING Qdrant; one that needs it fails fast with
    fix-it instructions if it isn't reachable. Pass `--mock` BEFORE the subcommand to run
    on an embedded store with no Docker and no model download.
    """
    global _MOCK
    _MOCK = mock


def _cfg() -> Settings:
    """Resolve settings, applying `--mock` overrides (embedded Qdrant + hashing embedder)."""
    settings = get_settings()
    if _MOCK:
        settings = settings.model_copy(
            update={
                "qdrant_url": _MOCK_QDRANT_PATH,
                "embed_backend": "hashing",
                "transcribe_backend": "fake",
            }
        )
    return settings


def _fmt_ts(seconds: float) -> str:
    """Seconds → MM:SS (for transcript segment timestamps)."""
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def require_qdrant(settings: Settings) -> None:
    """Fail fast (with how-to-fix guidance) if a live Qdrant is required but unreachable.

    Embedded/in-memory stores (e.g. under `--mock`) are always available, so this is a
    no-op for them; only an http(s) Qdrant URL is health-checked.
    """
    url = settings.qdrant_url
    if not url.startswith(("http://", "https://")):
        return
    from qdrant_client import QdrantClient

    try:
        client = QdrantClient(url=url, api_key=settings.qdrant_api_key.get_secret_value() or None)
        client.get_collections()
        client.close()
    except Exception:  # noqa: BLE001 - any failure here means "not reachable"
        typer.secho(f"\n✗ Qdrant is not reachable at {url}.", fg=typer.colors.RED, err=True)
        typer.echo("  • Start it (Docker):  make up    then re-run.", err=True)
        typer.echo("  • Or run offline:     add --mock  (embedded store + hashing", err=True)
        typer.echo("                        embedder; tries the flow, not real quality).", err=True)
        raise typer.Exit(1) from None


def _primary_ip() -> str:
    """Best-effort primary outbound IP (no packets sent). Empty string on failure."""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))  # selects the outbound interface; sends nothing
            ip: str = sock.getsockname()[0]
            return ip
    except OSError:
        return ""


def _ui_display_urls(ui_host: str, port: int) -> list[str]:
    """Browsable URLs for the startup banner. ``0.0.0.0``/``::`` are bind addresses, not
    routable in a browser, so list loopback plus the machine's primary IP (e.g. the WSL2 /
    LAN address — handy when localhost forwarding into the VM doesn't work)."""
    if ui_host not in ("0.0.0.0", "::"):
        return [f"http://{ui_host}:{port}"]
    urls = [f"http://127.0.0.1:{port}"]
    ip = _primary_ip()
    if ip and ip != "127.0.0.1":
        urls.append(f"http://{ip}:{port}")
    return urls


@app.command()
def version() -> None:
    """Print the maayan version."""
    typer.echo(f"maayan {__version__}")


@app.command()
def ingest(
    book: str = typer.Option(None, "--book", help="A single Sefaria base ref to ingest."),
    all_books: bool = typer.Option(False, "--all", help="Ingest every book in config.books."),
    limit: int = typer.Option(
        None, "--limit", help="Max chapters per book (handy for a quick sample)."
    ),
    sample: int = typer.Option(5, "--sample", help="How many ingested chunks to print."),
) -> None:
    """Pull chassidus/Kabbalah text from Sefaria, normalize, and store as chunks."""
    settings = _cfg()
    if all_books:
        refs = settings.books
    elif book:
        refs = [book]
    else:
        raise typer.BadParameter("Pass --book '<ref>' or --all.")

    langs = [cast(Lang, language) for language in settings.ingest_langs if language in ("he", "en")]
    results = asyncio.run(_run_ingest(settings, refs, langs, limit))

    for r in results:
        typer.echo(f"  {r.book}: {r.sections} sections → {r.chunks} chunks upserted")

    # Show a sample of what landed.
    from maayan.corpus.store import ChunkStore

    with ChunkStore(settings.db_path) as store:
        typer.echo(f"\nTotal chunks in store: {store.count()}")
        typer.echo(f"\nSample of {sample} chunks:")
        for c in store.get_chunks(limit=sample):
            preview = c.text[:90].replace("\n", " ")
            typer.echo(f"  [{c.lang}] {c.ref}\n      {preview}…")


async def _run_ingest(
    settings: Settings, refs: list[str], langs: list[Lang], limit: int | None
) -> list[IngestResult]:
    import httpx

    from maayan.clock import SystemClock
    from maayan.corpus.ingest import ingest_books
    from maayan.corpus.sefaria import SefariaClient
    from maayan.corpus.store import ChunkStore

    async with httpx.AsyncClient(timeout=30.0) as http:
        client = SefariaClient(
            http,
            SystemClock(),
            base_url=settings.sefaria_base_url,
            rate_limit_seconds=settings.sefaria_rate_limit_seconds,
        )
        with ChunkStore(settings.db_path) as store:
            return await ingest_books(
                refs, client=client, store=store, langs=langs, max_chapters=limit
            )


@app.command(name="ingest-chabad")
def ingest_chabad(
    book: str = typer.Option(None, "--book", help="A Chabad Library book name (see config)."),
    all_books: bool = typer.Option(False, "--all", help="Ingest every config.chabad_books book."),
    limit: int = typer.Option(
        None, "--limit", help="Max leaf pages per book (handy for a quick sample)."
    ),
) -> None:
    """Pull a non-Sefaria text (e.g. Likutei Torah) from chabadlibrary.org into the store."""
    settings = _cfg()
    if all_books:
        chosen = list(settings.chabad_books.items())
    elif book:
        if book not in settings.chabad_books:
            raise typer.BadParameter(
                f"{book!r} is not in config.chabad_books ({', '.join(settings.chabad_books)})."
            )
        chosen = [(book, settings.chabad_books[book])]
    else:
        raise typer.BadParameter("Pass --book '<name>' or --all.")

    results = asyncio.run(_run_ingest_chabad(settings, chosen, limit))
    for r in results:
        typer.echo(f"  {r.book}: {r.sections} leaf pages → {r.chunks} chunks upserted")
    typer.echo("\nIngested as source='chabad' — index with `maayan index`, then it is retrievable.")


async def _run_ingest_chabad(
    settings: Settings, books: list[tuple[str, int]], limit: int | None
) -> list[IngestResult]:
    import httpx

    from maayan.clock import SystemClock
    from maayan.corpus.chabad import ChabadLibraryClient, ingest_chabad_books
    from maayan.corpus.store import ChunkStore

    async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "maayan/0.1"}) as http:
        client = ChabadLibraryClient(
            http,
            SystemClock(),
            base_url=settings.chabad_base_url,
            rate_limit_seconds=settings.chabad_rate_limit_seconds,
        )
        with ChunkStore(settings.db_path) as store:
            return await ingest_chabad_books(
                [(name, rid) for name, rid in books],
                client=client,
                store=store,
                max_leaves=limit,
                max_chars=settings.chabad_chunk_chars,
            )


@app.command()
def index(
    rebuild: bool = typer.Option(
        False, "--rebuild", help="Drop the collection and re-embed everything."
    ),
) -> None:
    """Embed stored chunks and upsert them into Qdrant (hybrid dense + sparse)."""
    from maayan.corpus.store import ChunkStore
    from maayan.embed.factory import build_embedder
    from maayan.index.pipeline import index_chunks
    from maayan.index.qdrant import QdrantIndex, build_qdrant_client

    settings = _cfg()
    require_qdrant(settings)
    typer.echo(f"Embedder: {settings.embed_backend} ({settings.embed_model})")
    embedder = build_embedder(settings)
    client = build_qdrant_client(settings)
    qindex = QdrantIndex(client, settings.collection_name, embedder.dim)

    with ChunkStore(settings.db_path) as store:
        pending = store.count(only_unindexed=True)
        typer.echo(f"Chunks to index: {'all' if rebuild else pending}")
        result = index_chunks(
            store=store,
            embedder=embedder,
            index=qindex,
            batch_size=settings.embed_batch_size,
            rebuild=rebuild,
        )

    typer.echo(
        f"\nEmbedded {result.embedded} chunks → collection "
        f"'{settings.collection_name}' now has {result.total_points} points."
    )

    # Show a sample payload.
    with ChunkStore(settings.db_path) as store:
        sample = store.get_chunks(limit=1)
    if sample:
        payload = qindex.retrieve(sample[0].id)
        if payload:
            ref = payload.get("ref")
            text = str(payload.get("text", ""))[:80]
            typer.echo(f"\nSample payload @ {ref}:")
            typer.echo(f"  lang={payload.get('lang')} source={payload.get('source')}")
            typer.echo(f"  section_path={payload.get('section_path')}")
            typer.echo(f"  text={text}…")


@app.command()
def health(
    embed: bool = typer.Option(
        False, "--embed",
        help="Also load the embedder and probe it (~15s + several GB). Off by default: "
        "a health check must never be the thing that loads a model.",
    ),
) -> None:
    """Is the stack actually working: vector store, embedder, generation backend.

    Distinct from the knowledge dashboard (`maayan stats`), which counts what is IN
    the corpus. This says whether the parts that make it usable are reachable right
    now — the difference between "no results" and "Qdrant is down".

    Exits non-zero if anything is down or degraded, so it can guard a deploy or feed
    an uptime check.
    """
    from maayan.embed.factory import build_embedder
    from maayan.health.factory import build_health_service
    from maayan.health.models import format_report

    settings = _cfg()
    embedder = build_embedder(settings) if embed else None
    report = build_health_service(settings, embedder=embedder).check()
    typer.echo(format_report(report))
    if not report.ok:
        raise typer.Exit(code=1)


@app.command()
def coverage(
    remote: bool = typer.Option(
        False, "--remote",
        help="Also fetch an INDEPENDENT segment count from Sefaria (network) and compare.",
    ),
) -> None:
    """Audit that everything which should be retrievable actually is.

    Counts the corpus from each side — stored chunks, Qdrant points, and (with
    `--remote`) the upstream source — and flags any book where they disagree. A
    silent partial ingest or half-finished re-index shows up here as a mismatch
    instead of quietly degrading every retrieval metric downstream.

    Exits non-zero when anything fails to reconcile, so it can guard a pipeline.
    """
    import asyncio

    from maayan.corpus.store import ChunkStore
    from maayan.index.coverage import build_report, format_report
    from maayan.index.qdrant import QdrantIndex, build_qdrant_client

    settings = _cfg()
    require_qdrant(settings)
    with ChunkStore(settings.db_path) as store:
        stored = store.counts_by_book()
    # Counting never touches a vector, so use the configured dim and skip loading bge-m3.
    qindex = QdrantIndex(
        build_qdrant_client(settings), settings.collection_name, settings.embed_dim
    )
    indexed = qindex.count_by_book(sorted(stored))

    expected: dict[str, int] | None = None
    if remote:
        typer.echo(f"Fetching shapes for {len(settings.books)} Sefaria books…")
        expected = asyncio.run(_sefaria_expected_counts(settings))

    report = build_report(
        stored, indexed, expected=expected, total_indexed=qindex.count()
    )
    typer.echo(format_report(report))
    if not report.ok:
        raise typer.Exit(code=1)


async def _sefaria_expected_counts(settings: Settings) -> dict[str, int]:
    """Segment count per configured book, straight from Sefaria's shape API."""
    import httpx

    from maayan.corpus.sefaria import SefariaClient

    counts: dict[str, int] = {}
    async with httpx.AsyncClient(timeout=30.0) as http:
        client = SefariaClient(
            http, SystemClock(),
            base_url=settings.sefaria_base_url,
            rate_limit_seconds=settings.sefaria_rate_limit_seconds,
        )
        for book in settings.books:
            shape = await client.fetch_shape(book)
            counts[book] = sum(shape.chapter_lengths)
    return counts


@app.command()
def search(
    query: str = typer.Argument(..., help="Query text (Hebrew or English)."),
    k: int = typer.Option(None, "--k", help="How many results to return."),
    book: str = typer.Option(None, "--book", help="Restrict to a book."),
    source: str = typer.Option(
        None, "--source", help="Restrict to a source (sefaria/expert/derived/term)."
    ),
    graph: bool = typer.Option(
        None, "--graph/--no-graph",
        help="Widen supported hits one hop along approved edges (overrides "
        "GRAPH_EXPAND_ENABLED).",
    ),
) -> None:
    """Hybrid (dense + sparse) retrieval over the indexed corpus."""
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    require_qdrant(settings)
    retriever = build_retriever(settings, graph=graph)
    results = retriever.retrieve(query, k=k, book=book, source=source).results

    if not results:
        typer.echo("No results.")
        return
    typer.echo(f'Top {len(results)} for: "{query}"\n')
    for i, r in enumerate(results, 1):
        typer.echo(f"{i:>2}. [{r.score:.4f}] {r.ref}  ({r.lang}/{r.source})")
        typer.echo(f"      {r.first_line(100)}")
        for line in (_via_line(r), _provenance_line(r)):
            if line:
                typer.echo(line)


@app.command()
def inspect(
    query: str = typer.Argument(..., help="Query text (Hebrew or English)."),
    k: int = typer.Option(None, "--k", help="Hits to show per stage."),
    book: str = typer.Option(None, "--book", help="Restrict to a book."),
    source: str = typer.Option(None, "--source", help="Restrict to a source."),
    rerank: bool = typer.Option(
        None, "--rerank/--no-rerank", help="Override RERANK_ENABLED for this run."
    ),
    expand: bool = typer.Option(
        None, "--expand/--no-expand", help="Override QUERY_EXPAND_ENABLED for this run."
    ),
) -> None:
    """Explain one retrieval: per-branch scores and the answer/refuse decision.

    Shows the query as actually sent, the dense / sparse / fused (/ rerank) rankings
    side by side, the absolute gate signals, and why the gate answered or refused —
    so "why did this refuse?" is a ten-second question, not an investigation.
    """
    from maayan.retrieve.factory import build_inspector
    from maayan.retrieve.trace import format_trace

    settings = _cfg()
    require_qdrant(settings)
    inspector = build_inspector(settings, rerank=rerank, expand=expand)
    trace = inspector.inspect(query, k=k, book=book, source=source)
    typer.echo(format_trace(trace))


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your question (Hebrew or English)."),
    k: int = typer.Option(None, "--k", help="How many sources to ground on."),
    book: str = typer.Option(None, "--book", help="Restrict to a book."),
    thread_id: str = typer.Option(
        None, "--thread", help="Ask within an existing topic thread (uses prior turns as context)."
    ),
    topic: str = typer.Option(
        None, "--topic", help="Start a new topic thread with this title, then ask within it."
    ),
    reason: bool = typer.Option(
        None, "--reason/--no-reason",
        help="Two-stage analyze→synthesize answering (overrides RAG_REASONING_ENABLED).",
    ),
    expand: bool = typer.Option(
        None, "--expand/--no-expand",
        help="Multi-query expansion + RRF fusion (overrides QUERY_EXPAND_ENABLED).",
    ),
    verify: bool = typer.Option(
        None, "--verify/--no-verify",
        help="Flag answer claims not supported by their cited sources.",
    ),
    graph: bool = typer.Option(
        None, "--graph/--no-graph",
        help="Graph expansion: widen supported grounding one hop along approved edges "
        "(overrides GRAPH_EXPAND_ENABLED).",
    ),
    agent: bool = typer.Option(
        None, "--agent/--no-agent",
        help="Chavrusa mode: a bounded multi-hop study loop (overrides AGENT_ENABLED). "
        "The refusal gate is unchanged.",
    ),
    show_trace: bool = typer.Option(
        False, "--show-trace", help="With --agent: print the study trace (the stepper)."
    ),
    show_reasoning: bool = typer.Option(
        False, "--show-reasoning", help="Print the study map produced in reasoning mode."
    ),
) -> None:
    """Answer grounded ONLY in retrieved sources, with citations (refuses if unsupported)."""
    from maayan.capture.factory import build_capture_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.parent import build_parent_context
    from maayan.generate.rag import RAGService
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    require_qdrant(settings)
    embedder = build_embedder(settings)  # built once, shared with capture
    backend = build_generation_backend(settings)
    use_expand = settings.query_expand_enabled if expand is None else expand
    use_reasoning = settings.rag_reasoning_enabled if reason is None else reason
    use_verify = settings.answer_verify_enabled if verify is None else verify
    use_agent = settings.agent_enabled if agent is None else agent
    retriever = build_retriever(
        settings, embedder=embedder, expand=use_expand, graph=graph,
        backend=backend if use_expand else None,
    )
    rag = RAGService(
        retriever, backend, score_threshold=settings.effective_score_threshold,
        reasoning=use_reasoning, verify=use_verify,
        parent_context=build_parent_context(settings),
        parent_context_chars=settings.parent_context_chars,
    )

    if use_agent and (thread_id or topic):
        typer.echo("error: --agent does not run inside threads yet; drop --thread/--topic.")
        raise typer.Exit(1)

    # Within a thread, prior turns are passed as NON-citable context; retrieval and
    # default-deny are unchanged. Outside a thread, this is a plain one-shot ask.
    active_thread: str | None = None
    trace = None
    if use_agent:
        from maayan.agent.factory import build_agent_service

        trace = build_agent_service(settings, retriever, rag, backend).study(question, k=k)
        answer = trace.answer
    elif thread_id or topic:
        from maayan.threads.factory import build_thread_service
        from maayan.threads.flow import ask_in_thread

        threads = build_thread_service(settings)
        active_thread = threads.start_thread(topic).id if topic else thread_id
        if active_thread is None:  # defensive; one of thread_id/topic is always set here
            raise typer.BadParameter("Pass --thread <id> or --topic '<title>'.")
        answer = ask_in_thread(
            rag, threads, active_thread, question,
            max_context_turns=settings.thread_context_turns,
        ).answer
    else:
        answer = rag.ask(question, k=k, book=book)

    # Record the session so an expert can annotate it later.
    capture = build_capture_service(settings, embedder=embedder)
    session = capture.start_session(answer)

    # Ask telemetry (Prompt 37): refusals become inquiries instead of evaporating.
    if settings.ask_log_enabled:
        from maayan.inquiry.log import AskLog

        AskLog(settings.db_path, SystemClock()).record(
            question=question, refused=not answer.grounded, top_score=answer.relevance,
            session_id=session.id, thread_id=active_thread, cited_refs=answer.cited_refs,
        )

    if not answer.grounded:
        typer.echo(f"\n[refused] {answer.text}")
        if answer.sources:
            typer.echo("\n(Closest, but below the relevance threshold:)")
            for s in answer.sources[:3]:
                typer.echo(f"  - {s.ref}")
        typer.echo(f"\nSession: {session.id}")
        if active_thread:
            typer.echo(f"Thread:  {active_thread}  (turn appended)")
        return

    if show_reasoning and answer.reasoning:
        typer.echo(f"\nStudy map:\n{answer.reasoning}")
    typer.echo(f"\n{answer.text}\n")
    typer.echo("Sources:")
    cited = set(answer.cited_refs)
    for s in answer.sources:
        mark = "*" if s.ref in cited else " "
        typer.echo(f"  [{mark}] {s.ref}")
        via = _via_line(s, indent="       ")
        if via:
            typer.echo(via)
    if answer.cited_refs:
        typer.echo(f"\nCited: {', '.join(answer.cited_refs)}")
    if answer.unsupported_claims:
        typer.echo("\n⚠ Claims not clearly supported by their cited sources:")
        for claim in answer.unsupported_claims:
            typer.echo(f"  - {claim}")
    if trace is not None:
        if show_trace:
            typer.echo("")
            _print_trace(trace)
        typer.echo(f"\nTrace: {trace.id}  (GET /api/traces/{trace.id})")
    typer.echo(f"\nSession: {session.id}")
    if active_thread:
        typer.echo(f"Thread:  {active_thread}  (ask turn appended; "
                   "follow up with `maayan ask '...' --thread " + active_thread + "`)")
    typer.echo("Annotate it:  maayan annotate --session "
               f"{session.id} --author 'Your Name' --kind connection --body '...' "
               "--ref '<ref>' --ref '<ref>'")


_TRACE_VERB_GLYPH = {
    "search": "🔍 חיפש",
    "open_section": "📖 פתח",
    "walk_graph": "🕸 הלך בגרף",
    "lookup_term": "📚 בדק מונח",
    "conclude": "✔ סיכם",
}


def _print_trace(trace: object) -> None:
    """Render a StudyTrace as the vertical stepper — a shiur transcript, not a log."""
    from maayan.agent.models import StudyTrace
    from maayan.graph.models import EVIDENCE_GLYPH

    assert isinstance(trace, StudyTrace)
    typer.echo("כיצד נלמד?")
    for i, step in enumerate(trace.steps, 1):
        action = step.action
        label = _TRACE_VERB_GLYPH.get(action.verb, action.verb)
        target = getattr(action, "query", None) or getattr(action, "ref", None) or getattr(
            action, "term", None
        )
        head = f"{i}. {label}" + (f'  "{target}"' if target else "")
        typer.echo(f"  {head}")
        digest = step.digest
        if digest.hits:
            top = digest.hits[0]
            typer.echo(f"       → {len(digest.hits)} sources (top: {top.ref}, {top.score:.2f})")
        for edge in digest.edges:
            glyph = EVIDENCE_GLYPH.get(edge.evidence, "?")
            typer.echo(f"       → {glyph} {edge.rel_type} ({edge.author}) → {edge.far}")
        if digest.term:
            typer.echo(f"       → {digest.term}")
        if digest.note:
            typer.echo(f"       → {digest.note}")
    budgets = trace.budgets
    if trace.forced:
        # Budget exhaustion is shown honestly, never disguised as a conclusion.
        which = budgets.exhausted or "malformed reply"
        typer.echo(f"  ⏸ הגיע לגבול ({which}) — סיכם עם מה שנאסף")
    typer.echo(
        f"  budgets: hops {budgets.hops_used}/{budgets.hops_max} · "
        f"chunks {budgets.chunks_used}/{budgets.chunks_max} · "
        f"calls {budgets.calls_used}/{budgets.calls_max}"
    )


def _provenance_line(result: object) -> str:
    """A one-line provenance note for expert/derived search results (empty for sefaria)."""
    # result is a retrieve.models.SearchResult; typed loosely to keep cli imports thin.
    r = result
    source = getattr(r, "source", "")
    meta = getattr(r, "payload", {}).get("metadata", {}) or {}
    if source == "derived":
        grounded = ", ".join(meta.get("grounded_in", []))
        return (f"      ↳ derived from an expert seed by {meta.get('author', '?')}, "
                f"developed by {meta.get('developed_by', '?')}, grounded in {grounded}")
    if source == "expert":
        linked = ", ".join(meta.get("linked_refs", []) or [])
        line = f"      ↳ expert {meta.get('kind', 'note')} by {meta.get('author', '?')}"
        return line + (f"; connects {linked}" if linked else "")
    if source == "chabad":
        path = ", ".join(meta.get("path", []) or [])
        return f"      ↳ chabadlibrary.org{f'; {path}' if path else ''}"
    if source == "term":
        surfaces = ", ".join(meta.get("surface_forms", []))
        return (f"      ↳ term [{meta.get('term_type', '?')}] by {meta.get('author', '?')}"
                + (f"; surfaces: {surfaces}" if surfaces else ""))
    return ""


def _via_line(result: object, *, indent: str = "      ") -> str:
    """The provenance thread for a graph-expanded hit: WHY this source appeared.

    Empty for seed hits — the absence is the design (unmarked = found by search,
    marked = brought by knowledge).
    """
    via = getattr(result, "via", None)
    if via is None:
        return ""
    from maayan.graph.models import EVIDENCE_GLYPH

    glyph = EVIDENCE_GLYPH.get(via.evidence, "?")
    return f"{indent}↳ via {via.rel_type} {glyph} ({via.author}) from {via.seed_ref}"


def _parse_refs(ref: list[str], refs: str) -> list[str]:
    """Collect linked refs from a repeatable --ref plus a ' | '-delimited --refs.

    Sefaria refs CONTAIN commas (e.g. "Tanya, Part I; Likkutei Amarim 1:13"), so a
    comma split shreds them. We instead take each --ref verbatim and split --refs on
    " | ", a delimiter that refs never contain — keeping multi-comma refs intact.
    """
    out = [r.strip() for r in ref if r.strip()]
    if refs:
        out.extend(part.strip() for part in refs.split(" | ") if part.strip())
    return out


@app.command()
def annotate(
    session: str = typer.Option(..., "--session", help="Session id (printed by `ask`)."),
    body: str = typer.Option(..., "--body", help="The expert's note / seed knowledge."),
    author: str = typer.Option(..., "--author", help="Expert name/id (required — provenance)."),
    kind: str = typer.Option(
        "connection", "--kind", help="correction|connection|addition|objection"
    ),
    ref: list[str] = typer.Option(  # noqa: B008 (Typer manages the per-call list default)
        None, "--ref", help="A source ref to link (repeatable; preserves commas)."
    ),
    refs: str = typer.Option(
        "", "--refs", help="Source refs to link, separated by ' | ' (refs never contain it)."
    ),
    move: str = typer.Option(None, "--move", help="Free move tag, e.g. 'pasuk->concept'."),
    directive: str = typer.Option(
        None, "--directive", help="Seed directive — what the model should develop (sep. from body)."
    ),
    opens_aspect: bool = typer.Option(
        False, "--opens-aspect", help="Mark this as a seed that opens a new aspect."
    ),
) -> None:
    """Record an expert contribution and index it as retrievable expert knowledge."""
    from maayan.capture.factory import build_capture_service

    settings = _cfg()
    capture = build_capture_service(settings)
    linked = _parse_refs(ref or [], refs)
    ann = capture.add_annotation(
        session, author=author, kind=kind, body=body, linked_refs=linked, move=move,
        directive=directive, opens_aspect=opens_aspect,
    )
    label = "seed" if ann.opens_aspect else "annotation"
    typer.echo(f"Recorded {label} {ann.id} ({ann.kind}) by {ann.author}.")
    typer.echo("Indexed as an expert chunk — it will now surface in retrieval.")
    if linked:
        typer.echo(f"Linked: {', '.join(linked)}")
    if ann.directive:
        typer.echo(f"Directive (for develop, kept out of embed text): {ann.directive}")


@app.command()
def session(session_id: str = typer.Argument(..., help="Session id to display.")) -> None:
    """Show a recorded session and its expert annotations."""
    from maayan.capture.store import CaptureStore

    settings = _cfg()
    store = CaptureStore(settings.db_path)
    s = store.get_session(session_id)
    if s is None:
        typer.echo("Session not found.")
        return
    typer.echo(f"Q: {s.question}")
    typer.echo(f"A: {s.answer_text[:300]}")
    typer.echo(f"Retrieved: {', '.join(s.retrieved_refs)}")
    annotations = store.get_annotations(session_id)
    typer.echo(f"\nAnnotations ({len(annotations)}):")
    for a in annotations:
        seed = " (seed → opens aspect)" if a.opens_aspect else ""
        typer.echo(f"  - [{a.kind}]{seed} by {a.author}: {a.body[:120]}")
        if a.linked_refs:
            typer.echo(f"      links: {', '.join(a.linked_refs)}  move: {a.move}")
        if a.directive:
            typer.echo(f"      directive: {a.directive}")


@app.command()
def develop(
    seed: str = typer.Option(..., "--seed", help="Contribution id of the seed to develop."),
    thread_id: str = typer.Option(
        None, "--thread", help="Develop within this thread (default: start a new one)."
    ),
) -> None:
    """Develop a seed under its directive, grounded in the corpus (a proposal, not corpus)."""
    from maayan.capture.store import CaptureStore
    from maayan.develop.factory import build_development_service
    from maayan.threads.factory import build_thread_service

    settings = _cfg()
    require_qdrant(settings)
    contribution = CaptureStore(settings.db_path).get_annotation(seed)
    if contribution is None:
        typer.echo(f"Seed contribution {seed!r} not found.")
        raise typer.Exit(1)

    threads = build_thread_service(settings)
    if thread_id is None:
        title = (contribution.directive or contribution.body)[:50]
        thread_id = threads.start_thread(f"Develop: {title}").id
        # Record the seed as the opening turn so the thread shows seed → development.
        threads.add_turn(
            thread_id, turn_type="seed", author=contribution.author,
            text=contribution.body, record_id=contribution.id,
        )

    dev = build_development_service(settings).develop(contribution, thread_id=thread_id)

    if not dev.grounded:
        typer.echo(f"\n[refused] {dev.text}")
        typer.echo(f"\nThread: {thread_id}")
        return

    typer.echo(f"\n{dev.text}\n")
    typer.echo(f"Grounded in: {', '.join(dev.grounded_in)}")
    if dev.cited_refs:
        typer.echo(f"Cited:       {', '.join(dev.cited_refs)}")
    typer.echo(f"\nDevelopment {dev.id} (status={dev.status}, by {dev.model}).")
    if dev.status == "proposed":
        typer.echo("A proposal — not indexed as corpus yet.")
        typer.echo(f"Approve it:  maayan approve {dev.id}   (or: maayan reject {dev.id})")
    else:
        typer.echo("Auto-approved → indexed as a derived corpus chunk.")
    typer.echo(f"Thread: {thread_id}")


@app.command()
def approve(
    development_id: str = typer.Argument(..., help="Development id to approve."),
) -> None:
    """Approve a proposed development → index it as a retrievable `derived` corpus chunk."""
    from maayan.develop.factory import build_development_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        dev = build_development_service(settings).approve(development_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Approved {dev.id} → indexed as a derived chunk.")
    typer.echo(f"  by {dev.model}, grounded in: {', '.join(dev.grounded_in)}")
    typer.echo("It will now surface in retrieval (search --source derived).")


@app.command()
def reject(
    development_id: str = typer.Argument(..., help="Development id to reject."),
) -> None:
    """Reject a proposed development. Nothing is indexed; the corpus is unchanged."""
    from maayan.develop.factory import build_development_service

    settings = _cfg()
    try:
        dev = build_development_service(settings).reject(development_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Rejected {dev.id}. Nothing indexed.")


@app.command()
def threads() -> None:
    """List persisted topic threads (most recently updated first)."""
    from maayan.threads.factory import build_thread_service

    settings = _cfg()
    service = build_thread_service(settings)
    rows = service.list_threads()
    if not rows:
        typer.echo("No threads yet. Start one as you ask/seed (Prompt 14 wires the UI).")
        return
    typer.echo(f"{len(rows)} thread(s):")
    for t in rows:
        typer.echo(f"  {t.id}  · {t.title}  (updated {t.updated_at:%Y-%m-%d %H:%M})")


@app.command()
def thread(thread_id: str = typer.Argument(..., help="Thread id to display.")) -> None:
    """Show a topic thread with its ordered turns."""
    from maayan.threads.factory import build_thread_service

    settings = _cfg()
    detail = build_thread_service(settings).get_thread_with_turns(thread_id)
    if detail is None:
        typer.echo("Thread not found.")
        return
    typer.echo(f"# {detail.thread.title}   ({detail.thread.id})")
    typer.echo(f"  created {detail.thread.created_at:%Y-%m-%d %H:%M} · "
               f"{len(detail.turns)} turns")
    for turn in detail.turns:
        snippet = turn.text[:120].replace("\n", " ")
        typer.echo(f"\n  {turn.ordinal}. [{turn.turn_type}] by {turn.author}")
        typer.echo(f"      {snippet}")
        if turn.record_id:
            typer.echo(f"      ↳ record {turn.record_id}")


@app.command(name="add-term")
def add_term(
    canonical: str = typer.Option(..., "--canonical", help="Display form, e.g. the Name of 72."),
    definition: str = typer.Option(..., "--definition", help="What the term means."),
    author: str = typer.Option(..., "--author", help="Who defined it (required — provenance)."),
    term_type: str = typer.Option(
        "concept", "--type", help="name|sefirah|partzuf|expansion|concept|other"
    ),
    surface: list[str] = typer.Option(  # noqa: B008 (Typer manages the per-call list default)
        None, "--surface", help="A surface form to match (repeatable; gershayim/quote-insensitive)."
    ),
    related: list[str] = typer.Option(  # noqa: B008 (Typer manages the per-call list default)
        None, "--related", help="A related/sibling term (repeatable)."
    ),
    source_ref: list[str] = typer.Option(  # noqa: B008 (Typer manages the per-call list default)
        None, "--source-ref", help="A supporting reference (repeatable)."
    ),
    gematria: int = typer.Option(None, "--gematria", help="Numeric value, if any (e.g. 72)."),
    sacred: bool = typer.Option(False, "--sacred", help="Mark as a Holy Name."),
) -> None:
    """Define a lexicon term / Holy Name and index it as retrievable knowledge."""
    from typing import cast

    from maayan.lexicon.factory import build_term_service
    from maayan.lexicon.models import TermType

    settings = _cfg()
    require_qdrant(settings)
    term = build_term_service(settings).add_term(
        canonical=canonical, definition=definition, author=author,
        term_type=cast(TermType, term_type), surface_forms=surface or [],
        related_terms=related or [], source_refs=source_ref or [],
        gematria=gematria, sacred=sacred,
    )
    typer.echo(f"Defined term {term.id} — {term.canonical} [{term.term_type}] by {term.author}.")
    typer.echo("Indexed as a term chunk — it will now surface in retrieval.")
    if term.surface_forms:
        typer.echo(f"Surface forms (protected from expansion): {', '.join(term.surface_forms)}")


@app.command()
def terms() -> None:
    """List curated lexicon terms."""
    from maayan.lexicon.factory import build_term_service

    rows = build_term_service(_cfg()).list_terms()
    if not rows:
        typer.echo("No terms yet. Define one with `maayan add-term`.")
        return
    typer.echo(f"{len(rows)} term(s):")
    for t in rows:
        g = f" · gematria {t.gematria}" if t.gematria is not None else ""
        typer.echo(f"  {t.id}  · {t.canonical}  [{t.term_type}]{g}  by {t.author}")


@app.command(name="lexicon-suggest")
def lexicon_suggest(
    seed: bool = typer.Option(
        True, "--seed/--no-seed", help="Draft definitions for the curated seed pack."
    ),
    mine: bool = typer.Option(
        False, "--mine/--no-mine", help="Also mine gershayim term candidates from the corpus."
    ),
    limit: int = typer.Option(20, "--limit", help="Max mined candidates to draft (cost control)."),
    model: str = typer.Option(
        None, "--model", help="Override the drafting model (e.g. an OpenRouter Claude slug)."
    ),
    include_unsupported: bool = typer.Option(
        False, "--include-unsupported", help="Also queue ungrounded drafts (flagged), for review."
    ),
) -> None:
    """Auto-draft lexicon definitions (corpus-grounded, cited) into the review queue.

    Nothing is indexed here: each draft lands as 'pending' for `lexicon-review` →
    `lexicon-approve`. Makes real generation calls — set LEXICON_DRAFT_MODEL (or --model)
    to the OpenRouter Claude slug to draft with Claude.
    """
    from maayan.corpus.store import ChunkStore
    from maayan.lexicon.factory import build_lexicon_populator
    from maayan.lexicon.populate import mine_term_candidates

    settings = _cfg()
    if model:
        settings = settings.model_copy(update={"lexicon_draft_model": model})
    require_qdrant(settings)
    populator = build_lexicon_populator(settings)

    drafted = []
    if seed:
        typer.echo("Drafting seed-pack terms…")
        drafted += populator.suggest_from_seed(persist_unsupported=include_unsupported)
    if mine:
        chunks = ChunkStore(settings.db_path).get_chunks()
        cands = mine_term_candidates(
            chunks, min_count=settings.lexicon_mine_min_count, top_n=settings.lexicon_mine_top_n
        )[:limit]
        typer.echo(f"Mined {len(cands)} candidate term(s); drafting…")
        drafted += populator.suggest_from_candidates(cands, persist_unsupported=include_unsupported)

    supported = sum(1 for s in drafted if s.supported)
    typer.echo(
        f"Drafted {len(drafted)} term(s): {supported} grounded & queued, "
        f"{len(drafted) - supported} skipped (ungrounded)."
    )
    typer.echo("Review: `maayan lexicon-review`, then `maayan lexicon-approve <id> --author ...`.")


@app.command(name="lexicon-review")
def lexicon_review() -> None:
    """List drafted lexicon terms awaiting expert approval (read-only; no models loaded)."""
    from maayan.lexicon.suggestions import SuggestionStore

    pending = SuggestionStore(_cfg().db_path).list(status="pending")
    if not pending:
        typer.echo("No pending suggestions. Run `maayan lexicon-suggest` first.")
        return
    typer.echo(f"{len(pending)} pending suggestion(s):")
    for s in pending:
        refs = ", ".join(s.source_refs) or "—"
        typer.echo(f"  {s.id}  · {s.canonical} [{s.term_type}]  (drafted by {s.model})")
        typer.echo(f"      {s.definition}")
        typer.echo(f"      ↳ grounds: {refs}")


@app.command(name="lexicon-approve")
def lexicon_approve(
    suggestion_id: str = typer.Argument(..., help="Pending suggestion id (from lexicon-review)."),
    author: str = typer.Option(..., "--author", help="The expert approving it (becomes author)."),
) -> None:
    """Approve a drafted term → index it as retrievable knowledge (author = you, the approver)."""
    from maayan.lexicon.factory import build_lexicon_populator

    settings = _cfg()
    require_qdrant(settings)
    term = build_lexicon_populator(settings).approve(suggestion_id, author=author)
    typer.echo(f"Approved → indexed term {term.id} — {term.canonical} by {term.author}.")
    typer.echo("It will now surface in retrieval (search --source term).")


@app.command(name="lexicon-reject")
def lexicon_reject(
    suggestion_id: str = typer.Argument(..., help="The pending suggestion id to reject."),
) -> None:
    """Reject a drafted term (read-only on models; just marks it rejected)."""
    from maayan.lexicon.suggestions import SuggestionStore

    SuggestionStore(_cfg().db_path).set_status(suggestion_id, "rejected")
    typer.echo(f"Rejected suggestion {suggestion_id}.")


@app.command(name="connectors-suggest")
def connectors_suggest(
    from_goldset: bool = typer.Option(
        False, "--from-goldset", help="Use the cross-text gold set questions as probes."
    ),
    limit: int = typer.Option(20, "--limit", help="Max connection candidates to draft (cost)."),
    k: int = typer.Option(8, "--k", help="Sources retrieved per probe to pair across books."),
    model: str = typer.Option(
        None, "--model", help="Override the drafting model (e.g. an OpenRouter Claude slug)."
    ),
    include_unsupported: bool = typer.Option(
        False, "--include-unsupported", help="Also queue ungrounded drafts (flagged), for review."
    ),
) -> None:
    """Auto-draft cross-text connections (grounded in both ends, cited) into the review queue.

    Nothing is indexed here: each draft lands as 'pending' for `connectors-review` →
    `connectors-approve`. Makes real generation calls — set LEXICON_DRAFT_MODEL (or --model)
    to the OpenRouter Claude slug to draft with Claude.
    """
    from maayan.capture.factory import build_connection_populator
    from maayan.capture.populate import CONNECTION_PROBES, mine_connection_candidates
    from maayan.embed.factory import build_embedder
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    if model:
        settings = settings.model_copy(update={"lexicon_draft_model": model})
    require_qdrant(settings)

    embedder = build_embedder(settings)
    retriever = build_retriever(settings, embedder=embedder)
    probes = list(CONNECTION_PROBES)
    if from_goldset:
        from maayan.eval.goldset import load_goldset

        probes = [ex.question for ex in load_goldset(settings.eval_crosstext_goldset_path)]
    candidates = mine_connection_candidates(retriever, probes, k=k)[:limit]
    typer.echo(f"Mined {len(candidates)} cross-text candidate(s); drafting…")

    populator = build_connection_populator(settings, embedder=embedder)
    drafted = populator.suggest(candidates, persist_unsupported=include_unsupported)
    supported = sum(1 for s in drafted if s.supported)
    typer.echo(
        f"Drafted {len(drafted)} connection(s): {supported} grounded & queued, "
        f"{len(drafted) - supported} skipped (not cross-text / ungrounded)."
    )
    typer.echo("Review: `maayan connectors-review`, then `connectors-approve <id> --author ...`.")


@app.command(name="connectors-review")
def connectors_review() -> None:
    """List drafted cross-text connections awaiting approval (read-only; no models loaded)."""
    from maayan.capture.suggestions import ConnectionSuggestionStore

    pending = ConnectionSuggestionStore(_cfg().db_path).list(status="pending")
    if not pending:
        typer.echo("No pending connections. Run `maayan connectors-suggest` first.")
        return
    typer.echo(f"{len(pending)} pending connection(s):")
    for s in pending:
        typer.echo(f"  {s.id}  · {' ↔ '.join(s.books)}  (drafted by {s.model})")
        typer.echo(f"      {s.statement}")
        typer.echo(f"      ↳ grounds: {', '.join(s.source_refs) or '—'}")


@app.command(name="connectors-approve")
def connectors_approve(
    suggestion_id: str = typer.Argument(..., help="Pending connection id (connectors-review)."),
    author: str = typer.Option(..., "--author", help="The expert approving it (becomes author)."),
) -> None:
    """Approve a drafted connection → index it as a retrievable cross-text connection."""
    from maayan.capture.factory import build_connection_populator

    settings = _cfg()
    require_qdrant(settings)
    ann = build_connection_populator(settings).approve(suggestion_id, author=author)
    typer.echo(f"Approved → indexed connection {ann.id} by {ann.author}.")
    typer.echo("It will now surface in retrieval alongside the sources it connects.")


@app.command(name="connectors-reject")
def connectors_reject(
    suggestion_id: str = typer.Argument(..., help="The pending connection id to reject."),
) -> None:
    """Reject a drafted connection (read-only on models; just marks it rejected)."""
    from maayan.capture.suggestions import ConnectionSuggestionStore

    ConnectionSuggestionStore(_cfg().db_path).set_status(suggestion_id, "rejected")
    typer.echo(f"Rejected connection {suggestion_id}.")


@app.command()
def populate(
    what: str = typer.Option("all", "--what", help="What to populate: lexicon | connectors | all."),
    seed: bool = typer.Option(True, "--seed/--no-seed", help="Draft the curated seed pack."),
    mine: bool = typer.Option(True, "--mine/--no-mine", help="Mine candidates from the corpus."),
    limit: int = typer.Option(20, "--limit", help="Max mined candidates per kind (cost control)."),
    approve: bool = typer.Option(
        False, "--approve", help="Auto-approve supported drafts (index them). Needs --author."
    ),
    author: str = typer.Option("", "--author", help="Approver name (required with --approve)."),
    model: str = typer.Option(
        None, "--model", help="Override the drafting model (e.g. an OpenRouter slug)."
    ),
    pace: float = typer.Option(
        None, "--pace", help="Seconds between drafts (default: config populate_pace_seconds)."
    ),
    include_unsupported: bool = typer.Option(
        False, "--include-unsupported", help="Also queue ungrounded drafts (flagged), for review."
    ),
) -> None:
    """Paced, resumable populate drip for lexicon terms and/or cross-text connections.

    Each draft is grounded in retrieved sources, cited, and faithfulness-checked; nothing
    is indexed unless you pass --approve (which still refuses unsupported drafts in code).
    Spacing + backoff let heavily rate-limited free models drip through 429s, and every
    draft persists as it happens — so a run that dies mid-way resumes cleanly on re-run.
    """
    if what not in ("lexicon", "connectors", "all"):
        raise typer.BadParameter("--what must be one of: lexicon | connectors | all")
    if approve and not author.strip():
        raise typer.BadParameter("--approve requires --author")

    settings = _cfg()
    if model:
        settings = settings.model_copy(update={"lexicon_draft_model": model})
    require_qdrant(settings)
    clock = SystemClock()
    pace_s = settings.populate_pace_seconds if pace is None else pace

    if what in ("lexicon", "all"):
        _populate_lexicon(
            settings, clock, pace_s, seed=seed, mine=mine, limit=limit,
            approve=approve, author=author, include_unsupported=include_unsupported,
        )
    if what in ("connectors", "all"):
        _populate_connectors(
            settings, clock, pace_s, mine=mine, limit=limit,
            approve=approve, author=author, include_unsupported=include_unsupported,
        )


def _populate_lexicon(
    settings: Settings,
    clock: Clock,
    pace: float,
    *,
    seed: bool,
    mine: bool,
    limit: int,
    approve: bool,
    author: str,
    include_unsupported: bool,
) -> None:
    from maayan.corpus.store import ChunkStore
    from maayan.lexicon.factory import build_lexicon_populator
    from maayan.lexicon.populate import SEED_TERMS, mine_term_candidates
    from maayan.lexicon.suggestions import SuggestionStore
    from maayan.populate.drip import run_drip

    populator = build_lexicon_populator(settings)
    queued: set[str] = set()
    for sug in SuggestionStore(settings.db_path).list():
        queued.add(sug.canonical)
        queued.update(sug.surface_forms)

    seeds = (
        [s for s in SEED_TERMS
         if not (s.canonical in queued or any(f in queued for f in s.surface_forms))]
        if seed
        else []
    )
    mined: list[Any] = []
    if mine:
        chunks = ChunkStore(settings.db_path).get_chunks()
        candidates = mine_term_candidates(
            chunks, min_count=settings.lexicon_mine_min_count, top_n=settings.lexicon_mine_top_n
        )
        mined = [c for c in candidates[:limit] if c.surface not in queued]

    work: list[tuple[str, Any]] = [("seed", s) for s in seeds] + [("mined", c) for c in mined]
    total = len(work)
    typer.echo(f"[lexicon] {total} to draft (seed={len(seeds)} mined={len(mined)}), pace={pace}s")

    def draft_one(item: tuple[str, Any]) -> Sequence[Any]:
        kind, obj = item
        if kind == "seed":
            return populator.suggest_from_seed([obj], persist_unsupported=include_unsupported)
        return populator.suggest_from_candidates([obj], persist_unsupported=include_unsupported)

    def on_result(idx: int, item: tuple[str, Any], drafts: Sequence[Any]) -> None:
        name = getattr(item[1], "canonical", None) or getattr(item[1], "surface", "?")
        for draft in drafts:
            typer.echo(f"  [{idx}/{total}] {name} supported={draft.supported}")

    def on_error(idx: int, item: tuple[str, Any], exc: Exception, attempt: int) -> None:
        typer.echo(f"  ! [{idx}/{total}] {type(exc).__name__} (attempt {attempt}) — backing off")

    stats = asyncio.run(
        run_drip(
            work, draft_one, clock=clock, pace=pace,
            max_retries=settings.populate_max_retries, backoff=settings.populate_backoff_seconds,
            on_result=on_result, on_error=on_error,
        )
    )
    typer.echo(
        f"[lexicon] drafted={stats.drafted} supported={stats.supported} failed={stats.failed}"
    )
    if approve:
        indexed = 0
        for pending in populator.list_pending():
            if pending.supported:
                populator.approve(pending.id, author=author)
                indexed += 1
        typer.echo(f"[lexicon] approved & indexed {indexed} term(s) as {author!r}.")


def _populate_connectors(
    settings: Settings,
    clock: Clock,
    pace: float,
    *,
    mine: bool,
    limit: int,
    approve: bool,
    author: str,
    include_unsupported: bool,
) -> None:
    from maayan.capture.factory import build_connection_populator
    from maayan.capture.populate import CONNECTION_PROBES, mine_connection_candidates
    from maayan.capture.suggestions import ConnectionSuggestionStore
    from maayan.embed.factory import build_embedder
    from maayan.eval.goldset import load_goldset
    from maayan.populate.drip import run_drip
    from maayan.retrieve.factory import build_retriever

    if not mine:
        typer.echo("[connectors] nothing to do (--no-mine).")
        return

    embedder = build_embedder(settings)
    retriever = build_retriever(settings, embedder=embedder)
    goldset_qs = [ex.question for ex in load_goldset(settings.eval_crosstext_goldset_path)]
    probes = list(dict.fromkeys([*CONNECTION_PROBES, *goldset_qs]))

    done = {frozenset(s.refs) for s in ConnectionSuggestionStore(settings.db_path).list()}
    mined = mine_connection_candidates(retriever, probes, k=settings.populate_connector_k)
    candidates = [c for c in mined[:limit] if frozenset(e.ref for e in c.ends) not in done]

    populator = build_connection_populator(settings, embedder=embedder)
    total = len(candidates)
    typer.echo(f"[connectors] {total} to draft (probes={len(probes)}), pace={pace}s")

    def draft_one(cand: Any) -> Sequence[Any]:
        return populator.suggest([cand], persist_unsupported=include_unsupported)

    def on_result(idx: int, cand: Any, drafts: Sequence[Any]) -> None:
        ends = " ↔ ".join(e.ref for e in cand.ends)
        for draft in drafts:
            typer.echo(f"  [{idx}/{total}] {ends} supported={draft.supported}")

    def on_error(idx: int, cand: Any, exc: Exception, attempt: int) -> None:
        typer.echo(f"  ! [{idx}/{total}] {type(exc).__name__} (attempt {attempt}) — backing off")

    stats = asyncio.run(
        run_drip(
            candidates, draft_one, clock=clock, pace=pace,
            max_retries=settings.populate_max_retries, backoff=settings.populate_backoff_seconds,
            on_result=on_result, on_error=on_error,
        )
    )
    typer.echo(
        f"[connectors] drafted={stats.drafted} supported={stats.supported} failed={stats.failed}"
    )
    if approve:
        indexed = 0
        for pending in populator.list_pending():
            if pending.supported:
                populator.approve(pending.id, author=author)
                indexed += 1
        typer.echo(f"[connectors] approved & indexed {indexed} connection(s) as {author!r}.")


@app.command()
def bench(
    goldset: str = typer.Option(None, "--goldset", help="Benchmark gold set (default: config)."),
    no_ablation: bool = typer.Option(
        False, "--no-ablation", help="Skip the Arm-A text-only vs +synthetic ablation."
    ),
    graph: bool = typer.Option(
        False, "--graph",
        help="Run Arm A as the A-graph condition (text + synthetic + graph expansion). "
        "BENCHMARK_PLAN rung 2 compares runs with this off vs on.",
    ),
    limit: int = typer.Option(0, "--limit", help="Only run the first N questions (0 = all)."),
) -> None:
    """Blinded head-to-head: grounded maayan (Arm A) vs frontier closed-book (Arm B).

    Grades both answers against the expert gold answer with a blinded frontier judge,
    and (unless --no-ablation) runs Arm A text-only vs +synthetic to isolate what the
    populated layer adds. Needs a gold set with `answer` + `stratum` fields.
    """
    from maayan.embed.factory import build_embedder
    from maayan.eval.benchmark import (
        build_closed_book,
        build_pairwise_judge,
        format_benchmark_report,
        run_benchmark,
    )
    from maayan.eval.goldset import load_goldset
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    require_qdrant(settings)
    path = goldset or settings.bench_goldset_path
    examples = load_goldset(path)
    if limit > 0:
        examples = examples[:limit]
    gradable = sum(1 for ex in examples if ex.answer is not None and not ex.should_refuse)
    closed_model = settings.bench_closed_book_model or settings.generation_model
    judge_model = (
        settings.bench_judge_model or settings.eval_judge_model or settings.generation_model
    )
    condition = "A-graph (text + synthetic + graph)" if graph else "A-synth (text + synthetic)"
    typer.echo(f"Benchmark gold set: {path} ({len(examples)} questions, {gradable} gradable)")
    typer.echo(f"Arm A maayan [{condition}]: {settings.generation_model} · "
               f"Arm B closed-book: {closed_model}")
    typer.echo(
        f"Blinded grader: {judge_model} · seed={settings.bench_seed} · ablation={not no_ablation}\n"
    )
    if judge_model in (settings.generation_model, closed_model):
        typer.echo("⚠  grader shares a model with an arm under test — set bench_judge_model.\n")

    embedder = build_embedder(settings)
    backend = build_generation_backend(settings)
    retriever = build_retriever(
        settings, embedder=embedder, expand=settings.query_expand_enabled, graph=graph,
        backend=backend if settings.query_expand_enabled else None,
    )
    rag = RAGService(
        retriever, backend, score_threshold=settings.effective_score_threshold,
        reasoning=settings.rag_reasoning_enabled, verify=settings.answer_verify_enabled,
    )
    report = run_benchmark(
        rag, build_closed_book(settings), build_pairwise_judge(settings), examples,
        seed=settings.bench_seed, ablation=not no_ablation,
    )
    typer.echo(format_benchmark_report(report))


@app.command()
def term(term_id: str = typer.Argument(..., help="Term id to display.")) -> None:
    """Show one lexicon term."""
    from maayan.lexicon.factory import build_term_service

    t = build_term_service(_cfg()).get_term(term_id)
    if t is None:
        typer.echo("Term not found.")
        return
    gem = f"  ·  gematria {t.gematria}" if t.gematria is not None else ""
    typer.echo(f"{t.canonical}   [{t.term_type}]{gem}")
    typer.echo(f"  {t.definition}")
    if t.surface_forms:
        typer.echo(f"  surface forms: {', '.join(t.surface_forms)}")
    if t.related_terms:
        typer.echo(f"  related: {', '.join(t.related_terms)}")
    if t.source_refs:
        typer.echo(f"  sources: {', '.join(t.source_refs)}")
    typer.echo(f"  by {t.author}" + ("  · sacred (Holy Name)" if t.sacred else ""))


@app.command()
def retract(
    target: str = typer.Argument(
        ..., help="The ref OR chunk id of the expert/derived/term chunk to retract."
    ),
    author: str = typer.Option(..., "--author", help="Who is retracting it (required)."),
    reason: str = typer.Option(..., "--reason", help="Why, e.g. 'superseded' / 'typo' / 'wrong'."),
) -> None:
    """Retract a piece of layered knowledge (expert/derived/term). Printed text is immutable.

    Provenanced, not a silent delete: the chunk leaves retrieval and stays gone across a
    `--rebuild`, while the retraction is recorded with who/when/why. To CORRECT a mistake,
    retract the wrong chunk (--reason superseded) and re-add the right one.
    """
    from maayan.retract.factory import build_retraction_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        r = build_retraction_service(settings).retract(target, author=author, reason=reason)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Retracted {r.ref}  (source={r.source}, chunk {r.chunk_id}).")
    typer.echo(f"  by {r.author} · reason: {r.reason}")
    typer.echo("Gone from retrieval and skipped by `index --rebuild`. The retraction is recorded.")


@app.command()
def retractions() -> None:
    """List recorded retractions (the provenanced removals of layered knowledge)."""
    from maayan.retract.factory import build_retraction_service

    rows = build_retraction_service(_cfg()).list_retractions()
    if not rows:
        typer.echo("No retractions yet. Retract a chunk with `maayan retract <ref-or-id> ...`.")
        return
    typer.echo(f"{len(rows)} retraction(s):")
    for r in rows:
        when = r.timestamp.strftime("%Y-%m-%d %H:%M")
        typer.echo(f"  {when} · [{r.source}] {r.ref}")
        typer.echo(f"      by {r.author} · {r.reason}")


@app.command(name="eval")
def evaluate(
    goldset: str = typer.Option(
        None, "--goldset", help="Gold set YAML/JSON path (default: per-mode config path)."
    ),
    compare: bool = typer.Option(
        False, "--compare", help="Compare retrieval variants (hybrid/dense, top-k) side by side."
    ),
    develop: bool = typer.Option(
        False, "--develop", help="Score the DEVELOP step (grounding + honest refusal) instead."
    ),
    crosstext: bool = typer.Option(
        False, "--crosstext", help="Score CROSS-TEXT co-retrieval (book-diversity@k) instead."
    ),
    answer: bool = typer.Option(
        False, "--answer",
        help="Score ANSWER quality (citations + faithfulness via an LLM judge) instead.",
    ),
    graph: bool = typer.Option(
        False, "--graph",
        help="With --crosstext: also run with graph expansion ON and report both "
        "(what does structure buy?).",
    ),
    captured: bool = typer.Option(
        False, "--captured",
        help="Run the machine-grown CAPTURED goldset (every approval drafted a case); "
        "writes a date-stamped JSON report and prints deltas vs the previous run.",
    ),
    lexical: bool = typer.Option(
        False, "--lexical",
        help="Score LEXICAL RECALL (term -> every chunk that contains it) instead. "
        "Ground truth comes from the corpus, so it measures recall of a term's whole "
        "discussion rather than top-1 relevance.",
    ),
    rebuild: bool = typer.Option(
        False, "--rebuild",
        help="With --lexical: regenerate the case file from the current corpus.",
    ),
    rerank: bool = typer.Option(
        False, "--rerank",
        help="With --compare: hybrid with vs without the cross-encoder reranker "
        "(downloads bge-reranker-v2-m3).",
    ),
    k: int = typer.Option(10, "--k", help="The k to highlight in the comparison table."),
) -> None:
    """Score retrieval (hit@k, recall@k, MRR), or the develop / cross-text / answer step."""
    settings = _cfg()
    require_qdrant(settings)

    if lexical:
        _eval_lexical(settings, goldset=goldset, rebuild=rebuild)
        return

    if captured:
        from maayan.eval.captured import (
            CapturedGoldsetStore,
            CapturedRunRecord,
            format_delta,
            load_previous_report,
            to_gold_examples,
            write_captured_report,
        )
        from maayan.eval.harness import format_report, run_eval
        from maayan.retrieve.factory import build_retriever

        store = CapturedGoldsetStore(settings.db_path)
        captured_examples = store.list_examples()
        if not captured_examples:
            typer.echo("(captured goldset is empty — approvals grow it automatically)")
            return
        gold = to_gold_examples(captured_examples)
        gate_only = [ex for ex in captured_examples if not ex.expected_refs]
        typer.echo(
            f"Captured goldset: {len(captured_examples)} examples "
            f"({len(gold)} ranked, {len(gate_only)} gate-only)\n"
        )
        retriever = build_retriever(settings)
        report = run_eval(
            retriever, gold, settings.eval_ks, score_threshold=settings.effective_score_threshold
        )
        typer.echo(format_report(report))
        answered = sum(
            1
            for ex in gate_only
            if retriever.retrieve(ex.question).relevance >= settings.effective_score_threshold
        )
        if gate_only:
            typer.echo(
                f"\nanswered-inquiry checks: {answered}/{len(gate_only)} "
                "now clear the gate (were refusals)"
            )
        record = CapturedRunRecord(
            date=SystemClock().now().isoformat(timespec="seconds"),
            n_ranked=len(gold), n_gate_only=len(gate_only), gate_only_answered=answered,
            ks=settings.eval_ks,
            hit={str(kk): v for kk, v in report.hit.items()},
            recall={str(kk): v for kk, v in report.recall.items()},
            mrr=report.mrr, answer_rate=report.answer_rate,
        )
        previous = load_previous_report(settings.captured_reports_dir)
        report_path = write_captured_report(record, settings.captured_reports_dir)
        typer.echo(f"\nreport: {report_path}")
        typer.echo(format_delta(record, previous))
        return

    if crosstext:
        from maayan.eval.crosstext_harness import format_crosstext_report, run_crosstext_eval
        from maayan.eval.goldset import load_goldset
        from maayan.retrieve.factory import build_retriever

        ct_path = goldset or settings.eval_crosstext_goldset_path
        ct_examples = load_goldset(ct_path)
        typer.echo(f"Cross-text gold set: {ct_path} ({len(ct_examples)} questions)\n")
        if graph:
            off = run_crosstext_eval(build_retriever(settings, graph=False), ct_examples, k=k)
            on = run_crosstext_eval(build_retriever(settings, graph=True), ct_examples, k=k)
            typer.echo("— graph expansion OFF —")
            typer.echo(format_crosstext_report(off))
            typer.echo("\n— graph expansion ON —")
            typer.echo(format_crosstext_report(on))
            typer.echo(
                f"\nΔ coverage: {on.mean_coverage - off.mean_coverage:+.3f}   "
                f"Δ ≥2-book rate: {on.multi_book_rate - off.multi_book_rate:+.3f}"
            )
            return
        ct_report = run_crosstext_eval(build_retriever(settings), ct_examples, k=k)
        typer.echo(format_crosstext_report(ct_report))
        return

    if answer:
        from maayan.embed.factory import build_embedder
        from maayan.eval.answer_harness import format_answer_report, run_answer_eval
        from maayan.eval.goldset import load_goldset
        from maayan.eval.judge import build_answer_judge
        from maayan.generate.factory import build_generation_backend
        from maayan.generate.rag import RAGService
        from maayan.retrieve.factory import build_retriever

        a_path = goldset or settings.eval_answer_goldset_path
        a_examples = load_goldset(a_path)
        typer.echo(f"Answer gold set: {a_path} ({len(a_examples)} questions)")
        typer.echo(f"Default-deny gate threshold: {settings.effective_score_threshold}")
        judge_model = settings.eval_judge_model or settings.generation_model
        typer.echo(
            f"Pipeline: expand={settings.query_expand_enabled} "
            f"reason={settings.rag_reasoning_enabled} verify={settings.answer_verify_enabled} "
            f"· judge={judge_model}\n"
        )
        # Evaluate the REAL configured pipeline (expansion/reasoning/verify per .env).
        embedder = build_embedder(settings)
        backend = build_generation_backend(settings)
        retriever = build_retriever(
            settings, embedder=embedder, expand=settings.query_expand_enabled,
            backend=backend if settings.query_expand_enabled else None,
        )
        rag = RAGService(
            retriever, backend, score_threshold=settings.effective_score_threshold,
            reasoning=settings.rag_reasoning_enabled, verify=settings.answer_verify_enabled,
        )
        a_report = run_answer_eval(rag, build_answer_judge(settings), a_examples)
        typer.echo(format_answer_report(a_report))
        return

    if develop:
        from maayan.develop.factory import build_develop_eval_setup
        from maayan.eval.develop_goldset import load_develop_goldset
        from maayan.eval.develop_harness import format_develop_report, run_develop_eval

        dev_path = goldset or settings.eval_develop_goldset_path
        dev_examples = load_develop_goldset(dev_path)
        typer.echo(f"Develop gold set: {dev_path} ({len(dev_examples)} seeds)")
        typer.echo(f"Default-deny gate threshold: {settings.effective_score_threshold}\n")
        service, dev_threads, clock = build_develop_eval_setup(settings)
        dev_report = run_develop_eval(service, dev_threads, clock, dev_examples)
        typer.echo(format_develop_report(dev_report))
        return

    from maayan.eval.goldset import load_goldset
    from maayan.eval.harness import (
        default_variants,
        format_comparison,
        format_report,
        rerank_variants,
        run_comparison,
        run_eval,
    )
    from maayan.retrieve.factory import build_retriever

    path = goldset or settings.eval_goldset_path
    examples = load_goldset(path)
    typer.echo(f"Gold set: {path} ({len(examples)} questions)")
    typer.echo(f"Default-deny gate threshold: {settings.effective_score_threshold}\n")

    if compare:
        from maayan.embed.factory import build_embedder

        embedder = build_embedder(settings)  # built once, shared across same-model variants
        reports = run_comparison(
            settings,
            rerank_variants() if rerank else default_variants(),
            examples,
            settings.eval_ks,
            score_threshold=settings.effective_score_threshold,
            embedder=embedder,
        )
        typer.echo(format_comparison(reports, k=k))
    else:
        retriever = build_retriever(settings)
        report = run_eval(
            retriever, examples, settings.eval_ks,
            score_threshold=settings.effective_score_threshold,
        )
        typer.echo(format_report(report))


def _eval_lexical(settings: Settings, *, goldset: str | None, rebuild: bool) -> None:
    """Run (or regenerate) the lexical recall guard."""
    from maayan.corpus.store import ChunkStore
    from maayan.eval.lexical import (
        LexicalGoldset,
        format_lexical_report,
        load_lexical_goldset,
        run_lexical_eval,
        save_lexical_goldset,
        select_cases,
    )
    from maayan.retrieve.factory import build_retriever

    path = goldset or settings.eval_lexical_goldset_path
    if rebuild:
        with ChunkStore(settings.db_path) as store:
            chunks = store.get_chunks()
            cases = select_cases(
                chunks,
                settings.eval_lexical_terms,
                min_occurrences=settings.eval_lexical_min_occurrences,
                max_occurrences=settings.eval_lexical_max_occurrences,
            )
            save_lexical_goldset(
                LexicalGoldset(corpus_chunks=len(chunks), cases=cases), path
            )
        skipped = len(settings.eval_lexical_terms) - len(cases)
        typer.echo(
            f"Wrote {len(cases)} cases to {path} "
            f"({skipped} candidate term(s) outside the occurrence range).\n"
        )

    if not Path(path).exists():
        typer.echo(f"No lexical gold set at {path}. Generate one with --lexical --rebuild.")
        raise typer.Exit(1)
    gold = load_lexical_goldset(path)
    with ChunkStore(settings.db_path) as store:
        live = store.count()
    if gold.corpus_chunks and gold.corpus_chunks != live:
        typer.echo(
            f"WARNING: cases were generated against {gold.corpus_chunks} chunks but the "
            f"store now has {live}. Re-run with --rebuild, or the ground truth is stale.\n"
        )
    typer.echo(f"Lexical gold set: {path} ({len(gold.cases)} terms)\n")
    report = run_lexical_eval(
        build_retriever(settings), gold.cases, settings.eval_ks
    )
    typer.echo(format_lexical_report(report))


@app.command(name="eval-expand")
def eval_expand(
    goldset: str = typer.Option(
        None, "--goldset", help="Gold set path (default: retrieval goldset, or cross-text)."
    ),
    crosstext: bool = typer.Option(
        False, "--crosstext", help="Use the cross-text gold set (expansion helps most here)."
    ),
    k: int = typer.Option(10, "--k", help="The k to highlight in the comparison."),
) -> None:
    """Compare retrieval WITHOUT vs WITH query expansion — the recall@k / MRR lift."""
    from dataclasses import replace

    from maayan.embed.factory import build_embedder
    from maayan.eval.goldset import load_goldset
    from maayan.eval.harness import EvalReport, format_comparison, run_eval
    from maayan.generate.base import GenerationBackend
    from maayan.generate.factory import build_generation_backend
    from maayan.retrieve.factory import build_retriever
    from maayan.retrieve.retriever import Retrieving

    settings = _cfg()
    require_qdrant(settings)
    path = goldset or (
        settings.eval_crosstext_goldset_path if crosstext else settings.eval_goldset_path
    )
    examples = load_goldset(path)
    typer.echo(f"Gold set: {path} ({len(examples)} questions)")

    embedder = build_embedder(settings)  # shared across both variants
    # Enable the LLM expander if a backend is configured; else compare lexicon-only.
    backend: GenerationBackend | None = None
    try:
        backend = build_generation_backend(settings)
    except ValueError:
        typer.echo("(no generation backend configured — expansion is lexicon-only)")
    mode = "lexicon+LLM" if backend else "lexicon-only"

    base = build_retriever(settings, embedder=embedder, expand=False)
    expanded = build_retriever(settings, embedder=embedder, expand=True, backend=backend)

    def _scored(retriever: Retrieving, label: str) -> EvalReport:
        report = run_eval(
            retriever, examples, settings.eval_ks,
            score_threshold=settings.effective_score_threshold,
        )
        return replace(report, variant=label)

    reports = [_scored(base, "no-expand"), _scored(expanded, f"expand ({mode})")]
    typer.echo("")
    typer.echo(format_comparison(reports, k=k))


@app.command()
def compose(
    title: str = typer.Option(..., "--title", help="The piece's title."),
    intent: str = typer.Option(..., "--intent", help="What the piece should do / teach."),
    author: str = typer.Option(..., "--author", help="Who is composing it (required)."),
    content_type: str = typer.Option(
        "shiur_outline", "--type", help="shiur_outline|essay|digest|other"
    ),
    sections: int = typer.Option(
        None, "--sections", help="Desired section count (still capped by compose_max_sections)."
    ),
    book: str = typer.Option(None, "--book", help="Restrict retrieval to a book (source scope)."),
    thread_id: str = typer.Option(None, "--thread", help="Compose within an existing thread."),
) -> None:
    """Propose a grounded multi-section outline from a brief (scaffolding; fill it next)."""
    import uuid as _uuid
    from typing import cast

    from maayan.capture.convert import detect_lang
    from maayan.compose.factory import build_composition_service
    from maayan.compose.models import Brief, ContentType, SourceScope

    settings = _cfg()
    require_qdrant(settings)
    brief = Brief(
        id=str(_uuid.uuid4()), title=title, intent=intent, author=author,
        content_type=cast(ContentType, content_type),
        lang=detect_lang(intent),
        target_sections=sections,
        source_scope=SourceScope(book=book),
        thread_id=thread_id,
    )
    composition = build_composition_service(settings).propose_outline(brief)

    typer.echo(f'Proposed outline for "{brief.title}" ({brief.content_type}):\n')
    for i, section in enumerate(composition.sections, 1):
        typer.echo(f"{i:>2}. {section.heading}")
        typer.echo(f"      ↳ retrieval: {section.query}")
    typer.echo(
        f"\nComposition {composition.id} (status={composition.status}, by {composition.model})."
    )
    if settings.compose_auto_outline:
        _print_filled_document(composition)
        typer.echo("\ncompose_auto_outline=true → filled immediately.")
    else:
        typer.echo("Edit/approve the outline, then fill it:  maayan compose-fill " + composition.id)


@app.command(name="compose-fill")
def compose_fill(
    composition_id: str = typer.Argument(..., help="Composition id (printed by `compose`)."),
) -> None:
    """Fill an outline's sections with grounded, cited passages — or honest gaps."""
    from maayan.compose.factory import build_composition_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        composition = build_composition_service(settings).fill(composition_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    _print_filled_document(composition)


def _print_filled_document(composition: object) -> None:
    """Render a filled composition: each section, its citations, and gap markers."""
    sections = getattr(composition, "sections", [])
    for i, section in enumerate(sections, 1):
        if section.supported:
            typer.echo(f"\n## {i}. {section.heading}")
            typer.echo(section.text)
            if section.cited_refs:
                typer.echo(f"   Cited: {', '.join(section.cited_refs)}")
        else:
            typer.echo(f"\n## {i}. {section.heading}   [GAP — corpus silent]")
            typer.echo(section.text)
    grounded = sum(1 for s in sections if s.supported)
    typer.echo(f"\n{grounded}/{len(sections)} sections grounded; "
               f"{len(sections) - grounded} honest gap(s).")


@app.command(name="compose-export")
def compose_export(
    composition_id: str = typer.Argument(..., help="Composition id to export."),
    out: str = typer.Option(..., "--out", help="Path to write the assembled markdown to."),
) -> None:
    """Assemble a composition into markdown (with a provenance footer) and write it to a file."""
    from pathlib import Path

    from maayan.compose.factory import build_composition_service

    try:
        markdown = build_composition_service(_cfg()).assemble(composition_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(markdown, encoding="utf-8")
    typer.echo(f"Wrote {len(markdown)} chars → {out}")


@app.command(name="compose-approve")
def compose_approve(
    composition_id: str = typer.Argument(..., help="Composition id to approve."),
) -> None:
    """Approve a composition (does NOT bulk-index the prose; promote connections instead)."""
    from maayan.compose.factory import build_composition_service

    try:
        composition = build_composition_service(_cfg()).approve(composition_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Approved {composition.id}. Nothing indexed — the prose is a draft, not corpus.")
    typer.echo("Promote a connection to feed the corpus:  maayan compose-promote "
               f"{composition.id} --section <n> --author '...' --insight '...'")


@app.command(name="compose-reject")
def compose_reject(
    composition_id: str = typer.Argument(..., help="Composition id to reject."),
) -> None:
    """Reject a composition. Changes nothing in the corpus."""
    from maayan.compose.factory import build_composition_service

    try:
        composition = build_composition_service(_cfg()).reject(composition_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Rejected {composition.id}. The corpus is unchanged.")


@app.command(name="compose-promote")
def compose_promote(
    composition_id: str = typer.Argument(..., help="Composition id."),
    section: int = typer.Option(..., "--section", help="1-based section number to promote."),
    author: str = typer.Option(..., "--author", help="Who is promoting it (required)."),
    insight: str = typer.Option(..., "--insight", help="The connecting insight (the knowledge)."),
) -> None:
    """Promote one section's connection into the corpus via the existing capture loop."""
    from maayan.compose.factory import build_composition_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        ann = build_composition_service(settings).promote_connection(
            composition_id, section - 1, author=author, insight=insight
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    typer.echo(f"Promoted section {section} → expert connection {ann.id} by {ann.author}.")
    if ann.linked_refs:
        typer.echo(f"Connects: {', '.join(ann.linked_refs)}")
    typer.echo("Indexed as an expert chunk — it will now surface in retrieval.")


@app.command()
def compositions() -> None:
    """List compositions (proposed / approved / rejected)."""
    from maayan.compose.factory import build_composition_service

    rows = build_composition_service(_cfg()).list_compositions()
    if not rows:
        typer.echo("No compositions yet. Start one with `maayan compose`.")
        return
    typer.echo(f"{len(rows)} composition(s):")
    for c in rows:
        typer.echo(f"  {c.id}  · {c.status}  · {len(c.sections)} sections "
                   f"({c.supported_sections} grounded, {c.gap_sections} gaps)  by {c.model}")


@app.command()
def composition(
    composition_id: str = typer.Argument(..., help="Composition id to show."),
) -> None:
    """Show one composition (assembled markdown)."""
    from maayan.compose.factory import build_composition_service

    try:
        typer.echo(build_composition_service(_cfg()).assemble(composition_id))
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


@app.command()
def stats() -> None:
    """A steward's-eye view of the Knowledge base: chunks, contributions, developments, more.

    Read-only. Use it to decide what to retract and to watch the corpus grow.
    """
    from maayan.stats.factory import build_stats_service
    from maayan.stats.service import format_stats

    snapshot = build_stats_service(_cfg()).collect()
    typer.echo(format_stats(snapshot))


@app.command()
def transcribe(
    audio_path: str = typer.Argument(..., help="Path to an audio file (a shiur recording)."),
    lang: str = typer.Option(None, "--lang", help="ASR language code (default from config)."),
) -> None:
    """Store + transcribe a recording into timestamped segments (the shiur pipeline spine).

    Idempotent by content hash. The transcript is printed, not yet ingested — review
    and approval into source="shiur" corpus come in later prompts. Use `--mock` (or
    TRANSCRIBE_BACKEND=fake) to try the flow offline without downloading Whisper.
    """
    from pathlib import Path

    from maayan.audio.store import AudioStore
    from maayan.transcribe.factory import build_transcriber

    settings = _cfg()
    transcriber = build_transcriber(settings)
    used_lang = lang or settings.transcribe_lang
    typer.echo(f"Transcriber: {settings.transcribe_backend} (lang={used_lang})")

    with AudioStore(settings.db_path) as store:
        asset = store.store_file(audio_path, owner="cli", audio_dir=settings.audio_dir)
    meta = f", {asset.duration_s:.1f}s @ {asset.sample_rate}Hz" if asset.duration_s else ""
    typer.echo(f"Stored audio {asset.id} ({asset.filename}){meta}")

    transcript = transcriber.transcribe(Path(asset.path), lang=lang)
    transcript = transcript.model_copy(update={"audio_id": asset.id})
    typer.echo(
        f"\nTranscript {transcript.id} — {transcript.backend}/{transcript.model}, "
        f"{transcript.lang}, {len(transcript.segments)} segment(s):\n"
    )
    for seg in transcript.segments:
        typer.echo(f"  [{_fmt_ts(seg.start_s)}–{_fmt_ts(seg.end_s)}] {seg.display_text}")


@app.command()
def backup(
    keep: int | None = typer.Option(
        None, "--keep", help="How many recent backups to retain (default: config backup_keep)."
    ),
) -> None:
    """Back up the SQLite knowledge layer (consistent online copy) to the backup dir."""
    from maayan.backup import backup_sqlite

    settings = _cfg()
    dest = backup_sqlite(
        settings.db_path,
        settings.backup_dir,
        keep=keep if keep is not None else settings.backup_keep,
    )
    typer.echo(f"Backed up {settings.db_path} → {dest}")


@app.command()
def ui() -> None:
    """Run the local chat + capture web UI (FastAPI)."""
    import uvicorn

    from maayan.agent.factory import build_agent_service
    from maayan.capture.factory import build_capture_service
    from maayan.compose.factory import build_composition_service
    from maayan.corpus.store import ChunkStore
    from maayan.develop.factory import build_development_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.parent import build_parent_context
    from maayan.generate.rag import RAGService
    from maayan.inbox.factory import build_inbox_service
    from maayan.lexicon.factory import build_term_service
    from maayan.logconfig import configure_logging
    from maayan.ocr.factory import build_ocrer
    from maayan.retract.factory import build_retraction_service
    from maayan.retrieve.factory import build_retriever
    from maayan.stats.factory import build_stats_service
    from maayan.threads.factory import build_thread_service
    from maayan.transcribe.factory import build_transcription_service
    from maayan.ui.app import create_app
    from maayan.users.factory import build_user_service

    settings = _cfg()
    configure_logging(settings.log_level)  # surface diagnostics (e.g. compose fill gate) in the log
    require_qdrant(settings)
    embedder = build_embedder(settings)  # built once, shared across services
    backend = build_generation_backend(settings)
    retriever = build_retriever(
        settings, embedder=embedder, expand=settings.query_expand_enabled,
        backend=backend if settings.query_expand_enabled else None,
    )
    rag = RAGService(
        retriever, backend, score_threshold=settings.effective_score_threshold,
        reasoning=settings.rag_reasoning_enabled, verify=settings.answer_verify_enabled,
        parent_context=build_parent_context(settings),
        parent_context_chars=settings.parent_context_chars,
    )
    capture = build_capture_service(settings, embedder=embedder)
    threads = build_thread_service(settings)
    develop = build_development_service(settings, embedder=embedder)
    terms = build_term_service(settings, embedder=embedder)
    retraction = build_retraction_service(settings, embedder=embedder)
    stats = build_stats_service(settings)
    compose_service = build_composition_service(settings, embedder=embedder)
    transcription = build_transcription_service(settings, terms=terms, embedder=embedder)
    chunks_store = ChunkStore(settings.db_path)  # read-only reader/library browsing
    ocr = build_ocrer(settings)  # None unless OCR_BACKEND set (additive capture surface)
    inbox = build_inbox_service(settings)
    users = build_user_service(settings)
    if settings.auth_enabled:
        seeded = users.ensure_seed_admin()
        if seeded is not None:
            typer.echo(f"auth: seeded first admin '{seeded.username}' (rotate the password!)")

    # Inquiry queue wiring (Prompt 37): telemetry + the שאלות לרב panel.
    from maayan.eval.captured import build_captured_recorder
    from maayan.graph.apparatus import ApparatusService
    from maayan.graph.store import GraphStore
    from maayan.inquiry.log import AskLog
    from maayan.inquiry.store import InquiryStore
    from maayan.lexicon.store import TermStore
    from maayan.lexicon.suggestions import SuggestionStore

    clock = SystemClock()
    ask_log = AskLog(settings.db_path, clock) if settings.ask_log_enabled else None
    recorder = build_captured_recorder(settings, clock=clock)
    graph_store = GraphStore(settings.db_path)
    # The margins (Prompt 36): read-only composition over the same stores.
    from maayan.develop.store import DevelopmentStore

    apparatus = ApparatusService(
        chunks_store, graph_store, TermStore(settings.db_path),
        DevelopmentStore(settings.db_path),
    )
    from maayan.health.factory import build_health_service

    application = create_app(
        rag, capture, threads, develop, terms, retraction, stats, compose_service,
        users=users,
        transcription=transcription,
        chunks=chunks_store,
        ocr=ocr,
        inbox=inbox,
        ask_log=ask_log,
        inquiries=InquiryStore(settings.db_path, clock, recorder=recorder),
        graph=graph_store,
        suggestions=SuggestionStore(settings.db_path),
        apparatus=apparatus,
        traces=_trace_store(settings),
        agent=build_agent_service(settings, retriever, rag, backend),
        captured=_captured_store(settings),
        # The UI already holds the loaded embedder, so the health probe can exercise
        # it for real without paying the ~15s model load a second time.
        health=build_health_service(settings, embedder=embedder),
        retriever=retriever,
        settings=settings,
        ocr_lang=settings.ocr_lang,
        context_turns=settings.thread_context_turns,
        auth_enabled=settings.auth_enabled,
        session_cookie_name=settings.session_cookie_name,
        cookie_secure=settings.auth_cookie_secure,
        cookie_max_age=settings.session_ttl_hours * 3600,
    )
    urls = _ui_display_urls(settings.ui_host, settings.ui_port)
    suffix = "  [auth: login required]" if settings.auth_enabled else ""
    typer.echo("maayan UI → " + "  or  ".join(urls) + suffix)
    typer.echo("  (open one of those in your browser; not the 0.0.0.0 bind address)")
    uvicorn.run(application, host=settings.ui_host, port=settings.ui_port)


# --- knowledge graph (Phase 7, Prompt 33) -----------------------------------
# Typed, provenanced, gated relations between refs and concepts. Construction at
# the edge as always: the commands build the stores and inject them.
graph_app = typer.Typer(
    help="Typed knowledge-graph edges: add, approve, list, show, backfill.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(graph_app, name="graph")


def _graph_store_cli() -> GraphStore:
    from maayan.graph.store import GraphStore

    return GraphStore(_cfg().db_path)


def _trace_store(settings: Settings) -> Any:
    from maayan.agent.store import TraceStore

    return TraceStore(settings.db_path)


def _captured_store(settings: Settings) -> Any:
    from maayan.eval.captured import CapturedGoldsetStore

    return CapturedGoldsetStore(settings.db_path)


def _parse_endpoint(
    ref: str | None, concept_id: str | None, side: str
) -> RefEndpoint | ConceptEndpoint:
    from maayan.graph.models import ConceptEndpoint, RefEndpoint

    if (ref is None) == (concept_id is None):
        typer.echo(f"error: give exactly one of --{side} (a ref) or --{side}-concept")
        raise typer.Exit(1)
    if ref is not None:
        return RefEndpoint(ref=ref)
    assert concept_id is not None  # the exactly-one check above guarantees it
    return ConceptEndpoint(concept_id=concept_id)


def _relation_line(relation: Relation, *, perspective: str | None = None) -> str:
    """One human line per edge: badge, endpoints, author, status."""
    from maayan.graph.models import EVIDENCE_GLYPH, endpoint_str

    glyph = EVIDENCE_GLYPH.get(relation.evidence, "?")
    subject, obj = endpoint_str(relation.subject), endpoint_str(relation.object)
    if perspective is not None and subject == perspective:
        arrow = f"—{relation.rel_type}→ {obj}"
    elif perspective is not None and obj == perspective:
        arrow = f"←{relation.rel_type}— {subject}"
    else:
        arrow = f"{subject} —{relation.rel_type}→ {obj}"
    status = "" if relation.status == "approved" else f"  [{relation.status}]"
    return f"{glyph} {arrow}   ({relation.author}, {relation.evidence}){status}"


@graph_app.command("add")
def graph_add(
    rel_type: str = typer.Option(..., "--type", "-t", help="Relation type (e.g. connects)."),
    author: str = typer.Option(..., "--author", "-a", help="Who asserts this edge."),
    subject: str | None = typer.Option(None, "--subject", "-s", help="Subject ref."),
    subject_concept: str | None = typer.Option(None, "--subject-concept"),
    object_ref: str | None = typer.Option(None, "--object", "-o", help="Object ref."),
    object_concept: str | None = typer.Option(None, "--object-concept"),
    note: str | None = typer.Option(None, "--note", help="Optional free-form note."),
    confidence: float | None = typer.Option(
        None, "--confidence", help="0–1; defaults to graph_default_confidence."
    ),
) -> None:
    """Propose a typed relation (evidence 'expert'). Approval is a separate, gated step."""
    from typing import get_args

    from maayan.graph.models import Relation, RelationType

    if rel_type not in get_args(RelationType):
        known = ", ".join(get_args(RelationType))
        typer.echo(f"error: unknown --type {rel_type!r}; one of: {known}")
        raise typer.Exit(1)
    settings = _cfg()
    relation = Relation.make(
        subject=_parse_endpoint(subject, subject_concept, "subject"),
        object=_parse_endpoint(object_ref, object_concept, "object"),
        rel_type=cast("RelationType", rel_type),
        evidence="expert",
        confidence=confidence if confidence is not None else settings.graph_default_confidence,
        author=author,
        note=note,
        created_at=SystemClock().now(),
    )
    stored = _graph_store_cli().save_relation(relation)
    typer.echo(_relation_line(stored))
    typer.echo(f"id: {stored.id}")
    if stored.status == "proposed":
        typer.echo(f"proposed — approve with: maayan graph approve {stored.id} --author <you>")


@graph_app.command("approve")
def graph_approve(
    relation_id: str = typer.Argument(..., help="Relation id to approve."),
    author: str = typer.Option(..., "--author", "-a", help="The approving human."),
) -> None:
    """Approve one proposed relation (the only path to 'approved')."""
    try:
        relation = _graph_store_cli().approve(relation_id, author=author)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"approved: {_relation_line(relation)}")


@graph_app.command("retract")
def graph_retract(
    relation_id: str = typer.Argument(..., help="Relation id to retract."),
    author: str = typer.Option(..., "--author", "-a", help="Who retracts it."),
    reason: str = typer.Option(..., "--reason", "-r", help="Why (audited)."),
) -> None:
    """Retract one relation — audited (who/when/why), never a silent delete."""
    from maayan.retract.factory import build_retraction_service

    try:
        retraction = build_retraction_service(_cfg()).retract_relation(
            relation_id, author=author, reason=reason
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"retracted: {retraction.ref}  (by {retraction.author}: {retraction.reason})")


@graph_app.command("list")
def graph_list(
    status: str | None = typer.Option(None, "--status", help="proposed|approved|retracted"),
    rel_type: str | None = typer.Option(None, "--type", "-t"),
    evidence: str | None = typer.Option(None, "--evidence", "-e"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """List relations, optionally filtered."""
    rows = _graph_store_cli().list_relations(
        status=status, rel_type=rel_type, evidence=evidence, limit=limit
    )
    if not rows:
        typer.echo("(no relations match)")
        return
    for relation in rows:
        typer.echo(_relation_line(relation))
        typer.echo(f"    id: {relation.id}")


@graph_app.command("show")
def graph_show(
    ref: str = typer.Option(..., "--ref", help="Canonical ref to show the edges of."),
) -> None:
    """Show every relation touching a ref, grouped by type (the margins, in text)."""
    from maayan.graph.models import RefEndpoint

    relations = _graph_store_cli().relations_for(RefEndpoint(ref=ref))
    if not relations:
        typer.echo(f"(no relations touch {ref!r})")
        return
    typer.echo(f"{ref} — {len(relations)} relation(s)")
    current: str | None = None
    for relation in relations:  # relations_for orders by rel_type
        if relation.rel_type != current:
            current = relation.rel_type
            typer.echo(f"  {current}:")
        typer.echo(f"    {_relation_line(relation, perspective=ref)}")


@graph_app.command("backfill")
def graph_backfill() -> None:
    """Lift existing expert connection chunks into typed relations (idempotent)."""
    from maayan.corpus.store import ChunkStore
    from maayan.graph.backfill import backfill_relations

    settings = _cfg()
    result = backfill_relations(
        ChunkStore(settings.db_path), _graph_store_cli(), SystemClock(), settings
    )
    typer.echo(
        f"expert chunks seen: {result.chunks_seen}  "
        f"(connections: {result.connection_chunks}, skipped: {result.skipped_chunks})"
    )
    typer.echo(
        f"relations created: {result.relations_created}  "
        f"already present: {result.relations_existing}"
    )


@graph_app.command("ingest-links")
def graph_ingest_links(
    book: str | None = typer.Option(
        None, "--book", help="Only refs of this book (name or base-ref prefix)."
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Fetch links for at most N (unfetched) refs."
    ),
    join: bool = typer.Option(
        True, "--join/--no-join", help="Run the deterministic pasuk join afterwards."
    ),
) -> None:
    """Ingest Sefaria's curated links as edges — no model, no spend. Resumable."""
    import httpx as _httpx

    from maayan.corpus.store import ChunkStore
    from maayan.graph.links import LinksCursorStore, SefariaLinksClient, ingest_links

    settings = _cfg()
    if not settings.graph_links_enabled:
        typer.echo("graph link ingestion is disabled (GRAPH_LINKS_ENABLED=false)")
        raise typer.Exit(1)
    clock = SystemClock()

    async def _run() -> None:
        async with _httpx.AsyncClient(timeout=30.0) as http:
            client = SefariaLinksClient(
                http,
                clock,
                base_url=settings.sefaria_base_url,
                rate_limit_seconds=settings.sefaria_rate_limit_seconds,
            )
            result = await ingest_links(
                ChunkStore(settings.db_path),
                _graph_store_cli(),
                LinksCursorStore(settings.db_path),
                client,
                clock,
                settings,
                book=book,
                limit=limit,
            )
        typer.echo(
            f"refs: {result.refs_seen} seen, {result.refs_fetched} fetched, "
            f"{result.refs_skipped} already done, {result.refs_failed} failed (will retry)"
        )
        typer.echo(
            f"links: {result.links_seen} seen, {result.links_kept} kept → "
            f"{result.relations_created} new edges ({result.relations_existing} existing)"
        )

    asyncio.run(_run())
    if join:
        _run_pasuk_join()


def _run_pasuk_join() -> None:
    from maayan.graph.links import pasuk_join

    result = pasuk_join(_graph_store_cli(), SystemClock())
    typer.echo(
        f"pasuk join: {result.pasukim} shared pesukim, {result.pairs} pairs → "
        f"{result.relations_created} new parallels ({result.relations_existing} existing)"
    )


@graph_app.command("pasuk-join")
def graph_pasuk_join() -> None:
    """Create deterministic 'parallels' edges between refs sharing a pasuk anchor."""
    _run_pasuk_join()


@graph_app.command("stats")
def graph_stats() -> None:
    """Graph tallies by type / evidence / status."""
    counts = _graph_store_cli().counts()
    typer.echo(f"concepts: {counts.concepts}   relations: {counts.relations}")
    for label, tally in (
        ("by type", counts.by_rel_type),
        ("by evidence", counts.by_evidence),
        ("by status", counts.by_status),
    ):
        if tally:
            parts = ", ".join(f"{k}={v}" for k, v in sorted(tally.items()))
            typer.echo(f"  {label}: {parts}")


# --- the margins: a daf apparatus per ref (Phase 7, Prompt 36) ----------------
@app.command()
def apparatus(
    ref: str = typer.Argument(..., help="Canonical ref to show the margins of."),
) -> None:
    """Everything the beis medrash knows about one ref — the daf's margins, in text."""
    from maayan.develop.store import DevelopmentStore
    from maayan.graph.apparatus import ApparatusService
    from maayan.graph.models import EVIDENCE_GLYPH
    from maayan.lexicon.store import TermStore

    settings = _cfg()
    from maayan.corpus.store import ChunkStore

    service = ApparatusService(
        ChunkStore(settings.db_path), _graph_store_cli(),
        TermStore(settings.db_path), DevelopmentStore(settings.db_path),
    )
    result = service.assemble(ref)
    corpus_note = "" if result.in_corpus else "  (outside the corpus)"
    typer.echo(f"{result.ref} — גליון · {result.total}{corpus_note}")
    if result.total == 0:
        typer.echo("  הגליון עדיין ריק")  # an empty apparatus is a statement, not an error
        return
    for group in result.relation_groups:
        typer.echo(f"  {group.rel_type}:")
        for item in group.items:
            glyph = EVIDENCE_GLYPH.get(item.relation.evidence, "?")
            outside = "" if item.in_corpus else "  [outside the corpus]"
            typer.echo(f"    {glyph} {item.far_label}   ({item.relation.author}){outside}")
            if item.far_snippet:
                typer.echo(f"       {item.far_snippet}")
    if result.terms:
        names = " · ".join(t.canonical for t in result.terms)
        typer.echo(f"  מונחים: {names}")
    for layer in result.expert_layer:
        who = f" ({layer.author}, {layer.kind})" if layer.author else ""
        typer.echo(f"  ● [{layer.source}]{who} {layer.snippet}")
    for dev in result.developments:
        typer.echo(f"  ◐ [derived] ({dev.author}) {dev.snippet}")


# --- inquiry queue: שאלות לרב (Phase 7, Prompt 37) ---------------------------
# The system's questions for the scholar, ranked by expected value of an answer.
inquiries_app = typer.Typer(
    help="שאלות לרב — the system's prioritized questions for the scholar.",
    invoke_without_command=True,
    add_completion=False,
)
app.add_typer(inquiries_app, name="inquiries")

# Deep links: each kind resolves through an EXISTING flow — the queue routes
# attention, it never edits.
_INQUIRY_RESOLVE_HINTS = {
    "refused_question": "ענה → maayan annotate (או הוסף מקור/קשר) ואז inquiries answer",
    "undergrounded_term": "אשר → maayan add-term / lexicon-review; דחה → inquiries dismiss",
    "low_evidence_relation": "בדוק → maayan graph show; דחה קשר → maayan graph retract",
    "contradiction": "הכרע → maayan graph retract על הקשר השגוי",
    "re_review": "אשר מחדש או retract (chazarah)",
}


def _inquiry_store_cli() -> Any:
    from maayan.eval.captured import build_captured_recorder
    from maayan.inquiry.store import InquiryStore

    settings = _cfg()
    return InquiryStore(
        settings.db_path, SystemClock(), recorder=build_captured_recorder(settings)
    )


@inquiries_app.callback()
def inquiries_list(
    ctx: typer.Context,
    kind: str | None = typer.Option(None, "--kind", help="Filter by inquiry kind."),
    all_statuses: bool = typer.Option(
        False, "--all", help="Include answered/dismissed items too."
    ),
) -> None:
    """List open inquiries by priority (highest first)."""
    if ctx.invoked_subcommand is not None:
        return
    store = _inquiry_store_cli()
    items = store.list(status=None if all_statuses else "open", kind=kind)
    if not items:
        typer.echo("(no open inquiries — run `maayan inquiries generate` after some use)")
        return
    for item in items:
        status = "" if item.status == "open" else f"  [{item.status}]"
        typer.echo(f"？ {item.kind}   priority {item.priority:.1f}{status}")
        typer.echo(f"   {item.title}")
        parts = " + ".join(f"{k}({v:g})" for k, v in item.priority_parts.items())
        typer.echo(f"   priority = {parts}")
        if item.detail:
            typer.echo(f"   {item.detail}")
        if item.resolution:
            typer.echo(f"   ✓ {item.resolution}")
        hint = _INQUIRY_RESOLVE_HINTS.get(item.kind, "")
        if hint and item.status == "open":
            typer.echo(f"   {hint}")
        typer.echo(f"   id: {item.id}\n")
    harvest = store.harvest_today()
    if harvest:
        tally = ", ".join(f"{k}: {v}" for k, v in sorted(harvest.items()))
        typer.echo(f"היום נענו → {tally}")


@inquiries_app.command("generate")
def inquiries_generate() -> None:
    """Regenerate the queue from telemetry, the deny-list, and the graph."""
    from maayan.graph.store import GraphStore
    from maayan.inquiry.generate import generate_inquiries
    from maayan.inquiry.log import AskLog
    from maayan.lexicon.suggestions import SuggestionStore

    settings = _cfg()
    clock = SystemClock()
    report = generate_inquiries(
        _inquiry_store_cli(),
        clock,
        settings,
        ask_log=AskLog(settings.db_path, clock) if settings.ask_log_enabled else None,
        suggestions=SuggestionStore(settings.db_path),
        graph=GraphStore(settings.db_path),
    )
    by_kind = ", ".join(f"{k}={v}" for k, v in sorted(report.by_kind.items())) or "—"
    typer.echo(
        f"created: {report.created} ({by_kind})   refreshed: {report.refreshed}   "
        f"kept closed: {report.skipped_terminal}"
    )


@inquiries_app.command("answer")
def inquiries_answer(
    item_id: str = typer.Argument(..., help="Inquiry id to close."),
    resolution: str = typer.Option(
        ..., "--resolution", "-r",
        help="What answering created (chunk/term/relation id + a word).",
    ),
) -> None:
    """Mark an inquiry answered, recording what it created."""
    try:
        item = _inquiry_store_cli().mark_answered(item_id, resolution=resolution)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"נענה ✓  {item.title}")
    typer.echo(f"→ {item.resolution}")


@inquiries_app.command("dismiss")
def inquiries_dismiss(
    item_id: str = typer.Argument(..., help="Inquiry id to dismiss."),
    reason: str = typer.Option("dismissed", "--reason", help="Optional why (teaches the queue)."),
) -> None:
    """Dismiss an inquiry — a first-class outcome; it will not be regenerated."""
    try:
        item = _inquiry_store_cli().mark_dismissed(item_id, resolution=reason)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"נדחה ✗  {item.title}")


# --- user management (auth / multi-user) ------------------------------------
# These manage the accounts the web UI logs in with. Auth is off unless
# AUTH_ENABLED=true (see docs/cloud_deploy/02_USER_MANAGEMENT.md), but you can seed
# accounts any time. Passwords are prompted, never passed as flags.
user_app = typer.Typer(
    help="Manage web-UI user accounts (auth).", no_args_is_help=True, add_completion=False
)
app.add_typer(user_app, name="user")


def _user_service_cli() -> UserService:
    from maayan.users.factory import build_user_service

    return build_user_service(_cfg())


def _find_user_id(svc: UserService, username: str) -> str | None:
    for u in svc.list_users():
        if u.username == username:
            return u.id
    return None


def _create_user_cli(username: str, display_name: str, role: str) -> None:
    password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    try:
        out: UserOut = _user_service_cli().create_user(
            username=username,
            password=password,
            display_name=display_name,
            role=cast("Role", role),
            created_by="cli",
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"created {out.role}: {out.username} ({out.id})")


@user_app.command("create-admin")
def user_create_admin(
    username: str = typer.Option(..., "--username", "-u", help="Admin username."),
    display_name: str = typer.Option("", "--display-name", help="Defaults to username."),
) -> None:
    """Create an admin account (prompts for the password)."""
    _create_user_cli(username, display_name, "admin")


@user_app.command("create")
def user_create(
    username: str = typer.Option(..., "--username", "-u"),
    display_name: str = typer.Option("", "--display-name"),
    admin: bool = typer.Option(False, "--admin", help="Make this user an admin."),
) -> None:
    """Create a member (or, with --admin, an admin) account."""
    _create_user_cli(username, display_name, "admin" if admin else "member")


@user_app.command("list")
def user_list() -> None:
    """List all user accounts."""
    rows = _user_service_cli().list_users()
    if not rows:
        typer.echo("(no users yet — create one with `maayan user create-admin`)")
        return
    for u in rows:
        flag = "" if u.active else "  [disabled]"
        typer.echo(f"{u.role:6}  {u.username:20}  {u.display_name}{flag}")


def _user_set_active(username: str, active: bool) -> None:
    svc = _user_service_cli()
    uid = _find_user_id(svc, username)
    if uid is None:
        typer.echo(f"error: no such user: {username}")
        raise typer.Exit(1)
    svc.set_active(uid, active)
    typer.echo(f"{'enabled' if active else 'disabled'}: {username}")


@user_app.command("disable")
def user_disable(username: str = typer.Argument(..., help="Username to disable.")) -> None:
    """Disable an account (revokes its sessions immediately)."""
    _user_set_active(username, False)


@user_app.command("enable")
def user_enable(username: str = typer.Argument(..., help="Username to enable.")) -> None:
    """Re-enable a disabled account."""
    _user_set_active(username, True)


@user_app.command("passwd")
def user_passwd(username: str = typer.Argument(..., help="Username to reset.")) -> None:
    """Reset an account's password (prompts; revokes existing sessions)."""
    svc = _user_service_cli()
    uid = _find_user_id(svc, username)
    if uid is None:
        typer.echo(f"error: no such user: {username}")
        raise typer.Exit(1)
    password = typer.prompt("New password", hide_input=True, confirmation_prompt=True)
    try:
        svc.change_password(uid, password)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"password updated for {username}")


@app.command()
def summarize(
    book: str = typer.Option(..., "--book", help="The sefer to summarize, section by section."),
    units: int | None = typer.Option(
        None, "--units", "-n", help="Draft at most N sections this run (sampling / cost)."
    ),
    model: str = typer.Option(
        None, "--model", help="Override the drafting model (e.g. an OpenRouter slug)."
    ),
    pace: float = typer.Option(
        None, "--pace", help="Seconds between sections (default: config summary_pace_seconds)."
    ),
    include_unsupported: bool = typer.Option(
        False, "--include-unsupported", help="Also queue ungrounded drafts (flagged), for review."
    ),
) -> None:
    """Drip-draft one grounded, faithfulness-checked summary per section (indexes nothing).

    Each draft lands 'proposed' for `summaries` → `summary-approve`. Makes real generation
    calls — set SUMMARY_DRAFT_MODEL (or --model) to draft with a stronger model.
    """
    from maayan.summarize.factory import build_summary_service

    settings = _cfg()
    if model:
        settings = settings.model_copy(update={"summary_draft_model": model})
    if pace is not None:
        settings = settings.model_copy(update={"summary_pace_seconds": pace})
    require_qdrant(settings)

    service = build_summary_service(settings)
    stats = asyncio.run(
        service.draft_book(book, units=units, persist_unsupported=include_unsupported)
    )
    typer.echo(
        f"[summarize] {book}: drafted {stats.drafted} section(s), "
        f"{stats.supported} grounded & queued, {stats.failed} failed."
    )
    typer.echo("Review: `maayan summaries`, then `maayan summary-approve <id> --author ...`.")


@app.command()
def summaries(
    book: str | None = typer.Option(None, "--book", help="Only this book's pending summaries."),
) -> None:
    """List pending section summaries awaiting approval (read-only; no models loaded)."""
    from maayan.summarize.store import SummaryStore

    pending = SummaryStore(_cfg().db_path).list(status="proposed", book=book)
    if not pending:
        typer.echo("No pending summaries. Run `maayan summarize --book ...` first.")
        return
    typer.echo(f"{len(pending)} pending summary(ies):")
    for s in pending:
        flag = "" if s.supported else "  [ungrounded]"
        typer.echo(f"  {s.id}  · {s.parent_label or s.parent_ref}{flag}")
        typer.echo(f"      {s.text[:120]}")


@app.command(name="summary-approve")
def summary_approve(
    summary_id: str = typer.Argument(..., help="Pending summary id (from `maayan summaries`)."),
    author: str = typer.Option(..., "--author", help="The expert approving it (becomes author)."),
) -> None:
    """Approve a drafted summary → index it as a retrievable summary chunk."""
    from maayan.summarize.factory import build_summary_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        summary = build_summary_service(settings).approve(summary_id, author=author)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"approved summary of {summary.parent_label or summary.parent_ref} by {author}.")
    typer.echo("It will now surface in retrieval; its margins lead down into the passages.")


@app.command(name="summary-reject")
def summary_reject(
    summary_id: str = typer.Argument(..., help="The pending summary id to reject."),
) -> None:
    """Reject a drafted summary (indexes nothing; the corpus is unchanged)."""
    from maayan.summarize.factory import build_summary_service

    try:
        build_summary_service(_cfg()).reject(summary_id)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"rejected summary {summary_id}.")


study_app = typer.Typer(
    help="Study programs: sweep a sefer, unit by unit, drafting proposed edges for the gates.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(study_app, name="study")


@study_app.command("run")
def study_run(
    book: str = typer.Option(..., "--book", help="The sefer to sweep (a corpus book name)."),
    task: str = typer.Option(
        "relations", "--task", help="What to draft: relations | terms | mashal."
    ),
    units: int | None = typer.Option(
        None, "--units", "-n", help="Process at most N units this run (sampling / cost)."
    ),
    program_id: str | None = typer.Option(
        None, "--program", help="Resume an existing program instead of starting a new one."
    ),
    author: str = typer.Option(
        None, "--author", "-a", help="Program author (provenance on every drafted edge)."
    ),
    model: str = typer.Option(
        None, "--model", help="Override the drafting model (e.g. an OpenRouter slug)."
    ),
    pace: float = typer.Option(
        None, "--pace", help="Seconds between units (default: config study_pace_seconds)."
    ),
) -> None:
    """Sweep a book into proposed, cited, typed edges — paced, resumable, gate-preserving.

    Nothing is indexed or approved: each supported proposal lands as a *proposed*
    relation (evidence derived_bootstrap) awaiting the Rav. Makes real generation calls —
    set STUDY_PROGRAM_MODEL (or --model) to draft with a stronger model.
    """
    from typing import get_args as _get_args

    from maayan.agent.program_factory import build_study_program_runner
    from maayan.agent.program_models import ProgramTask

    if task not in _get_args(ProgramTask):
        raise typer.BadParameter("--task must be one of: relations | terms | mashal")

    settings = _cfg()
    if model:
        settings = settings.model_copy(update={"study_program_model": model})
    if pace is not None:
        settings = settings.model_copy(update={"study_pace_seconds": pace})
    require_qdrant(settings)

    runner = build_study_program_runner(settings)
    if program_id is not None:
        from maayan.agent.program_store import ProgramStore

        program = ProgramStore(settings.db_path).get_program(program_id)
        if program is None:
            typer.echo(f"error: no study program with id {program_id!r}")
            raise typer.Exit(1)
    else:
        who = (author or "").strip()
        if not who:
            raise typer.BadParameter("--author is required when starting a new program")
        program = runner.create(
            book=book,
            task=cast("ProgramTask", task),
            author=f"program:{who}",
            model=settings.study_program_model,
        )
    typer.echo(
        f"[study] program {program.id} · {program.book} · task={program.task} · "
        f"from unit {program.cursor}/{program.total_units}, pace={settings.study_pace_seconds}s"
    )
    program = asyncio.run(runner.run(program, units=units))
    c = program.counts
    typer.echo(
        f"[study] {program.status}: {program.cursor}/{program.total_units} units · "
        f"drafted {c.drafted}, passed {c.passed_checks}, queued {c.queued} "
        f"(model calls {c.model_calls})"
    )
    typer.echo(
        f"Review: `maayan graph list --status proposed`; "
        f"report: `maayan study report {program.id}`."
    )


@study_app.command("status")
def study_status() -> None:
    """List study programs and their progress (read-only; no models loaded)."""
    from maayan.agent.program_store import ProgramStore

    programs = ProgramStore(_cfg().db_path).list_programs()
    if not programs:
        typer.echo("No study programs yet. Start one: `maayan study run --book ... --author ...`.")
        return
    for p in programs:
        c = p.counts
        typer.echo(
            f"{p.id}  · {p.book} · {p.task} · {p.status} · {p.cursor}/{p.total_units} units · "
            f"drafted {c.drafted}/passed {c.passed_checks}/queued {c.queued}"
        )


@study_app.command("report")
def study_report(
    program_id: str = typer.Argument(..., help="Program id (from `maayan study status`)."),
    out: str | None = typer.Option(
        None, "--out", help="Write the markdown report to this path instead of stdout."
    ),
) -> None:
    """Emit the drafted/passed/queued funnel report (POPULATE_REPORT-style markdown)."""
    from pathlib import Path

    from maayan.agent.program import render_report_markdown
    from maayan.agent.program_factory import build_study_program_runner

    settings = _cfg()
    require_qdrant(settings)
    try:
        report = build_study_program_runner(settings).build_report(program_id)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    markdown = render_report_markdown(report)
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(markdown, encoding="utf-8")
        typer.echo(f"Wrote report → {out}")
    else:
        typer.echo(markdown)


sugya_app = typer.Typer(
    help="Sugya pages: consolidate clusters of approved knowledge into curated, gated pages.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(sugya_app, name="sugya")


@sugya_app.command("draft")
def sugya_draft(
    concept: str = typer.Option(..., "--concept", help="Concept the cluster is anchored on."),
    author: str = typer.Option(..., "--author", "-a", help="Who is drafting (provenance)."),
) -> None:
    """Draft a proposed sugya page from the cluster anchored on a concept (indexes nothing)."""
    from maayan.consolidate.factory import build_sugya_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        page = build_sugya_service(settings).draft(concept=concept, author=author)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"drafted sugya page {page.id} · «{page.title}» · {len(page.sections)} section(s)")
    for section in page.sections:
        typer.echo(f"  {section.title}: cites {', '.join(section.cited_refs) or '—'}")
    typer.echo(f"Approve: `maayan sugya approve {page.id} --author <you>`.")


@sugya_app.command("approve")
def sugya_approve(
    page_id: str = typer.Argument(..., help="Proposed sugya page id (from `sugya list`)."),
    author: str = typer.Option(..., "--author", "-a", help="The approving human."),
) -> None:
    """Approve a page → index it as retrievable sugya chunks; supersede the prior version."""
    from maayan.consolidate.factory import build_sugya_service

    settings = _cfg()
    require_qdrant(settings)
    try:
        page = build_sugya_service(settings).approve(page_id, author=author)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(
        f"approved sugya «{page.title}» v{page.version} — indexed {len(page.chunk_ids)} chunk(s)."
    )
    if page.supersedes is not None:
        typer.echo(f"superseded {page.supersedes} (its chunks retracted, audited).")


@sugya_app.command("reject")
def sugya_reject(
    page_id: str = typer.Argument(..., help="Proposed sugya page id to reject."),
) -> None:
    """Reject a proposed page (indexes nothing; the corpus is unchanged)."""
    from maayan.consolidate.factory import build_sugya_service

    try:
        build_sugya_service(_cfg()).reject(page_id)
    except ValueError as exc:
        typer.echo(f"error: {exc}")
        raise typer.Exit(1) from exc
    typer.echo(f"rejected sugya page {page_id}.")


@sugya_app.command("list")
def sugya_list(
    status: str | None = typer.Option(
        None, "--status", help="proposed|approved|superseded|rejected"
    ),
) -> None:
    """List sugya pages (read-only; no models loaded)."""
    from maayan.consolidate.factory import build_sugya_service

    pages = build_sugya_service(_cfg()).list(status=status)
    if not pages:
        typer.echo("(no sugya pages)")
        return
    for page in pages:
        typer.echo(
            f"{page.id}  · «{page.title}» v{page.version} · {page.status} · "
            f"{len(page.sections)} section(s) · cites {len(page.cited_refs)} ref(s)"
        )


@app.command()
def chazarah() -> None:
    """Run one chazarah pass: queue re-review inquiries for aging/low-evidence/unused edges."""
    from maayan.consolidate.factory import build_chazarah_scheduler

    report = build_chazarah_scheduler(_cfg()).run()
    typer.echo(
        f"chazarah: scheduled {report.scheduled} target(s), queued {report.queued} re-review(s)."
    )
    for reason, n in sorted(report.by_reason.items()):
        typer.echo(f"  {reason}: {n}")
    typer.echo(
        "Review: the שאלות לרב panel (re_review items), or `maayan inquiries --kind re_review`."
    )


# All CLI subcommands registered.


if __name__ == "__main__":
    app()
