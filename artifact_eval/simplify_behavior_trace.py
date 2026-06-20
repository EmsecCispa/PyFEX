#!/usr/bin/env python3
"""Render PyFEX behavior-trace JSONL as compact human-readable call logs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]


def shorten_path(path: str, base_dir: Path | None, basename: bool) -> str:
    if not path:
        return "<unknown>"
    if path.startswith("<") and path.endswith(">"):
        return path
    candidate = Path(path)
    if basename:
        return candidate.name
    if base_dir is not None:
        try:
            return str(candidate.resolve().relative_to(base_dir))
        except (OSError, ValueError):
            pass
    return path


def truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def value_repr(value: Any, limit: int) -> str:
    if isinstance(value, dict):
        rendered = value.get("repr")
        if rendered is not None:
            return truncate(str(rendered), limit)
        rendered_type = value.get("type")
        if rendered_type:
            return f"<{rendered_type}>"
    return truncate(repr(value), limit)


def format_args(row: dict[str, Any], limit: int) -> str:
    args = [value_repr(arg, limit) for arg in row.get("args", [])]
    kwargs = row.get("kwargs", {})
    if isinstance(kwargs, dict):
        for key in sorted(kwargs):
            args.append(f"{key}={value_repr(kwargs[key], limit)}")
    return ", ".join(args)


def format_row(
    row: dict[str, Any],
    *,
    base_dir: Path | None,
    basename: bool,
    max_arg_repr: int,
    include_pid: bool,
    include_kind: bool,
) -> str | None:
    if row.get("event") != "function_call":
        return None

    caller = row.get("caller", {})
    if not isinstance(caller, dict):
        caller = {}
    file_name = shorten_path(str(caller.get("file") or ""), base_dir, basename)
    line = caller.get("line") or "?"
    function = row.get("function") or "<unknown>"
    args = format_args(row, max_arg_repr)

    metadata: list[str] = []
    if include_pid and row.get("pid") is not None:
        metadata.append(f"pid={row['pid']}")
    if include_kind and row.get("kind") is not None:
        metadata.append(f"kind={row['kind']}")
    suffix = f" [{' '.join(metadata)}]" if metadata else ""
    return f"[{file_name}:{line}] [{function}]({args}){suffix}"


def render_trace(args: argparse.Namespace, output: TextIO) -> int:
    input_path = Path(args.trace_jsonl)
    base_dir = None if args.full_path else Path(args.base_dir).resolve()
    rendered = 0
    skipped = 0

    with input_path.open("r", encoding="utf-8", errors="replace") as fp:
        for line_no, line in enumerate(fp, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                skipped += 1
                if args.warn:
                    print(f"warning: skipped malformed JSONL line {line_no}: {exc}", file=sys.stderr)
                continue
            if not isinstance(row, dict):
                skipped += 1
                continue
            formatted = format_row(
                row,
                base_dir=base_dir,
                basename=args.basename,
                max_arg_repr=args.max_arg_repr,
                include_pid=args.include_pid,
                include_kind=args.include_kind,
            )
            if formatted is None:
                skipped += 1
                continue
            output.write(formatted + "\n")
            rendered += 1

    if args.summary:
        print(f"rendered={rendered} skipped={skipped}", file=sys.stderr)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PyFEX behavior_trace.jsonl into compact call-log text.",
        epilog=(
            "Example:\n"
            "  python3 artifact_eval/simplify_behavior_trace.py "
            "artifact_eval/samples/logs/001_x/behavior_trace.jsonl -o trace.simple.log"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("trace_jsonl", help="Input PYFEX_TRACE_LOG_FILE JSONL path.")
    parser.add_argument("-o", "--output", help="Output path. Default: stdout.")
    parser.add_argument("--base-dir", default=str(REPO_ROOT), help="Base directory used to shorten absolute paths.")
    parser.add_argument("--full-path", action="store_true", help="Keep full filenames instead of shortening with --base-dir.")
    parser.add_argument("--basename", action="store_true", help="Show only basename for each caller file.")
    parser.add_argument("--max-arg-repr", type=int, default=180, help="Maximum characters per argument repr. Use 0 to disable.")
    parser.add_argument("--include-pid", action="store_true", help="Append pid metadata.")
    parser.add_argument("--include-kind", action="store_true", help="Append callable-kind metadata.")
    parser.add_argument("--summary", action="store_true", help="Print rendered/skipped counts to stderr.")
    parser.add_argument("--warn", action="store_true", help="Warn about malformed JSONL rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            return render_trace(args, fp)
    return render_trace(args, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
