import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    left, right = 1
    return left, right


assert_opcode(trigger, "UNPACK_SEQUENCE")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
left, right = trigger()
assert_dummy(left)
assert_dummy(right)
print("PASS: UNPACK_SEQUENCE crash recovery pushed DummyObjects for failed unpacking")
