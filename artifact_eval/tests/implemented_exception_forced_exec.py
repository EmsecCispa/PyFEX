"""Forced-execution exception-handling behaviors in PyFEX-core/Python/ceval.c.

Re-executes this file under the PyFEX interpreter (``sys.executable``, the built
``./python`` when the artifact harness runs the suite) with forced execution
enabled, and asserts on the combined stdout+stderr.

RAISE_VARARGS suppress-child -- when FE forks a child that suppresses a
    ``raise``, the child continues only when an in-bounds next instruction
    exists and otherwise ``_exit(0)`` cleanly, so a *terminal* ``raise`` (the
    last op in a function) is handled safely. Assertion: the terminal-raise
    failure signature is absent. (The natural traceback for the raised error is
    expected and is NOT a failure.)

JUMP_IF_NOT_EXC_MATCH force-enter -- FE forks the ``res == 0`` case to force
    entry into an ``except`` handler whose type did NOT match. Assertion: a
    unique marker printed only from inside a non-matching ``except`` handler
    appears under FE (and the FE-off control proves it is FE-produced).

Run directly (from the artifact root):
    FORCE_EXEC_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
        PyFEX-core/python artifact_eval/tests/implemented_exception_forced_exec.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile


MARKER = "MARKER-FORCED-NONMATCHING-HANDLER-9f3a"

# Fix A's distinct bug signature. None of these substrings may appear in the
# terminal-raise run after the bounds guard is in place.
BUG_A_SIGNATURES = ("unknown opcode", "opcode: 0", "lineno: -1")


def target_terminal_raise() -> None:
    """A function whose LAST statement is a bare ``raise`` (Fix A)."""
    x = 1
    y = 2
    raise ValueError("boom-from-terminal-raise")


def target_force_enter() -> None:
    """try-body raises IndexError via an op; the except is a non-matching type."""
    try:
        bad = [][0]  # IndexError via BINARY_SUBSCR -- not a KeyError
        print("UNREACHED-after-index")
    except KeyError:
        print(MARKER)
    print("after-try")


def run_target(target: str, *, force_exec: bool) -> str:
    """Re-exec this file under the PyFEX interpreter, return combined output."""
    env = os.environ.copy()
    for key in (
        "FORCE_EXEC_ENABLE", "FORCE_EXEC_MERGE_ENABLE",
        "FORCE_EXEC_GLOBAL_LIMIT", "FORCE_EXEC_LOCAL_LIMIT",
        "FORCE_EXEC_MAX_PROCS",
    ):
        env.pop(key, None)
    if force_exec:
        env["FORCE_EXEC_ENABLE"] = "1"
        # Branch merging makes forced children _exit at their reconvergence
        # point instead of running the whole remaining program, keeping the
        # run bounded and clean.
        env["FORCE_EXEC_MERGE_ENABLE"] = "1"
        # Bound the total number of forks.
        env["FORCE_EXEC_GLOBAL_LIMIT"] = "20"
        # Leave FORCE_EXEC_MAX_PROCS at the interpreter default (8) so the
        # force-enter fork this test asserts on is not starved for slots;
        # branch merging keeps concurrency low.
    env["PYFEX_EXC_FE_TARGET"] = target
    env["PYTHONUNBUFFERED"] = "1"
    # Capture combined output to a temp FILE, not a PIPE. Forced execution
    # forks children that inherit the child's stdout fd; with a PIPE,
    # subprocess.run's communicate() blocks until *every* such grandchild
    # closes it (which lags when branch merging is off). A regular file
    # decouples us from pipe-EOF -- we wait only for the direct child to
    # exit -- so a lingering forced grandchild can't hang the harness.
    with tempfile.TemporaryFile("w+") as out:
        subprocess.run(
            [sys.executable, os.path.abspath(__file__)],
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        out.seek(0)
        return out.read()


def check_fix_a() -> bool:
    """Terminal raise under FE must not emit Fix A's unknown-opcode signature."""
    out = run_target("terminal_raise", force_exec=True)
    hits = [sig for sig in BUG_A_SIGNATURES if sig in out]
    if hits:
        print(f"FAIL[A]: terminal-raise FE output contains bug signature {hits}:\n{out}")
        return False
    # The natural traceback for the raised error is expected -- confirm the raise
    # actually fired so the test exercises the RAISE_VARARGS path it claims to.
    if "boom-from-terminal-raise" not in out:
        print(f"FAIL[A]: expected ValueError traceback not present:\n{out}")
        return False
    print("PASS[A]: terminal-raise suppress-child stays in-bounds (no unknown-opcode)")
    return True


def check_fix_b() -> bool:
    """FE must force entry into the non-matching except handler (marker prints)."""
    control = run_target("force_enter", force_exec=False)
    if MARKER in control:
        print(f"FAIL[B]: marker leaked into FE-off control (not FE-produced):\n{control}")
        return False

    out = run_target("force_enter", force_exec=True)
    if MARKER not in out:
        print(f"FAIL[B]: FE did not force entry into non-matching handler:\n{out}")
        return False
    print("PASS[B]: forced execution entered the non-matching except handler")
    return True


def driver_main() -> int:
    ok = check_fix_a()
    ok = check_fix_b() and ok
    if not ok:
        return 1
    print("PASS: forced-execution exception fixes (RAISE_VARARGS, JUMP_IF_NOT_EXC_MATCH)")
    return 0


if __name__ == "__main__":
    _target = os.environ.get("PYFEX_EXC_FE_TARGET")
    if _target == "terminal_raise":
        target_terminal_raise()
    elif _target == "force_enter":
        target_force_enter()
    else:
        raise SystemExit(driver_main())
