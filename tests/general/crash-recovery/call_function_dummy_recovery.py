import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy


def trigger():
    not_callable = 1
    return not_callable()


opcodes = [instr.opname for instr in __import__("dis").get_instructions(trigger)]
assert "CALL_FUNCTION" in opcodes or "CALL" in opcodes

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: CALL_FUNCTION crash recovery returned DummyObject on non-callable invocation")
