"""Dual-mode DummyObject provenance controlled by PYFEX_PROVENANCE_MODE.

A crash-recovery DummyObject records how it was produced. The mode is read once,
lazily, from PYFEX_PROVENANCE_MODE (Objects/dummyobject.c):

  recursive  -- per propagation a symbolic operand record is retained in
                ->original_operands, so .provenance renders a NESTED expression
                (e.g. SUBSCRIPT(ADD(dummy, 1), 2)); str(dummy) ends with
                "; provenance: <expr>"; .trace gains a "Symbolic provenance:"
                section. Op labels are the uppercased operation name
                (add->ADD, subscript->SUBSCRIPT, getattr->GETATTR, negate->NEGATIVE).

  flat (default / unset / any non-"recursive" value) -- historical behaviour:
                a flat append-log only; ->original_operands stays None; no operand
                refs retained. .provenance is the bare leaf "dummy" for every
                dummy; str(dummy) shows the "; lineage[N] ops: ..." suffix and NO
                "provenance:"; .trace has NO "Symbolic provenance:" section.

This harness is run by the SYSTEM python3 because the artifact runner's
clean_env() strips PYFEX_* (so a registered case cannot rely on an externally set
PYFEX_PROVENANCE_MODE). It spawns the built PyFEX-core/python itself with the
env each mode needs and asserts the deterministic outputs of both modes. The
flat-mode assertions are the load-bearing back-compat / zero-overhead-by-default
guard.

Run directly:
    python3 artifact_eval/tests/implemented_recursive_provenance.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERP = REPO_ROOT / "PyFEX-core" / "python"

# Delimited markers so multi-line values (str(z), z.trace) survive extraction.
BEGIN = "<<<PROV:{key}>>>"
END = "<<<END:{key}>>>"

TARGET_SRC = textwrap.dedent(
    '''
    x = undefined_name_xyz      # NameError -> leaf dummy
    y = x + 1                   # ADD(dummy, 1)
    z = y[2]                    # SUBSCRIPT(ADD(dummy, 1), 2)
    w = -z                      # NEGATIVE(SUBSCRIPT(ADD(dummy, 1), 2))
    a = x.foo                   # GETATTR(dummy, 'foo')

    def emit(key, value):
        print("<<<PROV:%s>>>" % key)
        print(value, end="")
        print("\\n<<<END:%s>>>" % key)

    emit("z_prov", z.provenance)
    emit("w_prov", w.provenance)
    emit("a_prov", a.provenance)
    emit("z_str", str(z))
    emit("z_trace", z.trace)
    '''
)


def extract(output: str, key: str) -> str:
    begin = BEGIN.format(key=key)
    end = END.format(key=key)
    if begin not in output or end not in output:
        raise AssertionError(f"marker {key} missing from output")
    body = output.split(begin, 1)[1].split(end, 1)[0]
    # emit() prints a newline after BEGIN and a newline before END.
    return body[1:-1]


def run(mode: str | None) -> tuple[str, subprocess.CompletedProcess[str]]:
    env = os.environ.copy()
    # Strip any inherited mode so the flat run is truly default.
    env.pop("PYFEX_PROVENANCE_MODE", None)
    env["CRASH_RECOVERY_ENABLE"] = "1"
    if mode is not None:
        env["PYFEX_PROVENANCE_MODE"] = mode

    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_prov_"))
    target = work_dir / "target.py"
    target.write_text(TARGET_SRC, encoding="utf-8")

    proc = subprocess.run(
        [str(INTERP), str(target)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return proc.stdout, proc


def main() -> int:
    rec_out, rec_proc = run("recursive")
    flat_out, flat_proc = run(None)

    failures: list[str] = []

    if rec_proc.returncode != 0:
        failures.append(f"recursive run exited {rec_proc.returncode}")
    if flat_proc.returncode != 0:
        failures.append(f"flat run exited {flat_proc.returncode}")

    if not failures:
        try:
            r_z = extract(rec_out, "z_prov")
            r_w = extract(rec_out, "w_prov")
            r_a = extract(rec_out, "a_prov")
            r_str = extract(rec_out, "z_str")
            r_trace = extract(rec_out, "z_trace")

            f_z = extract(flat_out, "z_prov")
            f_str = extract(flat_out, "z_str")
            f_trace = extract(flat_out, "z_trace")
        except AssertionError as exc:
            failures.append(str(exc))
        else:
            # ---- recursive mode: nested symbolic expression ----
            if r_z != "SUBSCRIPT(ADD(dummy, 1), 2)":
                failures.append(f"recursive z.provenance != expected: {r_z!r}")
            if r_w != "NEGATIVE(SUBSCRIPT(ADD(dummy, 1), 2))":
                failures.append(f"recursive w.provenance != expected: {r_w!r}")
            if r_a != "GETATTR(dummy, 'foo')":
                failures.append(f"recursive a.provenance != expected: {r_a!r}")
            if "; provenance: SUBSCRIPT(ADD(dummy, 1), 2)" not in r_str:
                failures.append(f"recursive str(z) missing provenance suffix: {r_str!r}")
            if "Symbolic provenance:" not in r_trace:
                failures.append("recursive z.trace missing 'Symbolic provenance:' section")
            if "SUBSCRIPT(ADD(dummy, 1), 2)" not in r_trace:
                failures.append("recursive z.trace missing the symbolic expression")

            # ---- flat mode: back-compat guard (must stay default behaviour) ----
            if f_z != "dummy":
                failures.append(f"flat z.provenance must be bare 'dummy', got: {f_z!r}")
            if "lineage[" not in f_str:
                failures.append(f"flat str(z) missing 'lineage[' suffix: {f_str!r}")
            if "provenance:" in f_str:
                failures.append(f"flat str(z) must NOT contain 'provenance:': {f_str!r}")
            if "Symbolic provenance:" in f_trace:
                failures.append("flat z.trace must NOT contain 'Symbolic provenance:'")

    if failures:
        print("FAIL: recursive provenance dual-mode")
        for f in failures:
            print("  - " + f)
        print("---- recursive output ----")
        print(rec_out)
        print("---- flat output ----")
        print(flat_out)
        return 1

    print("PASS: PYFEX_PROVENANCE_MODE recursive renders nested expr; flat stays leaf 'dummy'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
