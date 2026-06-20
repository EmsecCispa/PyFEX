import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


class BrokenIterator:
    def __iter__(self):
        return self

    def __next__(self):
        raise RuntimeError("broken next")


def trigger():
    for item in BrokenIterator():
        return item
    return None


assert_opcode(trigger, "FOR_ITER")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: FOR_ITER crash recovery returned a DummyObject on iterator failure")
