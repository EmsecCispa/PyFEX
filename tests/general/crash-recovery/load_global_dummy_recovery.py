import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    return missing_global_name


assert_opcode(trigger, "LOAD_GLOBAL")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: LOAD_GLOBAL crash recovery returned DummyObject for a missing global")
