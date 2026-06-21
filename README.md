# maayan — Esoteric Torah RAG

**maayan** (מעיין, "wellspring") is a local-first retrieval system for chassidus /
Kabbalah text. It ingests Torah sources, retrieves the relevant pieces for a
question, and asks an open model to answer **only from those sources, with
citations** — refusing when nothing supports an answer. An **expert capture loop**
records how a scholar corrects and connects sources and feeds that back in as new
retrievable knowledge. That loop is the point.

- **Local:** Qdrant (vector DB), `bge-m3` embeddings, optional reranker, all app
  code, the UI.
- **Cloud:** only the final generation call → OpenRouter (swappable to local
  Ollama).

See [`CLAUDE.md`](CLAUDE.md) for architecture + house rules and
[`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) for the full build plan and the prompt
behind each step.

## Quickstart

```bash
# 1. Install dependencies (core is fast; ML extras pull torch)
uv sync
uv sync --extra ml        # embeddings/reranker (Prompt 2+)

# 2. Configure
cp .env.example .env      # add your OPENROUTER_API_KEY

# 3. Start local Qdrant
make up

# 4. Build the corpus and ask (as each prompt lands)
make ingest               # pull + chunk Tanya / Likutei Torah / Torah Or
make index                # embed + index into Qdrant
make ask Q='מהי בחירה חופשית'
```

`make help` lists all targets. `make test` runs the suite (network + models
mocked).

## Status

Built prompt-by-prompt — see the task list / `docs/BUILD_PLAN.md`:

- [x] **Prompt 0** — Bootstrap, house rules, config, Docker, CI scaffolding
- [ ] Prompt 1 — Sefaria ingestion
- [ ] Prompt 2 — Embedding + Qdrant indexing
- [ ] Prompt 3 — Hybrid retrieval (+ optional rerank)
- [ ] Prompt 4 — RAG generation via OpenRouter (grounded, cited, default-deny)
- [ ] Prompt 5 — Expert capture loop
- [ ] Prompt 6 — Local chat + capture UI
- [ ] Prompt 7 — Eval harness
- [ ] Prompt 8 — Local generation via Ollama

## License / attribution

Sefaria texts are **CC-BY-NC**. This project is for personal, non-commercial Torah
study; attribute [Sefaria](https://www.sefaria.org). Revisit licensing before any
commercial use.
