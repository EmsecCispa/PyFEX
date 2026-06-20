#!/usr/bin/env python3
"""Run artifact-evaluation smoke tests for PyFEX-core."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent / "tests"

PYFEX_ENV_KEYS = {
    "CRASH_RECOVERY_ENABLE",
    "CRASH_RECOVERY_GLOBAL_LIMIT",
    "CRASH_RECOVERY_LOCATION_LIMIT",
    "CRASH_RECOVERY_LOG_FILE",
    "CRASH_RECOVERY_PEER_QUERY",
    "DFA_INVOKE_CAP",
    "DFA_INVOKE_LOG",
    "DORMANT_FUNC_LOG_FILE",
    "FORCE_EXEC_ENABLE",
    "FORCE_EXEC_GLOBAL_LIMIT",
    "FORCE_EXEC_LOCAL_LIMIT",
    "FORCE_EXEC_LOCATION_LIMIT",
    "FORCE_EXEC_LOG_FILE",
    "FORCE_EXEC_LOOP_ITER_LIMIT",
    "FORCE_EXEC_MAX_PROCS",
    "FORCE_EXEC_MAX_PROCS_HARD_CAP",
    "FORCE_EXEC_MERGE_ENABLE",
    "FORCE_EXEC_MERGE_SCOPE_FILE",
    "FORCE_EXEC_MERGE_SCOPE_FUNC",
    "FORCE_EXEC_MERGE_WAIT_MS",
    "FORCE_EXEC_RETAIN_SHARED_STATE",
    "FORCE_EXEC_SHARED_OBJECT_ENABLE",
    "PYFEX_ENABLE_IN_COROUTINES",
    "PYFEX_INTERPRETER",
    "PYFEX_RUNTIME_LOG_FILE",
    "PYFEX_SCOPE_DIR",
    "PYFEX_TRACE_LOG_FILE",
    "PYFEX_NETWORK_BLOCK_LOG_FILE",
    "PYFEX_NETWORK_SANDBOX",
    "PYFEX_PROVENANCE_MODE",
}


@dataclass(frozen=True)
class Case:
    name: str
    script: Path
    category: str


CASES = [
    Case("implemented_forced_exec", TEST_DIR / "implemented_forced_exec.py", "implemented"),
    Case("implemented_crash_recovery", TEST_DIR / "implemented_crash_recovery.py", "implemented"),
    Case("implemented_trace_reporter", TEST_DIR / "implemented_trace_reporter.py", "implemented"),
    Case("implemented_network_sandbox", TEST_DIR / "implemented_network_sandbox.py", "implemented"),
    Case("implemented_try_except_continuation", TEST_DIR / "implemented_try_except_continuation.py", "implemented"),
    Case("implemented_exception_forced_exec", TEST_DIR / "implemented_exception_forced_exec.py", "implemented"),
    Case("implemented_forced_exec_proc_cap", TEST_DIR / "implemented_forced_exec_proc_cap.py", "implemented"),
    Case("implemented_dfa_driver", TEST_DIR / "implemented_dfa_driver.py", "implemented"),
    Case("implemented_dfa_required_arg", TEST_DIR / "implemented_dfa_required_arg.py", "implemented"),
    Case("implemented_dfa_package_scope", TEST_DIR / "implemented_dfa_package_scope.py", "implemented"),
    Case("implemented_entrypoint_discovery", TEST_DIR / "implemented_entrypoint_discovery.py", "implemented"),
    Case("implemented_recursive_provenance", TEST_DIR / "implemented_recursive_provenance.py", "implemented"),
    Case("implemented_dummy_hash_index", TEST_DIR / "implemented_dummy_hash_index.py", "implemented"),
    Case("implemented_pyc_scope", TEST_DIR / "implemented_pyc_scope.py", "implemented"),
]


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in PYFEX_ENV_KEYS:
        env.pop(key, None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def run_case(interp: Path, case: Case, verbose: bool) -> tuple[bool, str]:
    start = time.time()
    proc = subprocess.run(
        [str(interp), str(case.script)],
        cwd=REPO_ROOT,
        env=clean_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )
    elapsed = time.time() - start
    output = proc.stdout.strip()
    ok = proc.returncode == 0
    status = "PASS" if ok else "FAIL"
    line = f"{status} {case.category:11s} {case.name} ({elapsed:.2f}s)"
    if verbose or not ok:
        if output:
            line += "\n" + indent(output)
    return ok, line


def run_unit_tests(interp: Path, verbose: bool) -> tuple[bool, str]:
    # Self-configuring focused tests set their own env and run uniformly. The
    # env-driven integration tests (test_*.py, relocated from the old top-level
    # tests/) require per-test feature env vars and are run manually (see
    # tests/README.md), so they are excluded from this auto-run glob.
    tests = sorted(
        p for p in (REPO_ROOT / "tests" / "general").glob("*/*.py")
        if not p.name.startswith("test_")
    )
    start = time.time()
    failures: list[tuple[str, int, str]] = []
    for test in tests:
        proc = subprocess.run(
            [str(interp), str(test)],
            cwd=REPO_ROOT,
            env=clean_env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        if proc.returncode != 0:
            failures.append((str(test.relative_to(REPO_ROOT)), proc.returncode, proc.stdout))
    elapsed = time.time() - start
    if failures:
        lines = [f"FAIL general   {len(failures)}/{len(tests)} failed ({elapsed:.2f}s)"]
        for name, code, out in failures:
            lines.append(f"{name} exited {code}")
            if verbose and out:
                lines.append(indent(out.strip()))
        return False, "\n".join(lines)
    return True, f"PASS general     {len(tests)} cross-version focused tests ({elapsed:.2f}s)"


def indent(text: str) -> str:
    return "\n".join(f"    {line}" for line in text.splitlines())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pyfex",
        default=str(REPO_ROOT / "PyFEX-core" / "python"),
        help="Path to the PyFEX interpreter.",
    )
    parser.add_argument(
        "--include-unit-tests",
        action="store_true",
        help="Also run all cross-version focused tests under tests/general/*/*.py.",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only cases whose name contains this substring. Can be repeated.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    interp = Path(args.pyfex).resolve()
    if not interp.exists():
        sys.stderr.write(f"PyFEX interpreter not found: {interp}\n")
        return 2

    selected = CASES
    for needle in args.only:
        selected = [case for case in selected if needle in case.name]
    if not selected:
        sys.stderr.write("No tests selected.\n")
        return 2

    all_ok = True
    for case in selected:
        ok, line = run_case(interp, case, args.verbose)
        print(line)
        all_ok = all_ok and ok

    if args.include_unit_tests:
        ok, line = run_unit_tests(interp, args.verbose)
        print(line)
        all_ok = all_ok and ok

    print(f"SUMMARY {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
