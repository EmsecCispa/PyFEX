"""A byte-compiled main script (`python foo.pyc`) is in scope for PyFEX.

Change under test: PyFEX-core/Python/pyfex_forceexec.c. The new helper
``_Py_PyFEX_SameScriptBase`` makes the main-script basename comparison in
``_Py_PyFEX_FilenameMatches`` treat a trailing ".pyc" as equivalent to ".py".
So running ``python foo.pyc`` (whose frames carry ``co_filename`` "foo.py")
matches ``sys.argv[0]`` "foo.pyc" by stem, and crash recovery / forced
execution activate for that main module -- WITHOUT needing ``PYFEX_SCOPE_DIR``.

Why this is load-bearing (non-tautological): under the OLD engine the ".pyc"
main module was out of scope (basename "foo.pyc" != "foo.py"), so crash
recovery would NOT fire on it and the target program would die with
``NameError: name 'undefined_seed_value' is not defined``. This test asserts
the opposite: the recovered value is a DummyObject, both branches of an
``if`` execute (forced execution forked the .pyc's main module), and no
NameError/traceback escapes.

The .pyc is compiled with a *basename* ``co_filename`` (``dfile="target.py"``),
the realistic relocatable case, so the match relies on the stem rule rather
than an absolute-path coincidence.

This harness is run by the system ``python3`` and spawns
``PyFEX-core/python`` itself. Forced execution is bounded by
``FORCE_EXEC_MERGE_ENABLE=1`` + ``FORCE_EXEC_GLOBAL_LIMIT=20``.

Run directly:
    python3 artifact_eval/tests/implemented_pyc_scope.py
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

# Markers the target prints. Crash recovery is proven by DUMMY_TOKEN appearing
# on the "recovered:" line; forced execution by BOTH branch markers appearing.
CONCRETE = "[concrete] benign"
FORCED = "[forced] HIDDEN"
DUMMY_TOKEN = "DummyObject"
# If the .pyc main module were out of scope, this is how the run would die.
OLD_ENGINE_FAILURE = "NameError"

TARGET_SOURCE = textwrap.dedent(
    """
    x = undefined_seed_value          # NameError -> crash recovery -> dummy

    def guard():
        return True

    if guard():
        print("[concrete] benign", flush=True)
    else:
        print("[forced] HIDDEN", flush=True)   # forced execution reaches this

    print("recovered:", x + 1, flush=True)     # uses the recovered dummy
    """
)


def pyfex_env() -> dict[str, str]:
    """CR + FE enabled, bounded, and PYFEX_SCOPE_DIR explicitly unset."""
    env = os.environ.copy()
    env.pop("PYFEX_SCOPE_DIR", None)
    env.update(
        {
            "CRASH_RECOVERY_ENABLE": "1",
            "FORCE_EXEC_ENABLE": "1",
            # Merge makes forced children _exit at their post-dominator instead
            # of running the whole remaining program -- keeps the run bounded.
            "FORCE_EXEC_MERGE_ENABLE": "1",
            # Bound forking so a regression cannot fork unbounded.
            "FORCE_EXEC_GLOBAL_LIMIT": "20",
            "PYTHONUNBUFFERED": "1",
        }
    )
    return env


def run_script(script: Path) -> str:
    """Run a target under the PyFEX interp; return combined stdout+stderr.

    A temp FILE (not a PIPE) decouples us from forced-execution grandchildren
    that inherit stdout: we wait only for the direct child to exit.
    """
    with tempfile.TemporaryFile("w+") as out:
        subprocess.run(
            [str(INTERP), str(script)],
            cwd=REPO_ROOT,
            env=pyfex_env(),
            stdout=out,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        out.seek(0)
        return out.read()


def check(label: str, output: str) -> bool:
    """Assert the in-scope signature on combined (forked) output.

    Substring checks only -- forced-execution interleaves child output, so
    line ordering / boundaries are non-deterministic and must not be asserted.
    """
    ok = True
    # Crash recovery fired on this main module: the recovered value is a Dummy.
    recovered_lines = [ln for ln in output.splitlines() if "recovered:" in ln]
    if not any(DUMMY_TOKEN in ln for ln in recovered_lines):
        print(f"FAIL[{label}]: recovered value is not a {DUMMY_TOKEN} "
              f"(crash recovery did not fire): {recovered_lines!r}")
        ok = False
    # Forced execution forked this main module: BOTH branches executed.
    if CONCRETE not in output:
        print(f"FAIL[{label}]: concrete branch marker {CONCRETE!r} missing")
        ok = False
    if FORCED not in output:
        print(f"FAIL[{label}]: forced branch marker {FORCED!r} missing "
              f"(forced execution did not fork this main module)")
        ok = False
    # No uncaught NameError/traceback escaped (the OLD-engine death mode).
    if OLD_ENGINE_FAILURE in output or "Traceback" in output:
        print(f"FAIL[{label}]: uncaught error escaped (main module looks "
              f"out of scope)")
        ok = False
    return ok


def main() -> int:
    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_pyc_scope_"))
    target_py = work_dir / "target.py"
    target_pyc = work_dir / "target.pyc"
    target_py.write_text(TARGET_SOURCE, encoding="utf-8")

    # Compile to a sibling .pyc with a BASENAME co_filename (dfile="target.py"):
    # the realistic, relocatable case where the match relies on the stem rule.
    compiled = subprocess.run(
        [
            str(INTERP),
            "-c",
            "import py_compile,sys; py_compile.compile("
            "sys.argv[1], cfile=sys.argv[2], dfile=sys.argv[3], doraise=True)",
            str(target_py),
            str(target_pyc),
            "target.py",
        ],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    if compiled.returncode != 0 or not target_pyc.exists():
        print(compiled.stdout)
        print("FAIL: could not byte-compile target to .pyc")
        return 1

    # Primary assertion: the .pyc main module is in scope (CR + FE fire).
    pyc_out = run_script(target_pyc)
    pyc_ok = check("pyc", pyc_out)

    # Control: the SAME target as .py source must behave identically, proving
    # the .py path is unchanged by the new ".pyc"-stem matching.
    py_out = run_script(target_py)
    py_ok = check("py-control", py_out)

    if not (pyc_ok and py_ok):
        print("---- .pyc output ----")
        print(pyc_out)
        print("---- .py control output ----")
        print(py_out)
        return 1

    print("PASS: byte-compiled .pyc main script is in scope for PyFEX "
          "(crash recovery + forced execution fired; .py path unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
