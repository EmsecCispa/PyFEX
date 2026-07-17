"""Verify the whitelist of builtins that always execute with dummy args.

PyFEX usually propagates dummies through function calls when any argument
is a dummy (call_function / do_call_core in ceval.c). The whitelist
exempts the observability builtins -- print, repr, str, type, isinstance,
id, len, hash -- so analysts can inspect a dummy.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy

os.environ["CRASH_RECOVERY_ENABLE"] = "1"


def make_dummy():
    return undefined_variable_xyz  # noqa: F821


d = make_dummy()
assert_dummy(d)

# Each whitelisted builtin must dispatch to the real builtin. For builtins
# backed by DummyObject's own protocols (tp_repr, tp_str, tp_hash via
# identity, sq_length / mp_length), that yields a concrete value. Builtins
# whose internal protocol fails on a dummy (e.g. hash if tp_hash is absent)
# would end up crash-recovered back into a dummy -- still not hijacked.
assert type(d).__name__ == "DummyObject"
assert isinstance(d, object) is True
assert isinstance(id(d), int)
assert isinstance(len(d), int)
assert isinstance(repr(d), str) and repr(d).startswith("<DummyObject")
assert isinstance(str(d), str) and str(d).startswith("DummyObject(")

# print(dummy) must emit output (not get silently hijacked).
captured = []
orig = sys.stdout.write
def spy(text):
    captured.append(text)
    return orig(text)
sys.stdout.write = spy
try:
    print("DUMMY:", d)
finally:
    sys.stdout.write = orig

joined = "".join(captured)
assert "DUMMY:" in joined, f"print prefix missing: {joined!r}"
assert "DummyObject" in joined, f"dummy str missing from print output: {joined!r}"

# Non-whitelisted builtin called with a dummy arg should still propagate
# (i.e. return a dummy) per the scope-aware hijack policy. sorted() is an
# out-of-scope C builtin that isn't in the whitelist.
result = sorted([d])
assert_dummy(result)

print("PASS: whitelisted builtins dispatch normally on dummies; others propagate")
