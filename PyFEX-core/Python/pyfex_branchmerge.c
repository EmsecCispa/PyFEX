/* PyFEX Branch Merge Mechanism
 *
 * Tracks forked execution branches and merges their state at
 * reconvergence points (post-dominators). Uses shared memory
 * to transfer state between parent and child processes.
 */

#include "Python.h"
#include "pyfex.h"
#include "pyfex_sharedmem.h"
#include "dummyobject.h"
#include "frameobject.h"
#include "opcode.h"

#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* ========== Branch Merge Globals ========== */

BranchMergeInfo _Py_ForceExec_BranchStack[MAX_BRANCH_DEPTH];
volatile int _Py_ForceExec_BranchStackTop = 0;

MergedStateEntry _Py_ForceExec_MergedStateStack[MAX_BRANCH_DEPTH];
volatile int _Py_ForceExec_MergedStateStackTop = 0;

int *_Py_ForceExec_BranchCounter = NULL;

// Re-entrancy guard for LoadAndMergeChildState
int _Py_ForceExec_MergeInProgress = 0;

/* ========== Internal Helpers ========== */

static int _Py_ForceExec_AddLongMetadata(PyObject *state, const char *key, long value) {
    PyObject *number = PyLong_FromLong(value);
    if (number == NULL) {
        return 0;
    }
    if (PyDict_SetItemString(state, key, number) < 0) {
        Py_DECREF(number);
        return 0;
    }
    Py_DECREF(number);
    return 1;
}

static int _Py_ForceExec_AddScopeMetadata(PyObject *state, PyFrameObject *f) {
    if (!f || !f->f_code || !f->f_code->co_filename || !f->f_code->co_name) {
        return 1;
    }

    PyObject *scope = PyUnicode_FromFormat("%U:%U", f->f_code->co_filename, f->f_code->co_name);
    if (scope == NULL) {
        return 0;
    }
    if (PyDict_SetItemString(state, "scope", scope) < 0) {
        Py_DECREF(scope);
        return 0;
    }
    Py_DECREF(scope);
    return 1;
}

static PyObject *_Py_ForceExec_CopyPicklableDict(PyObject *source, int filter_globals,
                                                 Py_ssize_t *skipped_count) {
    PyObject *filtered = PyDict_New();
    if (filtered == NULL) {
        return NULL;
    }

    if (source == NULL || !PyDict_Check(source)) {
        return filtered;
    }

    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next(source, &pos, &key, &value)) {
        if (filter_globals) {
            const char *key_str = PyUnicode_Check(key) ? PyUnicode_AsUTF8(key) : NULL;
            if (key_str && key_str[0] == '_') {
                continue;
            }
            if (PyModule_Check(value) || PyType_Check(value) || PyCFunction_Check(value)) {
                continue;
            }
        }

        PyObject *probe = _Py_PickleObject(value);
        if (probe == NULL) {
            PyErr_Clear();
            (*skipped_count)++;
            continue;
        }
        Py_DECREF(probe);

        if (PyDict_SetItem(filtered, key, value) < 0) {
            Py_DECREF(filtered);
            return NULL;
        }
    }

    return filtered;
}

// Helper to check if needle is in comma-separated haystack
static int _Py_ForceExec_CheckScope(const char *haystack, const char *needle) {
    if (!haystack || !needle || !*needle) return 0;
    const char *p = haystack;
    size_t len = strlen(needle);
    while ((p = strstr(p, needle)) != NULL) {
        if ((p == haystack || p[-1] == ',') &&
            (p[len] == '\0' || p[len] == ',')) {
            return 1;
        }
        p++;
    }
    return 0;
}

// Helper: decode instruction at index, handling EXTENDED_ARG prefixes.
static void _Py_ForceExec_DecodeInstr(const _Py_CODEUNIT *first_instr, Py_ssize_t code_len,
                                       int *idx, int *out_opcode, int *out_oparg) {
    _Py_CODEUNIT instr = first_instr[*idx];
    int opcode = _Py_OPCODE(instr);
    int oparg_val = _Py_OPARG(instr);

    while (opcode == EXTENDED_ARG && *idx + 1 < code_len) {
        (*idx)++;
        instr = first_instr[*idx];
        oparg_val = (oparg_val << 8) | _Py_OPARG(instr);
        opcode = _Py_OPCODE(instr);
    }
    *out_opcode = opcode;
    *out_oparg = oparg_val;
}

