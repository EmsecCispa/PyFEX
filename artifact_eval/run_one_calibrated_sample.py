#!/usr/bin/env python3
"""Run exactly one prepared calibrated sample under PyFEX."""

from __future__ import annotations

import argparse
import configparser
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLES_DIR = REPO_ROOT / "artifact_eval" / "samples"
WRAPPER = REPO_ROOT / "artifact_eval" / "run_pyfex_program.py"
SIMPLIFIER = REPO_ROOT / "artifact_eval" / "simplify_behavior_trace.py"
SUMMARIZER = REPO_ROOT / "artifact_eval" / "summarize_dfa_coverage.py"
DFA_DRIVER = REPO_ROOT / "tools" / "dfa_driver.py"
PYFEX_INTERP = REPO_ROOT / "PyFEX-core" / "python"


SKIP_ENTRY_DIRS = {
    "__pycache__",
    ".eggs",
    "build",
    "dist",
    "doc",
    "docs",
    "example",
    "examples",
    "test",
    "tests",
}


@dataclass(frozen=True)
class EntryPoint:
    label: str
    kind: str
    path: Path | None = None
    module: str | None = None
    args: tuple[str, ...] = ()


def load_manifest(samples_dir: Path) -> list[dict[str, str]]:
    manifest = samples_dir / "selection_manifest.csv"
    if not manifest.is_file():
        raise SystemExit(f"Selection manifest not found: {manifest}")
    with manifest.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def select_row(rows: list[dict[str, str]], rank: int | None, sample_id: str | None) -> dict[str, str]:
    if rank is None and sample_id is None:
        raise SystemExit("Provide --rank or --sample-id")
    for row in rows:
        if rank is not None and int(row["rank"]) == rank:
            return row
        if sample_id is not None and row["sample_id"] == sample_id:
            return row
    raise SystemExit("Requested sample not found in selection_manifest.csv")


def count_jsonl_events(path: Path) -> tuple[int, int]:
    rows = 0
    calls = 0
    if not path.is_file():
        return rows, calls
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            rows += 1
            try:
                if json.loads(line).get("event") == "function_call":
                    calls += 1
            except json.JSONDecodeError:
                pass
    return rows, calls


def count_runtime_events(path: Path) -> tuple[int, int, int]:
    if not path.is_file():
        return 0, 0, 0
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    recoveries = sum(1 for line in lines if "RECOVERY:" in line)
    forks = sum(1 for line in lines if "FORK:" in line)
    return len(lines), recoveries, forks


def count_jsonl_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            if line.strip():
                count += 1
    return count


