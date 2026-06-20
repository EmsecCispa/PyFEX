#!/usr/bin/env python3
"""Test line number tracking in eval() and exec() code."""

import sys
import traceback

def test_eval_single_line():
    """Test eval with single line - should show line 1"""
    print("\n=== Test 1: eval() single line ===")
    try:
        result = eval("1 / 0")  # Line 1 in eval'd code
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"Exception at: {exc_tb.tb_frame.f_code.co_filename}:{exc_tb.tb_lineno}")
        print(f"Function: {exc_tb.tb_frame.f_code.co_name}")
        traceback.print_exc()

def test_exec_single_line():
    """Test exec with single line - should show line 1"""
    print("\n=== Test 2: exec() single line ===")
    try:
        exec("result = 10 / 0")  # Line 1 in exec'd code
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"Exception at: {exc_tb.tb_frame.f_code.co_filename}:{exc_tb.tb_lineno}")
        traceback.print_exc()

def test_exec_multi_line():
    """Test exec with multi-line string - tracks each line"""
    print("\n=== Test 3: exec() multi-line ===")
    code = """
x = 10
y = 20
z = x / 0  # This is line 4 in the exec'd string
result = z + 5
"""
    try:
        exec(code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"Exception at: {exc_tb.tb_frame.f_code.co_filename}:{exc_tb.tb_lineno}")
        print(f"Code shows error at line {exc_tb.tb_lineno} of exec'd string")
        traceback.print_exc()

def test_exec_with_filename():
    """Test exec with custom filename"""
    print("\n=== Test 4: exec() with custom filename ===")
    code = """
a = 1
b = 2
c = a / 0  # Line 4
"""
    try:
        exec(compile(code, filename="<dynamic_payload>", mode="exec"))
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"Exception at: {exc_tb.tb_frame.f_code.co_filename}:{exc_tb.tb_lineno}")
        traceback.print_exc()

def test_nested_exec():
    """Test nested exec - each level has its own line numbering"""
    print("\n=== Test 5: Nested exec() ===")
    outer_code = """
inner_code = '''
x = 5
y = x / 0  # Line 3 in inner exec
'''
exec(inner_code)  # Line 5 in outer exec
"""
    try:
        exec(outer_code)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()

        # Walk the traceback to show all frames
        print("Traceback walk:")
        frame = exc_tb
        while frame is not None:
            print(f"  {frame.tb_frame.f_code.co_filename}:{frame.tb_lineno} in {frame.tb_frame.f_code.co_name}")
            frame = frame.tb_next

        print("\nFull traceback:")
        traceback.print_exc()

def test_compile_with_offset():
    """Test compile with line offset"""
    print("\n=== Test 6: compile() with line offset ===")

    # You can set a starting line number!
    code_str = "result = 100 / 0"
    code_obj = compile(code_str, filename="<injected>", mode="exec")

    # Note: There's no direct way to set line offset in compile(),
    # but the code object's co_firstlineno shows the first line
    print(f"Code first line number: {code_obj.co_firstlineno}")

    try:
        exec(code_obj)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"Exception at: {exc_tb.tb_frame.f_code.co_filename}:{exc_tb.tb_lineno}")

def inspect_exec_code_object():
    """Inspect the code object created by exec"""
    print("\n=== Test 7: Inspect exec code object ===")

    code_str = """
line_1 = 1
line_2 = 2
line_3 = 3 / 0
line_4 = 4
"""

    code_obj = compile(code_str, filename="<inspection>", mode="exec")

    print(f"Code object details:")
    print(f"  Filename: {code_obj.co_filename}")
    print(f"  First line: {code_obj.co_firstlineno}")
    print(f"  Line table: {code_obj.co_linetable}")
    print(f"  Name: {code_obj.co_name}")

    # Try to execute it
    try:
        exec(code_obj)
    except ZeroDivisionError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        print(f"\nException occurred at line {exc_tb.tb_lineno} in {exc_tb.tb_frame.f_code.co_filename}")

if __name__ == "__main__":
    test_eval_single_line()
    test_exec_single_line()
    test_exec_multi_line()
    test_exec_with_filename()
    test_nested_exec()
    test_compile_with_offset()
    inspect_exec_code_object()

    print("\n" + "="*60)
    print("Key Findings:")
    print("- eval()/exec() code has its own line numbering")
    print("- Line numbers start from 1 within the string")
    print("- Multi-line strings preserve line info")
    print("- You can set custom filename with compile()")
    print("- Each nested exec has independent line tracking")
    print("="*60)
