import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode, assert_dummy


def trigger():
    return 1 / 0


assert_any_opcode(trigger, ("BINARY_TRUE_DIVIDE", "BINARY_OP"))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: divide-by-zero crash recovery returned DummyObject on binary division")
