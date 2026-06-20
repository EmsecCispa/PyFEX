"""DummyObject nb_index (dummy_index) and tp_hash (dummy_hash) slots.

Two slots were added to PyDummy_Type (Objects/dummyobject.c):

  nb_index (dummy_index)  -- returns a real int 0 (like dummy_int/dummy_float),
                            so a dummy is usable wherever __index__ is required:
                            list[dummy], a dummy-bounded slice, "%d" % dummy.
                            Under the OLD code list[dummy] produced a dummy via
                            the BINARY_SUBSCR crash-recovery path; with nb_index
                            it indexes for real, so [10, 20, 30][dummy] -> 10 and
                            the result is a concrete int, NOT a dummy. That is the
                            load-bearing, non-tautological guard here.

  tp_hash (dummy_hash)    -- returns a fixed constant 1 for EVERY dummy. Without a
                            tp_hash a type defining tp_richcompare is unhashable
                            ("unhashable type: 'DummyObject'"), so a dummy could
                            not be a dict key or set member. dummy_richcompare
                            propagates an always-truthy dummy for ==, so any two
                            dummies compare "equal" and therefore MUST hash equal
                            to preserve the hash/eq invariant. The consequence is
                            that all dummies collapse to a single dict/set key.

The target uses DIRECT subscript / slice / "%d" / dict-key / set-member contexts.
It deliberately does NOT route a dummy through a builtin CALL (range(dummy),
hex(dummy), bool(dummy), dict.get(dummy)): a dummy passed as a call ARGUMENT is
short-circuited by the separate CALL_FUNCTION crash-recovery path (returns a
dummy) BEFORE nb_index/tp_hash are consulted -- pre-existing, orthogonal
behaviour that would make call-based assertions misleading.

Crash recovery only (no forced execution) -> no fork-bomb risk.

This harness is run by the SYSTEM python3 because the artifact runner's
clean_env() strips CRASH_RECOVERY_ENABLE (so a registered case cannot rely on an
externally set CR env). It writes the target to a tempfile and spawns the built
PyFEX-core/python itself with CRASH_RECOVERY_ENABLE=1, then asserts the
deterministic markers in stdout.

Run directly:
    python3 artifact_eval/tests/implemented_dummy_hash_index.py
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

TARGET_SRC = textwrap.dedent(
    '''
    x = undefined_seed              # NameError -> leaf dummy (LOAD_NAME recovery)

    # nb_index: dummy stands in as 0 in direct index/slice/format contexts.
    print("IDX|", [10, 20, 30][x])  # -> 10, a concrete int (NOT a dummy)
    print("ITYPE|", type([10, 20, 30][x]).__name__)
    print("SLICE|", [1, 2, 3, 4][x:x])  # dummy-bounded slice -> []
    print("FMT|", "%d" % x)         # __index__/format -> 0

    # tp_hash: dummy usable as a dict key / set member; all dummies collapse.
    d = {}
    d[x] = "a"
    print("DGET_A|", d[x])          # -> a (round-trips by hash/eq)
    print("IN|", x in {x})          # -> True
    y = x + 1                       # a structurally different dummy
    d[y] = "b"                      # collapses onto the same single key
    print("DLEN|", len(d))          # -> 1
    print("DGET_B|", d[x])          # -> b
    print("HASHEQ|", hash(x) == hash(y))  # equal dummies hash equal -> True
    '''
)


EXPECTED = {
    "IDX": "10",
    "ITYPE": "int",
    "SLICE": "[]",
    "FMT": "0",
    "DGET_A": "a",
    "IN": "True",
    "DLEN": "1",
    "DGET_B": "b",
    "HASHEQ": "True",
}


def parse_markers(output: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in output.splitlines():
        if "|" not in line:
            continue
        key, _, value = line.partition("|")
        found[key.strip()] = value.strip()
    return found


def main() -> int:
    env = os.environ.copy()
    env["CRASH_RECOVERY_ENABLE"] = "1"

    work_dir = Path(tempfile.mkdtemp(prefix="pyfex_ae_hashidx_"))
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
    output = proc.stdout

    failures: list[str] = []
    if proc.returncode != 0:
        failures.append(f"target exited {proc.returncode} (expected 0)")
    for bad in ("unhashable", "TypeError"):
        if bad in output:
            failures.append(f"output contains forbidden token {bad!r}")

    found = parse_markers(output)
    for key, want in EXPECTED.items():
        if key not in found:
            failures.append(f"marker {key} missing")
        elif found[key] != want:
            failures.append(f"{key}: expected {want!r}, got {found[key]!r}")

    if failures:
        print("FAIL: dummy nb_index / tp_hash slots")
        for f in failures:
            print("  - " + f)
        print("---- target output ----")
        print(output)
        return 1

    print("PASS: dummy nb_index indexes as 0 (real int); tp_hash makes dummies "
          "hashable and collapse to one key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
