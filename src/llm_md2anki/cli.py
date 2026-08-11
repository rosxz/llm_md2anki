"""CLI entry for MVP."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(prog="llm_md2anki")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("convert")
    p.add_argument("input", help="Path to markdown file or - for stdin")
    p.add_argument("--chunked", action="store_true", help="Prefer chunked conversion")
    p.add_argument("--whole", action="store_true", help="Force whole-file conversion")
    p.add_argument("--output", help="Write converted markdown to this file")
    p.add_argument("--provider", default="gemini", choices=["gemini", "openrouter", "opencode"], help="LLM provider")
    p.add_argument("--api-key", help="API key override")
    p.add_argument("--model", default="gemini-2.0-flash", help="Model name")
    p.add_argument("--base-url", help="API base URL override (e.g. for opencode server)")
    p.add_argument(
        "--reasoning",
        dest="reasoning_effort",
        default=None,
        help="OpenCode reasoning effort: off/low/medium/high/max (e.g. 'off' to disable thinking)",
    )

    args = parser.parse_args()
    if args.cmd != "convert":
        parser.print_help()
        return 1

    orchestrator = Orchestrator(
        provider_name=args.provider,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        reasoning_effort=args.reasoning_effort,
    )
    if args.input == "-":
        data = sys.stdin.read()
        converted = orchestrator.run_from_text(data, chunked=args.chunked, whole=args.whole)
    else:
        converted = orchestrator.run_from_file(args.input, chunked=args.chunked, whole=args.whole)

    if args.output:
        Path(args.output).write_text(converted, encoding="utf-8")
        print(f"Wrote converted markdown to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
