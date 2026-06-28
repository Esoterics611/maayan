"""Transcription spine for the shiur pipeline (Prompt 25+).

A swappable `Transcriber` turns a recording into a timestamped `Transcript`. The
local Whisper backend and (later) a cloud backend both implement the protocol, so
the choice is config-driven — exactly like `generate/` (OpenRouter ↔ Ollama). A
reviewed + approved transcript becomes `source="shiur"` corpus in Prompt 28.
"""
