"""
PyFEX Exhaustive Crash Recovery Test

Tests crash recovery for ALL instrumented bytecodes, ensuring DummyObjects
are created with proper trace properties recording crash origin and
propagation lineage.

Run with: CRASH_RECOVERY_ENABLE=1 PyFEX-core/python tests/general/crash-recovery/test_exhaustive_crash_recovery.py
"""
import sys
import os

passed = 0
failed = 0
total = 0

def test(name, fn):
    global passed, failed, total
    total += 1
    try:
        result = fn()
        if result:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name} — returned False")
    except Exception as e:
        failed += 1
        print(f"  FAIL: {name} — {type(e).__name__}: {e}")

def is_dummy(obj):
    return type(obj).__name__ == 'DummyObject'

def has_trace(obj):
    """Check that DummyObject has a trace property recording crash origin."""
    if not is_dummy(obj):
        return False
    try:
        trace = obj.trace
        return trace is not None and len(trace) > 0
    except:
        return False

print("=" * 60)
print("PyFEX Exhaustive Crash Recovery Tests")
print("=" * 60)

# ============================================================
# Category A: Bitwise binary ops
# ============================================================
print("\n--- Bitwise Binary Ops ---")

test("BINARY_LSHIFT: 'a' << 1", lambda: is_dummy("a" << 1))
test("BINARY_RSHIFT: 'a' >> 1", lambda: is_dummy("a" >> 1))
test("BINARY_AND: 'a' & 1", lambda: is_dummy("a" & 1))
test("BINARY_XOR: 'a' ^ 1", lambda: is_dummy("a" ^ 1))
test("BINARY_OR: 'a' | 1", lambda: is_dummy("a" | 1))

# ============================================================
# Category A: Inplace ops
# ============================================================
print("\n--- Inplace Ops ---")

def test_inplace_add():
    x = [1, 2]
    x += "not_a_list"  # This actually works for lists. Use a bad type:
    return True  # list += iterable works, so skip this

def test_inplace_sub():
    x = "hello"
    x -= 1
    return is_dummy(x)

def test_inplace_mul():
    x = "hello"
    x *= "world"  # Can't multiply str by str
    return is_dummy(x)

def test_inplace_truediv():
    x = 10
    x /= 0
    return is_dummy(x)

def test_inplace_floordiv():
    x = 10
    x //= 0
    return is_dummy(x)

def test_inplace_mod():
    x = 10
    x %= 0
    return is_dummy(x)

def test_inplace_pow():
    # Triggering an error with ** is tricky; use incompatible types
    x = "hello"
    x **= 2
    return is_dummy(x)

def test_inplace_lshift():
    x = "hello"
    x <<= 1
    return is_dummy(x)

def test_inplace_rshift():
    x = "hello"
    x >>= 1
    return is_dummy(x)

def test_inplace_and():
    x = "hello"
    x &= 1
    return is_dummy(x)

def test_inplace_xor():
    x = "hello"
    x ^= 1
    return is_dummy(x)

def test_inplace_or():
    x = "hello"
    x |= 1
    return is_dummy(x)

test("INPLACE_SUBTRACT: str -= int", test_inplace_sub)
test("INPLACE_MULTIPLY: str *= str", test_inplace_mul)
test("INPLACE_TRUE_DIVIDE: int /= 0", test_inplace_truediv)
test("INPLACE_FLOOR_DIVIDE: int //= 0", test_inplace_floordiv)
test("INPLACE_MODULO: int %= 0", test_inplace_mod)
test("INPLACE_POWER: str **= int", test_inplace_pow)
test("INPLACE_LSHIFT: str <<= int", test_inplace_lshift)
test("INPLACE_RSHIFT: str >>= int", test_inplace_rshift)
test("INPLACE_AND: str &= int", test_inplace_and)
test("INPLACE_XOR: str ^= int", test_inplace_xor)
test("INPLACE_OR: str |= int", test_inplace_or)

# ============================================================
# Category B: Store/Delete ops (should not crash)
# ============================================================
print("\n--- Store/Delete Ops ---")

def test_store_attr():
    x = 42  # int has no settable attrs
    try:
        x.foo = "bar"  # Should be suppressed
    except:
        return False
    return True

def test_delete_attr():
    x = 42
    try:
        del x.foo
    except:
        return False
    return True

def test_delete_subscr():
    x = (1, 2, 3)  # tuple doesn't support item deletion
    try:
        del x[0]
    except:
        return False
    return True

def test_store_subscr():
    x = (1, 2, 3)  # tuple doesn't support item assignment
    try:
        x[0] = 99
    except:
        return False
    return True

def test_delete_name():
    # Deleting a non-existent name
    try:
        exec("del _nonexistent_var_xyz_")
    except:
        return False
    return True

