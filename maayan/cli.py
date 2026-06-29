"""maayan CLI entrypoint (typer).

Each subcommand is wired up in its own prompt/module as the build progresses.
This file stays a thin layer: it parses args, builds the concrete services
(embedder, qdrant client, generation backend, clock) and injects them into the
library code. No business logic lives here.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import typer

from maayan import __version__
from maayan.config import Settings, get_settings
from maayan.corpus.ingest import IngestResult
from maayan.corpus.models import Lang

if TYPE_CHECKING:
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
def search(
    query: str = typer.Argument(..., help="Query text (Hebrew or English)."),
    k: int = typer.Option(None, "--k", help="How many results to return."),
    book: str = typer.Option(None, "--book", help="Restrict to a book."),
    source: str = typer.Option(
        None, "--source", help="Restrict to a source (sefaria/expert/derived/term)."
    ),
) -> None:
    """Hybrid (dense + sparse) retrieval over the indexed corpus."""
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    require_qdrant(settings)
    retriever = build_retriever(settings)
    results = retriever.retrieve(query, k=k, book=book, source=source).results

    if not results:
        typer.echo("No results.")
        return
    typer.echo(f'Top {len(results)} for: "{query}"\n')
    for i, r in enumerate(results, 1):
        typer.echo(f"{i:>2}. [{r.score:.4f}] {r.ref}  ({r.lang}/{r.source})")
        typer.echo(f"      {r.first_line(100)}")
        prov = _provenance_line(r)
        if prov:
            typer.echo(prov)


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
    show_reasoning: bool = typer.Option(
        False, "--show-reasoning", help="Print the study map produced in reasoning mode."
    ),
) -> None:
    """Answer grounded ONLY in retrieved sources, with citations (refuses if unsupported)."""
    from maayan.capture.factory import build_capture_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.retrieve.factory import build_retriever

    settings = _cfg()
    require_qdrant(settings)
    embedder = build_embedder(settings)  # built once, shared with capture
    backend = build_generation_backend(settings)
    use_expand = settings.query_expand_enabled if expand is None else expand
    use_reasoning = settings.rag_reasoning_enabled if reason is None else reason
    use_verify = settings.answer_verify_enabled if verify is None else verify
    retriever = build_retriever(
        settings, embedder=embedder, expand=use_expand,
        backend=backend if use_expand else None,
    )
    rag = RAGService(
        retriever, backend, score_threshold=settings.score_threshold,
        reasoning=use_reasoning, verify=use_verify,
    )

    # Within a thread, prior turns are passed as NON-citable context; retrieval and
    # default-deny are unchanged. Outside a thread, this is a plain one-shot ask.
    active_thread: str | None = None
    if thread_id or topic:
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
    if answer.cited_refs:
        typer.echo(f"\nCited: {', '.join(answer.cited_refs)}")
    if answer.unsupported_claims:
        typer.echo("\n⚠ Claims not clearly supported by their cited sources:")
        for claim in answer.unsupported_claims:
            typer.echo(f"  - {claim}")
    typer.echo(f"\nSession: {session.id}")
    if active_thread:
        typer.echo(f"Thread:  {active_thread}  (ask turn appended; "
                   "follow up with `maayan ask '...' --thread " + active_thread + "`)")
    typer.echo("Annotate it:  maayan annotate --session "
               f"{session.id} --author 'Your Name' --kind connection --body '...' "
               "--ref '<ref>' --ref '<ref>'")


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
    k: int = typer.Option(10, "--k", help="The k to highlight in the comparison table."),
) -> None:
    """Score retrieval (hit@k, recall@k, MRR), or the develop / cross-text / answer step."""
    settings = _cfg()
    require_qdrant(settings)

    if crosstext:
        from maayan.eval.crosstext_harness import format_crosstext_report, run_crosstext_eval
        from maayan.eval.goldset import load_goldset
        from maayan.retrieve.factory import build_retriever

        ct_path = goldset or settings.eval_crosstext_goldset_path
        ct_examples = load_goldset(ct_path)
        typer.echo(f"Cross-text gold set: {ct_path} ({len(ct_examples)} questions)\n")
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
        typer.echo(f"Default-deny gate threshold: {settings.score_threshold}")
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
            retriever, backend, score_threshold=settings.score_threshold,
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
        typer.echo(f"Default-deny gate threshold: {settings.score_threshold}\n")
        service, dev_threads, clock = build_develop_eval_setup(settings)
        dev_report = run_develop_eval(service, dev_threads, clock, dev_examples)
        typer.echo(format_develop_report(dev_report))
        return

    from maayan.eval.goldset import load_goldset
    from maayan.eval.harness import (
        default_variants,
        format_comparison,
        format_report,
        run_comparison,
        run_eval,
    )
    from maayan.retrieve.factory import build_retriever

    path = goldset or settings.eval_goldset_path
    examples = load_goldset(path)
    typer.echo(f"Gold set: {path} ({len(examples)} questions)")
    typer.echo(f"Default-deny gate threshold: {settings.score_threshold}\n")

    if compare:
        from maayan.embed.factory import build_embedder

        embedder = build_embedder(settings)  # built once, shared across same-model variants
        reports = run_comparison(
            settings,
            default_variants(),
            examples,
            settings.eval_ks,
            score_threshold=settings.score_threshold,
            embedder=embedder,
        )
        typer.echo(format_comparison(reports, k=k))
    else:
        retriever = build_retriever(settings)
        report = run_eval(
            retriever, examples, settings.eval_ks, score_threshold=settings.score_threshold
        )
        typer.echo(format_report(report))


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
            retriever, examples, settings.eval_ks, score_threshold=settings.score_threshold
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
def ui() -> None:
    """Run the local chat + capture web UI (FastAPI)."""
    import uvicorn

    from maayan.capture.factory import build_capture_service
    from maayan.compose.factory import build_composition_service
    from maayan.corpus.store import ChunkStore
    from maayan.develop.factory import build_development_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.inbox.factory import build_inbox_service
    from maayan.lexicon.factory import build_term_service
    from maayan.ocr.factory import build_ocrer
    from maayan.retract.factory import build_retraction_service
    from maayan.retrieve.factory import build_retriever
    from maayan.stats.factory import build_stats_service
    from maayan.threads.factory import build_thread_service
    from maayan.transcribe.factory import build_transcription_service
    from maayan.ui.app import create_app
    from maayan.users.factory import build_user_service

    settings = _cfg()
    require_qdrant(settings)
    embedder = build_embedder(settings)  # built once, shared across services
    backend = build_generation_backend(settings)
    retriever = build_retriever(
        settings, embedder=embedder, expand=settings.query_expand_enabled,
        backend=backend if settings.query_expand_enabled else None,
    )
    rag = RAGService(
        retriever, backend, score_threshold=settings.score_threshold,
        reasoning=settings.rag_reasoning_enabled, verify=settings.answer_verify_enabled,
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

    application = create_app(
        rag, capture, threads, develop, terms, retraction, stats, compose_service,
        users=users,
        transcription=transcription,
        chunks=chunks_store,
        ocr=ocr,
        inbox=inbox,
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


# All CLI subcommands registered.


if __name__ == "__main__":
    app()
