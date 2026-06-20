#!/usr/bin/env python3
"""Test line number tracking in eval() and exec() code - showing innermost frame."""

import sys
import traceback

def get_innermost_frame(exc_tb):
    """Get the innermost (deepest) frame from traceback"""
    frame = exc_tb
    while frame.tb_next is not None:
        frame = frame.tb_next
    return frame

def test_eval_single_line():
    """Test eval with single line"""
    print("\n=== Test 1: eval() single line ===")
    print("Code: eval('1 / 0')")
    try:
        result = eval("1 / 0")
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        inner_frame = get_innermost_frame(exc_tb)
        print(f"✓ Error in: {inner_frame.tb_frame.f_code.co_filename}")
        print(f"✓ Line number: {inner_frame.tb_lineno}")
        print(f"✓ Function: {inner_frame.tb_frame.f_code.co_name}")

def test_exec_multi_line():
    """Test exec with multi-line string"""
    print("\n=== Test 2: exec() multi-line ===")
    code = """
x = 10
y = 20
z = x / 0  # This should be line 4
result = z + 5
"""
    print(f"Code string:\n{code}")
    try:
        exec(code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        inner_frame = get_innermost_frame(exc_tb)
        print(f"✓ Error in: {inner_frame.tb_frame.f_code.co_filename}")
        print(f"✓ Line number: {inner_frame.tb_lineno} (within exec'd string)")
        print(f"✓ The error is at line 4 of the exec'd code")

def test_exec_with_custom_filename():
    """Test exec with custom filename marker"""
    print("\n=== Test 3: exec() with custom filename ===")
    code = """
a = 1
b = 2
c = a / 0  # Line 4
"""
    print("Using compile() with filename='<malware_payload>'")
    try:
        exec(compile(code, filename="<malware_payload>", mode="exec"))
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        inner_frame = get_innermost_frame(exc_tb)
        print(f"✓ Error in: {inner_frame.tb_frame.f_code.co_filename}")
        print(f"✓ Line number: {inner_frame.tb_lineno}")
        print(f"✓ Custom filename appears in traceback!")

def test_nested_exec():
    """Test nested exec - each has independent line numbering"""
    print("\n=== Test 4: Nested exec() ===")
    outer_code = """
print("In outer exec")
inner_code = '''
x = 5
y = x / 0  # Line 3 in inner
'''
print("About to exec inner")
exec(inner_code)  # Line 7 in outer
"""
    print("Outer code nests an inner exec()")
    try:
        exec(outer_code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()

        print("\n✓ Full frame stack:")
        frame = exc_tb
        depth = 0
        while frame is not None:
            print(f"  [{depth}] {frame.tb_frame.f_code.co_filename}:{frame.tb_lineno} in {frame.tb_frame.f_code.co_name}")
            depth += 1
            frame = frame.tb_next

        inner_frame = get_innermost_frame(exc_tb)
        print(f"\n✓ Innermost error at: {inner_frame.tb_frame.f_code.co_filename}:{inner_frame.tb_lineno}")

def test_single_line_multiple_statements():
    """Test single line with multiple statements"""
    print("\n=== Test 5: Single line, multiple statements ===")
    code = "a = 1; b = 2; c = a / 0; d = 4"
    print(f"Code: {code}")
    try:
        exec(code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        inner_frame = get_innermost_frame(exc_tb)
        print(f"✓ Error in: {inner_frame.tb_frame.f_code.co_filename}")
        print(f"✓ Line number: {inner_frame.tb_lineno} (all statements on line 1)")

def test_with_crash_recovery():
    """Test with PyFEX crash recovery enabled"""
    print("\n=== Test 6: With PyFEX crash recovery ===")
    print("This shows how you'd see it in crash recovery mode")

    code = """
data = [1, 2, 3]
for i, val in enumerate(data):
    result = 100 / (val - 2)  # Line 4, crashes when val=2
    print(f"Result {i}: {result}")
"""

    print("Code with loop that crashes on iteration 2:")
    print(code)

    try:
        exec(code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        inner_frame = get_innermost_frame(exc_tb)

        print(f"✓ Error location: {inner_frame.tb_frame.f_code.co_filename}:{inner_frame.tb_lineno}")
        print(f"✓ In crash recovery, this would create DummyObject at line {inner_frame.tb_lineno}")

        # Show what info is available for crash recovery
        code_obj = inner_frame.tb_frame.f_code
        print(f"\n✓ Available for DummyObject:")
        print(f"  - Filename: {code_obj.co_filename}")
        print(f"  - Function: {code_obj.co_name}")
        print(f"  - Line number: {inner_frame.tb_lineno}")
        print(f"  - Bytecode offset: {inner_frame.tb_lasti}")

def demonstrate_c_api_usage():
    """Show what you'd see from C API perspective"""
    print("\n=== Test 7: C API perspective ===")

    code = """
def injected_function():
    x = 10
    y = 0
    return x / y  # Line 5

injected_function()
"""

    print("Code with function definition in exec:")
    print(code)

    try:
        exec(code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()

        print("\n✓ All frames in traceback:")
        frame = exc_tb
        while frame is not None:
            code_obj = frame.tb_frame.f_code
            print(f"\n  Frame: {code_obj.co_name}")
            print(f"    Filename: {code_obj.co_filename}")
            print(f"    Line: {frame.tb_lineno}")
            print(f"    Bytecode offset: {frame.tb_lasti}")
            print(f"    First line of code: {code_obj.co_firstlineno}")

            # This is what you'd access in C:
            # frame->f_code->co_filename
            # PyCode_Addr2Line(frame->f_code, lasti)

            frame = frame.tb_next

if __name__ == "__main__":
    test_eval_single_line()
    test_exec_multi_line()
    test_exec_with_custom_filename()
    test_nested_exec()
    test_single_line_multiple_statements()
    test_with_crash_recovery()
    demonstrate_c_api_usage()

    print("\n" + "="*70)
    print("SUMMARY: Getting Line Numbers in eval()/exec()")
    print("="*70)
    print("✓ YES - eval()/exec() code HAS line numbers")
    print("✓ Line numbers are relative to the STRING, not the calling code")
    print("✓ Multi-line strings: each line gets its own number (1, 2, 3...)")
    print("✓ Single-line strings: everything is on line 1")
    print("✓ Filename is '<string>' by default, customizable with compile()")
    print("✓ From C API: Use PyCode_Addr2Line(code, lasti) as usual")
    print("✓ Nested exec: each level has independent line numbering")
    print("="*70)
