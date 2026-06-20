# PyFEX test suite

Tests for the PyFEX interpreter, grouped by the capability they exercise:

```
tests/general/
  forced-exec/                 crash-recovery/      branch-merge/
  dummy-object/                provenance/          live-peer-state/
  dormant-function-analysis/   shared-object/       integration/
  basic-general/
  _helpers.py                  # shared helpers
```

There are two styles in `general/`:

- **Self-configuring** (no `test_` prefix, e.g.
  `forced-exec/pop_jump_if_false_force_exec.py`): each sets its own environment
  and runs uniformly with no external setup. These form the auto-run suite.
- **Env-driven integration** (`test_*.py`, e.g.
  `crash-recovery/test_crash_recovery_basic.py`): run with the built interpreter
  plus the relevant feature environment variables (examples below).

The artifact smoke tests live under `artifact_eval/tests/` and are driven by
`artifact_eval/run_artifact_tests.py`.

## Run the whole suite

```bash
# From the artifact root, after building PyFEX-core:
python3 artifact_eval/run_artifact_tests.py --pyfex PyFEX-core/python --include-unit-tests
```

This runs the artifact smoke tests plus every self-configuring test under
`tests/general/`.

## Run an integration test directly

From the artifact root:

```bash
CRASH_RECOVERY_ENABLE=1 \
    PyFEX-core/python tests/general/crash-recovery/test_crash_recovery_basic.py
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
    PyFEX-core/python tests/general/forced-exec/test_forced_exec.py
DORMANT_FUNC_LOG_FILE=/tmp/dfa.log \
    PyFEX-core/python tests/general/dormant-function-analysis/test_dormant_function_analysis.py
```
