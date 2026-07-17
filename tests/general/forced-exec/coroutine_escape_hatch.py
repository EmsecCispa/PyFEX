"""Verify PyFEX is disabled by default inside generator / coroutine /
async-generator frames, and that PYFEX_ENABLE_IN_COROUTINES=1 opts
back in.

Probes a generator that writes a "before" marker, then accesses an
undefined name, then writes an "after" marker. With CR disabled inside
the generator (the default), the undefined-name access unwinds the
generator before "after" is written. With the opt-in enabled, CR
substitutes a DummyObject for the undefined name and the yield fires,
so execution reaches "after".

Note: CR in the *caller's* frame may still swallow the outbound
NameError; we only observe side effects inside the generator body
itself.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import fresh_path, read_markers


marker_default = fresh_path("coro_default", ".log")
marker_optin = fresh_path("coro_optin", ".log")


def make_gen(marker_path):
    def gen():
        with open(marker_path, "a") as f:
            f.write("before\n"); f.flush()
        _ = undefined_name_in_generator  # noqa: F821 - NameError at runtime
        with open(marker_path, "a") as f:
            f.write("after\n"); f.flush()
        yield "done"
    return gen


os.environ["CRASH_RECOVERY_ENABLE"] = "1"

# --- Default: CR is OFF inside the generator frame. Undefined name
#     unwinds the generator before "after" is written.
os.environ.pop("PYFEX_ENABLE_IN_COROUTINES", None)
try:
    list(make_gen(marker_default)())
except BaseException:
    pass
default = read_markers(marker_default)
assert "before" in default, f"default: generator never started: {default!r}"
assert "after" not in default, (
    f"default: PyFEX should be off inside the generator, but 'after' was written: {default!r}"
)

# --- Opt-in: PYFEX_ENABLE_IN_COROUTINES=1 re-enables CR inside the
#     generator; the undefined name is substituted with a DummyObject
#     and execution reaches "after".
os.environ["PYFEX_ENABLE_IN_COROUTINES"] = "1"
try:
    list(make_gen(marker_optin)())
except BaseException:
    pass
optin = read_markers(marker_optin)
assert "before" in optin, f"opt-in: generator never started: {optin!r}"
assert "after" in optin, (
    f"opt-in: CR should substitute and resume past the undefined name: {optin!r}"
)

print("PASS: coroutine frames are off by default; PYFEX_ENABLE_IN_COROUTINES opts in")
