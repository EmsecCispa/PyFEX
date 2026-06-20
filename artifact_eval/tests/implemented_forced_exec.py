"""Smoke test: forced execution explores both sides of a conditional."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path


def append_marker(path: Path, marker: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(marker + "\n")
        handle.flush()


def read_markers(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def trigger(marker_path: Path) -> None:
    flag = True
    if flag:
        append_marker(marker_path, "natural-true")
    else:
        append_marker(marker_path, "forced-false")

    # Avoid accidental recursive forcing while the child process drains.
    os.environ["FORCE_EXEC_ENABLE"] = "0"
    time.sleep(0.1)


def main() -> int:
    marker_path = Path(tempfile.gettempdir()) / f"pyfex_ae_forced_{os.getpid()}.log"
    marker_path.unlink(missing_ok=True)

    os.environ["FORCE_EXEC_ENABLE"] = "1"
    os.environ["FORCE_EXEC_GLOBAL_LIMIT"] = "4"
    os.environ["FORCE_EXEC_LOCATION_LIMIT"] = "2"

    root_pid = os.getpid()
    trigger(marker_path)

    if os.getpid() != root_pid:
        return 0

    deadline = time.time() + 3.0
    expected = {"natural-true", "forced-false"}
    while time.time() < deadline:
        if expected <= read_markers(marker_path):
            print("PASS: forced execution explored natural and counterfactual branches")
            return 0
        time.sleep(0.05)

    print(f"FAIL: markers={sorted(read_markers(marker_path))}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
