"""Verify WITH_EXCEPT_START forked execution forces the __exit__ return
truthy so the "exception suppressed" path gets explored.

A context manager whose __exit__ returns False lets the exception
propagate. With the WITH_EXCEPT_START fork, a forked child overrides
the __exit__ return with Py_True, so the surrounding `with` statement
behaves as if the exception was suppressed.

This test uses the SETUP_WITH fork from 1.1 to drive an exception into
__exit__, then relies on the WITH_EXCEPT_START fork from 1.2 to observe
both suppression outcomes.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "0"

marker = fresh_path("with_except_fe", ".log")


class NonSuppressingCM:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Always return a concrete falsy value so real suppression is
        # never requested by the CM itself.
        return False


def trigger():
    suppressed = None
    try:
        with NonSuppressingCM():
            raise ValueError("body-raise")
    except ValueError:
        suppressed = False
    else:
        suppressed = True
    # Record whichever branch we ended up on.
    tag = "suppressed" if suppressed else "propagated"
    with open(marker, "a") as f:
        f.write(tag + "\n")


assert_opcode(trigger, "WITH_EXCEPT_START")

root_pid = os.getpid()
try:
    trigger()
except BaseException:
    # A grandchild of the SETUP_WITH fork may propagate the synthetic
    # exception out; swallow it so the test process can still finish.
    pass
if os.getpid() != root_pid:
    sys.exit(0)

# We expect the "propagated" outcome (from __exit__ returning False) AND
# the "suppressed" outcome (from the WITH_EXCEPT_START fork forcing True).
assert wait_for(
    lambda: {"suppressed", "propagated"} <= set(read_markers(marker)),
    timeout=2.0,
), f"missing markers; saw {read_markers(marker)!r}"

print("PASS: WITH_EXCEPT_START fork exposed both suppression outcomes")
