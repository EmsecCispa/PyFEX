"""Declared console/GUI entry-point discovery (the "C9" feature).

run_one_calibrated_sample.py now reads console_scripts / gui_scripts declared in
setup.cfg ([options.entry_points]) and pyproject.toml ([project.scripts] /
[project.gui-scripts]), and for each one generates a `_pyfex_entrypoint_*.py`
wrapper that imports `module`, walks the dotted attr path after the `:`, and
calls the resulting object if callable -- mirroring pip's generated console
scripts. This test covers the three parser/writer helpers and their wiring into
discover_entrypoints.

It must run under BOTH the PyFEX 3.10 interpreter (no tomllib -> the pyproject
parser uses its FALLBACK section reader) and system python3 (3.12 -> real
tomllib). The parsed result is identical either way, so we assert on the result,
not the path; step 4 additionally pins the fallback explicitly on any host.

Run:
  python3 artifact_eval/tests/implemented_entrypoint_discovery.py        # 3.12: tomllib
  PyFEX-core/python artifact_eval/tests/implemented_entrypoint_discovery.py  # 3.10: fallback
"""

from __future__ import annotations

import builtins
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERP = REPO_ROOT / "PyFEX-core" / "python"

sys.path.insert(0, str(REPO_ROOT / "artifact_eval"))
import run_one_calibrated_sample as R  # noqa: E402


