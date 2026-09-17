# competitor-shot-list

YouTube Short URL → `shot-list.json` + `shot-list.md` under `./output/<video-id>/`.

Canonical spec: [Implementation Spec v1 (locked)](https://linear.app/scroll-less/document/implementation-spec-v1-locked-8ac1a4a54af6).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
