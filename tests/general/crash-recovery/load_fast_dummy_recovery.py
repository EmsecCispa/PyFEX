import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode, assert_dummy


def trigger():
    if False:
        missing_local = 1
    return missing_local


assert_any_opcode(trigger, ("LOAD_FAST", "LOAD_FAST_CHECK"))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
dummy = assert_dummy(result)
assert dummy.error_reason
assert dummy.location
print("PASS: LOAD_FAST-style crash recovery returned DummyObject for an unbound local")
