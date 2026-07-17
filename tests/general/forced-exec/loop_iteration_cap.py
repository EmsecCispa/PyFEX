"""Verify that the loop-iteration cap force-exits loops after
FORCE_EXEC_LOOP_ITER_LIMIT iterations.

The cap is gated under FORCE_EXEC_ENABLE=1 and applies at FOR_ITER and at
backward jumps (POP_JUMP_IF_FALSE / POP_JUMP_IF_TRUE / JUMP_ABSOLUTE
targeting an offset <= the current one).

Three scenarios are covered:
  - a bounded `for` loop hitting the cap before completion
  - a `while True` that would otherwise spin forever
  - recursion where each frame's loop counter is independent
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Configure a small cap so the test runs quickly.
os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_LOOP_ITER_LIMIT"] = "25"
# Disable FE forking so the only behaviour we observe is the cap itself.
os.environ["FORCE_EXEC_GLOBAL_LIMIT"] = "0"


def bounded_for():
    count = 0
    for _ in range(1000):
        count += 1
    return count


def while_true_loop():
    count = [0]
    try:
        while True:
            count[0] += 1
    except RuntimeError as exc:
        return count[0], str(exc)
    return count[0], None  # unreachable


def per_frame_independence():
    # Calling bounded_for() twice in a row must cap each call independently.
    return bounded_for(), bounded_for()


cap = int(os.environ["FORCE_EXEC_LOOP_ITER_LIMIT"])

# 1. Bounded for-loop: should terminate at or near the cap, not at 1000.
n = bounded_for()
assert 1 < n <= cap, f"bounded_for() did not hit the cap: returned {n}"

# 2. while True: the cap raises a synthetic RuntimeError that the loop body
# catches, then returns the count. The count must be <= cap.
n, msg = while_true_loop()
assert 1 < n <= cap, f"while_true_loop count exceeded cap: {n}"
assert "loop-iteration cap" in (msg or ""), f"unexpected exception msg: {msg!r}"

# 3. Two successive calls: each frame has its own counter.
a, b = per_frame_independence()
assert 1 < a <= cap and 1 < b <= cap, (
    f"successive calls should each hit the cap independently: a={a} b={b}"
)

print("PASS: loop iteration cap terminates loops at the configured limit")
