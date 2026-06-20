import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy, assert_opcode


def trigger():
    import definitely_missing_pyfex_module as missing_module
    return missing_module


assert_opcode(trigger, "IMPORT_NAME")

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
result = trigger()
assert_dummy(result)
print("PASS: IMPORT_NAME crash recovery returned DummyObject for a missing module")
