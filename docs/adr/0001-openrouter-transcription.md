# OpenRouter speech-to-text by default

Competitor ads are transcribed via OpenRouter’s `/audio/transcriptions` API using `openai/whisper-large-v3` with segment timestamps (`verbose_json`), not local faster-whisper. Local Whisper remains available when `TRANSCRIPT_BACKEND=whisper`; CI and fixtures keep `stub`.

We cap analyzed video at **55 seconds** (`MAX_VIDEO_DURATION_SEC`) so a single STT request stays under upstream processing timeouts—no audio chunking in v1. If OpenRouter STT fails after retries, the job fails; we do not fall back to local Whisper automatically.

Public Shorts audio is sent to OpenRouter upstream providers; that trade-off is acceptable for this competitor-intel workflow. Record transcription backend and model in `analysis.models` on each shot list.