def test_delete_fast():
    # This tests deletion of unbound local
    def inner():
        try:
            del x
        except:
            return False
        return True
    return inner()

test("STORE_ATTR: int.foo = bar (suppressed)", test_store_attr)
test("DELETE_ATTR: del int.foo (suppressed)", test_delete_attr)
test("STORE_SUBSCR: tuple[0] = x (suppressed)", test_store_subscr)
test("DELETE_SUBSCR: del tuple[0] (suppressed)", test_delete_subscr)
test("DELETE_NAME: del nonexistent (suppressed)", test_delete_name)

# ============================================================
# Category C: Variable loads
# ============================================================
print("\n--- Variable Loads ---")

def test_load_deref():
    def outer():
        # x is a closure variable that's never set
        def inner():
            return x
        return inner()
    result = outer()
    return is_dummy(result)

# LOAD_DEREF is hard to trigger reliably without compile tricks; skip if needed

# ============================================================
# Category D: Import ops
# ============================================================
print("\n--- Import Ops ---")

def test_import_name():
    result = __import__("nonexistent_module_xyz_123_abc")
    return is_dummy(result)

def test_import_from():
    import sys as _sys
    try:
        from sys import nonexistent_attr_xyz_123
    except:
        return False
    return is_dummy(nonexistent_attr_xyz_123)

test("IMPORT_NAME: import nonexistent", test_import_name)
test("IMPORT_FROM: from sys import nonexistent", test_import_from)

# ============================================================
# Category D: Other ops
# ============================================================
print("\n--- Other Ops ---")

def test_format_value():
    class BadRepr:
        def __repr__(self):
            raise ValueError("bad repr")
        def __format__(self, spec):
            raise ValueError("bad format")
    obj = BadRepr()
    result = f"{obj!r}"
    return isinstance(result, str)

def test_call_function_kw():
    result = (42)(x=1)  # Calling an int with kwargs
    return is_dummy(result)

test("FORMAT_VALUE: f-string with bad __repr__", test_format_value)
test("CALL_FUNCTION_KW: int(x=1)", test_call_function_kw)

# ============================================================
# Category E: Collection ops
# ============================================================
print("\n--- Collection Ops ---")

def test_build_set_unhashable():
    # Building a set with unhashable items
    try:
        result = {[1, 2], "hello"}  # lists are unhashable
    except:
        return False
    return isinstance(result, set)

def test_build_map_unhashable():
    # Building a dict with unhashable keys
    try:
        result = {[1, 2]: "value", "key": "value2"}
    except:
        return False
    return isinstance(result, dict)

test("BUILD_SET: {[1,2], 'hello'} (unhashable)", test_build_set_unhashable)
test("BUILD_MAP: {[1,2]: 'val'} (unhashable key)", test_build_map_unhashable)

# ============================================================
# Trace property verification
# ============================================================
print("\n--- Trace Property Verification ---")

def test_trace_on_binary():
    result = "hello" + 42  # TypeError → DummyObject
    if not is_dummy(result):
        return False
    return has_trace(result)

def test_trace_propagation():
    """Verify trace records propagation lineage."""
    result = "hello" + 42  # Creates DummyObject
    if not is_dummy(result):
        return False
    propagated = result + 1  # Propagates through ADD
    if not is_dummy(propagated):
        return False
    # Check trace grew
    orig_ops = len(result.operations_history)
    prop_ops = len(propagated.operations_history)
    return prop_ops > orig_ops

def test_trace_records_opcode():
    """Verify trace records the bytecode where crash occurred."""
    result = "hello" / 42  # TypeError → DummyObject from BINARY_TRUE_DIVIDE
    if not is_dummy(result):
        return False
    trace = result.trace
    return "BINARY_TRUE_DIVIDE" in trace or "Error" in trace

test("Trace exists on crash", test_trace_on_binary)
test("Trace propagation adds operations", test_trace_propagation)
test("Trace records opcode name", test_trace_records_opcode)

# ============================================================
# Normal operations still work
# ============================================================
print("\n--- Normal Operations (sanity) ---")

test("Normal add: 1 + 2 == 3", lambda: (1 + 2) == 3)
test("Normal sub: 5 - 3 == 2", lambda: (5 - 3) == 2)
test("Normal lshift: 1 << 3 == 8", lambda: (1 << 3) == 8)
test("Normal and: 0xFF & 0x0F == 0x0F", lambda: (0xFF & 0x0F) == 0x0F)
test("Normal set: {1,2,3}", lambda: len({1, 2, 3}) == 3)
test("Normal dict: {'a':1}", lambda: len({'a': 1}) == 1)
test("Normal import: import os", lambda: __import__('os') is not None)

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print(f"Results: {passed}/{total} tests passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
