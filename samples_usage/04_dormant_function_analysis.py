"""Feature 4 -- Dormant Function Analysis (DFA).

Malware frequently DEFINES a malicious function but only CALLS it under a
condition that never fires during analysis (a command from C2, a specific date,
a target check). PyFEX logs every defined-vs-called function, and the driver
`tools/dfa_driver.py` then proactively invokes each never-called ("dormant")
function in a fresh recovery-enabled process so its body actually executes.

Because the driver runs each dormant in an output-suppressed analysis process,
this demo also has every function append to the file named by
``PYFEX_DEMO_MARKER`` -- so you can confirm the dormant body really executed.

Two-step run (from the artifact root, after building PyFEX-core):

    # 1) Record DEFINED / CALLED functions while running the sample normally.
    DORMANT_FUNC_LOG_FILE=/tmp/dfa.log PYFEX_DEMO_MARKER=/tmp/dfa_marker.txt \
        PyFEX-core/python samples_usage/04_dormant_function_analysis.py

    # 2) Actively invoke the dormant functions found in that log.
    PYFEX_DEMO_MARKER=/tmp/dfa_marker.txt PYFEX_INTERPRETER=PyFEX-core/python \
        python3 tools/dfa_driver.py /tmp/dfa.log samples_usage/04_dormant_function_analysis.py

    # 3) Confirm the dormant body ran:
    cat /tmp/dfa_marker.txt          # contains an "exfiltrate ran" line

In step 1 only `install()` runs; `exfiltrate` is logged DEFINED but never CALLED.
In step 2 the driver synthesises an argument and runs `exfiltrate`'s body.
"""

import os

MARKER = os.environ.get("PYFEX_DEMO_MARKER")


def _note(line: str) -> None:
    if MARKER:
        with open(MARKER, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")


def exfiltrate(target):
    # Never called below -> dormant. The driver triggers it in step 2.
    print("[dormant] exfiltrate() body ran -- would upload data to", target)
    _note("exfiltrate ran (arg type: %s)" % type(target).__name__)


def install():
    print("[active] install() ran during normal execution")
    _note("install ran")


install()
print("done")
