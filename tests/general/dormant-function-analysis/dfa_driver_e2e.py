"""End-to-end test for tools/dfa_driver.py.

Creates a synthetic target script with:
  - called_func: invoked during the target's top-level run
  - dormant_func: defined, never called
  - Cls.__init__ / Cls.called_method: invoked
  - Cls.dormant_method: defined, never called

Runs the target under PyFEX with DORMANT_FUNC_LOG_FILE to produce the
DEFINED/CALLED log, then invokes tools/dfa_driver.py which should:
  1. parse the log
  2. identify dormant_func and Cls.dormant_method as dormant
  3. spawn a wrapper per dormant and invoke it under PyFEX
Each dormant function writes to a marker when it runs, so the test
verifies that both dormants were successfully invoked.
"""
import os
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _helpers import TMP_ROOT, fresh_path, read_markers, wait_for


REPO_ROOT = Path(__file__).resolve().parents[3]
INTERP = REPO_ROOT / "PyFEX-core" / "python"
DRIVER = REPO_ROOT / "tools" / "dfa_driver.py"


work_dir = TMP_ROOT / f"dfa_e2e_{os.getpid()}"
work_dir.mkdir(parents=True, exist_ok=True)

marker = fresh_path("dfa_dormant_ran", ".log")
dfa_log = fresh_path("dfa_defined_called", ".log")
invoke_log = fresh_path("dfa_invoke", ".log")

target = work_dir / "dfa_target.py"
target.write_text(textwrap.dedent(f"""
    MARKER = {str(marker)!r}

    def _note(tag):
        with open(MARKER, "a") as fp:
            fp.write(tag + "\\n")

    def called_func():
        _note("called_func_ran")

    def dormant_func():
        _note("dormant_func_ran")

    class Cls:
        def __init__(self):
            _note("Cls_init_ran")

        def called_method(self):
            _note("Cls_called_method_ran")

        def dormant_method(self):
            _note("Cls_dormant_method_ran")

    called_func()
    _obj = Cls()
    _obj.called_method()
"""))

# Stage 1: run the target under PyFEX to produce the DEFINED/CALLED log.
# DORMANT_FUNC_LOG_FILE accumulates, so clear it first.
if dfa_log.exists():
    dfa_log.unlink()
env = {
    "CRASH_RECOVERY_ENABLE": "1",
    "DORMANT_FUNC_LOG_FILE": str(dfa_log),
}
env_prefix = " ".join(f"{k}={v}" for k, v in env.items())
os.system(f"{env_prefix} {INTERP} {target} >/dev/null 2>&1")

# Sanity: both called_func and dormant_func should appear as DEFINED;
# only called_func should appear as CALLED.
assert dfa_log.exists(), "dfa log was not produced"
log_text = dfa_log.read_text()
assert "DEFINED called_func" in log_text, f"log missing DEFINED called_func: {log_text}"
assert "DEFINED dormant_func" in log_text, f"log missing DEFINED dormant_func: {log_text}"
assert "CALLED called_func" in log_text, f"log missing CALLED called_func: {log_text}"
assert "CALLED dormant_func" not in log_text, (
    f"log unexpectedly shows CALLED dormant_func: {log_text}"
)

# Stage 2: first-run markers (sanity).
markers_after_stage1 = set(read_markers(marker))
assert "called_func_ran" in markers_after_stage1
assert "Cls_init_ran" in markers_after_stage1
assert "Cls_called_method_ran" in markers_after_stage1
assert "dormant_func_ran" not in markers_after_stage1
assert "Cls_dormant_method_ran" not in markers_after_stage1

# Stage 3: run the DFA driver. It should invoke dormant_func and
# Cls.dormant_method, each of which writes a marker.
driver_env = {
    "PYFEX_INTERPRETER": str(INTERP),
    "DFA_INVOKE_LOG": str(invoke_log),
    "DFA_INVOKE_CAP": "16",
}
driver_env_prefix = " ".join(f"{k}={v}" for k, v in driver_env.items())
os.system(
    f"{driver_env_prefix} {sys.executable} {DRIVER} {dfa_log} {target} >/dev/null 2>&1"
)

# Both dormants should have been invoked and their markers written.
def both_dormants_ran():
    m = set(read_markers(marker))
    return {"dormant_func_ran", "Cls_dormant_method_ran"} <= m


assert wait_for(both_dormants_ran, timeout=5.0), (
    f"dormant callables were not invoked; markers={read_markers(marker)!r} "
    f"invoke_log={read_markers(invoke_log)!r}"
)

# The invoke log should mark both dormants as invoked (not failed).
invoke_lines = read_markers(invoke_log)
assert any("invoked:dormant_func" in ln for ln in invoke_lines), (
    f"dormant_func not reported invoked: {invoke_lines}"
)
assert any("invoked:Cls.dormant_method" in ln for ln in invoke_lines), (
    f"Cls.dormant_method not reported invoked: {invoke_lines}"
)

print("PASS: DFA driver invoked dormant function and dormant class method")
