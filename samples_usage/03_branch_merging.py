"""Feature 3 -- Branch Merging (path reconvergence).

Forced execution alone forks at every branch, which multiplies processes. Branch
merging lets each forked child run only up to the branch's reconvergence
(post-dominator) point, publish its state to shared memory, and exit there --
so the parent absorbs what the alternate path computed without the process tree
exploding. This is what makes whole-program forced execution tractable.

Run (from the artifact root, after building PyFEX-core):

    FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 \
        PyFEX-core/python samples_usage/03_branch_merging.py

Expected: both the True and False configuration branches are explored, and
execution continues PAST the merge point exactly once (the `after merge` line
is not duplicated for every nested branch).
"""


def feature_enabled() -> bool:
    return False  # concretely disabled


# flush=True so the forked child's line survives its ``_exit`` at the merge.
if feature_enabled():
    mode = "stage-2-active"
    print("[branch] feature ON path explored", flush=True)
else:
    mode = "stage-1-only"
    print("[branch] feature OFF path explored", flush=True)

# Reconvergence point: both branches have been explored; the parent resumes the
# single concrete continuation here rather than re-running it per fork.
print("after merge -- continuing with mode:", mode, flush=True)
print("done", flush=True)
