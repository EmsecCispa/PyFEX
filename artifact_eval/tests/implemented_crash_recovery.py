"""Smoke test: crash recovery returns and propagates DummyObject values."""

from __future__ import annotations

import os


def missing_import():
    import pyfex_artifact_eval_missing_module as missing_module

    return missing_module


def main() -> int:
    os.environ["CRASH_RECOVERY_ENABLE"] = "1"
    os.environ["CRASH_RECOVERY_GLOBAL_LIMIT"] = "20"

    recovered = missing_import()
    if type(recovered).__name__ != "DummyObject":
        print(f"FAIL: expected DummyObject from missing import, got {type(recovered).__name__}")
        return 1

    propagated = recovered.client.fetch("payload")["token"]
    if type(propagated).__name__ != "DummyObject":
        print(f"FAIL: expected propagated DummyObject, got {type(propagated).__name__}")
        return 1

    trace_obj = getattr(propagated, "trace", "")
    trace_text = trace_obj if isinstance(trace_obj, str) else str(trace_obj)
    if "pyfex_artifact_eval_missing_module" not in trace_text:
        print(f"FAIL: propagated dummy trace lacks origin provenance: {trace_text!r}")
        return 1

    print("PASS: crash recovery produced a provenance-carrying propagated DummyObject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
