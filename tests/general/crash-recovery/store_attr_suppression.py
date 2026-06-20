import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode


def trigger():
    obj = 1
    obj.some_attr = 2
    return "continued"


assert_opcode(trigger, "STORE_ATTR")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert result == "continued"
print("PASS: STORE_ATTR crash recovery suppressed the store failure and continued")
