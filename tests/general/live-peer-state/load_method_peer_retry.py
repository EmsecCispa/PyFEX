import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode


def trigger():
    x = 10
    if x > 100:
        peer_obj = "from-child-method"
        time.sleep(0.1)
    else:
        time.sleep(0.2)
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    return peer_obj.upper()


assert_any_opcode(trigger, ("LOAD_METHOD", "LOAD_ATTR"))

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_ENABLE"] = "1"
os.environ["CRASH_RECOVERY_PEER_QUERY"] = "1"
root_pid = os.getpid()
result = trigger()

if os.getpid() != root_pid:
    sys.exit(0)

assert result == "FROM-CHILD-METHOD"
print("PASS: method-style peer retry succeeded with a serializable live peer value")
