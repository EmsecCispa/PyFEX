import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import wait_for


def in_scope():
    x = 10
    if x > 100:
        marker = "child"
    else:
        marker = "parent"
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.05)
    return marker


def out_of_scope():
    x = 10
    if x > 100:
        marker = "child"
    else:
        marker = "parent"
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.05)
    return marker


os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_MERGE_ENABLE"] = "1"
os.environ["FORCE_EXEC_SHARED_OBJECT_ENABLE"] = "1"
os.environ["FORCE_EXEC_RETAIN_SHARED_STATE"] = "1"
os.environ["FORCE_EXEC_MERGE_SCOPE_FUNC"] = "in_scope"

root_pid = os.getpid()
in_scope()

if os.getpid() != root_pid:
    sys.exit(0)

branch_id = get_last_branch_id()
assert branch_id >= 0
assert wait_for(lambda: len(recover_branch_states(branch_id)) >= 2, timeout=2.0)

out_of_scope()
assert get_last_branch_id() == branch_id
print("PASS: merge scope control only tracked the configured function")