// Compute byte-offset destination for a jump instruction at index i
static int _Py_ForceExec_JumpDest(int opcode, int oparg_val, int instr_idx) {
    if (opcode == JUMP_FORWARD) {
        int next_instr_offset = (instr_idx + 1) * (int)sizeof(_Py_CODEUNIT);
        return next_instr_offset + oparg_val * (int)sizeof(_Py_CODEUNIT);
    }
    if (opcode == JUMP_ABSOLUTE) {
        return oparg_val * (int)sizeof(_Py_CODEUNIT);
    }
    return -1;
}

/* ========== Public Functions ========== */

int _Py_ForceExec_BeginMergeSection(void) {
    if (_Py_ForceExec_MergeInProgress) {
        return 0;
    }
    _Py_ForceExec_MergeInProgress = 1;
    return 1;
}

void _Py_ForceExec_EndMergeSection(void) {
    _Py_ForceExec_MergeInProgress = 0;
}

int _Py_ForceExec_ShouldMerge(PyFrameObject *f) {
    char *enable_env = getenv("FORCE_EXEC_MERGE_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        return 0;
    }

    // Check file scope
    char *scope_file = getenv("FORCE_EXEC_MERGE_SCOPE_FILE");
    if (scope_file && *scope_file) {
        if (!f || !f->f_code || !f->f_code->co_filename) return 0;
        const char *filename = PyUnicode_AsUTF8(f->f_code->co_filename);
        if (!filename) return 0;

        // Check basename
        const char *base = strrchr(filename, '/');
        base = base ? base + 1 : filename;

        if (!_Py_ForceExec_CheckScope(scope_file, base) &&
            !_Py_ForceExec_CheckScope(scope_file, filename)) {
            return 0;
        }
    }

    // Check function scope
    char *scope_func = getenv("FORCE_EXEC_MERGE_SCOPE_FUNC");
    if (scope_func && *scope_func) {
        if (!f || !f->f_code || !f->f_code->co_name) return 0;
        const char *funcname = PyUnicode_AsUTF8(f->f_code->co_name);
        if (!funcname) return 0;

        if (!_Py_ForceExec_CheckScope(scope_func, funcname)) {
            return 0;
        }
    }

    return 1;
}

/* Returns 1 if the opcode opens a new nested control-flow region whose
 * interior merges/terminators must be ignored while computing the outer
 * merge point. Covers boolean branches, exception handling (try/except),
 * and context managers (with). */
static int _Py_ForceExec_IsNestingOpener(int op) {
    return op == POP_JUMP_IF_FALSE || op == POP_JUMP_IF_TRUE
        || op == JUMP_IF_FALSE_OR_POP || op == JUMP_IF_TRUE_OR_POP
        || op == JUMP_IF_NOT_EXC_MATCH
        || op == SETUP_FINALLY
        || op == SETUP_WITH;
}

/* Returns 1 if the opcode unconditionally terminates the current branch.
 * After one of these at depth 0, the fall-through branch is dead and no
 * merge point will be reached via a later skip-jump. */
static int _Py_ForceExec_IsBranchTerminator(int op) {
    return op == RETURN_VALUE || op == RAISE_VARARGS || op == RERAISE;
}

