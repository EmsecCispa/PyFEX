"""Feature 1 -- Forced Execution.

PyFEX forks a child process at conditional branches, so BOTH sides of an `if`
are exercised in a single run. Evasive code often hides its payload behind a
check that is false in a normal sandbox (anti-analysis guard, kill-switch,
date/host check); forced execution reaches that hidden branch anyway.

Run (from the artifact root, after building PyFEX-core):

    FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
        PyFEX-core/python samples_usage/01_forced_execution.py

Expected: you see BOTH the concrete (benign) line and the forced (hidden) line,
even though the guard concretely evaluates so the hidden branch would never run
normally. Branch merging keeps the exploration bounded.
"""


def looks_like_analysis_sandbox() -> bool:
    # In real malware this might inspect the hostname, MAC address, debugger,
    # or a kill date. Here it concretely returns True (so the payload branch
    # would normally be skipped).
    return True


# flush=True matters under forced execution: the forked child that takes the
# alternate branch ``_exit``s at the reconvergence point without flushing
# buffered stdout, so its line would otherwise be lost when output is piped.
if looks_like_analysis_sandbox():
    print("[concrete branch] environment looks monitored -- staying benign", flush=True)
else:
    # Forced execution still drives a child into this branch.
    print("[forced branch] HIDDEN PAYLOAD reached: would download & run stage 2", flush=True)

print("done", flush=True)
