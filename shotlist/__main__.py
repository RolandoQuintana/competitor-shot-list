"""CLI entry point: ``python -m shotlist``."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import version


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
    analyze.add_argument("url", help="Public YouTube Short URL")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "analyze":
        print(
            "analyze pipeline not implemented yet; use Docker shell to verify install",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
