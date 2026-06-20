"""Smoke test: artifact runner blocks Python network access by default."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WRAPPER = REPO_ROOT / "artifact_eval" / "run_pyfex_program.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pyfex_network_sandbox_") as tmp_name:
        tmp = Path(tmp_name)
        target = tmp / "network_probe.py"
        network_log = tmp / "network.log"
        target.write_text(
            "import errno\n"
            "import socket\n"
            "try:\n"
            "    socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "except OSError as exc:\n"
            "    print('blocked', getattr(exc, 'errno', None))\n"
            "    raise SystemExit(0 if getattr(exc, 'errno', None) == errno.ENETUNREACH else 1)\n"
            "raise SystemExit('network socket was not blocked')\n",
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(WRAPPER),
                "--network",
                "blocked",
                "--network-log-file",
                str(network_log),
                "--timeout",
                "5",
                str(target),
            ],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        if proc.returncode != 0:
            print(f"FAIL: network probe exited {proc.returncode}\n{proc.stdout}")
            return 1
        if not network_log.is_file():
            print("FAIL: network blocker did not write network.log")
            return 1

        rows = [
            json.loads(line)
            for line in network_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not any(row.get("event") == "network_blocked" and row.get("action") == "socket.socket" for row in rows):
            print(f"FAIL: socket block event missing from network log: {rows!r}")
            return 1

    print("PASS: artifact runner blocked and logged Python socket creation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
