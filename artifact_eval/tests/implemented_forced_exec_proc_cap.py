"""Regression test for the forced-execution concurrent live-process cap.

Feature under test (PyFEX-core/Python/pyfex_forceexec.c):
``_Py_ForceExec_ShouldFork`` refuses to fork once the number of *live* forced
children -- tracked in a shared-memory PID registry, liveness via
``kill(pid,0)`` -- reaches ``FORCE_EXEC_MAX_PROCS`` (default 8, clamped to
``FORCE_EXEC_MAX_PROCS_HARD_CAP``, default 256). Unlike
``FORCE_EXEC_GLOBAL_LIMIT`` (total forks over the whole run), this bounds
*concurrency*: how many forced interpreters are alive at the same instant.
That is the memory-safety property -- without it, a loop full of fork sites can
leave dozens of full interpreters resident at once.

Strategy
--------
The driver writes a tiny, SELF-CONTAINED target script to a temp file and runs
THAT under the PyFEX interpreter with forced execution on. The target is a loop
whose every iteration has an ``if`` branch (a ``POP_JUMP_IF_FALSE`` fork site)
followed by a ``time.sleep`` so forked children OVERLAP in time. The target is a
separate file ON PURPOSE: when branch merging is OFF, a forced child runs the
*entire remaining program* rather than ``_exit``-ing at a post-dominator. If the
target and driver were the same self-re-exec file, a forced child could fall
through into driver code and recursively spawn more interpreters -- a fork bomb.
A standalone target's forked children can only ever run the simple loop.

Branch merging is OFF in both runs deliberately: the concurrent cap is then the
ONLY thing bounding how many forced interpreters are alive at once, which is
exactly the property under test.

The driver runs the target, polling the number of live forced interpreters
(processes whose ``/proc/<pid>/comm`` == ``python``, excluding ``os.getpid()``)
and recording the PEAK. ``comm == python`` counts the whole forced tree (the
target root plus every live forced child); the cap bounds the forced children,
so a low cap keeps this whole-tree peak low.

Assertions (concrete, self-verifying)
--------------------------------------
1. LOW cap (FORCE_EXEC_MAX_PROCS=2): peak stays below LOW_CAP_CEILING. The cap
   reserves its slot atomically (CAS) at the fork, so the check-then-fork
   overshoot is tiny (~+1, measured low-cap peak ~3). The ceiling sits a small
   margin above the cap yet far below where an *ignored* cap would land (the
   high run shows the program wants ~24+), so it fails a broken/ignored cap.
2. The cap -- not program size / global budget -- is the limiter. HIGH cap
   (FORCE_EXEC_MAX_PROCS=24) must exceed the low-cap peak by a wide, stable GAP.
   Same program, same FORCE_EXEC_GLOBAL_LIMIT, merge still off: the only thing
   that changed is the cap. If the cap were ignored, both runs would peak at the
   same program-determined level and the gap would vanish.

Measured (PyFEX-core, this loop): low cap=2 -> peak ~3 (atomic reservation
keeps overshoot to ~+1); high cap=24 -> peak ~25. The two bands are cleanly
separated.

Bounding / safety
-----------------
FORCE_EXEC_GLOBAL_LIMIT caps total forks; merge off; a short loop; the driver
installs an RLIMIT_NPROC backstop (current task count + headroom) so a
regression cannot fork-bomb the host; survivors are SIGKILLed by PID (never the
driver) after every run.

Run directly (from the artifact root):
    python3 artifact_eval/tests/implemented_forced_exec_proc_cap.py
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import tempfile
import time


# --- knobs (small: fast, and can never fork-bomb) ---
LOW_CAP = 2
HIGH_CAP = 24
GLOBAL_LIMIT = 60      # high enough that the CAP, not this, binds the high run
LOOP_ITERS = 24
SLEEP_PER_ITER = 0.15  # keeps forked children overlapping in time
# Ceiling for the low-cap peak. The slot is reserved atomically (CAS) at the
# fork, so the check-then-fork overshoot is tiny (~+1 -> measured low-cap peak
# ~3 for cap 2). This ceiling sits a small margin above the cap yet far below
# the high-cap level (~25), so it fails a broken/ignored cap while never
# flaking on the tiny race.
LOW_CAP_CEILING = LOW_CAP + 6
# The high-cap peak must clear the low-cap peak by at least this much. Observed
# bands (low ~3, high ~25) leave a gap of ~22; 10 keeps generous, stable slack.
MIN_PEAK_GAP = 10
POLL_INTERVAL = 0.004
RLIMIT_HEADROOM = 400

# A self-contained forced-execution target. Kept separate from this driver so a
# forced child (merge OFF -> runs to program end) can only ever run this loop,
# never driver code. Each ``if`` is a POP_JUMP_IF_FALSE fork site; the sleep
# makes successive forks overlap.
TARGET_SRC = """\
import time, sys
for i in range({iters}):
    if i % 2 == 0:
        t = 1
    else:
        t = 2
    time.sleep({sleep})
