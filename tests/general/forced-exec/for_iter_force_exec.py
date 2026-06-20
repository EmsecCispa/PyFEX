import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_markers, assert_opcode, fresh_path


def trigger(log_path):
    seen_body = False
    for _value in [1]:
        seen_body = True
    append_marker(log_path, f"seen_body={seen_body}")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


assert_opcode(trigger, "FOR_ITER")

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("for_iter_force_exec")
trigger(log_path)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"seen_body=True", "seen_body=False"})
print("PASS: FOR_ITER forced execution explored loop-body and loop-exit paths")
