# competitor-shot-list

YouTube Short URL → `shot-list.json` + `shot-list.md` under `./output/<video-id>/`.

Canonical spec: [Implementation Spec v1 (locked)](https://linear.app/scroll-less/document/implementation-spec-v1-locked-8ac1a4a54af6).

## Primary reviewer command (v1)

```bash
cp .env.example .env   # set OPENROUTER_API_KEY for real runs
docker compose build
docker compose run --rm api python -m shotlist analyze "<youtube-short-url>"
```

Exit code `0` writes `shot-list.json` and `shot-list.md` under `./output/<video-id>/` on the host. Real runs use OpenRouter for per-frame vision (`OPENROUTER_VISION_MODEL`) and shot-list synthesis (`OPENROUTER_SYNTHESIS_MODEL`). Long jobs are capped by `JOB_TIMEOUT_SEC` (default 1800).

```bash
docker compose run --rm api python -m shotlist --help
```

Artifacts are written to `./output` on the host. Whisper / Hugging Face hub downloads are cached in the named Compose volume `whisper-cache` (`HF_HOME` inside the container).

Analyze flow: yt-dlp acquire → FFmpeg frames/audio → Whisper transcript → OpenRouter vision → OpenRouter synthesis → persist.

For a vision-free smoke test, set `VISION_BACKEND=mock` in `.env`. Videos longer than `MAX_VIDEO_DURATION_SEC` (default 90s) are rejected before synthesis.

### YouTube / Terms of Service

This tool uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) to download **public** URLs you supply for analysis. You are responsible for complying with [YouTube’s Terms of Service](https://www.youtube.com/t/terms) and applicable copyright law; use only content you have the right to process.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m shotlist --help
```

### CI-safe mock analyze (DIS-12)

Bundled fixture media under `shotlist/fixtures/ci-sample.mp4` — no YouTube, no OpenRouter. Uses FFmpeg for frames, `TRANSCRIPT_BACKEND=stub`, and `VISION_BACKEND=mock`.

```bash
make test-integration
# or
VISION_BACKEND=mock TRANSCRIPT_BACKEND=stub pytest -m integration
```

Inside Docker:

```bash
docker compose run --rm api python -m shotlist analyze --fixture
```

Artifacts land under `./output/ci-sample/` on the host bind mount.
