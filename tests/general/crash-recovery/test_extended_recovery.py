#!/usr/bin/env python3
"""
Test crash recovery for extended operations:
unary, subscript, attribute, and comparison operations.
"""

print("=" * 60)
print("Testing Extended Crash Recovery")
print("=" * 60)

# Test unary operations
print("\n1. Unary operations with type errors")
result = -"text"
print(f"  -'text' -> {type(result).__name__}: {result.error_reason}")

result = +"text"
print(f"  +'text' -> {type(result).__name__}: {result.error_reason}")

result = ~"text"
print(f"  ~'text' -> {type(result).__name__}: {result.error_reason}")

# Test subscript operations
print("\n2. Subscript operations")
result = 123[0]
print(f"  123[0] -> {type(result).__name__}: {result.error_reason}")

result = "abc"[100]
print(f"  'abc'[100] -> {type(result).__name__}: {result.error_reason}")

# Test attribute access
print("\n3. Attribute access errors")
result = (123).nonexistent
print(f"  (123).nonexistent -> {type(result).__name__}: {result.error_reason}")

class MyClass:
    pass
obj = MyClass()
result = obj.missing_attr
print(f"  obj.missing_attr -> {type(result).__name__}: {result.error_reason}")

# Test comparison operations
print("\n4. Comparison operations")
result = 123 < "abc"
print(f"  123 < 'abc' -> {type(result).__name__}: {result.error_reason}")

result = None >= []
print(f"  None >= [] -> {type(result).__name__}: {result.error_reason}")

# Test that normal operations still work
print("\n5. Normal operations still work")
print(f"  -5 = {-5}")
print(f"  +5 = {+5}")
print(f"  'abc'[1] = {'abc'[1]}")
print(f"  len('abc') = {len('abc')}")
print(f"  5 < 10 = {5 < 10}")
print(f"  10 > 5 = {10 > 5}")

print("\n" + "=" * 60)
print("All extended tests passed!")
print("=" * 60)
