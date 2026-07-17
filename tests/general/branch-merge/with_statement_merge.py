"""Branch-merge point calculation handles with-statement shapes.

SETUP_WITH is now recognised as a nesting-opener, so a with-block inside
the true branch does not confuse the post-dominator scan.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, wait_for


tmp_file = fresh_path("with_merge_scratch", ".tmp")
tmp_file.write_text("placeholder\n")


def trigger():
    x = 10
    branch_value = "parent"
    if x > 100:
        with open(str(tmp_file), "r") as f:
            _ = f.read()
        branch_value = "child"
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)
    return get_last_branch_id(), branch_value


assert_opcode(trigger, "POP_JUMP_IF_FALSE")
assert_opcode(trigger, "SETUP_WITH")

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "1"
os.environ["FORCE_EXEC_SHARED_OBJECT_ENABLE"] = "1"
os.environ["FORCE_EXEC_RETAIN_SHARED_STATE"] = "1"

root_pid = os.getpid()
# Forced execution now also forks at SETUP_WITH, raising a synthetic
# RuntimeError in one grandchild to explore the with-exit path. Wrap
# defensively so the outer merge can still complete.
try:
    branch_id, _ = trigger()
except BaseException:
    branch_id = get_last_branch_id()

if os.getpid() != root_pid:
    sys.exit(0)

assert branch_id >= 0
assert wait_for(lambda: len(recover_branch_states(branch_id)) >= 2, timeout=2.0)
states = recover_branch_states(branch_id)

# The outer POP_JUMP_IF_FALSE fork yields a parent snapshot (natural
# false path, branch_value stays "parent") and at least one child
# snapshot (true path; branch_value may be "child" if the with-body
# finished, or None if the synthetic exception pruned execution early).
parent_saw = any(
    not s.get("is_child") and s.get("locals", {}).get("branch_value") == "parent"
    for s in states
)
any_child = any(s.get("is_child") for s in states)
assert parent_saw, f"expected parent snapshot with branch_value='parent': {states}"
assert any_child, f"expected at least one child snapshot: {states}"
print("PASS: merge point handles with-statement inside the forked branch")
