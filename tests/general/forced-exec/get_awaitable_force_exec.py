"""Verify GET_AWAITABLE forked execution substitutes a synthetic
awaitable that resolves to a DummyObject in the child. Parent drives
the real awaitable.

Avoids asyncio's event loop by driving the coroutine manually with
send(None), so the fork does not interfere with an epoll fd.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_opcode, fresh_path, read_markers, wait_for


marker = fresh_path("get_awaitable_fe", ".log")


class _ImmediateAwaitable:
    """Awaitable that resolves synchronously to a concrete value without
    suspending. Mirrors the synthetic shape PyFEX injects."""
    def __init__(self, value):
        self._value = value
    def __await__(self):
        if False:
            yield
        return self._value


async def sample():
    x = await _ImmediateAwaitable("real")
    tag = "real" if x == "real" else (
        "dummy" if type(x).__name__ == "DummyObject" else f"other:{x!r}"
    )
    with open(marker, "a") as f:
        f.write(tag + "\n")


assert_opcode(sample, "GET_AWAITABLE")

# Enable FE only after the opcode introspection above; each ShouldFork
# that returns 1 (including for call logging) consumes the global fork
# budget, so we delay enabling FE until just before the driven call.
os.environ["FORCE_EXEC_ENABLE"] = "1"
os.environ["FORCE_EXEC_GLOBAL_LIMIT"] = "50"
os.environ["FORCE_EXEC_LOCATION_LIMIT"] = "1"
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
    timeout=2.0,
), f"expected both 'real' and 'dummy' markers; saw {read_markers(marker)!r}"

print("PASS: GET_AWAITABLE fork delivered both real and dummy results")
