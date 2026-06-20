import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    value = 1
    return value[0]


assert_opcode(trigger, "BINARY_SUBSCR")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: BINARY_SUBSCR crash recovery returned DummyObject on invalid subscription")
