import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, wait_for


def trigger():
    x = 10
    branch_value = "parent"
    if x > 100:
        branch_value = "child"
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)
    return get_last_branch_id(), branch_value


assert_opcode(trigger, "POP_JUMP_IF_FALSE")

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
values = {state.get("locals", {}).get("branch_value") for state in states}
assert {"parent", "child"} <= values
print("PASS: POP_JUMP_IF_FALSE merge tracking recovered both parent and child snapshots")