// Compute the immediate post-dominator for a conditional jump.
// Handles simple if/else, if/elif/else chains, nested conditionals,
// try/except, with-blocks, and early-return / raise branches.
int _Py_ForceExec_ComputeMergePoint(PyCodeObject *code, int fork_offset, int jump_target) {
    const _Py_CODEUNIT *first_instr = (_Py_CODEUNIT *)PyBytes_AS_STRING(code->co_code);
    Py_ssize_t code_len_bytes = PyBytes_GET_SIZE(code->co_code);
    Py_ssize_t code_len = code_len_bytes / sizeof(_Py_CODEUNIT);

    int fork_idx = fork_offset / (int)sizeof(_Py_CODEUNIT);
    int jump_idx = jump_target / (int)sizeof(_Py_CODEUNIT);

    if (jump_target <= fork_offset || jump_idx >= code_len) {
        // Backward jump (loop) or invalid - merge at end of code
        return (int)code_len_bytes;
    }

    // Pass 1: Scan the fall-through (true) branch for JUMP_FORWARD/JUMP_ABSOLUTE
    // that skips over the else block. Track nesting to ignore inner-conditional jumps.
    int candidate_merge = -1;
    int nesting = 0;

    for (int i = fork_idx + 1; i < jump_idx && i < code_len; i++) {
        int op, arg;
        _Py_ForceExec_DecodeInstr(first_instr, code_len, &i, &op, &arg);

        if (_Py_ForceExec_IsNestingOpener(op)) {
            nesting++;
            continue;
        }

        if (nesting > 0) {
            if (op == JUMP_FORWARD || op == JUMP_ABSOLUTE) {
                int dest = _Py_ForceExec_JumpDest(op, arg, i);
                // Check if this jump exits the nested block
                if (dest >= jump_target) {
                    nesting--;
                }
            }
            continue;
        }

        if (op == JUMP_FORWARD || op == JUMP_ABSOLUTE) {
            int dest = _Py_ForceExec_JumpDest(op, arg, i);
            if (dest >= jump_target) {
                candidate_merge = dest;
                break; // First depth-0 skip jump in the true branch
            }
        }

        // Depth-0 branch terminator: no further merge via skip-jump is
        // possible from this path.
        if (_Py_ForceExec_IsBranchTerminator(op)) {
            break;
        }
    }

    if (candidate_merge < 0) {
        // No jump found in true branch - simple if without else, or the
        // true branch terminates (return / raise). Merge at jump_target.
        return jump_target;
    }

    // Pass 2: Scan from jump_target (else/elif block) to candidate_merge.
    nesting = 0;
    int max_merge = candidate_merge;

    for (int i = jump_idx; i < code_len; i++) {
        int byte_offset = i * (int)sizeof(_Py_CODEUNIT);
        if (byte_offset >= max_merge) break;

        int op, arg;
        _Py_ForceExec_DecodeInstr(first_instr, code_len, &i, &op, &arg);

        if (_Py_ForceExec_IsNestingOpener(op)) {
            nesting++;
            continue;
        }

        if (nesting > 0) {
            if (op == JUMP_FORWARD || op == JUMP_ABSOLUTE) {
                int dest = _Py_ForceExec_JumpDest(op, arg, i);
                if (dest >= byte_offset) {
                    nesting--;
                }
            }
            continue;
        }

        if (op == JUMP_FORWARD || op == JUMP_ABSOLUTE) {
            int dest = _Py_ForceExec_JumpDest(op, arg, i);
            if (dest >= jump_target && dest > byte_offset) {
                // Another elif branch ending — take the maximum destination
                if (dest > max_merge) {
                    max_merge = dest;
                }
            }
        }

        // A depth-0 terminator in the else/elif region ends this branch's
        // contribution; no more skip-jumps will extend the merge point.
        if (_Py_ForceExec_IsBranchTerminator(op)) {
            break;
        }
    }

    return max_merge;
}

