import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import append_marker, assert_opcode, fresh_path, read_markers


def trigger(log_path):
    flag = True
    if flag:
        append_marker(log_path, "true-branch")
    else:
        append_marker(log_path, "false-branch")


assert_opcode(trigger, "POP_JUMP_IF_FALSE")

os.environ.pop("FORCE_EXEC_ENABLE", None)
log_path = fresh_path("disabled_by_default")
trigger(log_path)
markers = read_markers(log_path)

assert markers == ["true-branch"], markers
print("PASS: forced execution stays disabled by default")
