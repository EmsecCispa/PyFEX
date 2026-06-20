"""Verify GET_AITER / GET_ANEXT forked execution substitutes a
synthetic async iterator (one DummyObject then StopAsyncIteration) in
the child. Parent drives the real async iterator.

Avoids asyncio's event loop by driving a coroutine manually with
send(None).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for


marker = fresh_path("get_aiter_fe", ".log")


class _ImmediateAsyncIter:
    """Async iterator that yields a single concrete value without
    suspending."""
    def __init__(self, value):
        self._v = value
        self._done = False

    def __aiter__(self):
        return self

    def __anext__(self):
        if self._done:
            raise StopAsyncIteration
        self._done = True
        return _IAwait(self._v)


class _IAwait:
    def __init__(self, v):
        self._v = v

    def __await__(self):
        if False:
            yield
        return self._v


async def sample():
    async for item in _ImmediateAsyncIter("real"):
        tag = "real" if item == "real" else (
            "dummy" if type(item).__name__ == "DummyObject" else f"other:{item!r}"
        )
        with open(marker, "a") as f:
            f.write(tag + "\n")


assert_opcode(sample, "GET_AITER")
assert_opcode(sample, "GET_ANEXT")

os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_GLOBAL_LIMIT"] = "50"
os.environ["FORCE_EXEC_LOCATION_LIMIT"] = "1"
# This test asserts a SPECIFIC fork happens (GET_AITER/GET_ANEXT). The
# concurrent live-process cap (FORCE_EXEC_MAX_PROCS, default 8) is a
# memory-safety backstop that can starve a late fork when earlier forks fill
# the slots (no merge here). Set it above FORCE_EXEC_GLOBAL_LIMIT so the
# total-fork limit binds first and the async fork is never starved.
os.environ["FORCE_EXEC_MAX_PROCS"] = "64"
# Coroutine/generator frames are off by default; opt in for this test.
os.environ["PYFEX_ENABLE_IN_COROUTINES"] = "1"

root_pid = os.getpid()
coro = sample()
try:
    coro.send(None)
except StopIteration:
    pass
except BaseException:
    pass
if os.getpid() != root_pid:
    sys.exit(0)

assert wait_for(
    lambda: {"real", "dummy"} <= set(read_markers(marker)),
    timeout=3.0,
), f"expected both 'real' and 'dummy' markers; saw {read_markers(marker)!r}"

print("PASS: GET_AITER / GET_ANEXT fork delivered both real and dummy items")
