"""maayan CLI entrypoint (typer).

Each subcommand is wired up in its own prompt/module as the build progresses.
This file stays a thin layer: it parses args, builds the concrete services
(embedder, qdrant client, generation backend, clock) and injects them into the
library code. No business logic lives here.
"""

from __future__ import annotations

import asyncio
from typing import cast

import typer

from maayan import __version__
from maayan.config import Settings, get_settings
from maayan.corpus.ingest import IngestResult
from maayan.corpus.models import Lang

app = typer.Typer(
    name="maayan",
    help="Esoteric Torah RAG — ingest, index, retrieve, ask, and capture expert knowledge.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main() -> None:
    """maayan — see `maayan --help`. Subcommands land as each build prompt is implemented."""
    # Presence of a callback forces Typer into multi-command mode, so subcommands
    # (version, ingest, index, search, ask, ...) are invoked by name.


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
    settings = get_settings()
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
    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
    retriever = build_retriever(settings)
    results = retriever.search(query, k=k, book=book, source=source)

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
) -> None:
    """Answer grounded ONLY in retrieved sources, with citations (refuses if unsupported)."""
    from maayan.capture.factory import build_capture_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.retrieve.factory import build_retriever

    settings = get_settings()
    embedder = build_embedder(settings)  # built once, shared with capture
    retriever = build_retriever(settings, embedder=embedder)
    backend = build_generation_backend(settings)
    rag = RAGService(retriever, backend, score_threshold=settings.score_threshold)

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

    typer.echo(f"\n{answer.text}\n")
    typer.echo("Sources:")
    cited = set(answer.cited_refs)
    for s in answer.sources:
        mark = "*" if s.ref in cited else " "
        typer.echo(f"  [{mark}] {s.ref}")
    if answer.cited_refs:
        typer.echo(f"\nCited: {', '.join(answer.cited_refs)}")
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    settings = get_settings()
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

    rows = build_term_service(get_settings()).list_terms()
    if not rows:
        typer.echo("No terms yet. Define one with `maayan add-term`.")
        return
    typer.echo(f"{len(rows)} term(s):")
    for t in rows:
        g = f" · gematria {t.gematria}" if t.gematria is not None else ""
        typer.echo(f"  {t.id}  · {t.canonical}  [{t.term_type}]{g}  by {t.author}")


@app.command()
def term(term_id: str = typer.Argument(..., help="Term id to display.")) -> None:
    """Show one lexicon term."""
    from maayan.lexicon.factory import build_term_service

    t = build_term_service(get_settings()).get_term(term_id)
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
    k: int = typer.Option(10, "--k", help="The k to highlight in the comparison table."),
) -> None:
    """Score retrieval (hit@k, recall@k, MRR) or, with --develop, the develop step."""
    settings = get_settings()

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


@app.command()
def ui() -> None:
    """Run the local chat + capture web UI (FastAPI)."""
    import uvicorn

    from maayan.capture.factory import build_capture_service
    from maayan.develop.factory import build_development_service
    from maayan.embed.factory import build_embedder
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.lexicon.factory import build_term_service
    from maayan.retrieve.factory import build_retriever
    from maayan.threads.factory import build_thread_service
    from maayan.ui.app import create_app

    settings = get_settings()
    embedder = build_embedder(settings)  # built once, shared across services
    retriever = build_retriever(settings, embedder=embedder)
    backend = build_generation_backend(settings)
    rag = RAGService(retriever, backend, score_threshold=settings.score_threshold)
    capture = build_capture_service(settings, embedder=embedder)
    threads = build_thread_service(settings)
    develop = build_development_service(settings, embedder=embedder)
    terms = build_term_service(settings, embedder=embedder)

    application = create_app(
        rag, capture, threads, develop, terms, context_turns=settings.thread_context_turns
    )
    typer.echo(f"maayan UI → http://{settings.ui_host}:{settings.ui_port}")
    uvicorn.run(application, host=settings.ui_host, port=settings.ui_port)


# All CLI subcommands registered.


if __name__ == "__main__":
    app()
