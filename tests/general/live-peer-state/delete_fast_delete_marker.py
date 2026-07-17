import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    x = 10
    if x > 100:
        peer_value = 1337
        del peer_value
        time.sleep(0.1)
    else:
        time.sleep(0.2)
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    return peer_value


assert_opcode(trigger, "DELETE_FAST")

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_PEER_QUERY"] = "1"
root_pid = os.getpid()
result = trigger()

if os.getpid() != root_pid:
    sys.exit(0)

assert_dummy(result)
print("PASS: DELETE_FAST live delete marker prevented stale peer-value recovery")
