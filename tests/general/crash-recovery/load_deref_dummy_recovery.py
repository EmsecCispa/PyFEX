import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def outer():
    if False:
        closure_value = 1

    def inner():
        return closure_value

    assert_opcode(inner, "LOAD_DEREF")
    return inner()


os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = outer()
assert_dummy(result)
print("PASS: LOAD_DEREF crash recovery returned DummyObject for an unbound closure cell")
