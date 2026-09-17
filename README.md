# competitor-shot-list

YouTube Short URL → `shot-list.json` + `shot-list.md` under `./output/<video-id>/`.

Canonical spec: [Implementation Spec v1 (locked)](https://linear.app/scroll-less/document/implementation-spec-v1-locked-8ac1a4a54af6).

## Reviewer setup (Docker)

```bash
cp .env.example .env   # set OPENROUTER_API_KEY for real runs
docker compose build
docker compose run --rm api python -m shotlist --help
```

Artifacts are written to `./output` on the host. Whisper / Hugging Face hub downloads are cached in the named Compose volume `whisper-cache` (`HF_HOME` inside the container).

Target flow once the pipeline is wired:

```bash
docker compose run --rm api python -m shotlist analyze "<youtube-short-url>"
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m shotlist --help
```
