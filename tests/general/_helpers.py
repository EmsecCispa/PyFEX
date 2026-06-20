import dis
import os
import time
from pathlib import Path


TMP_ROOT = Path("/tmp/pyfex-unit-test")
TMP_ROOT.mkdir(parents=True, exist_ok=True)


def assert_opcode(func, opname):
    opnames = [instr.opname for instr in dis.get_instructions(func)]
    assert opname in opnames, f"{func.__name__} does not contain opcode {opname}: {opnames}"


def assert_any_opcode(func, opnames):
    actual = [instr.opname for instr in dis.get_instructions(func)]
    expected = tuple(opnames)
    assert any(opname in actual for opname in expected), (
        f"{func.__name__} does not contain any of {expected}: {actual}"
    )


def fresh_path(stem, suffix=".log"):
    return TMP_ROOT / f"{stem}_{os.getpid()}_{time.time_ns()}{suffix}"


def append_marker(path, marker):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{marker}\n")
        handle.flush()


def read_markers(path):
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def wait_for(predicate, timeout=2.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def assert_markers(path, expected, timeout=2.0):
    ok = wait_for(lambda: expected.issubset(set(read_markers(path))), timeout=timeout)
    got = set(read_markers(path))
    missing = expected - got
    assert ok and not missing, f"missing markers {sorted(missing)}; saw {sorted(got)}"


def assert_dummy(obj):
    assert type(obj).__name__ == "DummyObject", f"expected DummyObject, got {type(obj).__name__}: {obj!r}"
    return obj
