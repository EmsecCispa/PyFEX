"""Required-argument dormant replay actually runs the function body.

tools/dfa_driver.py synthesises a DummyObject for every required parameter UP
FRONT and supplies them at the call, so the call boundary is crossed and the
dormant function body executes. The arguments are built with operators rather
than list.append -- a DummyObject passed as a call argument to an out-of-scope
callable like list.append is intercepted by crash recovery, so the container is
assembled with bytecode ops instead. This test asserts the dormant body really
ran (a marker it writes is present), not merely that the call was attempted.
"""

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
    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_dfa_arg_gap_"))
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

            def dormant_needs_arg(required_arg):
                note("dormant_needs_arg:" + type(required_arg).__name__)

            def called_func():
                note("called_func")

            called_func()
            """
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update({"DORMANT_FUNC_LOG_FILE": str(dfa_log), "CRASH_RECOVERY_ENABLE": "1"})
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
    if not any(m.startswith("dormant_needs_arg:") for m in markers):
        print(f"FAIL: required-arg dormant body did not run: {sorted(markers)}")
        return 1

    invoke_lines = read_markers(invoke_log)
    if not any("invoked:dormant_needs_arg" in line for line in invoke_lines):
        print(f"FAIL: expected driver to report invocation: {sorted(invoke_lines)}")
        return 1

    print("PASS: required-argument dormant function was actually invoked (body ran)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
