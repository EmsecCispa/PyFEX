/* PyFEX Core API
 *
 * Branch merging, forced execution, crash recovery, and logging.
 * This header is included by ceval.c for inline eval-loop modifications.
 */

#ifndef Py_PYFEX_H
#define Py_PYFEX_H

#include "Python.h"
#include "frameobject.h"
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ========== Limit Defaults ========== */

#define FORCE_EXEC_GLOBAL_LIMIT_DEFAULT 100
#define FORCE_EXEC_LOCATION_LIMIT_DEFAULT 10
#define CRASH_RECOVERY_GLOBAL_LIMIT_DEFAULT 1000
#define CRASH_RECOVERY_LOCATION_LIMIT_DEFAULT 50

/* Hard cap on the number of *live* forced child processes at once
 * (memory safety; bounds concurrent CPython interpreters regardless of
 * merge state or loop shape). Operative value: env FORCE_EXEC_MAX_PROCS.
 * Its upper bound: env FORCE_EXEC_MAX_PROCS_HARD_CAP. */
#define FORCE_EXEC_MAX_PROCS_DEFAULT 8
#define FORCE_EXEC_MAX_PROCS_HARD_CAP_DEFAULT 256

/* ========== Branch Merge ========== */

#define MAX_BRANCH_DEPTH 64

typedef struct {
    int fork_offset;       /* Bytecode offset where fork occurred */
    int merge_offset;      /* Computed merge point (post-dominator) */
    int branch_id;         /* Unique ID for this branch pair */
    int is_child;          /* 1 if this is the child process */
    pid_t parent_pid;      /* Parent's PID for coordination */
    pid_t child_pid;       /* Child's PID (set by parent after fork) */
    PyObject *fork_filename;  /* Filename where fork occurred (for scoping) */
} BranchMergeInfo;

typedef struct {
    int branch_id;           /* Which branch this merged state belongs to */
    PyObject *merged_locals;  /* Dict: varname -> concrete value from child */
    PyObject *merged_globals; /* Dict: varname -> concrete value from child */
    int valid;               /* 1 if populated, 0 if not */
} MergedStateEntry;

/* Branch merge globals -- defined in pyfex_branchmerge.c */
extern BranchMergeInfo _Py_ForceExec_BranchStack[MAX_BRANCH_DEPTH];
extern volatile int _Py_ForceExec_BranchStackTop;
extern MergedStateEntry _Py_ForceExec_MergedStateStack[MAX_BRANCH_DEPTH];
extern volatile int _Py_ForceExec_MergedStateStackTop;
extern int *_Py_ForceExec_BranchCounter;
extern int _Py_ForceExec_MergeInProgress;
extern int _Py_ForceExec_IsForcedChildProcess;

/* Branch merge functions */
int _Py_ForceExec_BeginMergeSection(void);
void _Py_ForceExec_EndMergeSection(void);
int _Py_ForceExec_ShouldMerge(PyFrameObject *f);
int _Py_ForceExec_ComputeMergePoint(PyCodeObject *code, int fork_offset, int jump_target);
void _Py_ForceExec_SaveBranchState(PyFrameObject *f, BranchMergeInfo *info);
void _Py_ForceExec_LoadAndMergeChildState(PyFrameObject *f, BranchMergeInfo *info);

/* ========== Force Execution ========== */

int _Py_ForceExec_ShouldFork(PyFrameObject *f);
int _Py_ForceExec_ShouldTrackScope(PyFrameObject *f);

/* fork() wrapper for every PyFEX fork site: atomically reserves and
 * registers the child in the shared live-PID registry that backs the
 * concurrent-process cap. Returns >0 in parent, 0 in child, -1 on fork
 * failure, and -2 (without forking) when the cap is already reached. */
pid_t _Py_ForceExec_Fork(void);

/* Side-effect-free predicate for call-logging sites: forced execution is
 * enabled and the frame is in scope. Does NOT touch fork counters or the
 * concurrency registry (so logging never consumes fork budget/slots). */
int _Py_ForceExec_ShouldLogCall(PyFrameObject *f);

