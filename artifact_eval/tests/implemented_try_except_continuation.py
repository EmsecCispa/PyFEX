"""Smoke test: dummy iteration must not truncate forced try/except execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "artifact_eval" / "run_pyfex_program.py"


def target_probe() -> None:
    try:
        values = missing_dependency.call(domain_name="example.org")
        for value in values:
            if value.name == "needle":
                print(value)
    except Exception:
        pass
    print("after-probe")


def target_main() -> None:
    target_probe()
    print("after-module")


def driver_main() -> int:
    with tempfile.TemporaryDirectory(prefix="pyfex_try_except_") as tmp_name:
        tmp = Path(tmp_name)
        trace_log = tmp / "trace.jsonl"
        runtime_log = tmp / "runtime.log"
        proc = subprocess.run(
            [
                sys.executable,
                str(WRAPPER),
                "--crash-recovery-enable",
                "1",
                "--force-exec-enable",
                "1",
                "--force-exec-merge-enable",
                "1",
                "--force-exec-global-limit",
                "12",
                "--force-exec-location-limit",
                "2",
                "--force-exec-loop-iter-limit",
                "50",
                "--pyfex-scope-dir",
                str(Path(__file__).resolve().parent),
                "--pyfex-trace-log-file",
                str(trace_log),
                "--pyfex-runtime-log-file",
                str(runtime_log),
                "--network",
                "blocked",
                "--network-os-sandbox",
                "unshare",
                "--env",
                "PYFEX_TRY_EXCEPT_TARGET=1",
                str(Path(__file__).resolve()),
            ],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        if proc.returncode != 0:
            print(f"FAIL: target exited {proc.returncode}\n{proc.stdout}")
            print(runtime_log.read_text(encoding="utf-8", errors="replace") if runtime_log.is_file() else "")
            return 1
        if "after-probe" not in proc.stdout or "after-module" not in proc.stdout:
            print(f"FAIL: parent execution did not continue after dummy iteration\n{proc.stdout}")
            return 1

        calls = []
        with trace_log.open("r", encoding="utf-8") as fp:
            for line in fp:
                row = json.loads(line)
                if row.get("event") == "function_call":
                    calls.append((row.get("caller", {}).get("line"), row.get("function")))

        if (25, "print") not in calls or (30, "print") not in calls:
            print(f"FAIL: behavior trace missed post-try calls: {calls!r}")
            return 1

    print("PASS: dummy iteration continued and trace captured post-try calls")
    return 0


if __name__ == "__main__":
    if os.environ.get("PYFEX_TRY_EXCEPT_TARGET") == "1":
        target_main()
    else:
        raise SystemExit(driver_main())
