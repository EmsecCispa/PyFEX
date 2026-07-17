import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path


def define_functions():
    def dormant():
        return "dormant"

    def active():
        return "active"

    active()
    return dormant


assert_opcode(define_functions, "MAKE_FUNCTION")

log_path = fresh_path("dormant_function_analysis")
os.environ["DORMANT_FUNC_LOG_FILE"] = str(log_path)
_dormant = define_functions()

lines = Path(log_path).read_text(encoding="utf-8").splitlines()
assert any("DEFINED" in line and "dormant" in line for line in lines)
assert any("DEFINED" in line and "active" in line for line in lines)
assert any(line.startswith("CALLED ") and " active " in line for line in lines)
assert not any(line.startswith("CALLED ") and " dormant " in line for line in lines)
print("PASS: MAKE_FUNCTION DFA logging recorded defined-vs-called functions")
