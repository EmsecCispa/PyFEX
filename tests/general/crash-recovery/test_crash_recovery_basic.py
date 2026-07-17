#!/usr/bin/env python3
"""
Basic test for crash recovery feature.
Tests that BINARY_ADD creates dummy objects instead of crashing.
"""

print("=" * 60)
print("Testing Crash Recovery - BINARY_ADD")
print("=" * 60)

# Test 1: Type error in addition
print("\nTest 1: String + Integer (should create dummy)")
result = "hello" + 123
print(f"Result type: {type(result).__name__}")
print(f"Result: {result}")

# Test 2: Can we continue execution after error?
print("\nTest 2: Continuing execution after error")
x = 10
y = 20
z = x + y
print(f"Normal addition still works: {x} + {y} = {z}")

# Test 3: Using the dummy in further operations
print("\nTest 3: Operating on dummy object")
result2 = result + " world"
print(f"Dummy + string type: {type(result2).__name__}")
print(f"Dummy + string: {result2}")

# Test 4: Checking if dummy has trace property
print("\nTest 4: Checking dummy properties")
try:
    if hasattr(result, 'error_reason'):
        print(f"Error reason: {result.error_reason}")
    if hasattr(result, 'trace'):
        print(f"Trace:\n{result.trace}")
except Exception as e:
    print(f"Error accessing dummy properties: {e}")

print("\n" + "=" * 60)
print("Test completed successfully!")
print("=" * 60)
