import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy


code = compile("result = missing_name\n", str(Path(__file__)), "exec")
assert any(instr.opname == "LOAD_NAME" for instr in __import__("dis").get_instructions(code))

os.environ["CRASH_RECOVERY_ENABLE"] = "1"
namespace = {}
exec(code, namespace, namespace)
assert_dummy(namespace["result"])
print("PASS: LOAD_NAME crash recovery returned DummyObject for a missing name")
