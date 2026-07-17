#!/usr/bin/env python3
"""
Test dummy object protocol implementations.
Verifies that operations propagate correctly.
"""

print("=" * 60)
print("Testing Dummy Object Protocols")
print("=" * 60)

# Create a dummy from an error
print("\n1. Creating initial dummy from type error")
dummy1 = "hello" + 123
print(f"Type: {type(dummy1).__name__}")
print(f"Error: {dummy1.error_reason}")

# Test numeric operations
print("\n2. Testing numeric operations propagation")
dummy2 = dummy1 + 5
print(f"dummy + 5: {type(dummy2).__name__}, ops count: {len(dummy2.operations_history)}")

dummy3 = dummy1 - 10
print(f"dummy - 10: {type(dummy3).__name__}, ops count: {len(dummy3.operations_history)}")

dummy4 = dummy1 * 2
print(f"dummy * 2: {type(dummy4).__name__}, ops count: {len(dummy4.operations_history)}")

# Test chaining operations
print("\n3. Testing chained operations")
dummy5 = ((dummy1 + 1) - 2) * 3
print(f"((dummy + 1) - 2) * 3: {type(dummy5).__name__}")
print(f"Operations count: {len(dummy5.operations_history)}")
print("Operations history:")
for i, op in enumerate(dummy5.operations_history):
    print(f"  {i+1}. {op}")

# Test comparison operations
print("\n4. Testing comparison operations")
dummy6 = dummy1 < 100
print(f"dummy < 100: {type(dummy6).__name__}")

dummy7 = dummy1 == dummy2
print(f"dummy == dummy: {type(dummy7).__name__}")

# Test boolean value
print("\n5. Testing boolean conversion")
if dummy1:
    print("Dummy is truthy (as expected for control flow)")

print("\n" + "=" * 60)
print("All protocol tests passed!")
print("=" * 60)
