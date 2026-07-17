#!/usr/bin/env python3
"""Summarize PyFEX DFA coverage for a package run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


GENERATED_PREFIXES = ("_pyfex_", "_dfa_invoke_")
DEFAULT_SKIP_PARTS = {
    "__pycache__",
    ".eggs",
    "build",
    "dist",
}
TEST_DOC_PARTS = {
    "doc",
    "docs",
    "example",
    "examples",
    "test",
    "tests",
}


def is_generated(path: Path) -> bool:
    return any(path.name.startswith(prefix) for prefix in GENERATED_PREFIXES)


def should_skip(path: Path, package_dir: Path, exclude_tests_docs: bool) -> bool:
    try:
        rel = path.relative_to(package_dir)
    except ValueError:
        return True
    if is_generated(path):
        return True
    parts = set(rel.parts)
    if parts & DEFAULT_SKIP_PARTS:
        return True
    if any(part.endswith((".egg-info", ".dist-info")) for part in rel.parts):
        return True
    if exclude_tests_docs and parts & TEST_DOC_PARTS:
        return True
    return False


def package_py_files(package_dir: Path, exclude_tests_docs: bool) -> set[Path]:
    files: set[Path] = set()
    for path in package_dir.rglob("*.py"):
        resolved = path.resolve()
        if not should_skip(resolved, package_dir, exclude_tests_docs):
            files.add(resolved)
    return files


def parse_location(loc: str) -> tuple[Path, int] | None:
    if ":" not in loc:
        return None
    filename, lineno_text = loc.rsplit(":", 1)
    try:
        lineno = int(lineno_text)
    except ValueError:
        return None
    if filename.startswith("<") and filename.endswith(">"):
        return None
    return Path(filename).resolve(), lineno


def parse_dfa_logs(paths: Iterable[Path]) -> tuple[set[tuple[str, str, Path, int]], set[str], set[Path]]:
    defined: set[tuple[str, str, Path, int]] = set()
    called: set[str] = set()
    touched_files: set[Path] = set()

    for path in paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as fp:
            for raw in fp:
                line = raw.rstrip("\n")
                parts = line.split(" ", 3)
                if len(parts) != 4:
                    continue
                kind, qualname, name, loc = parts
                parsed = parse_location(loc)
                if parsed is not None:
                    filename, lineno = parsed
                    touched_files.add(filename)
                else:
                    filename = Path("<unknown>")
                    lineno = 0
                if kind == "DEFINED":
                    defined.add((qualname, name, filename, lineno))
                elif kind == "CALLED":
                    called.add(qualname)

    return defined, called, touched_files


def parse_trace_logs(paths: Iterable[Path]) -> set[Path]:
    touched: set[Path] = set()
    for path in paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as fp:
            for raw in fp:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict) or row.get("event") != "function_call":
                    continue
                caller = row.get("caller", {})
                if not isinstance(caller, dict):
                    continue
                filename = caller.get("file")
                if not isinstance(filename, str):
                    continue
                if filename.startswith("<") and filename.endswith(">"):
                    continue
                touched.add(Path(filename).resolve())
    return touched


def rel(path: Path, package_dir: Path) -> str:
    try:
        return str(path.relative_to(package_dir))
    except ValueError:
        return str(path)


def write_summary(
    output: Path,
    package_dir: Path,
    dfa_logs: list[Path],
    trace_logs: list[Path],
    exclude_tests_docs: bool,
) -> dict[str, int]:
    all_py_files = package_py_files(package_dir, exclude_tests_docs)
    defined, called, dfa_touched = parse_dfa_logs(dfa_logs)
    trace_touched = parse_trace_logs(trace_logs)
    touched_files = {
        path for path in (dfa_touched | trace_touched)
        if path in all_py_files
    }
    untouched_files = sorted(all_py_files - touched_files)
    dormant = sorted(
        item for item in defined
        if item[0] not in called and item[2] in all_py_files
    )

    lines = [
        "# PyFEX DFA Coverage Summary",
        "",
        f"package_dir: {package_dir}",
        f"dfa_logs: {len([path for path in dfa_logs if path.is_file()])}",
        f"trace_logs: {len([path for path in trace_logs if path.is_file()])}",
        f"python_files: {len(all_py_files)}",
        f"touched_files: {len(touched_files)}",
        f"untouched_files: {len(untouched_files)}",
        f"defined_functions: {sum(1 for item in defined if item[2] in all_py_files)}",
        f"called_functions: {len(called)}",
        f"defined_but_not_called: {len(dormant)}",
        "",
        "## Untouched Python Files",
    ]
    if untouched_files:
        lines.extend(f"- {rel(path, package_dir)}" for path in untouched_files)
    else:
        lines.append("- <none>")

    lines.extend(["", "## Defined But Not Called"])
    if dormant:
        for qualname, _name, filename, lineno in dormant:
            lines.append(f"- {rel(filename, package_dir)}:{lineno} {qualname}")
    else:
        lines.append("- <none>")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "python_files": len(all_py_files),
        "touched_files": len(touched_files),
        "untouched_files": len(untouched_files),
        "defined_but_not_called": len(dormant),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True, help="Copied package directory.")
    parser.add_argument("--dfa-log", action="append", default=[], help="DORMANT_FUNC_LOG_FILE path. Can be repeated.")
    parser.add_argument("--trace-log", action="append", default=[], help="Behavior trace JSONL path. Can be repeated.")
    parser.add_argument("-o", "--output", required=True, help="Summary output path.")
    parser.add_argument("--exclude-tests-docs", action="store_true", help="Exclude tests/docs/examples from untouched-file accounting.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stats = write_summary(
        Path(args.output),
        Path(args.package_dir).resolve(),
        [Path(path) for path in args.dfa_log],
        [Path(path) for path in args.trace_log],
        args.exclude_tests_docs,
    )
    print(
        "python_files={python_files} touched_files={touched_files} "
        "untouched_files={untouched_files} defined_but_not_called={defined_but_not_called}".format(**stats)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
