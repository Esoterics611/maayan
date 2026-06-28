"""OCR capture surface for non-Sefaria pages (Prompt 30).

A swappable `OCRer` turns a photographed/scanned page into text. The local Tesseract
backend and (later) a cloud OCR both implement the protocol, so the choice is
config-driven — exactly like `transcribe/` (Whisper ↔ cloud) and `generate/`
(OpenRouter ↔ Ollama). OCR output is *never* auto-ingested: it lands in a capture
field for the same human review gate as every other contribution.
"""
