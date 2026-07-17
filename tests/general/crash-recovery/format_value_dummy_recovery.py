import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode


class BrokenFormat:
    def __format__(self, spec):
        raise RuntimeError("format failed")


def trigger():
    value = BrokenFormat()
    return f"{value}"


assert_opcode(trigger, "FORMAT_VALUE")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert "DummyObject" in result
print("PASS: FORMAT_VALUE crash recovery returned a DummyObject placeholder string")
