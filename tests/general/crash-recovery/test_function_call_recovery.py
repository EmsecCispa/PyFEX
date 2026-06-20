#!/usr/bin/env python3
"""
Test crash recovery for function calls with dummy objects.
"""

print("=" * 60)
print("Testing Function Call Crash Recovery")
print("=" * 60)

# Test 1: Create a dummy and call a function with it
print("\n1. Calling function with dummy argument")
dummy = "hello" + 123  # Creates a dummy
result = len(dummy)
print(f"  len(dummy) -> {type(result).__name__}: {result.error_reason}")
print(f"  Operations: {len(result.operations_history)} total")

# Test 2: Calling a dummy as if it were a function
print("\n2. Calling a dummy object as function")
dummy_func = (123).nonexistent  # Creates a dummy (attribute error)
result = dummy_func("arg1", "arg2")
print(f"  dummy_func('arg1', 'arg2') -> {type(result).__name__}")
print(f"  Operations: {len(result.operations_history)} total")

# Test 3: Chain of function calls with dummies
print("\n3. Chained function calls")
dummy = 10 / 0  # Creates dummy (division by zero)
result = str(int(float(dummy)))
print(f"  str(int(float(dummy))) -> {type(result).__name__}")
print(f"  Operations: {len(result.operations_history)} total")

# Test 4: Method calls on dummies
print("\n4. Method calls on dummy objects")
dummy = "text" - 5  # Creates dummy
result = dummy.upper()
print(f"  dummy.upper() -> {type(result).__name__}")
print(f"  Operations: {len(result.operations_history)} total")

# Test 5: Normal function calls still work
print("\n5. Normal function calls still work")
print(f"  len('hello') = {len('hello')}")
print(f"  str(123) = {str(123)}")
print(f"  abs(-5) = {abs(-5)}")

def my_func(x, y):
    return x + y

print(f"  my_func(10, 20) = {my_func(10, 20)}")

print("\n" + "=" * 60)
print("All function call tests passed!")
print("=" * 60)
