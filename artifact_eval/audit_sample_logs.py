#!/usr/bin/env python3
"""Audit saved calibrated-sample logs for behavior-trace completeness."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOGS_DIR = REPO_ROOT / "artifact_eval" / "samples" / "logs"

DFA_ROW_RE = re.compile(r"^(?P<kind>DEFINED|CALLED)\s+(?P<qual>\S+)\s+(?P<name>\S+)\s+(?P<loc>.*):(?P<line>\d+)$")
FATAL_STDERR_RE = re.compile(
    r"Segmentation fault|core dumped|Fatal Python error|Aborted|Bus error|Illegal instruction|SystemError",
    re.IGNORECASE,
)
TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\):")


@dataclass(frozen=True)
class DfaCall:
    qualname: str
    name: str
    file: str
    line: int


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    sample: str
    entrypoint: str
    detail: str


def bool_value(text: str) -> bool:
    return str(text).strip().lower() in {"1", "true", "yes"}


def int_value(text: str) -> int:
    try:
        return int(str(text).strip() or "0")
    except ValueError:
        return 0


def logged_path(text: str) -> Path:
    path = Path(text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def read_entrypoint_rows(logs_dir: Path) -> list[tuple[str, dict[str, str]]]:
    rows: list[tuple[str, dict[str, str]]] = []
    for entrypoints_csv in sorted(logs_dir.glob("*/entrypoints.csv")):
        sample = entrypoints_csv.parent.name
        with entrypoints_csv.open("r", encoding="utf-8", newline="") as fp:
            for row in csv.DictReader(fp):
                rows.append((sample, row))
    return rows


def trace_function_names_by_location(path: Path) -> tuple[dict[tuple[str, int], list[str]], int, int, int]:
    by_location: dict[tuple[str, int], list[str]] = defaultdict(list)
    rows = 0
    calls = 0
    malformed = 0
    if not path.is_file():
        return by_location, rows, calls, malformed

    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            rows += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(event, dict) or event.get("event") != "function_call":
                continue
            caller = event.get("caller") or {}
            if not isinstance(caller, dict):
                caller = {}
            try:
                line_no = int(caller.get("line") or -1)
            except (TypeError, ValueError):
                line_no = -1
            by_location[(str(caller.get("file") or ""), line_no)].append(str(event.get("function") or ""))
            calls += 1
    return by_location, rows, calls, malformed


def read_dfa_calls(path: Path) -> tuple[list[DfaCall], int]:
    calls: list[DfaCall] = []
    defined = 0
    if not path.is_file():
        return calls, defined
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            match = DFA_ROW_RE.match(line)
            if not match:
                continue
            if match.group("kind") == "DEFINED":
                defined += 1
                continue
            calls.append(
                DfaCall(
                    qualname=match.group("qual"),
                    name=match.group("name"),
                    file=match.group("loc"),
                    line=int(match.group("line")),
                )
            )
    return calls, defined


def function_name_matches(trace_name: str, dfa_call: DfaCall) -> bool:
    if trace_name in {dfa_call.qualname, dfa_call.name}:
        return True
    if trace_name.endswith("." + dfa_call.name):
        return True
    if trace_name.endswith(".<locals>." + dfa_call.name):
        return True
    if dfa_call.qualname.endswith(trace_name):
        return True
    if trace_name.endswith(dfa_call.qualname):
        return True
    return False


def first_exception_line(stderr_text: str) -> str:
    for line in stderr_text.splitlines():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(Error|Exception|Warning):", line):
            return line.strip()
    return ""


def audit_entrypoint(sample: str, row: dict[str, str]) -> tuple[list[Issue], Counter[str]]:
    issues: list[Issue] = []
    stats: Counter[str] = Counter()
    entry_id = row.get("entry_id", "<unknown>")
    returncode = int_value(row.get("returncode", "0"))
    timed_out = bool_value(row.get("timed_out", "False"))
    csv_calls = int_value(row.get("function_call_events", "0"))
    csv_trace_rows = int_value(row.get("trace_rows", "0"))

    trace_path = logged_path(row.get("trace_path", ""))
    dfa_path = logged_path(row.get("dfa_path", ""))
    stderr_path = logged_path(row.get("stderr_path", ""))
    runtime_path = logged_path(row.get("runtime_path", ""))

    trace_by_location, trace_rows, trace_calls, malformed = trace_function_names_by_location(trace_path)
    dfa_calls, dfa_defined = read_dfa_calls(dfa_path)

    stats["entrypoints"] += 1
    stats["trace_rows"] += trace_rows
    stats["trace_calls"] += trace_calls
    stats["dfa_calls_checked"] += len(dfa_calls)
    stats["dfa_defined"] += dfa_defined

    if malformed:
        issues.append(Issue("error", "MALFORMED_TRACE_JSONL", sample, entry_id, f"{malformed} malformed rows in {trace_path}"))
        stats["malformed_trace_rows"] += malformed

    if trace_rows != csv_trace_rows or trace_calls != csv_calls:
        issues.append(
            Issue(
                "warning",
                "SUMMARY_TRACE_COUNT_MISMATCH",
                sample,
                entry_id,
                f"entrypoints.csv rows/calls={csv_trace_rows}/{csv_calls}, parsed={trace_rows}/{trace_calls}",
            )
        )

    if not trace_path.is_file() and dfa_calls:
        issues.append(Issue("error", "MISSING_TRACE_WITH_DFA_CALLS", sample, entry_id, f"{len(dfa_calls)} DFA calls but no trace file"))
    elif not trace_path.is_file() and returncode == 0:
        issues.append(Issue("info", "NO_FUNCTION_CALLS_OBSERVED", sample, entry_id, "no trace file and no DFA calls"))
        stats["no_call_entrypoints"] += 1

    missing_dfa_calls = 0
    for dfa_call in dfa_calls:
        trace_names = trace_by_location.get((dfa_call.file, dfa_call.line), [])
        if not any(function_name_matches(trace_name, dfa_call) for trace_name in trace_names):
            missing_dfa_calls += 1
            if missing_dfa_calls <= 5:
                seen = ", ".join(trace_names[:5]) if trace_names else "<none>"
                issues.append(
                    Issue(
                        "error",
                        "DFA_CALL_NOT_IN_TRACE",
                        sample,
                        entry_id,
                        f"{dfa_call.file}:{dfa_call.line} {dfa_call.qualname}; trace at line: {seen}",
                    )
                )
    stats["missing_dfa_calls"] += missing_dfa_calls
    if missing_dfa_calls > 5:
        issues.append(
            Issue(
                "error",
                "DFA_CALL_NOT_IN_TRACE_MORE",
                sample,
                entry_id,
                f"{missing_dfa_calls - 5} additional missing DFA calls omitted",
            )
        )

    if returncode != 0:
        stats["nonzero_entrypoints"] += 1
        severity = "error" if returncode < 0 or returncode >= 128 else "warning"
        issues.append(Issue(severity, "NONZERO_RETURN", sample, entry_id, f"returncode={returncode}"))

    if timed_out:
        stats["timeouts"] += 1
        issues.append(Issue("warning", "TIMEOUT", sample, entry_id, "entrypoint hit runner timeout"))

    stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    runtime_text = runtime_path.read_text(encoding="utf-8", errors="replace") if runtime_path.is_file() else ""
    fatal_match = FATAL_STDERR_RE.search(stderr_text) or FATAL_STDERR_RE.search(runtime_text)
    if fatal_match:
        stats["fatal_patterns"] += 1
        issues.append(Issue("error", "FATAL_INTERPRETER_PATTERN", sample, entry_id, fatal_match.group(0)))

    if TRACEBACK_RE.search(stderr_text):
        stats["stderr_tracebacks"] += 1
        first_exception = first_exception_line(stderr_text) or "traceback present"
        issues.append(Issue("warning", "STDERR_TRACEBACK", sample, entry_id, first_exception))

    if trace_calls == 0 and not dfa_calls and returncode == 0:
        stats["empty_success_entrypoints"] += 1

    return issues, stats


def render_report(logs_dir: Path, issues: list[Issue], stats: Counter[str], output: TextIO, max_issues: int) -> None:
    severities = Counter(issue.severity for issue in issues)
    error_count = severities["error"]
    warning_count = severities["warning"]
    info_count = severities["info"]

    samples = {sample_dir.name for sample_dir in logs_dir.iterdir() if sample_dir.is_dir()} if logs_dir.is_dir() else set()
    output.write("# PyFEX Sample Log Audit\n\n")
    output.write(f"- logs_dir: `{logs_dir}`\n")
    output.write(f"- samples_seen: {len(samples)}\n")
    output.write(f"- entrypoints_seen: {stats['entrypoints']}\n")
    output.write(f"- behavior_trace_rows: {stats['trace_rows']}\n")
    output.write(f"- behavior_function_calls: {stats['trace_calls']}\n")
    output.write(f"- dfa_calls_checked_against_trace: {stats['dfa_calls_checked']}\n")
    output.write(f"- dfa_calls_missing_from_trace: {stats['missing_dfa_calls']}\n")
    output.write(f"- nonzero_entrypoints: {stats['nonzero_entrypoints']}\n")
    output.write(f"- timed_out_entrypoints: {stats['timeouts']}\n")
    output.write(f"- stderr_traceback_entrypoints: {stats['stderr_tracebacks']}\n")
    output.write(f"- fatal_interpreter_patterns: {stats['fatal_patterns']}\n")
    output.write(f"- no_call_success_entrypoints: {stats['empty_success_entrypoints']}\n")
    output.write(f"- issues: errors={error_count}, warnings={warning_count}, info={info_count}\n\n")

    if stats["missing_dfa_calls"] == 0 and stats["fatal_patterns"] == 0:
        output.write("No behavior-trace truncation was detected by the DFA-vs-trace consistency check.\n\n")
    else:
        output.write("Potential PyFEX trace/runtime problems were detected; inspect the error rows below.\n\n")

    if not issues:
        output.write("No issues found.\n")
        return

    output.write("| severity | code | sample | entrypoint | detail |\n")
    output.write("| --- | --- | --- | --- | --- |\n")
    for issue in issues[:max_issues]:
        detail = issue.detail.replace("|", "\\|").replace("\n", " ")
        output.write(f"| {issue.severity} | {issue.code} | {issue.sample} | {issue.entrypoint} | {detail} |\n")
    if len(issues) > max_issues:
        output.write(f"\nOmitted {len(issues) - max_issues} additional issue rows. Increase `--max-issues` to show more.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit artifact_eval sample logs for trace completeness.")
    parser.add_argument("--logs-dir", default=str(DEFAULT_LOGS_DIR), help="Path to artifact_eval/samples/logs.")
    parser.add_argument("-o", "--output", help="Write a Markdown audit report to this path. Default: stdout.")
    parser.add_argument("--max-issues", type=int, default=200, help="Maximum issue rows to render.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on warnings as well as errors.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logs_dir = Path(args.logs_dir).resolve()
    if not logs_dir.is_dir():
        raise SystemExit(f"logs directory not found: {logs_dir}")

    rows = read_entrypoint_rows(logs_dir)
    if not rows:
        raise SystemExit(f"no entrypoints.csv files found under {logs_dir}")

    all_issues: list[Issue] = []
    total_stats: Counter[str] = Counter()
    for sample, row in rows:
        issues, stats = audit_entrypoint(sample, row)
        all_issues.extend(issues)
        total_stats.update(stats)

    all_issues.sort(key=lambda issue: ({"error": 0, "warning": 1, "info": 2}.get(issue.severity, 3), issue.sample, issue.entrypoint, issue.code))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fp:
            render_report(logs_dir, all_issues, total_stats, fp, args.max_issues)
    else:
        render_report(logs_dir, all_issues, total_stats, sys.stdout, args.max_issues)

    has_errors = any(issue.severity == "error" for issue in all_issues)
    has_warnings = any(issue.severity == "warning" for issue in all_issues)
    if has_errors or (args.strict and has_warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
