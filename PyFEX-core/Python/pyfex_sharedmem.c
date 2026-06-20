/* PyFEX Shared Memory Infrastructure
 *
 * Process-shared memory for inter-process communication during
 * forced execution. Pickle helpers for state serialization.
 * Builtin Python functions for object sharing across processes.
 */

#include "Python.h"
#include "pyfex_sharedmem.h"
#include "pyfex.h"
#include "dummyobject.h"
#include "frameobject.h"
#include "marshal.h"

#include <string.h>
#include <sys/mman.h>
#include <pthread.h>
#include <unistd.h>

/* ========== Shared Memory Globals ========== */

SharedMem *_Py_ForceExec_SharedMem = NULL;
int _Py_ForceExec_SharedMemIOInProgress = 0;

#define LIVE_PEER_ENTRY_NAME "live_peer_var"

/* ========== Pickle Cache (file-local) ========== */

static PyObject *cached_pickle_dumps = NULL;
static PyObject *cached_pickle_loads = NULL;

static int
_Py_ForceExec_ShouldRetainSharedState(void)
{
    char *retain_env = getenv("FORCE_EXEC_RETAIN_SHARED_STATE");
    return retain_env != NULL && strcmp(retain_env, "0") != 0;
}

/* ========== Shared Memory Init ========== */

int _Py_ForceExec_InitSharedMem(void) {
    if (_Py_ForceExec_SharedMem != NULL) return 1;

    // Allocate shared memory
    size_t total_size = sizeof(SharedMem) + SHARED_MEM_SIZE;
    _Py_ForceExec_SharedMem = mmap(NULL, total_size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);

    if (_Py_ForceExec_SharedMem == MAP_FAILED) {
        _Py_ForceExec_SharedMem = NULL;
        return 0;
    }

    // Initialize lock
    pthread_mutexattr_t attr;
    pthread_mutexattr_init(&attr);
    pthread_mutexattr_setpshared(&attr, PTHREAD_PROCESS_SHARED);
    pthread_mutex_init(&_Py_ForceExec_SharedMem->lock, &attr);
    pthread_mutexattr_destroy(&attr);

    _Py_ForceExec_SharedMem->offset = 0;
    return 1;
}

/* ========== Pickle Helpers ========== */

PyObject *_Py_PickleObject(PyObject *obj) {
    _Py_ForceExec_SharedMemIOInProgress++;
    if (cached_pickle_dumps == NULL) {
        PyObject *pickle = PyImport_ImportModule("pickle");
        if (!pickle) {
            _Py_ForceExec_SharedMemIOInProgress--;
            return NULL;
        }

        cached_pickle_dumps = PyObject_GetAttrString(pickle, "dumps");
        Py_DECREF(pickle);
        if (!cached_pickle_dumps) {
            _Py_ForceExec_SharedMemIOInProgress--;
            return NULL;
        }
    }

    PyObject *result = PyObject_CallOneArg(cached_pickle_dumps, obj);
    _Py_ForceExec_SharedMemIOInProgress--;
    return result;
}

PyObject *_Py_UnpickleObject(const char *data, Py_ssize_t size) {
    _Py_ForceExec_SharedMemIOInProgress++;
    if (cached_pickle_loads == NULL) {
        PyObject *pickle = PyImport_ImportModule("pickle");
        if (!pickle) {
            _Py_ForceExec_SharedMemIOInProgress--;
            return NULL;
        }

        cached_pickle_loads = PyObject_GetAttrString(pickle, "loads");
        Py_DECREF(pickle);
        if (!cached_pickle_loads) {
            _Py_ForceExec_SharedMemIOInProgress--;
            return NULL;
        }
    }

    PyObject *bytes = PyBytes_FromStringAndSize(data, size);
    if (!bytes) {
        _Py_ForceExec_SharedMemIOInProgress--;
        return NULL;
    }

    PyObject *obj = PyObject_CallOneArg(cached_pickle_loads, bytes);
    Py_DECREF(bytes);
    _Py_ForceExec_SharedMemIOInProgress--;
    return obj;
}

/* ========== Shared Memory Entry Operations ========== */

