"""Package-directory DFA replay runs dormant bodies across multiple modules.

tools/dfa_driver.py compute_dormant() accepts ``scope`` as a package DIRECTORY
(not just a single .py): every defined-but-never-called, non-underscore callable
under that directory is replayed, carrying its defining file so the right module
is imported per dormant. This is the mode the pipeline's run_dfa_replay() uses --
it concatenates per-entry DFA logs and passes the package directory as scope.

This exercises that directory-scope mode together with:
  * multi-file: a free function dormant in mod_a.py and a class-method dormant
    in mod_b.py, replayed in one driver pass over the package dir;
  * the class-method path: _instantiate(cls) builds Worker with None (NOT a
    DummyObject, which a type short-circuits) for its required __init__ arg, then
    _invoke synthesises a DummyObject for run()'s required arg so its body runs.

It asserts the dormant BODIES actually executed (marker file) AND the driver
reported each as invoked (invoked:<qualname> in DFA_INVOKE_LOG) -- not merely
that the call looked invoked while the body never ran.
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


def run_dfa_logging(target: Path, dfa_log: Path) -> subprocess.CompletedProcess:
    """Run one module under DFA logging + crash recovery, appending to dfa_log."""
    env = os.environ.copy()
    env.update({"DORMANT_FUNC_LOG_FILE": str(dfa_log), "CRASH_RECOVERY_ENABLE": "1"})
    return subprocess.run(
        [str(INTERP), str(target)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )


def main() -> int:
    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_dfa_pkg_"))
    pkg = work_dir / "pkg"
    pkg.mkdir()
    marker = work_dir / "markers.log"
    dfa_log = work_dir / "dfa.log"
    invoke_log = work_dir / "invoke.log"

    mod_a = pkg / "mod_a.py"
    mod_b = pkg / "mod_b.py"

    # mod_a: a dormant free function needing one required arg, plus a function
    # that IS called at module top level (must show up CALLED, never replayed).
    mod_a.write_text(
        textwrap.dedent(
            f"""
            MARKER = {str(marker)!r}

            def note(tag):
                with open(MARKER, "a", encoding="utf-8") as fp:
                    fp.write(tag + "\\n")

            def dormant_a(required):
                note("dormant_a:" + type(required).__name__)

            def called_a():
                note("called_a")

            called_a()
            """
        ),
        encoding="utf-8",
    )

    # mod_b: a dormant class whose __init__ needs a required arg and whose
    # method run() needs a required arg. Nothing instantiates or calls it.
    mod_b.write_text(
        textwrap.dedent(
            f"""
            MARKER = {str(marker)!r}

            def note(tag):
                with open(MARKER, "a", encoding="utf-8") as fp:
                    fp.write(tag + "\\n")

            class Worker:
                def __init__(self, required):
                    note("worker_init")

                def run(self, x):
                    note("worker_run")
            """
        ),
        encoding="utf-8",
    )

    # Produce a combined DFA log exactly as the pipeline does: run each module
    # once, appending DEFINED/CALLED lines to the same log file.
    for target in (mod_a, mod_b):
        proc = run_dfa_logging(target, dfa_log)
        if proc.returncode != 0:
            print(proc.stdout)
            print(f"FAIL: initial DFA logging run failed for {target.name}")
            return 1

    log_text = dfa_log.read_text(encoding="utf-8")
    # called_a must be CALLED; the two dormant callables must be DEFINED but not
    # CALLED. (Worker.__init__ may also be DEFINED, but it is underscore-private
    # so the driver skips it -- only Worker.run is replayed.)
    if "CALLED called_a" not in log_text:
        print(f"FAIL: called_a not recorded CALLED in DFA log:\n{log_text}")
        return 1
    for q in ("dormant_a", "Worker.run"):
        if f"DEFINED {q} " not in log_text:
            print(f"FAIL: {q} not recorded DEFINED in DFA log:\n{log_text}")
            return 1
        if f"CALLED {q} " in log_text:
            print(f"FAIL: {q} unexpectedly recorded CALLED in DFA log:\n{log_text}")
            return 1

    # Replay over the package DIRECTORY (scope = the dir, not a single file).
    env = os.environ.copy()
    env.update(
        {
            "PYFEX_INTERPRETER": str(INTERP),
            "DFA_INVOKE_LOG": str(invoke_log),
            "DFA_INVOKE_CAP": "8",
        }
    )
    replay = subprocess.run(
        [sys.executable, str(DRIVER), str(dfa_log), str(pkg)],
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
    invoke_lines = read_markers(invoke_log)

    def fail(reason: str) -> int:
        print(f"FAIL: {reason}")
        print(f"  markers     = {sorted(markers)}")
        print(f"  invoke_log  = {sorted(invoke_lines)}")
        print(f"  replay_out  = {replay.stdout.strip()}")
        return 1

    # Bodies must actually have run (markers written by the dormant functions
    # themselves), across BOTH modules.
    if not any(m.startswith("dormant_a:") for m in markers):
        return fail("free-function dormant body (mod_a.dormant_a) did not run")
    if "worker_run" not in markers:
        return fail("class-method dormant body (mod_b.Worker.run) did not run")

    # Driver must report each dormant as invoked (the pipeline counts these).
    if not any("invoked:dormant_a" in line for line in invoke_lines):
        return fail("driver did not report invoked:dormant_a")
    if not any("invoked:Worker.run" in line for line in invoke_lines):
        return fail("driver did not report invoked:Worker.run")

    print(
        "PASS: package-directory DFA replay ran dormant free function and "
        "dormant class method across two modules (bodies executed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
