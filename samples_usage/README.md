# PyFEX feature demos

Small, self-contained scripts that each demonstrate one PyFEX capability on a
tiny, evasive-malware-style example. They are meant to be read and run by hand
so you can see exactly what each feature does.

Each demo ships **twice**: as readable source (`0X_name.py`) and as pre-compiled
**bytecode** (`0X_name.pyc`, CPython 3.10). PyFEX runs the bytecode form
directly — the same way it ingests byte-compiled, source-less malware — and a
byte-compiled main script is recognized as in scope automatically, so no extra
configuration is needed.

**Prerequisite:** build the interpreter once (from the artifact root):

```bash
( cd PyFEX-core && ./configure && make -j"$(nproc)" )
```

## Run everything at once

```bash
samples_usage/run.sh
```

This runs the pre-compiled `.pyc` (bytecode) for every demo. The launcher
resolves all paths relative to itself, so the artifact folder can be moved
anywhere.

## Run a single demo

From the artifact root. These run the **bytecode** directly:

| # | Feature | Command |
|---|---|---|
| 1 | **Forced Execution** — explore both sides of a branch | `FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 PyFEX-core/python samples_usage/01_forced_execution.pyc` |
| 2 | **Resilient Crash Recovery** — keep running past errors via DummyObjects | `CRASH_RECOVERY_ENABLE=1 PyFEX-core/python samples_usage/02_crash_recovery.pyc` |
| 3 | **Branch Merging** — reconverge forked paths so exploration stays bounded | `FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 PyFEX-core/python samples_usage/03_branch_merging.pyc` |
| 4 | **Dormant Function Analysis** — invoke never-called functions | see `04_dormant_function_analysis.py` (two-step: log, then replay) |
| 5 | **Dummy Provenance** — recursive symbolic trace of a recovered value | `CRASH_RECOVERY_ENABLE=1 PYFEX_PROVENANCE_MODE=recursive PyFEX-core/python samples_usage/05_dummy_provenance.pyc` |

To read or run the **source** form instead, use the matching `0X_name.py` (its
docstring repeats the command). The `.py` and `.pyc` forms behave identically.

All features are off by default (zero overhead) and are enabled purely through
environment variables — see the top-level `README.md` for the full list.

## What you should see

- **01** prints both the concrete *and* the hidden-payload branch.
- **02** runs to completion and reconstructs a C2 URL despite a missing import,
  an undefined global, and a failed call.
- **03** explores both configuration branches and continues once past the merge.
- **04** logs `exfiltrate` as defined-but-never-called, then the driver runs its
  body in a fresh process.
- **05** prints `SUBSCRIPT(ADD(dummy, 1), 2)` and the full symbolic trace.
