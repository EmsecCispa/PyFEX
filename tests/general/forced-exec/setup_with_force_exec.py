"""Verify SETUP_WITH forked execution injects a synthetic exception to
explore the context manager's __exit__ path.

Without the fork, a `with` body that completes normally never reaches
the __exit__(exc_type, ...) branch with a non-None exception type. The
fork creates a child process that jumps straight to the handler with a
synthetic RuntimeError, so PyFEX sees what happens when the with-body
raises.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for

os.environ["FORCE_EXEC_ENABLE"] = "1"
# Disable merging so we only observe the fork's direct side effect.
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "0"

marker = fresh_path("setup_with_fe", ".log")


class TrackingCM:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Record whether an exception arrived. The parent process takes
        # the normal path (exc_type is None); the forked child takes the
        # synthetic-exception path (exc_type is RuntimeError).
        tag = "none" if exc_type is None else exc_type.__name__
        with open(marker, "a") as f:
            f.write(tag + "\n")
        # Return True so we suppress the synthetic exception in the
        # child; the parent's None passes through unchanged.
        return True


def trigger():
    with TrackingCM():
        return "body-complete"


assert_opcode(trigger, "SETUP_WITH")

root_pid = os.getpid()
trigger()
if os.getpid() != root_pid:
    sys.exit(0)

# Wait for both parent and child to write their markers.
assert wait_for(
    lambda: {"none", "RuntimeError"} <= set(read_markers(marker)),
    timeout=2.0,
), f"missing markers; saw {read_markers(marker)!r}"

print("PASS: SETUP_WITH fork exercised both normal and exception __exit__ paths")
