# competitor-shot-list
<img width="777" height="815" alt="image" src="https://github.com/user-attachments/assets/60fec34b-4dec-477b-baa8-3bb06b102301" />

A workflow to automate the process of re-creating a shot list from a competitor's video. When learning to create viral content, copying what works is essential when starting out. Openrouter vision and STT models are used to generate artifacts like frame by frame analysis (1 frame per second) and transcripts. The artifacts are analyzed by a synthesizer model to create the final shot list.

YouTube Short URL → `shot-list.json` + `shot-list.md` under `./output/<video-id>/`.

Canonical spec: [Implementation Spec v1 (locked)](https://linear.app/scroll-less/document/implementation-spec-v1-locked-8ac1a4a54af6).

## Primary reviewer command (v1)

```bash
cp .env.example .env   # set OPENROUTER_API_KEY for real runs
docker compose build
docker compose run --rm api python -m shotlist analyze "<youtube-short-url>"
```

Exit code `0` writes `shot-list.json` and `shot-list.md` under `./output/<video-id>/` on the host. Real runs use OpenRouter for speech-to-text (`OPENROUTER_TRANSCRIPTION_MODEL`), per-frame vision (`OPENROUTER_VISION_MODEL`), and shot-list synthesis (`OPENROUTER_SYNTHESIS_MODEL`).

```bash
docker compose run --rm api python -m shotlist --help
```

### HTTP API (DIS-14)

Start the API on the host (default `http://localhost:8000`):

```bash
docker compose up --build
```

Enqueue an analyze job (returns `202` with a `job_id`; poll status until `completed` or `failed`):

```bash
curl -sS -X POST 'http://localhost:8000/analyze?wait=false' \
  -H 'Content-Type: application/json' \
  -d '{"url":"<youtube-short-url>"}'

curl -sS "http://localhost:8000/jobs/<job_id>"
```

CI-safe mock run (no YouTube, no OpenRouter):

```bash
curl -sS -X POST 'http://localhost:8000/analyze?wait=true' \
  -H 'Content-Type: application/json' \
  -d '{"fixture":true}'
```

Block until the pipeline finishes (`wait=true`; same artifacts as the CLI under `./output/<video-id>/`):

```bash
curl -sS -X POST 'http://localhost:8000/analyze?wait=true' \
  -H 'Content-Type: application/json' \
  -d '{"url":"<youtube-short-url>"}'
```

**Errors:** Every failed job includes a JSON `error` object with `code` and `message`.

- **`POST /analyze?wait=true`** — failures use HTTP `400` (bad URL / config) or `422` (pipeline failures such as timeouts or empty shots), with `error` at the top level of the response body.
- **`POST /analyze?wait=false` + `GET /jobs/<job_id>`** — polling always uses HTTP `200`; check `status` (`failed`) and read `error` from the job JSON. Same `error` shape as sync mode, without remapping to 4xx on GET.

For long YouTube runs, prefer `wait=false` and poll so proxies do not time out the connection.

### Slack `/analyze` (DIS-16, optional)

When Slack env vars are set, the same FastAPI process handles a slash command that runs the **same** analyze job as HTTP/CLI. The command acks within 3 seconds with an ephemeral “Analyzing…” message; when the job finishes, **`shot-list.md` and `shot-list.json` are uploaded to the channel** (the bot auto-joins public channels; in private channels it falls back to your DM unless you `/invite` the app). Requires `files:write` and `channels:join` on the bot (see `manifest.json`).

**Slack CLI (create app from repo manifest):** install the [Slack CLI](https://docs.slack.dev/tools/slack-cli/guides/installing-the-slack-cli-for-mac-and-linux/) (`~/.local/bin/slack`), then from this repo:

```bash
slack login
pip install -e ".[dev]"   # slack-cli-hooks for CLI project validation
slack manifest validate
slack app install --environment local
```

Copy **Bot User OAuth Token** (`SLACK_BOT_TOKEN`) and an app-level token with `connections:write` (`SLACK_APP_TOKEN`) into `.env`, then `docker compose up --build`. Alternatively, create the app from `manifest.json` at [api.slack.com/apps/new](https://api.slack.com/apps/new) → “From an app manifest”.

**Local development (Socket Mode — recommended):** no public HTTPS URL required.

| Variable | Required | Notes |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | Yes | Bot token (`xoxb-…`) |
| `SLACK_APP_TOKEN` | Yes (Socket Mode) | App-level token (`xapp-…`) with connections:write |
| `SLACK_SIGNING_SECRET` | Yes (HTTP Request URL) | Verifies slash-command POSTs to the app |

With Socket Mode, start the API as usual (`python -m shotlist serve` or `docker compose up`). Bolt connects outbound to Slack; you do **not** need to expose `/slack/commands` on the public internet.

**Hosted HTTPS (nice-to-have):** configure the slash command Request URL to `https://<host>/slack/commands` and set `SLACK_SIGNING_SECRET` + `SLACK_BOT_TOKEN`. You can use Socket Mode and HTTP together, but pick one transport per workspace to avoid duplicate handling.

Artifacts are written to `./output` on the host. Whisper / Hugging Face hub downloads are cached in the named Compose volume `whisper-cache` (`HF_HOME` inside the container).

Analyze flow: yt-dlp acquire → FFmpeg frames/audio → OpenRouter transcription → OpenRouter vision → OpenRouter synthesis → persist.

For a vision-free smoke test, set `VISION_BACKEND=mock` in `.env`. For offline transcription, set `TRANSCRIPT_BACKEND=whisper`. Videos longer than `MAX_VIDEO_DURATION_SEC` (default 55s) are rejected before synthesis.


Artifacts land under `./output/ci-sample/` on the host bind mount.