// Save current frame state to shared memory for branch merging
void _Py_ForceExec_SaveBranchState(PyFrameObject *f, BranchMergeInfo *info) {
    if (!_Py_ForceExec_InitSharedMem()) {
        return;
    }

    // Create a dict with locals and important frame info
    PyObject *state = PyDict_New();
    if (!state) return;

    // Get locals
    if (PyFrame_FastToLocalsWithError(f) < 0) {
        Py_DECREF(state);
        return;
    }

    Py_ssize_t skipped_locals = 0;
    Py_ssize_t skipped_globals = 0;

    if (f->f_locals) {
        PyObject *filtered_locals = _Py_ForceExec_CopyPicklableDict(
            f->f_locals, 0, &skipped_locals);
        if (filtered_locals == NULL) {
            Py_DECREF(state);
            return;
        }
        if (PyDict_SetItemString(state, "locals", filtered_locals) < 0) {
            Py_DECREF(filtered_locals);
            Py_DECREF(state);
            return;
        }
        Py_DECREF(filtered_locals);
    }

    // Get globals (only items from the main script, not builtins)
    if (f->f_globals) {
        PyObject *filtered_globals = _Py_ForceExec_CopyPicklableDict(
            f->f_globals, 1, &skipped_globals);
        if (filtered_globals == NULL) {
            Py_DECREF(state);
            return;
        }
        if (PyDict_SetItemString(state, "globals", filtered_globals) < 0) {
            Py_DECREF(filtered_globals);
            Py_DECREF(state);
            return;
        }
        Py_DECREF(filtered_globals);
    }

    // Add metadata
    if (!_Py_ForceExec_AddLongMetadata(state, "branch_id", info->branch_id) ||
        PyDict_SetItemString(state, "is_child", info->is_child ? Py_True : Py_False) < 0 ||
        !_Py_ForceExec_AddLongMetadata(state, "pid", getpid()) ||
        !_Py_ForceExec_AddLongMetadata(state, "fork_offset", info->fork_offset) ||
        !_Py_ForceExec_AddLongMetadata(state, "merge_offset", info->merge_offset) ||
        !_Py_ForceExec_AddLongMetadata(state, "skipped_locals", skipped_locals) ||
        !_Py_ForceExec_AddLongMetadata(state, "skipped_globals", skipped_globals) ||
        !_Py_ForceExec_AddScopeMetadata(state, f)) {
        Py_DECREF(state);
        return;
    }

    // Pickle the state
    PyObject *pickled = _Py_PickleObject(state);
    Py_DECREF(state);

    if (!pickled) {
        PyErr_Clear();  // Ignore pickle errors for non-picklable objects
        return;
    }

    // Create scope key for this branch state
    char scope_key[256];
    snprintf(scope_key, sizeof(scope_key), "_branch_%d_%s",
             info->branch_id, info->is_child ? "child" : "parent");

    // Store in shared memory
    const char *name = "branch_state";
    char *data = PyBytes_AsString(pickled);
    Py_ssize_t data_len = PyBytes_Size(pickled);

    size_t name_len = strlen(name);
    size_t scope_len = strlen(scope_key);
    size_t entry_size = 4 + name_len + 4 + scope_len + 4 + data_len;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    if (_Py_ForceExec_SharedMem->offset + entry_size <= SHARED_MEM_SIZE) {
        char *ptr = _Py_ForceExec_SharedMem->data + _Py_ForceExec_SharedMem->offset;

        *(uint32_t*)ptr = (uint32_t)name_len; ptr += 4;
        memcpy(ptr, name, name_len); ptr += name_len;

        *(uint32_t*)ptr = (uint32_t)scope_len; ptr += 4;
        memcpy(ptr, scope_key, scope_len); ptr += scope_len;

        *(uint32_t*)ptr = (uint32_t)data_len; ptr += 4;
        memcpy(ptr, data, data_len);

        _Py_ForceExec_SharedMem->offset += entry_size;

        _Py_ForceExec_Log("MERGE_SAVE: branch_id=%d, is_child=%d, pid=%d, offset=%d\n",
                          info->branch_id, info->is_child, getpid(), info->merge_offset);
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    Py_DECREF(pickled);
}

// Load child's branch state from shared memory and merge into parent's frame.
// Called by the parent process at the post-dominator merge point.
// Conflict resolution: prefer concrete values over DummyObjects.
void _Py_ForceExec_LoadAndMergeChildState(PyFrameObject *f, BranchMergeInfo *info) {
    PyObject *child_state = NULL;
    if (!_Py_ForceExec_InitSharedMem()) {
        return;
    }

    // Construct the scope key for the child's branch state
    char child_scope[256];
    snprintf(child_scope, sizeof(child_scope), "_branch_%d_child", info->branch_id);

    // Wait briefly for child to save its state
    char *wait_env = getenv("FORCE_EXEC_MERGE_WAIT_MS");
    int wait_ms = wait_env ? atoi(wait_env) : 50;
    if (wait_ms < 0) wait_ms = 0;
    if (wait_ms > 5000) wait_ms = 5000; // Cap at 5s

    int found = 0;
    for (int elapsed = 0; elapsed < wait_ms; elapsed++) {
        // Reap child if it has exited
        int status;
        if (info->child_pid > 0) {
            waitpid(info->child_pid, &status, WNOHANG);
        }

        found = _Py_ForceExec_SharedMem_HasEntry("branch_state", child_scope);
        if (found) break;
        usleep(1000); // 1ms
    }

    if (!found) {
        _Py_ForceExec_Log("MERGE_ABSORB: no child state found for branch_id=%d after %dms\n",
                          info->branch_id, wait_ms);
        // Reap zombie child one more time
        if (info->child_pid > 0) {
            int status;
            waitpid(info->child_pid, &status, WNOHANG);
        }
        goto done;
    }

    // Load child state from shared memory
    child_state = _Py_ForceExec_SharedMem_Recover("branch_state", child_scope);
    if (child_state == NULL || !PyDict_Check(child_state)) {
        Py_XDECREF(child_state);
        _Py_ForceExec_Log("MERGE_ABSORB: failed to unpickle child state for branch_id=%d\n",
                          info->branch_id);
        child_state = NULL;
        goto done;
    }

    // Sync parent's fast locals to f_locals dict
    if (PyFrame_FastToLocalsWithError(f) < 0) {
        Py_DECREF(child_state);
        PyErr_Clear();
        child_state = NULL;
        goto done;
    }

    // Merge child locals into parent frame
    PyObject *child_locals = PyDict_GetItemString(child_state, "locals"); // borrowed
    if (child_locals && PyDict_Check(child_locals) && f->f_locals) {
        PyObject *key, *child_val;
        Py_ssize_t pos = 0;
        int merged_count = 0;

        while (PyDict_Next(child_locals, &pos, &key, &child_val)) {
            PyObject *parent_val = PyDict_GetItem(f->f_locals, key); // borrowed

            // Conflict resolution:
            // - Parent has NULL/missing or DummyObject, child has concrete -> use child's
            // - Both concrete -> keep parent (natural path priority)
            // - Both dummy -> keep parent's
            if (parent_val == NULL || Py_IS_TYPE(parent_val, &PyDummy_Type)) {
                if (!Py_IS_TYPE(child_val, &PyDummy_Type)) {
                    PyDict_SetItem(f->f_locals, key, child_val);
                    merged_count++;
                }
            }
        }

        // Sync back to fast locals
        if (merged_count > 0) {
            PyFrame_LocalsToFast(f, 0);
        }

        _Py_ForceExec_Log("MERGE_ABSORB: branch_id=%d, merged %d concrete values from child\n",
                          info->branch_id, merged_count);
    }

    // Merge child globals into parent globals (same conflict resolution)
    PyObject *child_globals = PyDict_GetItemString(child_state, "globals"); // borrowed
    if (child_globals && PyDict_Check(child_globals) && f->f_globals) {
        PyObject *key, *child_val;
        Py_ssize_t pos = 0;

        while (PyDict_Next(child_globals, &pos, &key, &child_val)) {
            PyObject *parent_val = PyDict_GetItem(f->f_globals, key); // borrowed

            if (parent_val == NULL || Py_IS_TYPE(parent_val, &PyDummy_Type)) {
                if (!Py_IS_TYPE(child_val, &PyDummy_Type)) {
                    PyDict_SetItem(f->f_globals, key, child_val);
                }
            }
        }
    }

    // Store merged state in MergedStateStack for peer query on crash
    if (_Py_ForceExec_MergedStateStackTop < MAX_BRANCH_DEPTH) {
        MergedStateEntry *entry = &_Py_ForceExec_MergedStateStack[
            _Py_ForceExec_MergedStateStackTop++];
        entry->branch_id = info->branch_id;
        entry->merged_locals = child_locals;
        Py_XINCREF(child_locals);
        entry->merged_globals = child_globals;
        Py_XINCREF(child_globals);
        entry->valid = 1;
    }

done:
    // Reap child process
    if (info->child_pid > 0) {
        int status;
        waitpid(info->child_pid, &status, WNOHANG);
    }

    if (child_state != NULL) {
        int removed_live = _Py_ForceExec_SharedMem_RemoveLiveEntriesByPid(info->child_pid);
        int removed_snapshot = _Py_ForceExec_SharedMem_RemoveEntry("branch_state", child_scope);
        if (removed_live > 0 || removed_snapshot > 0) {
            _Py_ForceExec_Log(
                "MERGE_CLEANUP: branch_id=%d, child_pid=%d, removed_live=%d, removed_snapshots=%d\n",
                info->branch_id, info->child_pid, removed_live, removed_snapshot);
        }
    }

    Py_XDECREF(child_state);
}
