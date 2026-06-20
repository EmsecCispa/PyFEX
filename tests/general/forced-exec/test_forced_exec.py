#!/usr/bin/env python3
"""Test script for forced execution feature in Python 3.12.

This script tests if the interpreter explores both branches of a conditional.
In forced execution mode, it should fork at the if statement and execute both paths.
"""

import os
import sys

print(f"[PID {os.getpid()}] Starting forced execution test")

x = 5

print(f"[PID {os.getpid()}] Before conditional: x = {x}")
sys.stdout.flush()  # Flush before fork to avoid buffer duplication

if x > 3:
    print(f"[PID {os.getpid()}] Took TRUE branch (x > 3)")
    result = "true_branch"
else:
    print(f"[PID {os.getpid()}] Took FALSE branch (x <= 3)")
    result = "false_branch"

print(f"[PID {os.getpid()}] After conditional: result = {result}")
print(f"[PID {os.getpid()}] Test complete")
