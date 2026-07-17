import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode


class Holder:
    def __init__(self, value):
        self.value = value


def trigger():
    x = 10
    if x > 100:
        peer_obj = Holder("from-child")
        time.sleep(0.1)
    else:
        time.sleep(0.2)
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    return peer_obj.value


assert_opcode(trigger, "LOAD_ATTR")

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_PEER_QUERY"] = "1"
root_pid = os.getpid()
result = trigger()

if os.getpid() != root_pid:
    sys.exit(0)

assert result == "from-child"
print("PASS: LOAD_ATTR retried successfully with a live peer object")
