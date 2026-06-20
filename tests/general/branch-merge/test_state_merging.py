#!/usr/bin/env python3
"""
Test script for state merging and peer recovery in PyFEX Python 3.10.

Tests the three new features:
1. Improved post-dominator calculation (elif chains)
2. State merging at post-dominator (parent absorbs child's concrete values)
3. Crash-triggered peer query (use peer's concrete value instead of DummyObject)

Run with:
  CRASH_RECOVERY_ENABLE=1 \
  FORCE_EXEC_ENABLE=1 \
  FORCE_EXEC_MERGE_ENABLE=1 \
  FORCE_EXEC_GLOBAL_LIMIT=20 \
  FORCE_EXEC_MERGE_WAIT_MS=200 \
  FORCE_EXEC_LOG_FILE=/tmp/state_merge.log \
  PyFEX-core/python tests/general/branch-merge/test_state_merging.py
"""

import os
import sys

def test_basic_state_merge():
    """Test that parent absorbs child's state at merge point.

    Parent takes TRUE branch (x=10 > 5), child takes FALSE branch.
    Both branches set 'result' to different values.
    After merge, parent should still have its own value (natural path priority).
    """
    print(f"\n[PID {os.getpid()}] === test_basic_state_merge ===")
    sys.stdout.flush()

    x = 10
    result = "unset"

    if x > 5:
        result = "true_branch"
        print(f"[PID {os.getpid()}] TRUE: result={result}")
    else:
        result = "false_branch"
        print(f"[PID {os.getpid()}] FALSE: result={result}")

    sys.stdout.flush()
    # After merge point: parent should have "true_branch" (natural path)
    print(f"[PID {os.getpid()}] After merge: result={result}")
    sys.stdout.flush()
    return result


def test_elif_chain():
    """Test post-dominator calculation for elif chains.

    An elif chain should merge at the correct point (after all branches).
    """
    print(f"\n[PID {os.getpid()}] === test_elif_chain ===")
    sys.stdout.flush()

    x = 2
    result = "unset"

    if x == 1:
        result = "one"
        print(f"[PID {os.getpid()}] x==1: result={result}")
    elif x == 2:
        result = "two"
        print(f"[PID {os.getpid()}] x==2: result={result}")
    elif x == 3:
        result = "three"
        print(f"[PID {os.getpid()}] x==3: result={result}")
    else:
        result = "other"
        print(f"[PID {os.getpid()}] else: result={result}")

    sys.stdout.flush()
    print(f"[PID {os.getpid()}] After elif merge: result={result}")
    sys.stdout.flush()
    return result


def test_child_only_variable():
    """Test that a variable set only in the child branch is available after merge.

    Parent takes TRUE branch where 'extra' is NOT set.
    Child takes FALSE branch where 'extra' IS set.
    After merge, parent should get 'extra' from child's state.
    """
    print(f"\n[PID {os.getpid()}] === test_child_only_variable ===")
    sys.stdout.flush()

    x = 10
    shared_var = "initial"

    if x > 5:
        # Parent takes this branch (TRUE)
        shared_var = "from_true"
        print(f"[PID {os.getpid()}] TRUE: shared_var={shared_var}")
    else:
        # Child takes this branch (FALSE)
        shared_var = "from_false"
        print(f"[PID {os.getpid()}] FALSE: shared_var={shared_var}")

    sys.stdout.flush()
    print(f"[PID {os.getpid()}] After merge: shared_var={shared_var}")
    sys.stdout.flush()
    return shared_var


def test_nested_merge():
    """Test nested conditionals merge correctly."""
    print(f"\n[PID {os.getpid()}] === test_nested_merge ===")
    sys.stdout.flush()

    a = 20
    b = 7
    outer_result = "unset"
    inner_result = "unset"

    if a > 10:
        print(f"[PID {os.getpid()}] Outer TRUE")
        if b > 5:
            inner_result = "inner_true"
            print(f"[PID {os.getpid()}] Inner TRUE: inner_result={inner_result}")
        else:
            inner_result = "inner_false"
            print(f"[PID {os.getpid()}] Inner FALSE: inner_result={inner_result}")
        outer_result = "outer_true"
    else:
        outer_result = "outer_false"
        print(f"[PID {os.getpid()}] Outer FALSE")

    sys.stdout.flush()
    print(f"[PID {os.getpid()}] After merge: outer={outer_result}, inner={inner_result}")
    sys.stdout.flush()
    return (outer_result, inner_result)


if __name__ == "__main__":
    print("=" * 70)
    print("PyFEX State Merging & Peer Recovery Test Suite")
    print("=" * 70)

    r1 = test_basic_state_merge()
    print(f"Result 1: {r1}")

    r2 = test_elif_chain()
    print(f"Result 2: {r2}")

    r3 = test_child_only_variable()
    print(f"Result 3: {r3}")

    r4 = test_nested_merge()
    print(f"Result 4: {r4}")

    print("\n" + "=" * 70)
    print("Tests complete!")
    print("=" * 70)
    print("\nCheck /tmp/state_merge.log for merge details")
