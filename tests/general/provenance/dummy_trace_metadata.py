import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    if False:
        missing_local = 1
    value = missing_local
    return value.payload


assert_opcode(trigger, "LOAD_ATTR")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
dummy = assert_dummy(result)
assert dummy.location
assert dummy.trace
assert dummy.operations_history
assert "payload" in str(dummy.operations_history) or "GETATTR" in str(dummy.operations_history)
print("PASS: DummyObject provenance keeps location and operation history")
