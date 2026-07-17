"""Test Dormant Function Analysis logging.

Run with:
    DORMANT_FUNC_LOG_FILE=/tmp/dfa_test.log PyFEX-core/python tests/general/dormant-function-analysis/test_dormant_function_analysis.py

Expected: The log file should contain DEFINED entries for all functions
and CALLED entries only for functions that were actually invoked.
Functions defined but never called are "dormant".
"""
import os
import sys

LOG_FILE = os.environ.get("DORMANT_FUNC_LOG_FILE")
if not LOG_FILE:
    print("ERROR: Set DORMANT_FUNC_LOG_FILE env var to run this test")
    sys.exit(1)

# Clear log file
if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)

# Re-set the env var so the interpreter picks it up fresh
# (It's already set, the logging is checked on each call)

print("=" * 60)
print("PyFEX Dormant Function Analysis Test")
print("=" * 60)

# Define some functions - some will be called, some won't
def called_function():
    return 42

def another_called():
    return "hello"

def dormant_function_1():
    """This function is defined but never called."""
    return "I am dormant"

def dormant_function_2():
    """This function is also never called."""
    return "Also dormant"

class MyClass:
    def called_method(self):
        return "method result"

    def dormant_method(self):
        return "dormant method"

# Call some functions
print("\n1. Calling functions...")
r1 = called_function()
print(f"   called_function() = {r1}")

r2 = another_called()
print(f"   another_called() = {r2}")

obj = MyClass()
r3 = obj.called_method()
print(f"   obj.called_method() = {r3}")

print(f"\n2. NOT calling: dormant_function_1, dormant_function_2, obj.dormant_method")

# Read and analyze the log
print(f"\n3. Analyzing log file: {LOG_FILE}")
if not os.path.exists(LOG_FILE):
    print("   ERROR: Log file was not created!")
    sys.exit(1)

with open(LOG_FILE, "r") as f:
    lines = f.readlines()

defined = set()
called = set()

for line in lines:
    line = line.strip()
    if not line:
        continue
    parts = line.split()
    if len(parts) >= 3:
        prefix = parts[0]
        qualname = parts[1]
        if prefix == "DEFINED":
            defined.add(qualname)
        elif prefix == "CALLED":
            called.add(qualname)

# Filter to just our test functions
our_functions = {
    "called_function", "another_called",
    "dormant_function_1", "dormant_function_2",
    "MyClass.called_method", "MyClass.dormant_method",
}

our_defined = defined & our_functions
our_called = called & our_functions
dormant = our_defined - our_called

print(f"\n   Defined (our functions): {sorted(our_defined)}")
print(f"   Called (our functions): {sorted(our_called)}")
print(f"   Dormant (defined - called): {sorted(dormant)}")

# Verify
passed = 0
total = 0

print("\n4. Verification:")

# Check that defined functions were logged
total += 1
expected_defined = {"called_function", "another_called", "dormant_function_1", "dormant_function_2"}
if expected_defined.issubset(our_defined):
    print(f"   PASS: All expected functions found in DEFINED entries")
    passed += 1
else:
    missing = expected_defined - our_defined
    print(f"   FAIL: Missing DEFINED entries for: {missing}")

# Check that called functions were logged
total += 1
expected_called = {"called_function", "another_called"}
if expected_called.issubset(our_called):
    print(f"   PASS: Called functions found in CALLED entries")
    passed += 1
else:
    missing = expected_called - our_called
    print(f"   FAIL: Missing CALLED entries for: {missing}")

# Check that dormant functions are correctly identified
total += 1
expected_dormant = {"dormant_function_1", "dormant_function_2"}
if expected_dormant.issubset(dormant):
    print(f"   PASS: Dormant functions correctly identified")
    passed += 1
else:
    missing = expected_dormant - dormant
    print(f"   FAIL: These should be dormant but weren't: {missing}")

# Total log entries
print(f"\n   Total log entries: {len(lines)} ({len(defined)} defined, {len(called)} called)")

print(f"\n{'=' * 60}")
print(f"Results: {passed}/{total} tests passed")
print(f"{'=' * 60}")

# Cleanup
os.remove(LOG_FILE)