// Check if shared memory contains an entry with given name and scope
int _Py_ForceExec_SharedMem_HasEntry(const char *target_name, const char *target_scope) {
    if (_Py_ForceExec_SharedMem == NULL) return 0;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;
    int found = 0;

    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        ptr += d_len; // Skip data

        if (n_len == strlen(target_name) && memcmp(n_str, target_name, n_len) == 0) {
            if (target_scope == NULL) {
                found = 1;
            } else if (s_len == strlen(target_scope) && memcmp(s_str, target_scope, s_len) == 0) {
                found = 1;
            }
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return found;
}

// Recover the last matching object from shared memory (returns new reference or NULL)
PyObject *_Py_ForceExec_SharedMem_Recover(const char *target_name, const char *target_scope) {
    if (_Py_ForceExec_SharedMem == NULL) return NULL;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;

    char *found_data = NULL;
    Py_ssize_t found_len = 0;

    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        char *d_str = ptr; ptr += d_len;

        if (n_len == strlen(target_name) && memcmp(n_str, target_name, n_len) == 0) {
            if (target_scope == NULL) {
                found_data = d_str;
                found_len = d_len;
            } else if (s_len == strlen(target_scope) && memcmp(s_str, target_scope, s_len) == 0) {
                found_data = d_str;
                found_len = d_len;
            }
        }
    }

    PyObject *result = NULL;
    if (found_data) {
        result = _Py_UnpickleObject(found_data, found_len);
        if (result == NULL) {
            PyErr_Clear(); // Ignore unpickle errors
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return result;
}

static PyObject *_Py_ForceExec_FindConcreteInBranchState(PyObject *state, PyObject *var_name) {
    PyObject *locals = PyDict_GetItemString(state, "locals");
    if (locals && PyDict_Check(locals)) {
        PyObject *value = PyDict_GetItem(locals, var_name);
        if (value != NULL && !Py_IS_TYPE(value, &PyDummy_Type)) {
            Py_INCREF(value);
            return value;
        }
    }

    PyObject *globals = PyDict_GetItemString(state, "globals");
    if (globals && PyDict_Check(globals)) {
        PyObject *value = PyDict_GetItem(globals, var_name);
        if (value != NULL && !Py_IS_TYPE(value, &PyDummy_Type)) {
            Py_INCREF(value);
            return value;
        }
    }

    return NULL;
}

static int
_Py_ForceExec_UseLivePeerState(PyFrameObject *f)
{
    char *peer_env = getenv("CRASH_RECOVERY_PEER_QUERY");
    char *force_env = getenv("FORCE_EXEC_ENABLE");

    if (peer_env && strcmp(peer_env, "0") == 0) {
        return 0;
    }
    if (force_env == NULL || strcmp(force_env, "1") != 0) {
        return 0;
    }
    return _Py_ForceExec_ShouldTrackScope(f);
}

static PyObject *
_Py_ForceExec_LiveStateScope(PyFrameObject *f)
{
    if (!f || !f->f_code || !f->f_code->co_filename || !f->f_code->co_name) {
        return NULL;
    }
    return PyUnicode_FromFormat("%U:%U", f->f_code->co_filename, f->f_code->co_name);
}

static void
_Py_ForceExec_GetLiveBranchInfo(PyFrameObject *f, int *branch_id, int *is_child)
{
    *branch_id = -1;
    *is_child = _Py_ForceExec_IsForcedChildProcess;

    for (int i = _Py_ForceExec_BranchStackTop - 1; i >= 0; i--) {
        BranchMergeInfo *info = &_Py_ForceExec_BranchStack[i];
        if (info->fork_filename == f->f_code->co_filename) {
            *branch_id = info->branch_id;
            *is_child = info->is_child;
            return;
        }
        if (info->fork_filename != NULL && f != NULL && f->f_code != NULL &&
            f->f_code->co_filename != NULL) {
            int same_file = PyObject_RichCompareBool(
                info->fork_filename, f->f_code->co_filename, Py_EQ);
            if (same_file == 1) {
                *branch_id = info->branch_id;
                *is_child = info->is_child;
                return;
            }
            if (same_file < 0) {
                PyErr_Clear();
            }
        }
    }
}

static int
_Py_ForceExec_AppendEntry(const char *name, const char *scope, const char *data, Py_ssize_t data_len)
{
    size_t name_len = strlen(name);
    size_t scope_len = strlen(scope);
    size_t entry_size = 4 + name_len + 4 + scope_len + 4 + data_len;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    if (_Py_ForceExec_SharedMem->offset + entry_size > SHARED_MEM_SIZE) {
        pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
        return 0;
    }

    char *ptr = _Py_ForceExec_SharedMem->data + _Py_ForceExec_SharedMem->offset;

    *(uint32_t*)ptr = (uint32_t)name_len; ptr += 4;
    memcpy(ptr, name, name_len); ptr += name_len;

    *(uint32_t*)ptr = (uint32_t)scope_len; ptr += 4;
    memcpy(ptr, scope, scope_len); ptr += scope_len;

    *(uint32_t*)ptr = (uint32_t)data_len; ptr += 4;
    memcpy(ptr, data, data_len);

    _Py_ForceExec_SharedMem->offset += entry_size;
    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return 1;
}

static int
_Py_ForceExec_SharedMem_RemoveEntryUnlocked(const char *target_name, const char *target_scope)
{
    char *read_ptr = _Py_ForceExec_SharedMem->data;
    char *write_ptr = _Py_ForceExec_SharedMem->data;
    char *end = read_ptr + _Py_ForceExec_SharedMem->offset;
    size_t target_name_len = strlen(target_name);
    size_t target_scope_len = target_scope ? strlen(target_scope) : 0;
    int removed = 0;

    while (read_ptr < end) {
        char *entry_start = read_ptr;

        uint32_t n_len = *(uint32_t*)read_ptr; read_ptr += 4;
        char *n_str = read_ptr; read_ptr += n_len;

        uint32_t s_len = *(uint32_t*)read_ptr; read_ptr += 4;
        char *s_str = read_ptr; read_ptr += s_len;

        uint32_t d_len = *(uint32_t*)read_ptr; read_ptr += 4;
        read_ptr += d_len;

        size_t entry_size = (size_t)(read_ptr - entry_start);
        int matches = 0;

        if ((size_t)n_len == target_name_len &&
            memcmp(n_str, target_name, target_name_len) == 0) {
            if (target_scope == NULL) {
                matches = 1;
            } else if ((size_t)s_len == target_scope_len &&
                       memcmp(s_str, target_scope, target_scope_len) == 0) {
                matches = 1;
            }
        }

        if (matches) {
            removed++;
            continue;
        }

        if (write_ptr != entry_start) {
            memmove(write_ptr, entry_start, entry_size);
        }
        write_ptr += entry_size;
    }

    _Py_ForceExec_SharedMem->offset = (size_t)(write_ptr - _Py_ForceExec_SharedMem->data);
    return removed;
}

static int
_Py_ForceExec_SharedMem_RemoveLiveEntriesByPidUnlocked(pid_t pid)
{
    char *read_ptr = _Py_ForceExec_SharedMem->data;
    char *write_ptr = _Py_ForceExec_SharedMem->data;
    char *end = read_ptr + _Py_ForceExec_SharedMem->offset;
    size_t live_name_len = strlen(LIVE_PEER_ENTRY_NAME);
    int removed = 0;

    while (read_ptr < end) {
        char *entry_start = read_ptr;

        uint32_t n_len = *(uint32_t*)read_ptr; read_ptr += 4;
        char *n_str = read_ptr; read_ptr += n_len;

        uint32_t s_len = *(uint32_t*)read_ptr; read_ptr += 4;
        read_ptr += s_len;

        uint32_t d_len = *(uint32_t*)read_ptr; read_ptr += 4;
        char *d_str = read_ptr; read_ptr += d_len;

        size_t entry_size = (size_t)(read_ptr - entry_start);
        int matches = 0;

        if ((size_t)n_len == live_name_len &&
            memcmp(n_str, LIVE_PEER_ENTRY_NAME, live_name_len) == 0) {
            PyObject *state = PyMarshal_ReadObjectFromString(d_str, d_len);
            if (state != NULL && PyDict_Check(state)) {
                PyObject *state_pid = PyDict_GetItemString(state, "pid");
                if (state_pid != NULL && PyLong_Check(state_pid)) {
                    long state_pid_value = PyLong_AsLong(state_pid);
                    if (!PyErr_Occurred() && state_pid_value == (long)pid) {
                        matches = 1;
                    } else {
                        PyErr_Clear();
                    }
                }
            } else {
                PyErr_Clear();
            }
            Py_XDECREF(state);
        }

        if (matches) {
            removed++;
            continue;
        }

        if (write_ptr != entry_start) {
            memmove(write_ptr, entry_start, entry_size);
        }
        write_ptr += entry_size;
    }

    _Py_ForceExec_SharedMem->offset = (size_t)(write_ptr - _Py_ForceExec_SharedMem->data);
    return removed;
}

static int
_Py_ForceExec_PublishLiveState(PyFrameObject *f, PyObject *var_name, PyObject *value, int deleted)
{
    PyObject *scope_obj = NULL;
    PyObject *payload = NULL;
    PyObject *pickled = NULL;
    const char *scope = NULL;
    int branch_id = -1;
    int is_child = 0;
    int ok = 0;

    if (!_Py_ForceExec_UseLivePeerState(f) || !_Py_ForceExec_InitSharedMem()) {
        return 0;
    }
    if (var_name == NULL || !PyUnicode_Check(var_name)) {
        return 0;
    }
    if (!deleted) {
        if (value == NULL || Py_IS_TYPE(value, &PyDummy_Type)) {
            return 0;
        }
    }

    scope_obj = _Py_ForceExec_LiveStateScope(f);
    if (scope_obj == NULL) {
        return 0;
    }
    scope = PyUnicode_AsUTF8(scope_obj);
    if (scope == NULL) {
        Py_DECREF(scope_obj);
        PyErr_Clear();
        return 0;
    }

    _Py_ForceExec_GetLiveBranchInfo(f, &branch_id, &is_child);

    payload = PyDict_New();
    if (payload == NULL) {
        goto done;
    }
    if (PyDict_SetItemString(payload, "var_name", var_name) < 0) {
        goto done;
    }
    if (PyDict_SetItemString(payload, "deleted", deleted ? Py_True : Py_False) < 0) {
        goto done;
    }
    if (!deleted && PyDict_SetItemString(payload, "value", value) < 0) {
        goto done;
    }

    PyObject *pid_obj = PyLong_FromLong(getpid());
    PyObject *branch_obj = PyLong_FromLong(branch_id);
    if (pid_obj == NULL || branch_obj == NULL) {
        Py_XDECREF(pid_obj);
        Py_XDECREF(branch_obj);
        goto done;
    }
    if (PyDict_SetItemString(payload, "pid", pid_obj) < 0 ||
        PyDict_SetItemString(payload, "branch_id", branch_obj) < 0 ||
        PyDict_SetItemString(payload, "is_child", is_child ? Py_True : Py_False) < 0) {
        Py_DECREF(pid_obj);
        Py_DECREF(branch_obj);
        goto done;
    }
    Py_DECREF(pid_obj);
    Py_DECREF(branch_obj);

    pickled = PyMarshal_WriteObjectToString(payload, Py_MARSHAL_VERSION);
    if (pickled == NULL) {
        PyErr_Clear();
        _Py_CrashRecovery_Log("LIVE_PUBLISH: skipped '%s' due to marshal failure\n",
                              PyUnicode_AsUTF8(var_name));
        goto done;
    }

    ok = _Py_ForceExec_AppendEntry(
        LIVE_PEER_ENTRY_NAME,
        scope,
        PyBytes_AS_STRING(pickled),
        PyBytes_GET_SIZE(pickled));
    if (ok) {
        _Py_CrashRecovery_Log("LIVE_PUBLISH: scope=%s var=%s deleted=%d pid=%d branch_id=%d is_child=%d\n",
                              scope, PyUnicode_AsUTF8(var_name), deleted, getpid(), branch_id, is_child);
    } else {
        _Py_CrashRecovery_Log("LIVE_PUBLISH: shared memory full for '%s'\n",
                              PyUnicode_AsUTF8(var_name));
    }

done:
    Py_XDECREF(pickled);
    Py_XDECREF(payload);
    Py_DECREF(scope_obj);
    return ok;
}

PyObject *_Py_ForceExec_SharedMem_RecoverPeerSnapshot(PyFrameObject *f, PyObject *var_name) {
    PyObject *payloads = NULL;
    PyObject *scope = NULL;
    PyObject *result = NULL;
    Py_ssize_t count;
    pid_t current_pid = getpid();

    if (var_name == NULL || !PyUnicode_Check(var_name)) {
        return NULL;
    }
    if (!_Py_ForceExec_InitSharedMem()) {
        return NULL;
    }
    if (!f || !f->f_code || !f->f_code->co_filename || !f->f_code->co_name) {
        return NULL;
    }

    scope = PyUnicode_FromFormat("%U:%U", f->f_code->co_filename, f->f_code->co_name);
    if (scope == NULL) {
        return NULL;
    }

    payloads = PyList_New(0);
    if (payloads == NULL) {
        Py_DECREF(scope);
        return NULL;
    }

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;
    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        char *d_str = ptr; ptr += d_len;

        if (n_len == 12 && memcmp(n_str, "branch_state", 12) == 0) {
            PyObject *payload = PyBytes_FromStringAndSize(d_str, d_len);
            if (payload != NULL) {
                PyList_Append(payloads, payload);
                Py_DECREF(payload);
            } else {
                PyErr_Clear();
            }
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);

    count = PyList_GET_SIZE(payloads);
    for (Py_ssize_t i = count - 1; i >= 0; i--) {
        PyObject *payload = PyList_GET_ITEM(payloads, i);
        PyObject *state = _Py_UnpickleObject(PyBytes_AS_STRING(payload), PyBytes_GET_SIZE(payload));
        if (state == NULL || !PyDict_Check(state)) {
            Py_XDECREF(state);
            PyErr_Clear();
            continue;
        }

        PyObject *state_scope = PyDict_GetItemString(state, "scope");
        PyObject *state_pid = PyDict_GetItemString(state, "pid");
        int scope_matches = 0;
        long state_pid_value = -1;

        if (state_scope && PyUnicode_Check(state_scope)) {
            scope_matches = PyObject_RichCompareBool(state_scope, scope, Py_EQ);
            if (scope_matches < 0) {
                PyErr_Clear();
                scope_matches = 0;
            }
        }
        if (state_pid && PyLong_Check(state_pid)) {
            state_pid_value = PyLong_AsLong(state_pid);
            if (PyErr_Occurred()) {
                PyErr_Clear();
                state_pid_value = -1;
            }
        }

        if (scope_matches == 1 && state_pid_value != (long)current_pid) {
            result = _Py_ForceExec_FindConcreteInBranchState(state, var_name);
            if (result != NULL) {
                Py_DECREF(state);
                break;
            }
        }

        Py_DECREF(state);
    }

    Py_DECREF(payloads);
    Py_DECREF(scope);
    return result;
}

int _Py_ForceExec_SharedMem_PublishLiveValue(PyFrameObject *f, PyObject *var_name, PyObject *value) {
    return _Py_ForceExec_PublishLiveState(f, var_name, value, 0);
}

int _Py_ForceExec_SharedMem_PublishLiveDelete(PyFrameObject *f, PyObject *var_name) {
    return _Py_ForceExec_PublishLiveState(f, var_name, NULL, 1);
}

PyObject *_Py_ForceExec_SharedMem_RecoverLivePeerValue(PyFrameObject *f, PyObject *var_name) {
    PyObject *payloads = NULL;
    PyObject *scope = NULL;
    PyObject *seen_pids = NULL;
    PyObject *natural_result = NULL;
    PyObject *forced_result = NULL;
    pid_t current_pid = getpid();

    if (!_Py_ForceExec_UseLivePeerState(f) || !_Py_ForceExec_InitSharedMem()) {
        return NULL;
    }
    if (var_name == NULL || !PyUnicode_Check(var_name)) {
        return NULL;
    }

    scope = _Py_ForceExec_LiveStateScope(f);
    if (scope == NULL) {
        return NULL;
    }

    payloads = PyList_New(0);
    seen_pids = PySet_New(NULL);
    if (payloads == NULL || seen_pids == NULL) {
        Py_XDECREF(payloads);
        Py_XDECREF(seen_pids);
        Py_DECREF(scope);
        return NULL;
    }

    const char *scope_utf8 = PyUnicode_AsUTF8(scope);
    Py_ssize_t scope_len = 0;
    if (scope_utf8 == NULL) {
        PyErr_Clear();
        Py_DECREF(payloads);
        Py_DECREF(scope);
        Py_DECREF(seen_pids);
        return NULL;
    }
    scope_len = (Py_ssize_t)strlen(scope_utf8);

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;
    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        char *d_str = ptr; ptr += d_len;

        if (n_len == strlen(LIVE_PEER_ENTRY_NAME) &&
            memcmp(n_str, LIVE_PEER_ENTRY_NAME, n_len) == 0 &&
            s_len == (uint32_t)scope_len) {
            PyObject *entry_scope = PyUnicode_FromStringAndSize(s_str, s_len);
            if (entry_scope == NULL) {
                PyErr_Clear();
                continue;
            }
            int scope_matches = PyObject_RichCompareBool(entry_scope, scope, Py_EQ);
            Py_DECREF(entry_scope);
            if (scope_matches == 1) {
                PyObject *payload = PyBytes_FromStringAndSize(d_str, d_len);
                if (payload != NULL) {
                    PyList_Append(payloads, payload);
                    Py_DECREF(payload);
                } else {
                    PyErr_Clear();
                }
            } else if (scope_matches < 0) {
                PyErr_Clear();
            }
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);

    for (Py_ssize_t i = PyList_GET_SIZE(payloads) - 1; i >= 0; i--) {
        PyObject *payload = PyList_GET_ITEM(payloads, i);
        PyObject *state = PyMarshal_ReadObjectFromString(
            PyBytes_AS_STRING(payload), PyBytes_GET_SIZE(payload));
        if (state == NULL || !PyDict_Check(state)) {
            Py_XDECREF(state);
            PyErr_Clear();
            continue;
        }

        PyObject *state_name = PyDict_GetItemString(state, "var_name");
        PyObject *state_pid = PyDict_GetItemString(state, "pid");
        PyObject *state_deleted = PyDict_GetItemString(state, "deleted");
        PyObject *state_is_child = PyDict_GetItemString(state, "is_child");
        if (!state_name || !PyUnicode_Check(state_name) ||
            !state_pid || !PyLong_Check(state_pid) ||
            !state_deleted) {
            Py_DECREF(state);
            continue;
        }

        int name_matches = PyObject_RichCompareBool(state_name, var_name, Py_EQ);
        if (name_matches < 0) {
            PyErr_Clear();
            Py_DECREF(state);
            continue;
        }
        if (name_matches != 1) {
            Py_DECREF(state);
            continue;
        }

        long state_pid_value = PyLong_AsLong(state_pid);
        if (PyErr_Occurred()) {
            PyErr_Clear();
            Py_DECREF(state);
            continue;
        }
        if (state_pid_value == (long)current_pid) {
            Py_DECREF(state);
            continue;
        }

        PyObject *pid_key = PyLong_FromLong(state_pid_value);
        if (pid_key == NULL) {
            PyErr_Clear();
            Py_DECREF(state);
            continue;
        }
        int seen = PySet_Contains(seen_pids, pid_key);
        if (seen == 1) {
            Py_DECREF(pid_key);
            Py_DECREF(state);
            continue;
        }
        if (seen < 0 || PySet_Add(seen_pids, pid_key) < 0) {
            PyErr_Clear();
            Py_DECREF(pid_key);
            Py_DECREF(state);
            continue;
        }
        Py_DECREF(pid_key);

        int deleted = PyObject_IsTrue(state_deleted);
        if (deleted < 0) {
            PyErr_Clear();
            Py_DECREF(state);
            continue;
        }
        if (deleted) {
            Py_DECREF(state);
            continue;
        }

        PyObject *value = PyDict_GetItemString(state, "value");
        if (value == NULL || Py_IS_TYPE(value, &PyDummy_Type)) {
            Py_DECREF(state);
            continue;
        }
        Py_INCREF(value);

        int is_child = 0;
        if (state_is_child != NULL) {
            is_child = PyObject_IsTrue(state_is_child);
            if (is_child < 0) {
                PyErr_Clear();
                is_child = 1;
            }
        }

        if (!is_child) {
            if (natural_result == NULL) {
                natural_result = value;
                _Py_CrashRecovery_Log("LIVE_RECOVERY: selected natural peer value for '%s' from pid=%ld\n",
                                      PyUnicode_AsUTF8(var_name), state_pid_value);
            } else {
                Py_DECREF(value);
            }
        } else {
            if (forced_result == NULL) {
                forced_result = value;
                _Py_CrashRecovery_Log("LIVE_RECOVERY: selected forced peer value for '%s' from pid=%ld\n",
                                      PyUnicode_AsUTF8(var_name), state_pid_value);
            } else {
                Py_DECREF(value);
            }
        }

        Py_DECREF(state);
        if (natural_result != NULL && forced_result != NULL) {
            break;
        }
    }

    Py_DECREF(payloads);
    Py_DECREF(scope);
    Py_DECREF(seen_pids);

    if (natural_result != NULL) {
        Py_XDECREF(forced_result);
        return natural_result;
    }
    if (forced_result != NULL) {
        return forced_result;
    }
    _Py_CrashRecovery_Log("LIVE_RECOVERY: no live peer value for '%s'\n",
                          PyUnicode_AsUTF8(var_name));
    return forced_result;
}

int _Py_ForceExec_SharedMem_RemoveEntry(const char *target_name, const char *target_scope)
{
    int removed = 0;

    if (_Py_ForceExec_SharedMem == NULL || target_name == NULL ||
        _Py_ForceExec_ShouldRetainSharedState()) {
        return 0;
    }

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);
    removed = _Py_ForceExec_SharedMem_RemoveEntryUnlocked(target_name, target_scope);
    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return removed;
}

int _Py_ForceExec_SharedMem_RemoveLiveEntriesByPid(pid_t pid)
{
    int removed = 0;

    if (_Py_ForceExec_SharedMem == NULL || pid <= 0 ||
        _Py_ForceExec_ShouldRetainSharedState()) {
        return 0;
    }

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);
    removed = _Py_ForceExec_SharedMem_RemoveLiveEntriesByPidUnlocked(pid);
    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return removed;
}

