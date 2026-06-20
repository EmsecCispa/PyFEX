import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode, assert_dummy


class Empty:
    pass


def trigger():
    obj = Empty()
    return obj.missing_method()


assert_any_opcode(trigger, ("LOAD_METHOD", "LOAD_ATTR"))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
dummy = assert_dummy(result)
assert dummy.error_reason
assert dummy.location
print("PASS: method lookup crash recovery returned DummyObject on missing method access")
