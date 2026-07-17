import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode, assert_dummy


def trigger():
    if False:
        missing_local = 1
    return missing_local + 5


assert_any_opcode(trigger, ("BINARY_ADD", "BINARY_OP"))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
dummy = assert_dummy(result)
history = str(dummy.operations_history)
assert "add" in history
print("PASS: binary add propagation preserved DummyObject state through arithmetic")