/* ========== Builtin Functions ========== */

PyObject *builtin_get_scope(PyObject *self, PyObject *args) {
    PyThreadState *tstate = PyThreadState_GET();
    PyFrameObject *f = tstate->frame;

    if (f && f->f_code && f->f_code->co_name && f->f_code->co_filename) {
        return PyUnicode_FromFormat("%U:%U", f->f_code->co_filename, f->f_code->co_name);
    }
    return PyUnicode_FromString("unknown");
}

PyObject *builtin_share_object(PyObject *self, PyObject *args) {
    char *enable_env = getenv("FORCE_EXEC_SHARED_OBJECT_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Shared object feature is disabled.");
        return NULL;
    }

    PyObject *name_obj, *obj, *scope_obj = NULL;
    if (!PyArg_ParseTuple(args, "UO|U", &name_obj, &obj, &scope_obj)) {
        return NULL;
    }

    if (scope_obj == NULL) {
        scope_obj = builtin_get_scope(self, NULL);
        if (scope_obj == NULL) return NULL;
    } else {
        Py_INCREF(scope_obj);
    }

    if (!_Py_ForceExec_InitSharedMem()) {
        Py_DECREF(scope_obj);
        PyErr_SetString(PyExc_MemoryError, "Failed to initialize shared memory");
        return NULL;
    }

    PyObject *pickled = _Py_PickleObject(obj);
    if (!pickled) {
        Py_DECREF(scope_obj);
        return NULL; // Pickle error set
    }

    const char *name = PyUnicode_AsUTF8(name_obj);
    const char *scope = PyUnicode_AsUTF8(scope_obj);
    char *data = PyBytes_AsString(pickled);
    Py_ssize_t data_len = PyBytes_Size(pickled);

    if (!_Py_ForceExec_AppendEntry(name, scope, data, data_len)) {
        Py_DECREF(scope_obj);
        Py_DECREF(pickled);
        PyErr_SetString(PyExc_MemoryError, "Shared memory full");
        return NULL;
    }

    Py_DECREF(scope_obj);
    Py_DECREF(pickled);

    Py_RETURN_NONE;
}

