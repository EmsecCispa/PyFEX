#!/usr/bin/env bash
# Run every PyFEX feature demo in turn.
#
# These run the PRE-COMPILED BYTECODE (the .pyc files next to each .py),
# demonstrating that PyFEX executes Python bytecode directly: PyFEX recognizes a
# byte-compiled main script (foo.pyc) as in scope just like its foo.py source,
# so no extra configuration is needed.
#
# Relocatable: all paths are resolved relative to THIS script, so the artifact
# folder can be moved anywhere. Requires that PyFEX-core has been built first
# (see the top-level README).
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"          # artifact root (parent of samples_usage)
INTERP="$ROOT/PyFEX-core/python"

if [ ! -x "$INTERP" ]; then
  echo "PyFEX-core is not built yet. Build it first:"
  echo "    ( cd \"$ROOT/PyFEX-core\" && ./configure && make -j\"\$(nproc)\" )"
  exit 1
fi

cd "$HERE"   # run from the demo folder so each demo's own filename resolves

echo "== 1. Forced Execution =="
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
  FORCE_EXEC_LOG_FILE=/dev/null "$INTERP" 01_forced_execution.pyc

echo; echo "== 2. Resilient Crash Recovery =="
CRASH_RECOVERY_ENABLE=1 "$INTERP" 02_crash_recovery.pyc

echo; echo "== 3. Branch Merging =="
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
  FORCE_EXEC_LOG_FILE=/dev/null "$INTERP" 03_branch_merging.pyc

echo; echo "== 4. Dormant Function Analysis (log + active replay) =="
LOG="$(mktemp)"; MARK="$(mktemp)"
echo "-- phase 1: normal run (only install() runs) --"
DORMANT_FUNC_LOG_FILE="$LOG" PYFEX_DEMO_MARKER="$MARK" \
  "$INTERP" 04_dormant_function_analysis.pyc
: > "$MARK"   # reset so the marker reflects only what the replay triggers
echo "-- phase 2: driver invokes the dormant exfiltrate() --"
PYFEX_DEMO_MARKER="$MARK" PYFEX_INTERPRETER="$INTERP" \
  python3 "$ROOT/tools/dfa_driver.py" "$LOG" 04_dormant_function_analysis.py
echo "-- proof the dormant body executed (marker file) --"
cat "$MARK"
rm -f "$LOG" "$MARK"

echo; echo "== 5. Dummy Provenance (recursive symbolic trace) =="
CRASH_RECOVERY_ENABLE=1 PYFEX_PROVENANCE_MODE=recursive \
  "$INTERP" 05_dummy_provenance.pyc

echo; echo "All demos finished."
