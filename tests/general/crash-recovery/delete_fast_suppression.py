import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode


def trigger():
    if False:
        missing_local = 1
    del missing_local
    return "continued"


assert_opcode(trigger, "DELETE_FAST")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert result == "continued"
print("PASS: DELETE_FAST crash recovery suppressed the unbound delete and continued")
