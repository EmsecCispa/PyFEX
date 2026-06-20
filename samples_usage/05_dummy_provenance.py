"""Feature 5 -- DummyObject provenance (symbolic trace).

Every DummyObject produced by crash recovery carries a trace of how it was
derived. With PYFEX_PROVENANCE_MODE=recursive the trace is a nested symbolic
expression, so an analyst can see exactly which failed value flowed into which
operations -- e.g. a recovered missing value that was incremented and then
indexed shows up as SUBSCRIPT(ADD(dummy, 1), 2).

Run (from the artifact root, after building PyFEX-core):

    CRASH_RECOVERY_ENABLE=1 PYFEX_PROVENANCE_MODE=recursive \
        PyFEX-core/python samples_usage/05_dummy_provenance.py

Expected: `.provenance` prints the nested expression and `.trace` shows the
origin plus a "Symbolic provenance:" section.
"""

missing = config_value_that_does_not_exist     # crash recovery -> seed dummy
derived = (missing + 1)[2]                      # ADD, then SUBSCRIPT

print("provenance:", derived.provenance)
print("-" * 60)
print(derived.trace)
print("done")
