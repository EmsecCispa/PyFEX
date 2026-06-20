#!/usr/bin/env python3
"""Run an arbitrary Python program under the PyFEX artifact interpreter.

The wrapper keeps artifact runs reproducible by clearing inherited PyFEX
environment variables, then setting every exposed option from documented
defaults plus CLI overrides.
"""

from __future__ import annotations

import argparse
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path

try:
    import resource
except ImportError:  # non-POSIX; the OS-level backstop is then unavailable
    resource = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERPRETER = REPO_ROOT / "PyFEX-core" / "python"
NETWORK_SANDBOX_DIR = REPO_ROOT / "artifact_eval" / "network_sandbox"


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
}

NETWORK_ENV_KEYS = {
    "PYFEX_NETWORK_BLOCK_LOG_FILE",
    "PYFEX_NETWORK_SANDBOX",
}


DEFAULT_ENV = {
    "CRASH_RECOVERY_ENABLE": "0",
    "CRASH_RECOVERY_GLOBAL_LIMIT": "1000",
    "CRASH_RECOVERY_LOCATION_LIMIT": "50",
    "CRASH_RECOVERY_PEER_QUERY": "1",
    "DFA_INVOKE_CAP": "32",
    "FORCE_EXEC_ENABLE": "0",
    "FORCE_EXEC_GLOBAL_LIMIT": "100",
    "FORCE_EXEC_LOCATION_LIMIT": "10",
    "FORCE_EXEC_LOOP_ITER_LIMIT": "200",
    # Memory safety: bound concurrent live forced processes, and default
    # branch merging ON so forced children _exit at their post-dominator
    # instead of accumulating. Both are no-ops when forced exec is off.
    "FORCE_EXEC_MAX_PROCS": "8",
    "FORCE_EXEC_MAX_PROCS_HARD_CAP": "256",
    "FORCE_EXEC_MERGE_ENABLE": "1",
    "FORCE_EXEC_MERGE_WAIT_MS": "50",
    "FORCE_EXEC_RETAIN_SHARED_STATE": "0",
    "FORCE_EXEC_SHARED_OBJECT_ENABLE": "0",
    "PYFEX_ENABLE_IN_COROUTINES": "0",
}


OPTION_TO_ENV = {
    "crash_recovery_enable": "CRASH_RECOVERY_ENABLE",
    "crash_recovery_global_limit": "CRASH_RECOVERY_GLOBAL_LIMIT",
    "crash_recovery_location_limit": "CRASH_RECOVERY_LOCATION_LIMIT",
    "crash_recovery_log_file": "CRASH_RECOVERY_LOG_FILE",
    "crash_recovery_peer_query": "CRASH_RECOVERY_PEER_QUERY",
    "dfa_invoke_cap": "DFA_INVOKE_CAP",
    "dfa_invoke_log": "DFA_INVOKE_LOG",
    "dormant_func_log_file": "DORMANT_FUNC_LOG_FILE",
    "force_exec_enable": "FORCE_EXEC_ENABLE",
    "force_exec_global_limit": "FORCE_EXEC_GLOBAL_LIMIT",
    "force_exec_local_limit": "FORCE_EXEC_LOCAL_LIMIT",
    "force_exec_location_limit": "FORCE_EXEC_LOCATION_LIMIT",
    "force_exec_log_file": "FORCE_EXEC_LOG_FILE",
    "force_exec_loop_iter_limit": "FORCE_EXEC_LOOP_ITER_LIMIT",
    "force_exec_max_procs": "FORCE_EXEC_MAX_PROCS",
    "force_exec_max_procs_hard_cap": "FORCE_EXEC_MAX_PROCS_HARD_CAP",
    "force_exec_merge_enable": "FORCE_EXEC_MERGE_ENABLE",
    "force_exec_merge_scope_file": "FORCE_EXEC_MERGE_SCOPE_FILE",
    "force_exec_merge_scope_func": "FORCE_EXEC_MERGE_SCOPE_FUNC",
    "force_exec_merge_wait_ms": "FORCE_EXEC_MERGE_WAIT_MS",
    "force_exec_retain_shared_state": "FORCE_EXEC_RETAIN_SHARED_STATE",
    "force_exec_shared_object_enable": "FORCE_EXEC_SHARED_OBJECT_ENABLE",
    "pyfex_enable_in_coroutines": "PYFEX_ENABLE_IN_COROUTINES",
    "pyfex_runtime_log_file": "PYFEX_RUNTIME_LOG_FILE",
    "pyfex_scope_dir": "PYFEX_SCOPE_DIR",
    "pyfex_trace_log_file": "PYFEX_TRACE_LOG_FILE",
}


