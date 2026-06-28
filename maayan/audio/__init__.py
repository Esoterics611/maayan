"""Audio asset storage for the shiur pipeline (Prompt 25+).

A recording is stored once (normalized to mono 16 kHz for Whisper) and deduped by
content hash, then transcribed (`transcribe/`), reviewed (Prompt 27), and approved
into `source="shiur"` corpus (Prompt 28). Timestamps on the transcript point back
into the stored audio so a cited shiur can play from the exact moment.
"""