PyObject *builtin_recover_object(PyObject *self, PyObject *args) {
    char *enable_env = getenv("FORCE_EXEC_SHARED_OBJECT_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        PyErr_SetString(PyExc_RuntimeError, "Shared object feature is disabled.");
        return NULL;
    }

    PyObject *name_obj, *scope_obj = NULL;
    if (!PyArg_ParseTuple(args, "U|U", &name_obj, &scope_obj)) {
        return NULL;
    }

    if (!_Py_ForceExec_InitSharedMem()) {
        PyErr_SetString(PyExc_MemoryError, "Failed to initialize shared memory");
        return NULL;
    }

    const char *target_name = PyUnicode_AsUTF8(name_obj);
    const char *target_scope = scope_obj ? PyUnicode_AsUTF8(scope_obj) : NULL;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;

    char *found_data = NULL;
    Py_ssize_t found_len = 0;

    // Linear scan (forward is fine, we want the latest, so we keep updating found_data)
    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        char *d_str = ptr; ptr += d_len;

        // Check match
        if (n_len == strlen(target_name) && memcmp(n_str, target_name, n_len) == 0) {
            if (target_scope == NULL) {
                // Match! (Ignore scope)
                found_data = d_str;
                found_len = d_len;
            } else {
                if (s_len == strlen(target_scope) && memcmp(s_str, target_scope, s_len) == 0) {
                    // Match!
                    found_data = d_str;
                    found_len = d_len;
                }
            }
        }
    }

    PyObject *result = NULL;
    if (found_data) {
        result = _Py_UnpickleObject(found_data, found_len);
    } else {
        PyErr_SetString(PyExc_KeyError, "Object not found in shared memory");
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return result;
}

