import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


class Empty:
    pass


def trigger():
    obj = Empty()
    return obj.missing_attr


assert_opcode(trigger, "LOAD_ATTR")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
dummy = assert_dummy(result)
assert dummy.error_reason
assert dummy.location
print("PASS: LOAD_ATTR crash recovery returned DummyObject on missing attribute access")
