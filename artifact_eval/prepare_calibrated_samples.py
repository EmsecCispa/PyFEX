#!/usr/bin/env python3
"""Prepare a deterministic 100-package sample set without executing it."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "Dataset"
DEFAULT_SAMPLES_DIR = REPO_ROOT / "artifact_eval" / "samples"


@dataclass(frozen=True)
class PackageInfo:
    name: str
    source: Path
    category: str
    py_files: int
    has_setup: bool
    has_pyproject: bool
    has_dist_info: bool
    has_egg_info: bool
    has_src_layout: bool
    has_main: bool


def stable_rank(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_py_files(root: Path) -> int:
    return sum(1 for _ in root.rglob("*.py"))


def classify_package(path: Path) -> PackageInfo:
    has_setup = (path / "setup.py").is_file()
    has_pyproject = (path / "pyproject.toml").is_file()
    has_dist_info = any(p.is_dir() and p.name.endswith(".dist-info") for p in path.iterdir())
    has_egg_info = any(p.is_dir() and p.name.endswith(".egg-info") for p in path.iterdir())
    has_src_layout = (path / "src").is_dir()
    has_main = any(p.name == "__main__.py" for p in path.rglob("__main__.py"))
    py_files = count_py_files(path)

    if has_src_layout:
        category = "src-layout"
    elif has_dist_info and not has_setup:
        category = "wheel-unpacked"
    elif has_setup and has_pyproject:
        category = "pep517-sdist"
    elif has_setup:
        category = "setup-sdist"
    elif has_main:
        category = "module-main"
    elif py_files <= 2:
        category = "small-module"
    else:
        category = "other-package"

    return PackageInfo(
        name=path.name,
        source=path,
        category=category,
        py_files=py_files,
        has_setup=has_setup,
        has_pyproject=has_pyproject,
        has_dist_info=has_dist_info,
        has_egg_info=has_egg_info,
        has_src_layout=has_src_layout,
        has_main=has_main,
    )


def select_representative(packages: list[PackageInfo], count: int) -> list[PackageInfo]:
    groups: dict[str, list[PackageInfo]] = {}
    for package in packages:
        groups.setdefault(package.category, []).append(package)
    for values in groups.values():
        values.sort(key=lambda p: stable_rank(p.name))

    selected: list[PackageInfo] = []
    selected_names: set[str] = set()
    categories = sorted(groups)
    index = 0

    while len(selected) < count and any(index < len(groups[c]) for c in categories):
        for category in categories:
            if len(selected) >= count:
                break
            values = groups[category]
            if index < len(values):
                package = values[index]
                selected.append(package)
                selected_names.add(package.name)
        index += 1

    if len(selected) < count:
        remaining = [p for p in packages if p.name not in selected_names]
        remaining.sort(key=lambda p: stable_rank(p.name))
        selected.extend(remaining[: count - len(selected)])

    return selected[:count]


def dir_size_bytes(path: Path) -> int:
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                pass
    return total


def import_roots(package_dir: Path) -> list[Path]:
    roots = [package_dir]
    src = package_dir / "src"
    if src.is_dir():
        roots.append(src)
    return roots


def import_roots_manifest(package_dir: Path) -> str:
    values: list[str] = []
    for root in import_roots(package_dir):
        values.append("." if root == package_dir else str(root.relative_to(package_dir)))
    return os.pathsep.join(values)


def read_top_level_names(package_dir: Path) -> list[str]:
    names: list[str] = []
    for info_dir in list(package_dir.glob("*.dist-info")) + list(package_dir.glob("*.egg-info")):
        top_level = info_dir / "top_level.txt"
        if top_level.is_file():
            for line in top_level.read_text(encoding="utf-8", errors="replace").splitlines():
                name = line.strip()
                if name and name.isidentifier():
                    names.append(name)

    if not names:
        for root in import_roots(package_dir):
            for child in sorted(root.iterdir()):
                if child.name.startswith(".") or child.name.startswith("_pyfex_"):
                    continue
                if child.name.endswith((".egg-info", ".dist-info", "__pycache__")):
                    continue
                if child.is_dir() and (child / "__init__.py").is_file() and child.name.isidentifier():
                    names.append(child.name)
                elif child.is_file() and child.suffix == ".py":
                    if child.stem not in {"setup", "__main__"} and child.stem.isidentifier():
                        names.append(child.stem)

    if not names:
        for child in sorted((package_dir / "src").rglob("*.py") if (package_dir / "src").is_dir() else []):
            if child.name in {"setup.py", "__main__.py", "__init__.py"}:
                continue
            if child.stem.isidentifier():
                names.append(child.stem)
                break

    return sorted(set(names))


def write_import_entry(package_dir: Path, modules: list[str]) -> Path:
    entry = package_dir / "_pyfex_import_entry.py"
    roots = import_roots_manifest(package_dir).split(os.pathsep)
    entry.write_text(
        "import importlib\n"
        "import pathlib\n"
        "import sys\n"
        "ROOT = pathlib.Path(__file__).resolve().parent\n"
        f"IMPORT_ROOTS = {roots!r}\n"
        "for rel in IMPORT_ROOTS:\n"
        "    candidate = ROOT if rel == '.' else ROOT / rel\n"
        "    if candidate.is_dir() and str(candidate) not in sys.path:\n"
        "        sys.path.insert(0, str(candidate))\n"
        f"MODULES = {modules!r}\n"
        "print('[pyfex-entry] modules=' + ','.join(MODULES))\n"
        "for name in MODULES:\n"
        "    print('[pyfex-entry] import ' + name)\n"
        "    importlib.import_module(name)\n",
        encoding="utf-8",
    )
    return entry


def choose_entry(package_dir: Path) -> tuple[str, Path, list[str]]:
    setup = package_dir / "setup.py"
    if setup.is_file():
        return "setup.py", setup, ["--name"]

    mains = sorted(package_dir.rglob("__main__.py"))
    if mains:
        return "__main__.py", mains[0], []

    modules = read_top_level_names(package_dir)
    if modules:
        return "import-top-level", write_import_entry(package_dir, modules), []

    py_files = sorted(package_dir.rglob("*.py"))
    if py_files:
        return "first-python-file", py_files[0], []

    return "no-python-entry", write_import_entry(package_dir, []), []


def archive_existing(samples_dir: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    archive = samples_dir.with_name(f"{samples_dir.name}.archive-{stamp}")
    suffix = 1
    while archive.exists():
        archive = samples_dir.with_name(f"{samples_dir.name}.archive-{stamp}-{suffix}")
        suffix += 1
    samples_dir.rename(archive)
    return archive


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Dataset root containing package directories.")
    parser.add_argument("--samples-dir", default=str(DEFAULT_SAMPLES_DIR), help="Output directory for selected samples.")
    parser.add_argument("--count", type=int, default=100, help="Number of package samples to select.")
    parser.add_argument(
        "--include-non-setup",
        action="store_true",
        help="Also allow packages without setup.py, using generated import/__main__ fallbacks.",
    )
    parser.add_argument(
        "--archive-existing",
        action="store_true",
        help="Move an existing samples directory aside before creating a fresh one.",
    )
    parser.add_argument("--force", action="store_true", help="Delete an existing samples output directory first.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = Path(args.dataset).resolve()
    samples_dir = Path(args.samples_dir).resolve()

    if not dataset.is_dir():
        raise SystemExit(f"Dataset directory not found: {dataset}")
    if samples_dir.exists():
        if args.archive_existing:
            archive = archive_existing(samples_dir)
            print(f"Archived existing samples directory to {archive}")
        elif not args.force:
            raise SystemExit(f"Output directory already exists; use --force to replace: {samples_dir}")
        else:
            shutil.rmtree(samples_dir)

    packages_dir = samples_dir / "packages"
    logs_dir = samples_dir / "logs"
    work_dir = samples_dir / "work"
    for path in (packages_dir, logs_dir, work_dir):
        path.mkdir(parents=True, exist_ok=True)

    packages = [classify_package(path) for path in sorted(dataset.iterdir()) if path.is_dir()]
    if not args.include_non_setup:
        packages = [package for package in packages if package.has_setup]
    if len(packages) < args.count:
        raise SystemExit(f"Only {len(packages)} eligible packages found for --count {args.count}")
    selected = select_representative(packages, args.count)

    rows: list[dict[str, object]] = []
    for rank, package in enumerate(selected, 1):
        sample_id = f"{rank:03d}_{package.name}"
        copied = packages_dir / sample_id
        shutil.copytree(package.source, copied)
        entry_kind, entry_path, entry_args = choose_entry(copied)
        rows.append(
            {
                "rank": rank,
                "sample_id": sample_id,
                "package_name": package.name,
                "source_path": str(package.source.relative_to(REPO_ROOT)),
                "copied_path": str(copied.relative_to(REPO_ROOT)),
                "category": package.category,
                "py_files": package.py_files,
                "size_bytes": dir_size_bytes(copied),
                "entry_kind": entry_kind,
                "entry_path": str(entry_path.relative_to(copied)),
                "entry_args": " ".join(entry_args),
                "entrypoint_policy": "setup+main+__main__+top-level-__init__",
                "import_roots": import_roots_manifest(copied),
                "has_setup": package.has_setup,
                "has_pyproject": package.has_pyproject,
                "has_dist_info": package.has_dist_info,
                "has_egg_info": package.has_egg_info,
                "has_src_layout": package.has_src_layout,
                "has_main": package.has_main,
                "stable_hash": stable_rank(package.name),
            }
        )

    write_csv(samples_dir / "selection_manifest.csv", rows)
    (samples_dir / "README.md").write_text(
        "# Selected Calibrated Samples\n\n"
        "This directory contains a deterministic, stratified 100-package subset "
        "copied from `Dataset`.\n\n"
        "By default, selected samples have a root `setup.py`, which is the "
        "first artifact-evaluation entry point. `run_one_calibrated_sample.py` "
        "also discovers and runs package `main.py`, `__main__.py`, and "
        "top-level package `__init__.py` entrypoints when present. Pass "
        "`--include-non-setup` to include wheel/pyproject-only packages that "
        "require fallback entry selection.\n\n"
        "- `selection_manifest.csv`: selected samples, source paths, categories, and entrypoints.\n"
        "- `packages/`: copied package directories.\n"
        "- `logs/`: per-sample outputs created by `run_one_calibrated_sample.py`.\n"
        "- `work/`: per-sample working directories and HOME directories for execution.\n\n"
        "Run samples one at a time, for example:\n\n"
        "```bash\n"
        "python3 artifact_eval/run_one_calibrated_sample.py --rank 1\n"
        "```\n",
        encoding="utf-8",
    )

    print(f"Prepared {len(rows)} samples under {samples_dir}")
    print(f"Wrote {samples_dir / 'selection_manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
