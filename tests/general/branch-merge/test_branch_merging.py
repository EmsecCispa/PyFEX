#!/usr/bin/env python3
"""
Test script for branch merging and object sharing in PyFEX Python 3.12.

Branch merging allows parent and child processes (created by forced execution)
to save their state at merge points where branches reconverge, enabling
comparison and analysis of different execution paths.
"""

import os
import sys

def simple_branch_test():
    """Simple test with one conditional - demonstrates basic merging"""
    print(f"[PID {os.getpid()}] Simple branch test starting")
    sys.stdout.flush()

    x = 10
    result = 0

    print(f"[PID {os.getpid()}] Before conditional: x={x}")
    sys.stdout.flush()

    if x > 5:
        print(f"[PID {os.getpid()}] TRUE branch: x > 5")
        result = x * 2
        print(f"[PID {os.getpid()}] result = {result}")
    else:
        print(f"[PID {os.getpid()}] FALSE branch: x <= 5")
        result = x + 10
        print(f"[PID {os.getpid()}] result = {result}")

    sys.stdout.flush()

    # Merge point is here - both branches reconverge
    print(f"[PID {os.getpid()}] After conditional (merge point): result={result}")
    sys.stdout.flush()

    print(f"[PID {os.getpid()}] Test complete")
    return result

def nested_branch_test():
    """Test with nested conditionals"""
    print(f"\n[PID {os.getpid()}] Nested branch test starting")
    sys.stdout.flush()

    a = 15
    b = 3
    result = 0

    print(f"[PID {os.getpid()}] a={a}, b={b}")
    sys.stdout.flush()

    if a > 10:
        print(f"[PID {os.getpid()}] Outer TRUE: a > 10")
        sys.stdout.flush()

        if b < 5:
            print(f"[PID {os.getpid()}] Inner TRUE: b < 5")
            result = a + b
        else:
            print(f"[PID {os.getpid()}] Inner FALSE: b >= 5")
            result = a - b

        print(f"[PID {os.getpid()}] Inner merge: result={result}")
    else:
        print(f"[PID {os.getpid()}] Outer FALSE: a <= 10")
        result = a * b

    sys.stdout.flush()

    print(f"[PID {os.getpid()}] Outer merge: result={result}")
    sys.stdout.flush()

    return result

def state_modification_test():
    """Test that shows how different branches modify state differently"""
    print(f"\n[PID {os.getpid()}] State modification test starting")
    sys.stdout.flush()

    data = {"count": 0, "value": 100}

    print(f"[PID {os.getpid()}] Initial state: {data}")
    sys.stdout.flush()

    condition = data["value"] > 50

    if condition:
        print(f"[PID {os.getpid()}] TRUE branch: incrementing count")
        data["count"] += 1
        data["value"] -= 25
        print(f"[PID {os.getpid()}] Modified: {data}")
    else:
        print(f"[PID {os.getpid()}] FALSE branch: decrementing count")
        data["count"] -= 1
        data["value"] += 50
        print(f"[PID {os.getpid()}] Modified: {data}")

    sys.stdout.flush()

    # At merge point, parent and child will have different states saved
    print(f"[PID {os.getpid()}] Merge point - state: {data}")
    sys.stdout.flush()

    return data

if __name__ == "__main__":
    print("="*70)
    print("PyFEX Branch Merging Test Suite")
    print("="*70)

    print("\nTo enable branch merging, run with:")
    print("  FORCE_EXEC_ENABLE=1 \\")
    print("  FORCE_EXEC_MERGE_ENABLE=1 \\")
    print("  FORCE_EXEC_GLOBAL_LIMIT=10 \\")
    print("  FORCE_EXEC_LOG_FILE=/tmp/merge.log \\")
    print("  ./python test_branch_merging.py")

    print("\nRunning tests...")

    result1 = simple_branch_test()
    print(f"\nTest 1 final result: {result1}")

    result2 = nested_branch_test()
    print(f"\nTest 2 final result: {result2}")

    result3 = state_modification_test()
    print(f"\nTest 3 final result: {result3}")

    print("\n" + "="*70)
    print("Tests complete!")
    print("="*70)
    print("\nCheck /tmp/merge.log for branch merging details")
    print("Branch states are saved in shared memory at merge points")
