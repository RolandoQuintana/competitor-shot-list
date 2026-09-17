"""CLI entry point: ``python -m shotlist``."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version

from shotlist.errors import (
    EmptyShotsError,
    InvalidVideoUrlError,
    JobTimeoutError,
    MissingOpenRouterApiKeyError,
    PipelineError,
    SynthesisError,
    VideoTooLongError,
)
from shotlist.pipeline import analyze_fixture, analyze_youtube_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shotlist",
        description="YouTube Short → production-oriented shot list artifacts",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('competitor-shot-list')}",
    )
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze a YouTube Short URL and write shot-list artifacts",
    )
    analyze.add_argument(
        "url",
        nargs="?",
        default=None,
        help="Public YouTube Short URL (not used with --fixture)",
    )
    analyze.add_argument(
        "--fixture",
        action="store_true",
        help="Run mock end-to-end analyze on bundled CI sample media",
    )
    subparsers.add_parser(
        "serve",
        help="Run the HTTP API (FastAPI + uvicorn)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "analyze":
        if args.fixture:
            try:
                out = analyze_fixture()
            except EmptyShotsError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except PipelineError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except Exception as exc:  # noqa: BLE001
                print(str(exc), file=sys.stderr)
                return 1
            print(out)
            return 0
        if not args.url:
            print("analyze: provide a URL or --fixture", file=sys.stderr)
            return 2
        try:
            out = analyze_youtube_url(args.url)
        except (
            InvalidVideoUrlError,
            VideoTooLongError,
            JobTimeoutError,
            SynthesisError,
            MissingOpenRouterApiKeyError,
        ) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except EmptyShotsError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except PipelineError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(str(exc), file=sys.stderr)
            return 1
        print(out)
        return 0
    if args.command == "serve":
        return serve()
    return 0


def serve() -> int:
    import os

    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "shotlist.api:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