/* ========== Loop iteration cap ==========
 *
 * Bounds the number of times a loop header is executed in a given frame.
 * Used to break infinite or excessively long loops during forced execution.
 *
 * Only active when FORCE_EXEC_ENABLE=1 and the current frame is in target
 * scope. Reads FORCE_EXEC_LOOP_ITER_LIMIT (default 200). Increments the
 * per-(frame, offset) counter and returns 1 when the counter reaches the
 * limit; callers should then skip the backward jump (or force a FOR_ITER
 * exit) so the loop terminates.
 */
#define FORCE_EXEC_LOOP_ITER_LIMIT_DEFAULT 200

int _Py_ForceExec_LoopIterCapHit(PyFrameObject *f, int offset);

/* Called from frame_dealloc to drop counter entries that reference the
 * frame being torn down. Prevents stale counts from leaking to the next
 * frame allocated at the same memory address (CPython's zombie-frame
 * reuse pattern). Safe to call with the loop-cap feature disabled. */
void _Py_ForceExec_LoopIterCapForgetFrame(PyFrameObject *f);

/* FOR_ITER item-injection tracking.
 * MarkYielded is called whenever a FOR_ITER site pushes an item onto
 * the stack (real or synthetic). HasYielded returns 1 if that site has
 * ever yielded an item on the current (frame, offset). Used to gate
 * item-injection so we only inject when the iterator was empty from
 * the start, not when a real iterator naturally ran out. */
void _Py_ForceExec_ForIterMarkYielded(PyFrameObject *f, int offset);
int _Py_ForceExec_ForIterHasYielded(PyFrameObject *f, int offset);

/* Return a new awaitable that resolves immediately to `value` without
 * ever yielding to an event loop. Implemented as a zero-yield Python
 * generator whose return is `value`, so the standard await protocol
 * drives it in one `__next__` call and extracts `value` from
 * StopIteration. Returns a new reference, or NULL on failure. */
PyObject *_Py_ForceExec_MakeSyntheticAwaitable(PyObject *value);

/* Return a new async iterator that yields one synthetic awaitable
 * (resolving to a DummyObject) then raises StopAsyncIteration. New
 * reference; NULL on failure. */
PyObject *_Py_ForceExec_MakeSyntheticAsyncIter(PyObject *value);

/* ========== Crash Recovery ========== */

int _Py_CrashRecovery_ShouldRecover(PyFrameObject *f);

PyObject *_Py_ForceExec_RecoverFromMergedState(
    PyThreadState *tstate, PyFrameObject *f,
    const char *opcode_name, int opcode, int oparg);

PyObject *_Py_ForceExec_TryAlternativeValues(
    PyThreadState *tstate, PyFrameObject *f,
    int opcode, int oparg,
    PyObject *original_operand);

/* ========== Logging ========== */

void _Py_ForceExec_Log(const char *fmt, ...);
void _Py_CrashRecovery_Log(const char *fmt, ...);
void _Py_ForceExec_LogCall(PyObject *func, PyObject **args, Py_ssize_t nargs);
void _Py_ForceExec_LogCallTuple(PyObject *func, PyObject *args, PyObject *kwargs);
void _Py_PyFEX_TraceLogCall(
    PyObject *func,
    PyFrameObject *caller,
    PyObject **args,
    Py_ssize_t nargs,
    PyObject *kwnames);
void _Py_PyFEX_TraceLogCallTuple(
    PyObject *func,
    PyFrameObject *caller,
    PyObject *args,
    PyObject *kwargs);
void _Py_PyFEX_RuntimeLogRecovery(
    const char *opcode_name,
    PyFrameObject *frame,
    PyObject *recovered);

/* ========== Dormant Function Analysis ========== */

void _Py_DormantFunc_Log(const char *prefix, PyObject *func, PyFrameObject *f);

/* ========== Scope and whitelist ========== */

/* Return 1 if the frame's source file is in target scope (main script or
 * under PYFEX_SCOPE_DIR), with f_back fallback for dynamic code. */
int _Py_PyFEX_FrameInScope(PyFrameObject *f);

/* Same for a bare code object (used when a callable's source file is
 * inspected without a live frame context, e.g. the call-hijack logic). */
int _Py_PyFEX_CodeInScope(PyCodeObject *code);

/* Return 1 if the callable is in the whitelist of builtins that should
 * always be allowed to run even with dummy arguments (print, repr, str,
 * type, isinstance, id, len, hash). */
int _Py_PyFEX_IsCallableWhitelisted(PyObject *func);

#ifdef __cplusplus
}
#endif
#endif /* !Py_PYFEX_H */
