"""Smoke test: DFA log plus tools/dfa_driver.py invokes dormant callables."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERP = REPO_ROOT / "PyFEX-core" / "python"
DRIVER = REPO_ROOT / "tools" / "dfa_driver.py"


def read_markers(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def main() -> int:
    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_dfa_"))
    marker = work_dir / "markers.log"
    dfa_log = work_dir / "dfa.log"
    invoke_log = work_dir / "invoke.log"
    target = work_dir / "target.py"

    target.write_text(
        textwrap.dedent(
            f"""
            MARKER = {str(marker)!r}

            def note(tag):
                with open(MARKER, "a", encoding="utf-8") as fp:
                    fp.write(tag + "\\n")

            def called_func():
                note("called_func")

            def dormant_func():
                note("dormant_func")

            class Carrier:
                def __init__(self):
                    note("carrier_init")

                def dormant_method(self):
                    note("dormant_method")

            called_func()
            """
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "DORMANT_FUNC_LOG_FILE": str(dfa_log),
            "CRASH_RECOVERY_ENABLE": "1",
        }
    )
    first = subprocess.run(
        [str(INTERP), str(target)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if first.returncode != 0:
        print(first.stdout)
        print("FAIL: initial DFA logging run failed")
        return 1

    log_text = dfa_log.read_text(encoding="utf-8")
    if "DEFINED dormant_func" not in log_text or "CALLED dormant_func" in log_text:
        print(f"FAIL: unexpected DFA log:\n{log_text}")
        return 1

    env = os.environ.copy()
    env.update(
        {
            "PYFEX_INTERPRETER": str(INTERP),
            "DFA_INVOKE_LOG": str(invoke_log),
            "DFA_INVOKE_CAP": "8",
        }
    )
    replay = subprocess.run(
        [sys.executable, str(DRIVER), str(dfa_log), str(target)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if replay.returncode != 0:
        print(replay.stdout)
        print("FAIL: DFA driver replay failed")
        return 1

    markers = read_markers(marker)
    if "dormant_func" not in markers:
        print(f"FAIL: dormant function was not invoked: {sorted(markers)}")
        return 1
    if "dormant_method" not in markers:
        print(f"FAIL: dormant class method was not invoked: {sorted(markers)}")
        return 1

    print("PASS: DFA driver invoked dormant function and dormant class method")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