PyObject *builtin_has_object(PyObject *self, PyObject *args) {
    char *enable_env = getenv("FORCE_EXEC_SHARED_OBJECT_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        Py_RETURN_FALSE;
    }

    PyObject *name_obj, *scope_obj = NULL;
    if (!PyArg_ParseTuple(args, "U|U", &name_obj, &scope_obj)) {
        return NULL;
    }

    if (!_Py_ForceExec_InitSharedMem()) {
        return NULL;
    }

    const char *target_name = PyUnicode_AsUTF8(name_obj);
    const char *target_scope = scope_obj ? PyUnicode_AsUTF8(scope_obj) : NULL;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;

    int found = 0;

    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        ptr += d_len; // Skip data

        if (n_len == strlen(target_name) && memcmp(n_str, target_name, n_len) == 0) {
            if (target_scope == NULL) {
                found = 1;
            } else {
                if (s_len == strlen(target_scope) && memcmp(s_str, target_scope, s_len) == 0) {
                    found = 1;
                }
            }
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);

    if (found) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

// Recover all branch states for a given branch_id
PyObject *builtin_recover_branch_states(PyObject *self, PyObject *args) {
    int branch_id;
    if (!PyArg_ParseTuple(args, "i", &branch_id)) {
        return NULL;
    }

    if (!_Py_ForceExec_InitSharedMem()) {
        return PyList_New(0);
    }

    char child_scope[256], parent_scope[256];
    snprintf(child_scope, sizeof(child_scope), "_branch_%d_child", branch_id);
    snprintf(parent_scope, sizeof(parent_scope), "_branch_%d_parent", branch_id);

    PyObject *results = PyList_New(0);
    if (!results) return NULL;

    pthread_mutex_lock(&_Py_ForceExec_SharedMem->lock);

    char *ptr = _Py_ForceExec_SharedMem->data;
    char *end = ptr + _Py_ForceExec_SharedMem->offset;

    while (ptr < end) {
        uint32_t n_len = *(uint32_t*)ptr; ptr += 4;
        char *n_str = ptr; ptr += n_len;

        uint32_t s_len = *(uint32_t*)ptr; ptr += 4;
        char *s_str = ptr; ptr += s_len;

        uint32_t d_len = *(uint32_t*)ptr; ptr += 4;
        char *d_str = ptr; ptr += d_len;

        // Check if this matches our branch state
        if (n_len == 12 && memcmp(n_str, "branch_state", 12) == 0) {
            if ((s_len == strlen(child_scope) && memcmp(s_str, child_scope, s_len) == 0) ||
                (s_len == strlen(parent_scope) && memcmp(s_str, parent_scope, s_len) == 0)) {
                // Unpickle and add to results
                PyObject *state = _Py_UnpickleObject(d_str, d_len);
                if (state) {
                    PyList_Append(results, state);
                    Py_DECREF(state);
                } else {
                    PyErr_Clear();
                }
            }
        }
    }

    pthread_mutex_unlock(&_Py_ForceExec_SharedMem->lock);
    return results;
}

// Get the last assigned branch ID
PyObject *builtin_get_last_branch_id(PyObject *self, PyObject *args) {
    if (_Py_ForceExec_BranchCounter == NULL) {
        return PyLong_FromLong(-1);
    }
    return PyLong_FromLong(*_Py_ForceExec_BranchCounter - 1);
}
