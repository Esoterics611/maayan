"""maayan CLI entrypoint (typer).

Each subcommand is wired up in its own prompt/module as the build progresses.
This file stays a thin layer: it parses args, builds the concrete services
(embedder, qdrant client, generation backend, clock) and injects them into the
library code. No business logic lives here.
"""

from __future__ import annotations

import typer

from maayan import __version__

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


# Subcommands (ingest, index, search, ask, annotate, ...) are registered by
# their modules as each build prompt lands. Kept out of the skeleton on purpose.


if __name__ == "__main__":
    app()
