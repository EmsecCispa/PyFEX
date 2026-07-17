import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_any_opcode, assert_markers, fresh_path


def rhs(log_path):
    append_marker(log_path, "rhs-evaluated")
    return "rhs"


def trigger(log_path):
    left = True
    result = left or rhs(log_path)
    append_marker(log_path, f"result={result!r}")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


assert_any_opcode(trigger, ("JUMP_IF_TRUE_OR_POP", "POP_JUMP_IF_TRUE"))

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("jump_if_true_or_pop_force_exec")
trigger(log_path)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"rhs-evaluated", "result=True", "result='rhs'"})
print("PASS: true short-circuit forced execution explored both outcomes")
