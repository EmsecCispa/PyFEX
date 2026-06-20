"""Smoke test: separate behavior trace and runtime debug logs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def make_dummy():
    return pyfex_trace_reporter_missing_name


def target_function(value, marker=None):
    return str(value), marker


def main() -> int:
    trace_path = Path(tempfile.gettempdir()) / f"pyfex_trace_reporter_{os.getpid()}.jsonl"
    runtime_path = Path(tempfile.gettempdir()) / f"pyfex_runtime_reporter_{os.getpid()}.log"
    trace_path.unlink(missing_ok=True)
    runtime_path.unlink(missing_ok=True)

    os.environ["PYFEX_TRACE_LOG_FILE"] = str(trace_path)
    os.environ["PYFEX_RUNTIME_LOG_FILE"] = str(runtime_path)
    os.environ["CRASH_RECOVERY_ENABLE"] = "1"

    dummy = make_dummy()
    propagated = dummy.payload["token"]
    target_function(7, marker=propagated)
    os.environ.pop("PYFEX_TRACE_LOG_FILE", None)
    os.environ.pop("PYFEX_RUNTIME_LOG_FILE", None)

    rows = []
    with trace_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    runtime_text = runtime_path.read_text(encoding="utf-8")

    calls = [row for row in rows if row.get("event") == "function_call"]
    recoveries = [row for row in rows if row.get("event") == "crash_recovery"]
    if recoveries:
        print(f"FAIL: behavior trace should not contain runtime recovery events: {recoveries!r}")
        return 1

    target_calls = [row for row in calls if row.get("function") == "target_function"]
    if not target_calls:
        print(f"FAIL: target_function call not logged: {rows!r}")
        return 1

    call = target_calls[-1]
    if call["args"][0]["repr"] != "7":
        print(f"FAIL: positional arg not logged correctly: {call!r}")
        return 1
    marker = call["kwargs"].get("marker")
    if not marker or marker.get("type") != "DummyObject":
        print(f"FAIL: dummy keyword arg missing from trace: {call!r}")
        return 1
    dummy_trace = marker.get("dummy_trace", "")
    if "Origin:" not in dummy_trace or "Lineage:" not in dummy_trace:
        print(f"FAIL: dummy trace is not human-readable: {dummy_trace!r}")
        return 1
    if "GETATTR: accessed attribute payload" not in dummy_trace:
        print(f"FAIL: dummy trace does not explain attribute propagation: {dummy_trace!r}")
        return 1
    if "GETITEM: subscripted the synthetic value" not in dummy_trace:
        print(f"FAIL: dummy trace does not explain item propagation: {dummy_trace!r}")
        return 1

    if "component=crash_recovery" not in runtime_text:
        print(f"FAIL: runtime log lacks crash recovery component: {runtime_text!r}")
        return 1
    if "RECOVERY: opcode=LOAD_GLOBAL" not in runtime_text and "RECOVERY: opcode=LOAD_NAME" not in runtime_text:
        print(f"FAIL: missing-name recovery was not logged to runtime log: {runtime_text!r}")
        return 1

    print("PASS: behavior trace logged calls/args and runtime log captured recovery events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
