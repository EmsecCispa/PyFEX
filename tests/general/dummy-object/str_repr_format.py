"""Verify the single-line str()/repr() format of a DummyObject.

The str/repr output must:
  - never raise and never return NULL
  - include basename of the originating file and the line number
  - include a compact chain of the most recent operation names

This test also exercises the scope-aware call dispatch fix: calling the
`repr` / `str` builtins with a dummy argument must actually invoke
tp_repr / tp_str rather than getting hijacked into a propagated dummy.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import assert_dummy

os.environ["CRASH_RECOVERY_ENABLE"] = "1"


def make_dummy():
    return undefined_variable_xyz  # noqa: F821 - triggers crash recovery


d = make_dummy()
assert_dummy(d)

r = repr(d)
s = str(d)

assert isinstance(r, str), f"repr returned non-str: {type(r).__name__}"
assert isinstance(s, str), f"str returned non-str: {type(s).__name__}"

assert r.startswith("<DummyObject") and r.endswith(">"), f"unexpected repr form: {r!r}"
assert s.startswith("DummyObject(") and s.endswith(")"), f"unexpected str form: {s!r}"

# Location suffix: @<basename>:<lineno>. Tolerant on lineno (compiler may
# report the def line or the return line), strict on the basename.
assert "@" in r and "@" in s, f"missing location anchor: r={r!r} s={s!r}"
assert "str_repr_format.py:" in r, f"basename/line missing from repr: {r!r}"
assert "str_repr_format.py:" in s, f"basename/line missing from str: {s!r}"

# str output must contain the Nops chain
assert "ops:" in s, f"expected 'ops:' in str: {s!r}"

# Chain propagates after a binary op
chained = d + 1
chained_s = str(chained)
assert "add" in chained_s, f"expected 'add' in chained str: {chained_s!r}"

# No newlines: must stay one line
assert "\n" not in r, f"repr has newline: {r!r}"
assert "\n" not in s, f"str has newline: {s!r}"

print("PASS: dummy str/repr format includes basename, line, and op chain")
