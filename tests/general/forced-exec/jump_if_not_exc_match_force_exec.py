import os
import sys
import time
import dis
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_any_opcode, assert_markers, assert_opcode, fresh_path


def trigger(log_path):
    outcome = None
    try:
        raise ValueError("boom")
    except ValueError:
        outcome = "value-error-handler"
    except TypeError:
        outcome = "type-error-handler"
    append_marker(log_path, outcome)
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)

# 3.7 and 3.10 has different opcode usage here.
if "JUMP_IF_NOT_EXC_MATCH" in dis.opmap:
    assert_opcode(trigger, "JUMP_IF_NOT_EXC_MATCH")
elif sys.version_info >= (3, 12):
    assert_any_opcode(trigger, ("CHECK_EXC_MATCH", "POP_JUMP_IF_FALSE"))
else:
    assert_opcode(trigger, "POP_JUMP_IF_FALSE")

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("jump_if_not_exc_match_force_exec")
trigger(log_path)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"value-error-handler", "type-error-handler"})
if "JUMP_IF_NOT_EXC_MATCH" in dis.opmap:
    print("PASS: JUMP_IF_NOT_EXC_MATCH forced execution explored both except-match outcomes")
elif sys.version_info >= (3, 12):
    print("PASS: 3.12 exception-match forcing explored both except-match outcomes")
else:
    print("PASS: 3.7-style exception-match forcing explored both except-match outcomes")
