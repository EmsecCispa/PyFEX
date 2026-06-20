"""Verify FOR_ITER item-injection fork: when an iterator naturally ends,
a forked child pushes a synthetic DummyObject and continues iterating,
so PyFEX can explore loop-body code that would otherwise stay dormant.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for

marker = fresh_path("for_iter_inject", ".log")


def trigger():
    # An empty iterable: natural iteration yields no items. Only the
    # item-injection fork can make the body run.
    for x in []:
        tag = "body:" + type(x).__name__
        with open(marker, "a") as f:
            f.write(tag + "\n")
    with open(marker, "a") as f:
        f.write("end\n")


assert_opcode(trigger, "FOR_ITER")

# Enable FE only after the opcode introspection above so its helper
# calls do not consume the fork budget before trigger() runs.
os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "0"

root_pid = os.getpid()
trigger()
if os.getpid() != root_pid:
    sys.exit(0)

# The natural-exit path writes "end"; the injection-fork child writes a
# "body:..." line with DummyObject as the item type.
assert wait_for(
    lambda: "end" in read_markers(marker)
    and any(m.startswith("body:DummyObject") for m in read_markers(marker)),
    timeout=2.0,
), f"missing markers; saw {read_markers(marker)!r}"

print("PASS: FOR_ITER item-injection ran loop body with a synthetic DummyObject")
