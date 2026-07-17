import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    return 1 < "a"


assert_opcode(trigger, "COMPARE_OP")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: COMPARE_OP crash recovery returned DummyObject on invalid comparison")
