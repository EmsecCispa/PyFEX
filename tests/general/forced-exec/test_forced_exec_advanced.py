#!/usr/bin/env python3
"""Advanced test for forced execution feature.

Tests:
1. Multiple conditionals (should fork at each)
2. Global fork limit (should stop forking after limit reached)
3. Nested conditionals
"""

import os
import sys

print(f"[PID {os.getpid()}] Test start")
sys.stdout.flush()

# Test 1: First conditional
x = 10
print(f"[PID {os.getpid()}] Test 1: x = {x}")
sys.stdout.flush()

if x > 5:
    print(f"[PID {os.getpid()}] Test 1: TRUE branch (x > 5)")
else:
    print(f"[PID {os.getpid()}] Test 1: FALSE branch (x <= 5)")
sys.stdout.flush()

# Test 2: Second conditional
y = 3
print(f"[PID {os.getpid()}] Test 2: y = {y}")
sys.stdout.flush()

if y < 5:
    print(f"[PID {os.getpid()}] Test 2: TRUE branch (y < 5)")
else:
    print(f"[PID {os.getpid()}] Test 2: FALSE branch (y >= 5)")
sys.stdout.flush()

# Test 3: Nested conditional
z = 7
print(f"[PID {os.getpid()}] Test 3: z = {z}")
sys.stdout.flush()

if z > 5:
    print(f"[PID {os.getpid()}] Test 3: Outer TRUE (z > 5)")
    sys.stdout.flush()
    if z > 8:
        print(f"[PID {os.getpid()}] Test 3: Inner TRUE (z > 8)")
    else:
        print(f"[PID {os.getpid()}] Test 3: Inner FALSE (z <= 8)")
else:
    print(f"[PID {os.getpid()}] Test 3: Outer FALSE (z <= 5)")
sys.stdout.flush()

print(f"[PID {os.getpid()}] Test complete")