def count_dfa(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return 0, 0
    defined = 0
    called = 0
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            if line.startswith("DEFINED "):
                defined += 1
            elif line.startswith("CALLED "):
                called += 1
    return defined, called


def build_pythonpath(package_dir: Path, row: dict[str, str]) -> str:
    roots: list[Path] = []
    manifest_roots = row.get("import_roots", "")
    if manifest_roots:
        for rel in manifest_roots.split(os.pathsep):
            if rel:
                roots.append(package_dir if rel == "." else package_dir / rel)
    else:
        roots.append(package_dir)
        src = package_dir / "src"
        if src.is_dir():
            roots.append(src)

    existing: set[str] = set()
    values: list[str] = []
    for root in roots:
        if root.is_dir():
            value = str(root.resolve())
            if value not in existing:
                existing.add(value)
                values.append(value)
    return os.pathsep.join(values)


def import_roots(package_dir: Path, row: dict[str, str]) -> list[Path]:
    roots: list[Path] = []
    manifest_roots = row.get("import_roots", "")
    if manifest_roots:
        for rel in manifest_roots.split(os.pathsep):
            if rel:
                roots.append(package_dir if rel == "." else package_dir / rel)
    else:
        roots.append(package_dir)
        src = package_dir / "src"
        if src.is_dir():
            roots.append(src)
    return [root.resolve() for root in roots if root.is_dir()]


def slugify(text: str) -> str:
    chars = [ch.lower() if ch.isalnum() else "_" for ch in text]
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug[:80] or "entry"


def skip_entry_path(path: Path, package_dir: Path) -> bool:
    try:
        rel = path.resolve().relative_to(package_dir)
    except ValueError:
        return True
    if path.name.startswith("_pyfex_"):
        return True
    if any(part in SKIP_ENTRY_DIRS for part in rel.parts):
        return True
    if any(part.endswith((".egg-info", ".dist-info")) for part in rel.parts):
        return True
    return False


def module_name_from_path(path: Path, roots: list[Path]) -> str | None:
    resolved = path.resolve()
    for root in sorted(roots, key=lambda value: len(str(value)), reverse=True):
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        parts = list(rel.with_suffix("").parts)
        if not parts:
            return None
        if parts[-1] == "__init__":
            parts = parts[:-1]
        elif parts[-1] == "__main__":
            parts = parts[:-1]
        if not parts or not all(part.isidentifier() for part in parts):
            return None
        return ".".join(parts)
    return None


def read_top_level_names(package_dir: Path, roots: list[Path]) -> list[str]:
    names: list[str] = []
    for info_dir in list(package_dir.glob("*.dist-info")) + list(package_dir.glob("*.egg-info")):
        top_level = info_dir / "top_level.txt"
        if top_level.is_file():
            for line in top_level.read_text(encoding="utf-8", errors="replace").splitlines():
                name = line.strip()
                if name and name.isidentifier():
                    names.append(name)

    if names:
        return sorted(set(names))

    for root in roots:
        for child in sorted(root.iterdir()):
            if child.name.startswith("_") or child.name in SKIP_ENTRY_DIRS:
                continue
            if child.name.endswith((".egg-info", ".dist-info")):
                continue
            if child.is_dir() and (child / "__init__.py").is_file() and child.name.isidentifier():
                names.append(child.name)
            elif child.is_file() and child.suffix == ".py" and child.stem.isidentifier():
                if child.stem not in {"setup", "__main__"}:
                    names.append(child.stem)
    return sorted(set(names))


def write_import_entry(package_dir: Path, module: str) -> Path:
    path = package_dir / f"_pyfex_import_{slugify(module)}.py"
    path.write_text(
        "import importlib\n"
        f"MODULE = {module!r}\n"
        "print('[pyfex-entry] import ' + MODULE)\n"
        "importlib.import_module(MODULE)\n",
        encoding="utf-8",
    )
    return path


def add_entry(entries: list[EntryPoint], seen: set[tuple[str, str, tuple[str, ...]]], entry: EntryPoint) -> None:
    target = entry.module if entry.module is not None else str(entry.path)
    key = (entry.kind, target, entry.args)
    if key in seen:
        return
    seen.add(key)
    entries.append(entry)


def parse_setup_cfg_scripts(setup_cfg: Path) -> list[tuple[str, str]]:
    """Return [(name, 'module:callable'), ...] declared under
    [options.entry_points] console_scripts / gui_scripts in setup.cfg.
    configparser folds the indented continuation lines into one value; each
    non-empty line is a `name = module:callable` mapping."""
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(setup_cfg, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return []
    if not parser.has_section("options.entry_points"):
        return []
    results: list[tuple[str, str]] = []
    for key in ("console_scripts", "gui_scripts"):
        if not parser.has_option("options.entry_points", key):
            continue
        for line in parser.get("options.entry_points", key).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, spec = line.partition("=")
            name, spec = name.strip(), spec.strip()
            if name and spec:
                results.append((name, spec))
    return results


def parse_pyproject_scripts(pyproject: Path) -> list[tuple[str, str]]:
    """Return [(name, 'module:callable'), ...] from [project.scripts] and
    [project.gui-scripts] in pyproject.toml. Prefers a real TOML parser
    (tomllib on 3.11+, then tomli); falls back to a minimal section reader
    since script values are always simple quoted strings."""
    try:
        text = pyproject.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    data = None
    for modname in ("tomllib", "tomli"):
        try:
            mod = __import__(modname)
        except ImportError:
            continue
        try:
            data = mod.loads(text)
        except Exception:
            data = None
        break

    results: list[tuple[str, str]] = []
    if data is not None:
        project = data.get("project", {})
        if isinstance(project, dict):
            for table in ("scripts", "gui-scripts"):
                section = project.get(table, {})
                if isinstance(section, dict):
                    for name, spec in section.items():
                        if isinstance(spec, str):
                            results.append((str(name), spec))
        return results

    # Fallback parser: locate the [project.scripts] / [project.gui-scripts]
    # tables and read `name = "module:callable"` lines until the next table.
    wanted = {"project.scripts", "project.gui-scripts"}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].replace('"', "").replace("'", "").strip()
            continue
        if current in wanted and "=" in line:
            key, _, val = line.partition("=")
            key = key.strip().strip("\"'")
            val = val.split("#", 1)[0].strip().strip("\"'")
            if key and val:
                results.append((key, val))
    return results


def write_console_script_entry(package_dir: Path, name: str, spec: str) -> Path | None:
    """Write a wrapper that invokes a console-script entry point. The spec is
    `module:object` where object is a (possibly dotted) attribute path to a
    callable -- the same thing pip's generated console scripts call. Returns the
    wrapper path, or None if the spec names no module."""
    module, _, attrs = spec.partition(":")
    module, attrs = module.strip(), attrs.strip()
    if not module:
        return None
    path = package_dir / f"_pyfex_entrypoint_{slugify(name)}.py"
    path.write_text(
        "import importlib\n"
        f"MODULE = {module!r}\n"
        f"ATTRS = {attrs!r}\n"
        "print('[pyfex-entry] console_script ' + MODULE + ((':' + ATTRS) if ATTRS else ''))\n"
        "obj = importlib.import_module(MODULE)\n"
        "for _part in ATTRS.split('.'):\n"
        "    if _part:\n"
        "        obj = getattr(obj, _part)\n"
        "if callable(obj):\n"
        "    obj()\n",
        encoding="utf-8",
    )
    return path


def discover_entrypoints(package_dir: Path, row: dict[str, str]) -> list[EntryPoint]:
    roots = import_roots(package_dir, row)
    entries: list[EntryPoint] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()

    setup = package_dir / "setup.py"
    if setup.is_file():
        add_entry(entries, seen, EntryPoint("setup.py", "setup.py", path=setup, args=("--name",)))

    # Declared console/GUI entry points (setup.cfg + pyproject.toml). pip would
    # install these as runnable scripts; here we generate a wrapper that invokes
    # the module:callable so its code path is exercised under PyFEX.
    for cfg_name, parse_fn in (
        ("setup.cfg", parse_setup_cfg_scripts),
        ("pyproject.toml", parse_pyproject_scripts),
    ):
        cfg = package_dir / cfg_name
        if not cfg.is_file():
            continue
        for name, spec in parse_fn(cfg):
            wrapper = write_console_script_entry(package_dir, name, spec)
            if wrapper is not None:
                add_entry(
                    entries,
                    seen,
                    EntryPoint(f"{cfg_name}:{name}", "console_script", path=wrapper),
                )

    for root in roots:
        for path in sorted(root.rglob("main.py")):
            if skip_entry_path(path, package_dir):
                continue
            module = module_name_from_path(path, roots)
            label = str(path.relative_to(package_dir))
            add_entry(entries, seen, EntryPoint(label, "main.py", path=None if module else path, module=module))

        for path in sorted(root.rglob("__main__.py")):
            if skip_entry_path(path, package_dir):
                continue
            module = module_name_from_path(path, roots)
            label = str(path.relative_to(package_dir))
            add_entry(entries, seen, EntryPoint(label, "__main__.py", path=None if module else path, module=module))

    top_level_names = read_top_level_names(package_dir, roots)
    for module in top_level_names:
        init_path = None
        for root in roots:
            candidate = root / module / "__init__.py"
            if candidate.is_file() and not skip_entry_path(candidate, package_dir):
                init_path = candidate
                break
        if init_path is not None:
            wrapper = write_import_entry(package_dir, module)
            add_entry(
                entries,
                seen,
                EntryPoint(str(init_path.relative_to(package_dir)), "__init__.py", path=wrapper, module=None),
            )
        else:
            for root in roots:
                candidate = root / f"{module}.py"
                if candidate.is_file() and not skip_entry_path(candidate, package_dir):
                    wrapper = write_import_entry(package_dir, module)
                    add_entry(entries, seen, EntryPoint(str(candidate.relative_to(package_dir)), "module.py", path=wrapper))
                    break

    if entries:
        return entries

    entry_path = package_dir / row["entry_path"]
    entry_args = tuple(row["entry_args"].split()) if row.get("entry_args") else ()
    if entry_path.is_file():
        add_entry(entries, seen, EntryPoint(row["entry_path"], row.get("entry_kind", "manifest"), path=entry_path, args=entry_args))
        return entries

    py_files = [path for path in sorted(package_dir.rglob("*.py")) if not skip_entry_path(path, package_dir)]
    if py_files:
        add_entry(entries, seen, EntryPoint(str(py_files[0].relative_to(package_dir)), "first-python-file", path=py_files[0]))
    return entries


def truncate_output(data: bytes, limit: int) -> str:
    text = data.decode("utf-8", errors="replace")
    if len(text) > limit:
        return text[:limit] + "\n[truncated]\n"
    return text


def write_simple_trace(trace_log: Path, simple_trace_log: Path) -> bool:
    if not trace_log.is_file():
        return False
    cmd = [
        sys.executable,
        str(SIMPLIFIER),
        str(trace_log),
        "--base-dir",
        str(REPO_ROOT),
        "-o",
        str(simple_trace_log),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.returncode == 0


def write_dfa_summary(package_dir: Path, dfa_logs: list[Path], trace_logs: list[Path], summary_path: Path) -> dict[str, int]:
    cmd = [
        sys.executable,
        str(SUMMARIZER),
        "--package-dir",
        str(package_dir),
        "-o",
        str(summary_path),
    ]
    for path in dfa_logs:
        cmd.extend(["--dfa-log", str(path)])
    for path in trace_logs:
        cmd.extend(["--trace-log", str(path)])

    proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stats = {
        "dfa_python_files": 0,
        "dfa_touched_files": 0,
        "dfa_untouched_files": 0,
        "dfa_defined_but_not_called": 0,
    }
    if proc.returncode != 0:
        return stats
    for token in proc.stdout.decode("utf-8", errors="replace").split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            parsed = int(value)
        except ValueError:
            continue
        if key == "python_files":
            stats["dfa_python_files"] = parsed
        elif key == "touched_files":
            stats["dfa_touched_files"] = parsed
        elif key == "untouched_files":
            stats["dfa_untouched_files"] = parsed
        elif key == "defined_but_not_called":
            stats["dfa_defined_but_not_called"] = parsed
    return stats


def run_dfa_replay(
    args: argparse.Namespace,
    package_dir: Path,
    dfa_logs: list[Path],
    log_dir: Path,
) -> dict[str, int]:
    """Actively invoke the package's dormant callables via tools/dfa_driver.py.

    The entrypoint runs only *log* which callables stayed dormant; this step
    actually executes them under crash recovery so their bodies run and emit
    traces. Dormant code may itself be malicious, so the driver -- and every
    per-dormant PyFEX subprocess it spawns -- runs inside the same OS network
    sandbox the entrypoints use (the spawned children inherit the unshare'd
    network namespace). Returns {"dfa_invoked": <count>}: the number of dormant
    callables the driver reported actually invoking."""
    combined = log_dir / "dfa_combined.log"
    invoke_log = log_dir / "dfa_invoke.log"
    combined.unlink(missing_ok=True)
    invoke_log.unlink(missing_ok=True)

    with combined.open("w", encoding="utf-8") as out:
        for path in dfa_logs:
            if path.is_file():
                out.write(path.read_text(encoding="utf-8", errors="replace"))
    if combined.stat().st_size == 0:
        return {"dfa_invoked": 0}

    env = os.environ.copy()
    env.update(
        {
            "PYFEX_INTERPRETER": str(PYFEX_INTERP),
            "DFA_INVOKE_LOG": str(invoke_log),
            "DFA_INVOKE_CAP": str(args.dfa_invoke_cap),
        }
    )
    cmd = [sys.executable, str(DFA_DRIVER), str(combined), str(package_dir)]
    if args.network == "blocked" and args.network_os_sandbox == "unshare":
        unshare = shutil.which("unshare")
        if unshare:
            cmd = [unshare, "--user", "--map-root-user", "--net", "--", *cmd]

    try:
        subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=args.dfa_invoke_timeout,
        )
    except subprocess.TimeoutExpired:
        pass

    invoked = 0
    if invoke_log.is_file():
        for line in invoke_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("invoked:"):
                invoked += 1
    return {"dfa_invoked": invoked}


def build_command(
    args: argparse.Namespace,
    entry: EntryPoint,
    package_dir: Path,
    pythonpath: str,
    home_dir: Path,
    trace_log: Path,
    runtime_log: Path,
    dfa_log: Path,
    network_log: Path,
) -> list[str]:
    cmd = [
        sys.executable,
        str(WRAPPER),
        "--crash-recovery-enable",
        "1",
        "--force-exec-enable",
        "1",
        "--force-exec-merge-enable",
        "1",
        "--force-exec-global-limit",
        str(args.force_exec_limit),
        "--force-exec-location-limit",
        str(args.force_exec_location_limit),
        "--force-exec-loop-iter-limit",
        str(args.loop_limit),
        "--pyfex-scope-dir",
        str(package_dir),
        "--pyfex-trace-log-file",
        str(trace_log),
        "--pyfex-runtime-log-file",
        str(runtime_log),
        "--dormant-func-log-file",
        str(dfa_log),
        "--cwd",
        str(package_dir),
        "--timeout",
        str(args.timeout),
        "--network",
        args.network,
        "--network-os-sandbox",
        args.network_os_sandbox,
        "--network-log-file",
        str(network_log),
        "--env",
        "PYTHONNOUSERSITE=1",
        "--env",
        f"HOME={home_dir}",
        "--env",
        f"PYTHONPATH={pythonpath}",
    ]
    if entry.module is not None:
        cmd.append("--module")
        cmd.append(entry.module)
    else:
        if entry.path is None:
            raise ValueError("entrypoint has neither path nor module")
        cmd.append(str(entry.path))
    if entry.args:
        cmd.append("--")
        cmd.extend(entry.args)
    return cmd


def run_entrypoint(
    args: argparse.Namespace,
    entry: EntryPoint,
    entry_index: int,
    package_dir: Path,
    pythonpath: str,
    home_dir: Path,
    log_dir: Path,
) -> dict[str, object]:
    entry_id = f"{entry_index:02d}_{slugify(entry.kind + '_' + entry.label)}"
    entry_log_dir = log_dir / entry_id
    entry_log_dir.mkdir(parents=True, exist_ok=True)

    trace_log = entry_log_dir / "behavior_trace.jsonl"
    simple_trace_log = entry_log_dir / "behavior_trace.simple.log"
    runtime_log = entry_log_dir / "runtime.log"
    dfa_log = entry_log_dir / "dfa.log"
    network_log = entry_log_dir / "network.log"
    dfa_summary = entry_log_dir / "dfa_summary.txt"
    stdout_log = entry_log_dir / "stdout.txt"
    stderr_log = entry_log_dir / "stderr.txt"
    for path in (trace_log, simple_trace_log, runtime_log, dfa_log, network_log, dfa_summary, stdout_log, stderr_log):
        path.unlink(missing_ok=True)

    cmd = build_command(args, entry, package_dir, pythonpath, home_dir, trace_log, runtime_log, dfa_log, network_log)
    if args.print_command:
        print(" ".join(cmd))

    start = time.time()
    proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    duration = time.time() - start

    stdout_log.write_text(truncate_output(proc.stdout, 200_000), encoding="utf-8")
    stderr_log.write_text(truncate_output(proc.stderr, 200_000), encoding="utf-8")
    network_log.touch(exist_ok=True)

    trace_rows, calls = count_jsonl_events(trace_log)
    simple_trace_ok = write_simple_trace(trace_log, simple_trace_log)
    runtime_lines, recoveries, forks = count_runtime_events(runtime_log)
    network_blocks = count_jsonl_lines(network_log)
    dfa_defined, dfa_called = count_dfa(dfa_log)
    dfa_stats = write_dfa_summary(package_dir, [dfa_log], [trace_log], dfa_summary)

    return {
        "entry_id": entry_id,
        "entry_label": entry.label,
        "entry_kind": entry.kind,
        "entry_path": str(entry.path.relative_to(package_dir)) if entry.path and entry.path.is_relative_to(package_dir) else "",
        "entry_module": entry.module or "",
        "entry_args": " ".join(entry.args),
        "returncode": proc.returncode,
        "timed_out": proc.returncode == 124,
        "duration_sec": round(duration, 3),
        "trace_rows": trace_rows,
        "function_call_events": calls,
        "simple_trace_generated": simple_trace_ok,
        "runtime_lines": runtime_lines,
        "recovery_events": recoveries,
        "fork_events": forks,
        "network_block_events": network_blocks,
        "dfa_defined": dfa_defined,
        "dfa_called": dfa_called,
        **dfa_stats,
        "stdout_path": str(stdout_log.relative_to(REPO_ROOT)),
        "stderr_path": str(stderr_log.relative_to(REPO_ROOT)),
        "trace_path": str(trace_log.relative_to(REPO_ROOT)),
        "simple_trace_path": str(simple_trace_log.relative_to(REPO_ROOT)),
        "runtime_path": str(runtime_log.relative_to(REPO_ROOT)),
        "network_path": str(network_log.relative_to(REPO_ROOT)),
        "dfa_path": str(dfa_log.relative_to(REPO_ROOT)),
        "dfa_summary_path": str(dfa_summary.relative_to(REPO_ROOT)),
        "command": " ".join(cmd),
    }


def write_entry_results(log_dir: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    csv_path = log_dir / "entrypoints.csv"
    jsonl_path = log_dir / "entrypoints.jsonl"
    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    with jsonl_path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")


def upsert_result(samples_dir: Path, result: dict[str, object]) -> None:
    csv_path = samples_dir / "results.csv"
    jsonl_path = samples_dir / "results.jsonl"
    rows: list[dict[str, object]] = []
    if csv_path.is_file():
        with csv_path.open("r", encoding="utf-8", newline="") as fp:
            rows = list(csv.DictReader(fp))

    rows = [row for row in rows if row.get("sample_id") != result["sample_id"]]
    rows.append(result)
    rows.sort(key=lambda row: int(str(row["rank"])))

    with csv_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(result.keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with jsonl_path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, sort_keys=True) + "\n")

    lines = [
        "# One-by-One PyFEX Sample Results",
        "",
        "| Rank | Sample | Category | Entrypoints | RC | Timeout | Calls | Recoveries | Forks | Network blocks | DFA defined/called | Untouched files | Duration s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {rank} | `{sample}` | {category} | {entrypoints} | {rc} | {timeout} | {calls} | {recoveries} | {forks} | {network_blocks} | {dfa_defined}/{dfa_called} | {untouched} | {duration} |".format(
                rank=row["rank"],
                sample=row["sample_id"],
                category=row["category"],
                entrypoints=row.get("entrypoint_count", row.get("entry_kind", "")),
                rc=row["returncode"],
                timeout=row["timed_out"],
                calls=row["function_call_events"],
                recoveries=row["recovery_events"],
                forks=row["fork_events"],
                network_blocks=row.get("network_block_events", ""),
                dfa_defined=row["dfa_defined"],
                dfa_called=row["dfa_called"],
                untouched=row.get("dfa_untouched_files", ""),
                duration=row["duration_sec"],
            )
        )
    (samples_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-dir", default=str(DEFAULT_SAMPLES_DIR))
    parser.add_argument("--rank", type=int, default=None, help="Rank from selection_manifest.csv.")
    parser.add_argument("--sample-id", default=None, help="Sample id from selection_manifest.csv.")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--force-exec-limit", type=int, default=12)
    parser.add_argument("--force-exec-location-limit", type=int, default=2)
    parser.add_argument("--loop-limit", type=int, default=50)
    parser.add_argument("--network", choices=("blocked", "host"), default="blocked")
    parser.add_argument(
        "--network-os-sandbox",
        choices=("unshare", "none"),
        default="unshare",
        help="OS network sandbox when --network=blocked. Default: unshare.",
    )
    parser.add_argument(
        "--dfa-invoke",
        action="store_true",
        help="After entrypoints run, actively invoke dormant callables via "
        "tools/dfa_driver.py (executes possibly-malicious dormant code inside "
        "the same network sandbox). Off by default.",
    )
    parser.add_argument("--dfa-invoke-cap", type=int, default=32, help="Max dormant callables to invoke (DFA_INVOKE_CAP).")
    parser.add_argument("--dfa-invoke-timeout", type=float, default=120.0, help="Wall-clock timeout for the DFA replay step.")
    parser.add_argument("--print-command", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    samples_dir = Path(args.samples_dir).resolve()
    row = select_row(load_manifest(samples_dir), args.rank, args.sample_id)

    sample_id = row["sample_id"]
    package_dir = (REPO_ROOT / row["copied_path"]).resolve()
    pythonpath = build_pythonpath(package_dir, row)
    entrypoints = discover_entrypoints(package_dir, row)
    if not entrypoints:
        raise SystemExit(f"No Python entrypoints found for {sample_id}")

    log_dir = samples_dir / "logs" / sample_id
    work_dir = samples_dir / "work" / sample_id
    home_dir = work_dir / "home"
    for path in (log_dir, work_dir, home_dir):
        path.mkdir(parents=True, exist_ok=True)

    sample_start = time.time()
    entry_results = [
        run_entrypoint(args, entry, index, package_dir, pythonpath, home_dir, log_dir)
        for index, entry in enumerate(entrypoints, 1)
    ]
    duration = time.time() - sample_start
    write_entry_results(log_dir, entry_results)

    dfa_summary_path = log_dir / "dfa_summary.txt"
    aggregate_dfa_stats = write_dfa_summary(
        package_dir,
        [REPO_ROOT / str(row["dfa_path"]) for row in entry_results],
        [REPO_ROOT / str(row["trace_path"]) for row in entry_results],
        dfa_summary_path,
    )

    dfa_replay_stats = {"dfa_invoked": 0}
    if args.dfa_invoke:
        dfa_replay_stats = run_dfa_replay(
            args,
            package_dir,
            [REPO_ROOT / str(row["dfa_path"]) for row in entry_results],
            log_dir,
        )

    first_nonzero = next((int(row["returncode"]) for row in entry_results if int(row["returncode"]) != 0), 0)
    timed_out = any(bool(row["timed_out"]) for row in entry_results)

    result = {
        "rank": int(row["rank"]),
        "sample_id": sample_id,
        "package_name": row["package_name"],
        "category": row["category"],
        "entrypoint_count": len(entry_results),
        "entrypoints": ",".join(str(entry["entry_id"]) for entry in entry_results),
        "returncode": first_nonzero,
        "timed_out": timed_out,
        "duration_sec": round(duration, 3),
        "cwd_path": str(package_dir.relative_to(REPO_ROOT)),
        "pythonpath": pythonpath,
        "trace_rows": sum(int(row["trace_rows"]) for row in entry_results),
        "function_call_events": sum(int(row["function_call_events"]) for row in entry_results),
        "simple_trace_generated": all(bool(row["simple_trace_generated"]) for row in entry_results),
        "runtime_lines": sum(int(row["runtime_lines"]) for row in entry_results),
        "recovery_events": sum(int(row["recovery_events"]) for row in entry_results),
        "fork_events": sum(int(row["fork_events"]) for row in entry_results),
        "network_block_events": sum(int(row["network_block_events"]) for row in entry_results),
        "dfa_defined": sum(int(row["dfa_defined"]) for row in entry_results),
        "dfa_called": sum(int(row["dfa_called"]) for row in entry_results),
        **aggregate_dfa_stats,
        **dfa_replay_stats,
        "logs_dir": str(log_dir.relative_to(REPO_ROOT)),
        "entry_results_path": str((log_dir / "entrypoints.csv").relative_to(REPO_ROOT)),
        "dfa_summary_path": str(dfa_summary_path.relative_to(REPO_ROOT)),
    }
    upsert_result(samples_dir, result)

    print(
        "rank={rank} sample={sample_id} rc={returncode} timeout={timed_out} "
        "entrypoints={entrypoint_count} calls={function_call_events} "
        "recoveries={recovery_events} forks={fork_events} net_blocks={network_block_events} dfa={dfa_defined}/{dfa_called} "
        "dfa_invoked={dfa_invoked} untouched_files={dfa_untouched_files} duration={duration_sec}s".format(**result)
    )
    print(f"logs={log_dir.relative_to(REPO_ROOT)}")
    return first_nonzero


if __name__ == "__main__":
    raise SystemExit(main())
