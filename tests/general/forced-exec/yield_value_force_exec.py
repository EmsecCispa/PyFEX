"""Verify YIELD_VALUE forked execution substitutes a DummyObject for
the yielded value in the child. Parent receives the real value; the
forked child receives a DummyObject so the consumer's downstream code
sees a counter-factual item.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for


marker = fresh_path("yield_value_fe", ".log")


def gen():
    yield "real"


def consume():
    for item in gen():
        tag = "real" if item == "real" else ("dummy" if type(item).__name__ == "DummyObject" else f"other:{item!r}")
        with open(marker, "a") as f:
            f.write(tag + "\n")


assert_opcode(gen, "YIELD_VALUE")

os.environ["FORCE_EXEC_ENABLE"] = "1"
# Coroutine/generator frames are off by default; opt in for this test.
os.environ["PYFEX_ENABLE_IN_COROUTINES"] = "1"

root_pid = os.getpid()
consume()
if os.getpid() != root_pid:
    sys.exit(0)

assert wait_for(
    lambda: {"real", "dummy"} <= set(read_markers(marker)),
    timeout=2.0,
), f"expected both 'real' and 'dummy' markers; saw {read_markers(marker)!r}"

print("PASS: YIELD_VALUE fork delivered both real and dummy items to consumer")
