import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_any_opcode, assert_dummy


class BrokenContext:
    pass


def trigger():
    with BrokenContext() as value:
        return value


assert_any_opcode(trigger, ("SETUP_WITH", "BEFORE_WITH"))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: context-manager setup crash recovery returned DummyObject for a broken context manager")
