import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_markers, assert_opcode, fresh_path


def trigger(log_path):
    flag = True
    if flag:
        append_marker(log_path, "true-branch")
    else:
        append_marker(log_path, "false-branch")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


assert_opcode(trigger, "POP_JUMP_IF_FALSE")

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("pop_jump_if_false_force_exec")
trigger(log_path)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"true-branch", "false-branch"})
print("PASS: POP_JUMP_IF_FALSE forced execution explored both branches")
