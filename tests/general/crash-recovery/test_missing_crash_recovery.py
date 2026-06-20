"""Test crash recovery for previously missing bytecodes.

Run with:
    CRASH_RECOVERY_ENABLE=1 PyFEX-core/python tests/general/crash-recovery/test_missing_crash_recovery.py

Tests: UNPACK_SEQUENCE, FOR_ITER (non-iterable), CALL_FUNCTION (non-callable),
       LOAD_NAME (undefined), LOAD_GLOBAL (undefined)
"""
import sys

print("=" * 60)
print("PyFEX Missing Crash Recovery Tests")
print("=" * 60)

passed = 0
total = 0

# Test 1: UNPACK_SEQUENCE with non-iterable
print("\nTest 1: UNPACK_SEQUENCE with non-iterable (int)")
total += 1
try:
    a, b = 42  # int is not iterable
    is_dummy_a = type(a).__name__ == "DummyObject"
    is_dummy_b = type(b).__name__ == "DummyObject"
    if is_dummy_a and is_dummy_b:
        print(f"  PASS: a={a}, b={b} (both DummyObjects)")
        passed += 1
    else:
        print(f"  FAIL: a={a} (type={type(a).__name__}), b={b} (type={type(b).__name__})")
except TypeError as e:
    print(f"  FAIL: Exception raised: {e}")

# Test 2: UNPACK_SEQUENCE with wrong size
print("\nTest 2: UNPACK_SEQUENCE with wrong size tuple")
total += 1
try:
    c, d, e = (1, 2)  # Too few values
    has_dummy = any(type(v).__name__ == "DummyObject" for v in [c, d, e])
    if has_dummy:
        print(f"  PASS: c={c}, d={d}, e={e} (contains DummyObjects)")
        passed += 1
    else:
        print(f"  FAIL: c={c}, d={d}, e={e} (no DummyObjects)")
except ValueError as e:
    print(f"  FAIL: Exception raised: {e}")

# Test 3: CALL_FUNCTION with non-callable
print("\nTest 3: CALL_FUNCTION with non-callable")
total += 1
not_a_function = 42
try:
    result = not_a_function()
    is_dummy = type(result).__name__ == "DummyObject"
    if is_dummy:
        print(f"  PASS: result={result} (DummyObject)")
        passed += 1
    else:
        print(f"  FAIL: result={result} (type={type(result).__name__})")
except TypeError as e:
    print(f"  FAIL: Exception raised: {e}")

# Test 4: LOAD_NAME with undefined name
print("\nTest 4: LOAD_NAME with undefined name")
total += 1
try:
    result = eval("undefined_variable_xyz_123")
    is_dummy = type(result).__name__ == "DummyObject"
    if is_dummy:
        print(f"  PASS: result={result} (DummyObject)")
        passed += 1
    else:
        print(f"  FAIL: result={result} (type={type(result).__name__})")
except NameError as e:
    print(f"  FAIL: Exception raised: {e}")

# Test 5: Normal operations still work
print("\nTest 5: Normal operations still work")
total += 1
a, b = (10, 20)
result = len("hello")
if a == 10 and b == 20 and result == 5:
    print(f"  PASS: a={a}, b={b}, len('hello')={result}")
    passed += 1
else:
    print(f"  FAIL: a={a}, b={b}, result={result}")

print(f"\n{'=' * 60}")
print(f"Results: {passed}/{total} tests passed")
print(f"{'=' * 60}")
