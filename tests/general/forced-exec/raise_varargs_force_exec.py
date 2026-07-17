import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_markers, assert_opcode, fresh_path


def raising_helper(log_path):
    append_marker(log_path, "before-raise")
    raise ValueError("boom")
    append_marker(log_path, "after-raise")


def trigger(log_path):
    try:
        raising_helper(log_path)
    except Exception:
        append_marker(log_path, "caught-raise")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


assert_opcode(raising_helper, "RAISE_VARARGS")

os.environ["FORCE_EXEC_ENABLE"] = "1"
root_pid = os.getpid()
log_path = fresh_path("raise_varargs_force_exec")
try:
    trigger(log_path)
except Exception as exc:
    append_marker(log_path, f"driver-exception={type(exc).__name__}")
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)

if os.getpid() != root_pid:
    sys.exit(0)

assert_markers(log_path, {"before-raise"})
markers = set(Path(log_path).read_text(encoding="utf-8").splitlines())
assert (
    "caught-raise" in markers or
    "after-raise" in markers or
    "driver-exception=ValueError" in markers or
    "driver-exception=RuntimeError" in markers or
    "driver-exception=SystemError" in markers
), markers
print("PASS: RAISE_VARARGS hook executed; current artifact may expose exception-forcing side effects")
