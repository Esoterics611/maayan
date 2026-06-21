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
    source: str = typer.Option(None, "--source", help="Restrict to a source (sefaria/expert)."),
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


@app.command()
def ask(
    question: str = typer.Argument(..., help="Your question (Hebrew or English)."),
    k: int = typer.Option(None, "--k", help="How many sources to ground on."),
    book: str = typer.Option(None, "--book", help="Restrict to a book."),
) -> None:
    """Answer grounded ONLY in retrieved sources, with citations (refuses if unsupported)."""
    from maayan.generate.factory import build_generation_backend
    from maayan.generate.rag import RAGService
    from maayan.retrieve.factory import build_retriever

    settings = get_settings()
    retriever = build_retriever(settings)
    backend = build_generation_backend(settings)
    rag = RAGService(retriever, backend, score_threshold=settings.score_threshold)
    answer = rag.ask(question, k=k, book=book)

    if not answer.grounded:
        typer.echo(f"\n[refused] {answer.text}")
        if answer.sources:
            typer.echo("\n(Closest, but below the relevance threshold:)")
            for s in answer.sources[:3]:
                typer.echo(f"  - {s.ref}")
        return

    typer.echo(f"\n{answer.text}\n")
    typer.echo("Sources:")
    cited = set(answer.cited_refs)
    for s in answer.sources:
        mark = "*" if s.ref in cited else " "
        typer.echo(f"  [{mark}] {s.ref}")
    if answer.cited_refs:
        typer.echo(f"\nCited: {', '.join(answer.cited_refs)}")


# Subcommands (annotate, ...) are registered as each build prompt lands.


if __name__ == "__main__":
    app()