def build_package(root: Path, marker: Path) -> Path:
    pkg = root / "pkgsrc"
    (pkg / "mypkg").mkdir(parents=True)
    (pkg / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mypkg" / "cli.py").write_text(
        textwrap.dedent(
            f"""
            MARKER = {str(marker)!r}

            def main():
                with open(MARKER, "a", encoding="utf-8") as fp:
                    fp.write("main-ran\\n")

            def gui_main():
                with open(MARKER, "a", encoding="utf-8") as fp:
                    fp.write("gui-ran\\n")
            """
        ),
        encoding="utf-8",
    )
    # A setup.py so discover_entrypoints emits the setup.py entry first; the
    # console_script entries must be inserted right after it.
    (pkg / "setup.py").write_text("from setuptools import setup\nsetup()\n", encoding="utf-8")
    # console_scripts (foo) + gui_scripts (guiapp) under [options.entry_points];
    # the indented `name = module:callable` lines are continuation lines that
    # configparser folds into one value.
    (pkg / "setup.cfg").write_text(
        textwrap.dedent(
            """
            [metadata]
            name = mypkg

            [options.entry_points]
            console_scripts =
                foo = mypkg.cli:main
            gui_scripts =
                guiapp = mypkg.cli:gui_main
            """
        ).lstrip(),
        encoding="utf-8",
    )
    # [project.scripts] (baz) + [project.gui-scripts] (guibaz). The unrelated
    # [project.urls] table must be ignored by parse_pyproject_scripts.
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "mypkg"
            version = "0.0.1"

            [project.scripts]
            baz = "mypkg.cli:main"

            [project.gui-scripts]
            guibaz = "mypkg.cli:gui_main"

            [project.urls]
            Homepage = "https://urls-table.example"
            Source = "https://urls-table.example/src"
            """
        ).lstrip(),
        encoding="utf-8",
    )
    return pkg


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="pyfex_ae_entrypoint_"))
    marker = work / "marker.log"
    pkg = build_package(work, marker)

    # 2) setup.cfg: ordered console_scripts then gui_scripts, folding respected.
    cfg = R.parse_setup_cfg_scripts(pkg / "setup.cfg")
    expected_cfg = [("foo", "mypkg.cli:main"), ("guiapp", "mypkg.cli:gui_main")]
    if cfg != expected_cfg:
        print(f"FAIL: parse_setup_cfg_scripts -> {cfg}, expected {expected_cfg}")
        return 1

    # 3) pyproject: [project.scripts] + [project.gui-scripts], [project.urls]
    # ignored. Compare as a set (membership is what the helper guarantees).
    pyp = R.parse_pyproject_scripts(pkg / "pyproject.toml")
    expected_pyp = {("baz", "mypkg.cli:main"), ("guibaz", "mypkg.cli:gui_main")}
    if set(pyp) != expected_pyp:
        print(f"FAIL: parse_pyproject_scripts -> {pyp}, expected {sorted(expected_pyp)}")
        return 1
    if any("urls-table.example" in spec for _name, spec in pyp):
        print(f"FAIL: [project.urls] leaked into pyproject scripts: {pyp}")
        return 1

    # 4) Pin the FALLBACK explicitly on any host: make tomllib AND tomli
    # unimportable, re-parse, and require the identical result.
    real_import = builtins.__import__

    def no_toml(name, *a, **k):
        if name in ("tomllib", "tomli"):
            raise ImportError(f"blocked {name} for fallback test")
        return real_import(name, *a, **k)

    builtins.__import__ = no_toml
    try:
        pyp_fallback = R.parse_pyproject_scripts(pkg / "pyproject.toml")
    finally:
        builtins.__import__ = real_import
    if set(pyp_fallback) != expected_pyp:
        print(f"FAIL: fallback pyproject parse -> {pyp_fallback}, expected {sorted(expected_pyp)}")
        return 1

    # 5) Generate the wrapper and run it under PyFEX (crash-recovery only -> no
    # fork-bomb risk). Assert main() body ran (marker) and the wrapper printed
    # its console_script line.
    wrapper = R.write_console_script_entry(pkg, "foo", "mypkg.cli:main")
    if wrapper is None or not Path(wrapper).is_file():
        print(f"FAIL: write_console_script_entry returned {wrapper}")
        return 1
    env = os.environ.copy()
    env["PYTHONPATH"] = str(pkg)
    env["CRASH_RECOVERY_ENABLE"] = "1"
    proc = subprocess.run(
        [str(INTERP), str(wrapper)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    marker_text = marker.read_text(encoding="utf-8") if marker.exists() else ""
    if proc.returncode != 0:
        print(proc.stdout)
        print(f"FAIL: wrapper subprocess exited {proc.returncode}")
        return 1
    if "main-ran" not in marker_text:
        print(f"FAIL: main() body did not run. marker={marker_text!r} stdout={proc.stdout!r}")
        return 1
    if "[pyfex-entry] console_script mypkg.cli:main" not in proc.stdout:
        print(f"FAIL: wrapper did not print its console_script line. stdout={proc.stdout!r}")
        return 1

    # 6) Spec edge cases: module-only (no colon) -> path returned (imports the
    # module); only-attrs (no module) -> None.
    module_only = R.write_console_script_entry(pkg, "x", "no_colon_module_only")
    if module_only is None or not Path(module_only).is_file():
        print(f"FAIL: module-only spec returned {module_only}, expected a wrapper path")
        return 1
    attrs_only = R.write_console_script_entry(pkg, "y", ":justattrs")
    if attrs_only is not None:
        print(f"FAIL: module-less spec ':justattrs' returned {attrs_only}, expected None")
        return 1

    # 7) Integration: discover_entrypoints must emit a console_script entry whose
    # label is prefixed with the source file (setup.cfg: / pyproject.toml:).
    # import_roots reads row.get("import_roots", "") (empty -> package_dir); the
    # row["entry_path"] fallback is never reached because entries are found.
    row = {"import_roots": ""}
    entries = R.discover_entrypoints(pkg, row)
    console = [e for e in entries if e.kind == "console_script"]
    if not console:
        labels = [(e.label, e.kind) for e in entries]
        print(f"FAIL: discover_entrypoints emitted no console_script entry. got={labels}")
        return 1
    if not any(
        e.label.startswith("setup.cfg:") or e.label.startswith("pyproject.toml:")
        for e in console
    ):
        print(f"FAIL: console_script labels not source-prefixed: {[e.label for e in console]}")
        return 1

    print("PASS: declared console/GUI entry points parsed, wrapped, and discovered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
