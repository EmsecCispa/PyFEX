"""Verify PYFEX_SCOPE_DIR extends the target scope beyond sys.argv[0].

By default PyFEX instruments only the script passed on the command line.
Setting PYFEX_SCOPE_DIR to a directory broadens the scope: any source
file under that directory becomes in-scope for crash recovery, forced
execution, dormant function analysis, and the scope-aware call dispatch.

This test runs two child processes via os.system (subprocess is not
available in this minimal PyFEX build). The first does not set
PYFEX_SCOPE_DIR and verifies that a call into a sibling module with a
dummy argument is propagated (hijacked). The second sets
PYFEX_SCOPE_DIR and verifies the call actually executes.
"""
import os
import shlex
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import TMP_ROOT, fresh_path

pkg_dir = TMP_ROOT / f"scope_pkg_{os.getpid()}"
pkg_dir.mkdir(parents=True, exist_ok=True)

(pkg_dir / "helper.py").write_text(textwrap.dedent("""
    def observe(x, marker):
        with open(marker, 'a') as f:
            f.write('observed type=' + type(x).__name__ + '\\n')
        return 'real-return'
"""))

MAIN_TEMPLATE = textwrap.dedent("""
    import sys
    sys.path.insert(0, __PKG_DIR__)
    import helper

    def make_dummy():
        return undefined_variable_xyz

    d = make_dummy()
    result = helper.observe(d, __MARKER__)
    with open(__MARKER__, 'a') as f:
        f.write('result_type=' + type(result).__name__ + '\\n')
""")


INTERP = str(Path(__file__).resolve().parents[3] / "PyFEX-core" / "python")


def run(env_extras):
    marker = fresh_path("scope_dir", ".marker")
    script = pkg_dir / f"run_{marker.stem}.py"
    script.write_text(
        MAIN_TEMPLATE
        .replace("__PKG_DIR__", repr(str(pkg_dir)))
        .replace("__MARKER__", repr(str(marker)))
    )
    env_prefix = " ".join(
        f"{k}={shlex.quote(v)}" for k, v in {"CRASH_RECOVERY_ENABLE": "1", **env_extras}.items()
    )
    os.system(f"{env_prefix} {shlex.quote(INTERP)} {shlex.quote(str(script))} >/dev/null 2>&1")
    return marker.read_text() if marker.exists() else ""


# Default scope: only the run script is in scope. helper.observe() lives
# in helper.py which is NOT in scope, so passing a dummy to it should be
# hijacked. observe() never runs, result is a DummyObject.
default_out = run({})
assert "observed" not in default_out, (
    f"default scope should have hijacked the call; saw: {default_out!r}"
)
assert "result_type=DummyObject" in default_out, (
    f"expected result_type=DummyObject in default run: {default_out!r}"
)

# Extended scope via PYFEX_SCOPE_DIR: helper.py is under pkg_dir, so it
# is now in scope. observe() executes normally when called with a dummy
# argument.
ext_out = run({"PYFEX_SCOPE_DIR": str(pkg_dir)})
assert "observed type=DummyObject" in ext_out, (
    f"expected observe() to run under PYFEX_SCOPE_DIR; saw: {ext_out!r}"
)
assert "result_type=str" in ext_out, (
    f"expected result_type=str when observe runs normally: {ext_out!r}"
)

print("PASS: PYFEX_SCOPE_DIR extends target scope for scope-aware call dispatch")
