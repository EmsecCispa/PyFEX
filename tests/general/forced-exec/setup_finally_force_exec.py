import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_any_opcode, assert_markers, assert_opcode, fresh_path


def trigger(log_path):
    try:
        append_marker(log_path, "try-path")
    except Exception:
        append_marker(log_path, "except-path")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


try:
    assert_opcode(trigger, "SETUP_FINALLY")
    opcode_name = "SETUP_FINALLY"
except AssertionError:
    try:
        assert_opcode(trigger, "SETUP_EXCEPT")
        opcode_name = "SETUP_EXCEPT"
    except AssertionError:
        assert_any_opcode(trigger, ("CHECK_EXC_MATCH", "PUSH_EXC_INFO"))
        opcode_name = "EXCEPTION_TABLE"

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("setup_finally_force_exec")
trigger(log_path)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"try-path", "except-path"})
if opcode_name == "SETUP_FINALLY":
    print("PASS: SETUP_FINALLY forced execution reached both try and forced-except paths")
elif opcode_name == "SETUP_EXCEPT":
    print("PASS: SETUP_EXCEPT/FINALLY forcing reached both try and forced-except paths")
else:
    print("PASS: 3.12 exception-table forcing reached both try and forced-except paths")
