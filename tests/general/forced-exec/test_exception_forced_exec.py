"""Test forced execution for exception handling (SETUP_FINALLY).

Run with:
    FORCE_EXEC_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 PyFEX-core/python tests/general/forced-exec/test_exception_forced_exec.py

Expected: parent goes through try block, forked child goes through except block.
Both PIDs should print their results.
"""
import os
import sys

print(f"[PID {os.getpid()}] Starting exception forced execution test")

# Test 1: Simple try/except - child should explore except branch
print(f"\n[PID {os.getpid()}] === Test 1: Simple try/except ===")
try:
    x = 42
    print(f"[PID {os.getpid()}] In try block: x = {x}")
except:
    x = 99
    print(f"[PID {os.getpid()}] In except block: x = {x}")

print(f"[PID {os.getpid()}] After try/except: x = {x}")

# Test 2: try/except with specific exception type
print(f"\n[PID {os.getpid()}] === Test 2: try/except ValueError ===")
try:
    y = "hello"
    print(f"[PID {os.getpid()}] In try block: y = {y}")
except ValueError:
    y = "caught_value_error"
    print(f"[PID {os.getpid()}] In except ValueError: y = {y}")
except:
    y = "caught_other"
    print(f"[PID {os.getpid()}] In except (other): y = {y}")

print(f"[PID {os.getpid()}] After try/except: y = {y}")

# Test 3: Nested try/except
print(f"\n[PID {os.getpid()}] === Test 3: Nested try/except ===")
try:
    a = 10
    try:
        b = 20
        print(f"[PID {os.getpid()}] Inner try: a={a}, b={b}")
    except:
        b = -1
        print(f"[PID {os.getpid()}] Inner except: b={b}")
    print(f"[PID {os.getpid()}] After inner: a={a}, b={b}")
except:
    a = -1
    print(f"[PID {os.getpid()}] Outer except: a={a}")

print(f"[PID {os.getpid()}] After nested: a={a}, b={b}")

print(f"\n[PID {os.getpid()}] Test complete")
