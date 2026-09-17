# Competitor shot list

Turns short competitor ads into a structured shot list: timed shots, visuals, dialogue, and on-screen text.

## Language

**Transcript**:
The spoken audio from the ad as searchable text, with time-aligned segments for mapping dialogue to shots.
_Avoid_: Caption file, subtitles (unless we mean burned-in on-screen text, which lives on shots)

**Transcript backend**:
The provider that produces a Transcript from extracted audio (fixture stub, local Whisper, or OpenRouter speech-to-text).
_Avoid_: ASR engine, speech model (fine for code; use backend in config and docs)

**Shot**:
A contiguous time range in the ad with visual description, dialogue attributed to that range, and optional on-screen text.
_Avoid_: Scene, clip

**Analyzed video**:
A competitor ad clip the pipeline ingests end-to-end. Duration must not exceed 55 seconds.
_Avoid_: Source file, upload (those are inputs; this is the bounded unit we analyze)