def zero_one(value: str) -> str:
    if value not in {"0", "1"}:
        raise argparse.ArgumentTypeError("expected 0 or 1")
    return value


def add_env_option(parser: argparse.ArgumentParser, name: str, **kwargs: object) -> None:
    env_name = OPTION_TO_ENV[name]
    default = DEFAULT_ENV.get(env_name, "unset")
    help_text = kwargs.pop("help", "")
    suffix = f" Env: {env_name}. Default: {default}."
    parser.add_argument(f"--{name.replace('_', '-')}", dest=name, default=None, help=help_text + suffix, **kwargs)


def parse_key_value(items: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--env expects KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise SystemExit(f"--env key cannot be empty: {item}")
        parsed[key] = value
    return parsed


def prepend_pythonpath(env: dict[str, str], path: Path) -> None:
    current = env.get("PYTHONPATH", "")
    parts = [str(path)]
    if current:
        parts.append(current)
    env["PYTHONPATH"] = os.pathsep.join(parts)


def build_env(args: argparse.Namespace, interp: Path) -> dict[str, str]:
    env = os.environ.copy()
    if not args.inherit_pyfex_env:
        for key in PYFEX_ENV_KEYS | NETWORK_ENV_KEYS:
            env.pop(key, None)

    for key, value in DEFAULT_ENV.items():
        env[key] = value

    for option, env_name in OPTION_TO_ENV.items():
        value = getattr(args, option)
        if value is not None:
            env[env_name] = str(value)

    env["PYFEX_INTERPRETER"] = str(interp)
    env["PYTHONUNBUFFERED"] = "1"

    for key, value in parse_key_value(args.env).items():
        env[key] = value

    if args.network == "blocked":
        env["PYFEX_NETWORK_SANDBOX"] = "blocked"
        if args.network_log_file:
            env["PYFEX_NETWORK_BLOCK_LOG_FILE"] = str(Path(args.network_log_file).resolve())
        env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        env.setdefault("PIP_NO_INDEX", "1")
        env.setdefault("PIP_DEFAULT_TIMEOUT", "1")
        prepend_pythonpath(env, NETWORK_SANDBOX_DIR)

    return env


def print_effective_env(env: dict[str, str]) -> None:
    for key in sorted(PYFEX_ENV_KEYS | NETWORK_ENV_KEYS):
        if key in env:
            print(f"{key}={shlex.quote(env[key])}")
        else:
            print(f"{key}=<unset>")


def build_execution_command(args: argparse.Namespace, cmd: list[str]) -> list[str]:
    if args.network != "blocked" or args.network_os_sandbox == "none":
        return cmd

    unshare = shutil.which("unshare")
    if unshare is None:
        raise SystemExit("OS network sandbox requested, but 'unshare' was not found")
    return [unshare, "--user", "--map-root-user", "--net", "--", *cmd]


def count_user_tasks() -> int | None:
    """Best-effort count of tasks (threads) owned by the current user, the
    quantity RLIMIT_NPROC is checked against. Returns None if unavailable."""
    try:
        uid = os.getuid()
        entries = os.listdir("/proc")
    except (OSError, AttributeError):
        return None
    total = 0
    for name in entries:
        if not name.isdigit():
            continue
        try:
            if os.stat(f"/proc/{name}").st_uid != uid:
                continue
            total += len(os.listdir(f"/proc/{name}/task"))
        except OSError:
            continue
    return total


def resolve_nproc_limit(spec: str, max_procs: int) -> int | None:
    """Resolve the --max-user-procs spec to an absolute RLIMIT_NPROC value.

    "auto" calibrates to the current task baseline plus generous headroom so
    only a genuine runaway is caught; "none" disables; an integer is used as
    given. Returns None when no limit should be set."""
    if resource is None or spec in ("none", "0"):
        return None
    if spec != "auto":
        try:
            return max(1, int(spec))
        except ValueError:
            return None
    baseline = count_user_tasks()
    if baseline is None:
        return None
    # Headroom dominated by the concurrent cap (each forced interpreter is a
    # few tasks); kept generous so unrelated user processes never trip it.
    return baseline + max(512, max_procs * 32)


def make_nproc_preexec(limit: int):
    """Return a preexec_fn that lowers the soft RLIMIT_NPROC to `limit`."""
    def _pre() -> None:
        try:
            _soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
            new_soft = limit if hard == resource.RLIM_INFINITY else min(limit, hard)
            resource.setrlimit(resource.RLIMIT_NPROC, (new_soft, hard))
        except Exception:
            pass
    return _pre


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Python target under PyFEX-core with explicit artifact-evaluation options.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 artifact_eval/run_pyfex_program.py target.py\n"
            "  python3 artifact_eval/run_pyfex_program.py --crash-recovery-enable 1 --force-exec-enable 1 target.py\n"
            "  python3 artifact_eval/run_pyfex_program.py --pyfex-trace-log-file /tmp/trace.jsonl --pyfex-runtime-log-file /tmp/runtime.log target.py -- --target-arg\n"
        ),
    )

    runner = parser.add_argument_group("runner")
    runner.add_argument("--pyfex", default=str(DEFAULT_INTERPRETER), help=f"PyFEX interpreter path. Default: {DEFAULT_INTERPRETER}.")
    runner.add_argument("--cwd", default=None, help="Working directory for the target. Default: current directory.")
    runner.add_argument("--module", action="store_true", help="Run PROGRAM as a module name via -m.")
    runner.add_argument("--timeout", type=float, default=None, help="Kill the target after this many seconds. Default: unset.")
    runner.add_argument(
        "--max-user-procs",
        default="auto",
        metavar="auto|none|N",
        help="OS-level RLIMIT_NPROC backstop for the target tree. 'auto' "
             "calibrates above the current task baseline; 'none' disables. "
             "Default: auto.",
    )
    runner.add_argument("--dry-run", action="store_true", help="Print command and effective PyFEX environment, but do not execute.")
    runner.add_argument("--print-env", action="store_true", help="Print the effective PyFEX environment before executing.")
    runner.add_argument("--inherit-pyfex-env", action="store_true", help="Do not clear inherited PyFEX env vars before applying defaults/overrides.")
    runner.add_argument("--env", action="append", default=[], metavar="KEY=VALUE", help="Extra environment override. Can be repeated.")
    runner.add_argument(
        "--network",
        choices=("blocked", "host"),
        default="blocked",
        help="Network policy for the target. Default: blocked.",
    )
    runner.add_argument(
        "--network-os-sandbox",
        choices=("unshare", "none"),
        default="unshare",
        help="OS network sandbox when --network=blocked. 'none' keeps only the Python-level blocker. Default: unshare.",
    )
    runner.add_argument(
        "--network-log-file",
        default=None,
        help="JSONL log for Python-level blocked network attempts. Default: unset.",
    )

    cr = parser.add_argument_group("crash recovery")
    add_env_option(cr, "crash_recovery_enable", type=zero_one, help="Enable resilient crash recovery.")
    add_env_option(cr, "crash_recovery_global_limit", type=int, help="Maximum total crash recoveries.")
    add_env_option(cr, "crash_recovery_location_limit", type=int, help="Maximum recoveries per bytecode location.")
    add_env_option(cr, "crash_recovery_peer_query", type=zero_one, help="Allow recovery from merged/live peer state.")
    add_env_option(cr, "crash_recovery_log_file", help="Legacy crash-recovery debug log. Prefer --pyfex-runtime-log-file.")

    fe = parser.add_argument_group("forced execution")
    add_env_option(fe, "force_exec_enable", type=zero_one, help="Enable forced execution forks.")
    add_env_option(fe, "force_exec_global_limit", type=int, help="Maximum total forced-execution forks.")
    add_env_option(fe, "force_exec_max_procs", type=int, help="Hard cap on concurrent live forced processes (memory safety).")
    add_env_option(fe, "force_exec_max_procs_hard_cap", type=int, help="Upper bound the --force-exec-max-procs value is clamped to.")
    add_env_option(fe, "force_exec_location_limit", type=int, help="Maximum forks per bytecode location.")
    add_env_option(fe, "force_exec_local_limit", type=int, help="Legacy alias retained for older docs/tests; current 3.10 uses FORCE_EXEC_LOCATION_LIMIT.")
    add_env_option(fe, "force_exec_loop_iter_limit", type=int, help="Per-frame loop-iteration cap; 0 disables.")
    add_env_option(fe, "force_exec_log_file", help="Legacy forced-execution debug log. Runtime default is force_exec.log when FE logs are emitted.")

    merge = parser.add_argument_group("branch merging and state sharing")
    add_env_option(merge, "force_exec_merge_enable", type=zero_one, help="Enable branch-state merging at reconvergence points.")
    add_env_option(merge, "force_exec_merge_wait_ms", type=int, help="Milliseconds parent waits for child merge snapshot.")
    add_env_option(merge, "force_exec_merge_scope_file", help="Comma-separated file/path allowlist for merge tracking.")
    add_env_option(merge, "force_exec_merge_scope_func", help="Comma-separated function-name allowlist for merge tracking.")
    add_env_option(merge, "force_exec_retain_shared_state", type=zero_one, help="Keep shared snapshots/live-state entries after use.")
    add_env_option(merge, "force_exec_shared_object_enable", type=zero_one, help="Expose share_object/recover_object builtins.")

    trace = parser.add_argument_group("trace, runtime debug, and scope")
    add_env_option(trace, "pyfex_trace_log_file", help="Behavior-profile JSONL log for function calls and arguments.")
    add_env_option(trace, "pyfex_runtime_log_file", help="Unified runtime/debug log for FE/CR/DFA/peer-state events.")
    add_env_option(trace, "pyfex_scope_dir", help="Treat every file under this directory as in target scope.")
    add_env_option(trace, "pyfex_enable_in_coroutines", type=zero_one, help="Opt into PyFEX hooks inside generator/coroutine frames.")

    dfa = parser.add_argument_group("dormant function analysis")
    add_env_option(dfa, "dormant_func_log_file", help="DFA DEFINED/CALLED log consumed by tools/dfa_driver.py.")
    add_env_option(dfa, "dfa_invoke_cap", type=int, help="DFA driver invocation cap; included for reproducible combined workflows.")
    add_env_option(dfa, "dfa_invoke_log", help="DFA driver per-invocation status log.")

    parser.add_argument("program", help="Target Python file, or module name when --module is used.")
    parser.add_argument("program_args", nargs=argparse.REMAINDER, help="Arguments passed to the target. Use -- before target args that start with '-'.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    interp = Path(args.pyfex).resolve()
    if not interp.exists():
        sys.stderr.write(f"PyFEX interpreter not found: {interp}\n")
        return 2

    program_args = list(args.program_args)
    if program_args and program_args[0] == "--":
        program_args = program_args[1:]

    cmd = [str(interp)]
    if args.module:
        cmd.extend(["-m", args.program])
    else:
        cmd.append(args.program)
    cmd.extend(program_args)

    env = build_env(args, interp)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()

    exec_cmd = build_execution_command(args, cmd)

    try:
        max_procs = int(env.get("FORCE_EXEC_MAX_PROCS", "8") or "8")
    except ValueError:
        max_procs = 8
    nproc_limit = resolve_nproc_limit(args.max_user_procs, max_procs)

    if args.dry_run or args.print_env:
        print("Command:")
        print(" ".join(shlex.quote(part) for part in exec_cmd))
        print("\nPyFEX environment:")
        print_effective_env(env)
        print(f"\nRLIMIT_NPROC backstop: {nproc_limit if nproc_limit is not None else '<unset>'}")

    if args.dry_run:
        return 0

    preexec = make_nproc_preexec(nproc_limit) if nproc_limit is not None else None
    try:
        proc = subprocess.run(
            exec_cmd, cwd=str(cwd), env=env, timeout=args.timeout, preexec_fn=preexec
        )
    except subprocess.TimeoutExpired as exc:
        sys.stderr.write(f"Target timed out after {exc.timeout} seconds\n")
        return 124

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
