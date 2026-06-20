#!/usr/bin/env python3
"""Test crash recovery combined with forced execution.

This tests that:
1. Crash recovery creates dummy objects instead of raising exceptions
2. Forced execution explores both branches even when crashes occur
"""

import os
import sys

print(f"[PID {os.getpid()}] Combined test start")
sys.stdout.flush()

# Test 1: Division by zero in conditional
x = 0
print(f"[PID {os.getpid()}] Test 1: Attempting division by zero")
sys.stdout.flush()

result = 10 / x  # Should create dummy object instead of raising ZeroDivisionError
print(f"[PID {os.getpid()}] Test 1: result = {result}, type = {type(result).__name__}")
sys.stdout.flush()

# Test 2: Conditional with crash
y = 5
print(f"[PID {os.getpid()}] Test 2: y = {y}")
sys.stdout.flush()

if y > 3:
    print(f"[PID {os.getpid()}] Test 2: TRUE branch")
    crash_result = 1 / 0  # Crash in TRUE branch
    print(f"[PID {os.getpid()}] Test 2: crash_result = {crash_result}")
else:
    print(f"[PID {os.getpid()}] Test 2: FALSE branch")
    crash_result = 5
    print(f"[PID {os.getpid()}] Test 2: crash_result = {crash_result}")
sys.stdout.flush()

print(f"[PID {os.getpid()}] Combined test complete")