sys.stdout.write("target-done\\n")
"""


def _rd_comm(entry: str) -> str:
    try:
        with open(f"/proc/{entry}/comm", "r") as fh:
            return fh.read().strip()
    except OSError:
        return ""  # process vanished or not ours


def _live_forced_count(me: int) -> int:
    """Count live forced interpreters: /proc/<pid>/comm == 'python', != self."""
    return sum(
        1
        for entry in os.listdir("/proc")
        if entry.isdigit() and int(entry) != me and _rd_comm(entry) == "python"
    )


def _kill_survivors(me: int) -> None:
    """SIGKILL leftover comm=python processes by PID, never ourselves.

    Looped: a freshly-killed parent can leave a child that only becomes
    reapable on a later pass.
    """
    for _ in range(6):
        killed_any = False
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == me or _rd_comm(entry) != "python":
                continue
            try:
                os.kill(pid, 9)
                killed_any = True
            except OSError:
                pass
        if not killed_any:
            break
        time.sleep(0.05)


def _child_env(max_procs: int) -> dict[str, str]:
    env = os.environ.copy()
    # Clean PyFEX slate so the caller's environment can't change the property
    # under test. In particular the DRIVER itself must NOT have
    # FORCE_EXEC_ENABLE -- only the target child gets it.
    for key in (
        "FORCE_EXEC_ENABLE", "FORCE_EXEC_MERGE_ENABLE",
        "FORCE_EXEC_GLOBAL_LIMIT", "FORCE_EXEC_LOCAL_LIMIT",
        "FORCE_EXEC_LOCATION_LIMIT", "FORCE_EXEC_MAX_PROCS",
        "FORCE_EXEC_MAX_PROCS_HARD_CAP",
    ):
        env.pop(key, None)
    env["FORCE_EXEC_ENABLE"] = "1"
    # Merge OFF: the concurrent cap is then the ONLY limiter on how many forced
    # interpreters are alive at once -- exactly what we measure.
    env["FORCE_EXEC_GLOBAL_LIMIT"] = str(GLOBAL_LIMIT)
    env["FORCE_EXEC_MAX_PROCS"] = str(max_procs)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def measure_peak(target_path: str, max_procs: int) -> int:
    """Run the target with the given cap; return peak live forced count.

    Output -> DEVNULL: forced children inherit the child's stdout fd, so a PIPE
    would block ``communicate()`` until every lingering grandchild closes it
    (merge is off). We only ever wait on the direct child via ``poll()``.
    """
    me = os.getpid()
    proc = subprocess.Popen(
        [sys.executable, target_path],
        env=_child_env(max_procs),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    peak = 0
    deadline = time.time() + 40  # generous; loop is ~LOOP_ITERS*SLEEP seconds
    try:
        while proc.poll() is None and time.time() < deadline:
            peak = max(peak, _live_forced_count(me))
            time.sleep(POLL_INTERVAL)
        peak = max(peak, _live_forced_count(me))  # final sample
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        _kill_survivors(me)
    return peak


def _install_nproc_backstop() -> None:
    """Cap RLIMIT_NPROC at (current task count + headroom) as a fork-bomb fuse.

    Counts current per-user tasks (threads) the way RLIMIT_NPROC does, then
    leaves generous headroom so legitimate forking is never starved while a
    runaway regression still hits a hard ceiling instead of the host.
    """
    me_uid = os.getuid()
    tasks = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            st = os.stat(f"/proc/{entry}")
        except OSError:
            continue
        if st.st_uid != me_uid:
            continue
        try:
            tasks += len(os.listdir(f"/proc/{entry}/task"))
        except OSError:
            tasks += 1
    soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
    target = tasks + RLIMIT_HEADROOM
    new_hard = hard if hard != resource.RLIM_INFINITY and hard < target else target
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (target, new_hard))
    except (ValueError, OSError):
        pass  # best-effort backstop; never block the test on it


def driver_main() -> int:
    _install_nproc_backstop()

    with tempfile.TemporaryDirectory() as tmp:
        target_path = os.path.join(tmp, "fe_proc_cap_target.py")
        with open(target_path, "w") as fh:
            fh.write(TARGET_SRC.format(iters=LOOP_ITERS, sleep=SLEEP_PER_ITER))

        low_peak = measure_peak(target_path, LOW_CAP)
        high_peak = measure_peak(target_path, HIGH_CAP)

    print(f"INFO: low-cap (MAX_PROCS={LOW_CAP}) peak live forced procs = {low_peak}")
    print(f"INFO: high-cap (MAX_PROCS={HIGH_CAP}) peak live forced procs = {high_peak}")

    ok = True

    # 1. The cap bounds concurrency: the low-cap peak stays just above the cap
    #    (atomic reservation -> ~+1 overshoot) and well under the ceiling, while
    #    an ignored cap would land the low run up at the high-cap level.
    if low_peak >= LOW_CAP_CEILING:
        print(
            f"FAIL[cap]: low-cap peak {low_peak} reached ceiling {LOW_CAP_CEILING} "
            f"(cap {LOW_CAP} not bounding concurrency)"
        )
        ok = False
    else:
        print(
            f"PASS[cap]: low-cap peak {low_peak} < ceiling {LOW_CAP_CEILING} "
            f"(cap {LOW_CAP} bounds concurrency)"
        )

    # 2. The cap -- not program size / global budget -- is the limiter. Raising
    #    the cap (same program, same GLOBAL_LIMIT, merge still off) lets
    #    materially more forced interpreters coexist. Require a wide, stable gap
    #    so a transient fluke can't pass.
    gap = high_peak - low_peak
    if gap < MIN_PEAK_GAP:
        print(
            f"FAIL[limiter]: gap {gap} (high {high_peak} - low {low_peak}) "
            f"< {MIN_PEAK_GAP}; cap may be ignored or program too small"
        )
        ok = False
    else:
        print(
            f"PASS[limiter]: high {high_peak} exceeds low {low_peak} by {gap} "
            f">= {MIN_PEAK_GAP} -> the cap is the limiter"
        )

    if not ok:
        return 1
    print("PASS: forced-execution concurrent live-process cap (FORCE_EXEC_MAX_PROCS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(driver_main())
