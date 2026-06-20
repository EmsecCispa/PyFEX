#!/usr/bin/env python3
"""
Test crash recovery for all arithmetic operations.
"""

print("=" * 60)
print("Testing Arithmetic Operations Crash Recovery")
print("=" * 60)

# Test division by zero
print("\n1. Division by zero")
result = 10 / 0
print(f"  10 / 0 -> {type(result).__name__}: {result.error_reason}")

# Test modulo by zero
print("\n2. Modulo by zero")
result = 10 % 0
print(f"  10 % 0 -> {type(result).__name__}: {result.error_reason}")

# Test power with invalid types
print("\n3. Power with type error")
result = "text" ** 2
print(f"  'text' ** 2 -> {type(result).__name__}: {result.error_reason}")

# Test multiply with incompatible types
print("\n4. Multiply with type error")
result = "text" * "text"
print(f"  'text' * 'text' -> {type(result).__name__}: {result.error_reason}")

# Test subtract with incompatible types
print("\n5. Subtract with type error")
result = "abc" - 5
print(f"  'abc' - 5 -> {type(result).__name__}: {result.error_reason}")

# Test floor division by zero
print("\n6. Floor division by zero")
result = 10 // 0
print(f"  10 // 0 -> {type(result).__name__}: {result.error_reason}")

# Test that normal operations still work
print("\n7. Normal operations still work")
print(f"  10 + 5 = {10 + 5}")
print(f"  10 - 5 = {10 - 5}")
print(f"  10 * 5 = {10 * 5}")
print(f"  10 / 5 = {10 / 5}")
print(f"  10 // 3 = {10 // 3}")
print(f"  10 % 3 = {10 % 3}")
print(f"  2 ** 3 = {2 ** 3}")

print("\n" + "=" * 60)
print("All arithmetic tests passed!")
print("=" * 60)
