"""Branch-merge point calculation stops scanning at a depth-0 branch
terminator (RETURN_VALUE / RAISE_VARARGS).

When the forced branch's true path returns early, there is no skip-jump
and the else path (plus the code after) IS the merge point. The scan
should not continue past the terminator looking for later jumps.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, wait_for


def inner():
    x = 10
    branch_value = "parent"
    if x > 100:
        # Early return in the true branch -- no JUMP_FORWARD to skip an else.
        return "returned-early"
    branch_value = "child"
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)
    return branch_value


def trigger():
    result = inner()
    return get_last_branch_id(), result


assert_opcode(inner, "POP_JUMP_IF_FALSE")
assert_opcode(inner, "RETURN_VALUE")

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "1"
os.environ["FORCE_EXEC_SHARED_OBJECT_ENABLE"] = "1"
os.environ["FORCE_EXEC_RETAIN_SHARED_STATE"] = "1"

root_pid = os.getpid()
branch_id, _ = trigger()

if os.getpid() != root_pid:
    sys.exit(0)

assert branch_id >= 0
assert wait_for(lambda: len(recover_branch_states(branch_id)) >= 2, timeout=2.0)
states = recover_branch_states(branch_id)

# Parent takes the natural (false) path and arrives at the merge point.
# Child takes the forced (true) path and returns from inner() before
# reaching the merge point, so its snapshot is taken in the caller scope.
# What we verify:
#   1. At least one parent-side snapshot is from inside inner()
#   2. At least one child snapshot exists (is_child=True)
parent_in_inner = any(
    not s.get("is_child") and s.get("scope", "").endswith(":inner")
    for s in states
)
any_child = any(s.get("is_child") for s in states)
assert parent_in_inner, f"expected parent snapshot inside inner: {states}"
assert any_child, f"expected a child snapshot: {states}"
print("PASS: merge scan stops at depth-0 RETURN_VALUE in the forked branch")
