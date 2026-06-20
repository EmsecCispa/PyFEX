/* PyFEX Force Execution, Crash Recovery, and Logging
 *
 * Force execution: decides whether to fork at conditional branches.
 * Crash recovery: decides whether to substitute DummyObjects on errors.
 * Peer recovery: queries merged branch state for concrete values.
 * Logging: debug output for force exec and crash recovery events.
 */

#include "Python.h"
#include "pycore_pyerrors.h"       // _PyErr_Clear()
#include "pyfex.h"
#include "pyfex_sharedmem.h"
#include "dummyobject.h"
#include "frameobject.h"
#include "opcode.h"

#include <stdarg.h>
#include <string.h>
#include <signal.h>
#include <sys/file.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

/* ========== Scope control ==========
 *
 * A frame/code object is "in scope" for PyFEX features if its source file
 * matches sys.argv[0] (exact, or by basename with a ".pyc" main script treated
 * as its ".py" source so `python foo.pyc` is in scope), OR is contained in the
 * directory named by the PYFEX_SCOPE_DIR environment variable.
 *
 * The scope directory is a single path. It matches a file whose path is
 * either exactly the directory or begins with "<dir>/" (boundary at '/').
 *
 * For dynamic code (filename starting with '<', e.g. '<string>', '<frozen ...>')
 * the frame walker follows f_back until it finds a real file and checks
 * that instead.
 */

static PyObject *_Py_PyFEX_GetMainScript(void) {
    PyObject *sys_argv = PySys_GetObject("argv");
    if (sys_argv == NULL || !PyList_Check(sys_argv) || PyList_Size(sys_argv) == 0) {
        return NULL;
    }
    return PyList_GetItem(sys_argv, 0);  /* borrowed */
}

static int _Py_PyFEX_PathInScopeDir(const char *path) {
    const char *scope_dir = getenv("PYFEX_SCOPE_DIR");
    if (scope_dir == NULL || scope_dir[0] == '\0' || path == NULL) {
        return 0;
    }
    size_t slen = strlen(scope_dir);
    if (slen == 0) return 0;
    /* Strip trailing '/' from the configured scope dir for consistent matching. */
    while (slen > 0 && scope_dir[slen - 1] == '/') slen--;
    if (slen == 0) return 0;
    if (strncmp(path, scope_dir, slen) != 0) return 0;
    char trailer = path[slen];
    return trailer == '\0' || trailer == '/';
}

/* Compare two path basenames, treating a trailing ".pyc" as equivalent to
 * ".py". This lets a byte-compiled main script (run as `python foo.pyc`, whose
 * frames carry co_filename "foo.py") be recognized as the same in-scope main
 * module as `python foo.py`. */
static int _Py_PyFEX_SameScriptBase(const char *a, const char *b) {
    if (a == NULL || b == NULL) return 0;
    size_t la = strlen(a), lb = strlen(b);
    /* Drop the trailing 'c' of a ".pyc" suffix so it compares as ".py". */
    if (la >= 4 && strcmp(a + la - 4, ".pyc") == 0) la -= 1;
    if (lb >= 4 && strcmp(b + lb - 4, ".pyc") == 0) lb -= 1;
    return la == lb && strncmp(a, b, la) == 0;
}

/* This helper must not touch the thread-state error: it is called from
 * crash-recovery paths where a real exception is pending. PyUnicode_AsUTF8
 * on a valid PyUnicode never raises, which is the only case we feed it. */
static int _Py_PyFEX_FilenameMatches(PyObject *filename) {
    if (filename == NULL || !PyUnicode_Check(filename)) return 0;
    PyObject *main_script = _Py_PyFEX_GetMainScript();

    if (main_script != NULL && PyUnicode_Check(main_script)) {
        if (PyUnicode_Compare(filename, main_script) == 0) return 1;
    }

    const char *f_str = PyUnicode_AsUTF8(filename);
    if (f_str == NULL) return 0;

    if (main_script != NULL && PyUnicode_Check(main_script)) {
        const char *m_str = PyUnicode_AsUTF8(main_script);
        if (m_str != NULL) {
            const char *f_base = strrchr(f_str, '/');
            f_base = f_base ? f_base + 1 : f_str;
            const char *m_base = strrchr(m_str, '/');
            m_base = m_base ? m_base + 1 : m_str;
            /* Equal basenames, treating foo.pyc as foo.py so a byte-compiled
             * main script is recognized as its source main module. */
            if (_Py_PyFEX_SameScriptBase(f_base, m_base)) return 1;
        }
    }

    if (_Py_PyFEX_PathInScopeDir(f_str)) return 1;
    return 0;
}

int _Py_PyFEX_FrameInScope(PyFrameObject *f) {
    if (f == NULL || f->f_code == NULL) return 0;
    PyObject *filename = f->f_code->co_filename;
    if (filename == NULL) return 0;

    if (_Py_PyFEX_FilenameMatches(filename)) return 1;

    /* Dynamic code (e.g. user-level exec strings) may legitimately be
     * in-scope if called from a main-script frame. Walk f_back for those.
     * Explicitly skip frozen stdlib frames (`<frozen ...>`) which run as
     * part of the import machinery -- we do not want CR / FE to fire
     * inside importlib just because it was invoked from main. */
    const char *f_str = PyUnicode_AsUTF8(filename);
    if (f_str != NULL && f_str[0] == '<'
        && strncmp(f_str, "<frozen", 7) != 0) {
        PyFrameObject *back = f->f_back;
        while (back != NULL) {
            if (back->f_code != NULL) {
                PyObject *bf = back->f_code->co_filename;
                if (bf != NULL && _Py_PyFEX_FilenameMatches(bf)) return 1;
            }
            back = back->f_back;
        }
    }
    return 0;
}

int _Py_PyFEX_CodeInScope(PyCodeObject *code) {
    if (code == NULL) return 0;
    return _Py_PyFEX_FilenameMatches(code->co_filename);
}

/* ========== Call whitelist ==========
 *
 * Names that should always be callable with dummy arguments so analysts can
 * observe dummies (e.g. print(dummy), repr(dummy)). Identified by identity
 * against the objects in the builtins module.
 */

#define PYFEX_WHITELIST_NAMES_COUNT 8
static const char *_Py_PyFEX_WhitelistNames[PYFEX_WHITELIST_NAMES_COUNT] = {
    "print", "repr", "str", "type", "isinstance", "id", "len", "hash"
};
static PyObject *_Py_PyFEX_WhitelistCache[PYFEX_WHITELIST_NAMES_COUNT];
static int _Py_PyFEX_WhitelistInited = 0;

static void _Py_PyFEX_InitWhitelist(void) {
    if (_Py_PyFEX_WhitelistInited) return;
    PyObject *builtins = PyEval_GetBuiltins();  /* borrowed */
    for (int i = 0; i < PYFEX_WHITELIST_NAMES_COUNT; i++) {
        _Py_PyFEX_WhitelistCache[i] = NULL;
        if (builtins != NULL) {
            PyObject *obj = PyDict_GetItemString(builtins, _Py_PyFEX_WhitelistNames[i]);
            /* Store borrowed reference; builtins dict is long-lived. */
            _Py_PyFEX_WhitelistCache[i] = obj;
        }
    }
    _Py_PyFEX_WhitelistInited = 1;
}

int _Py_PyFEX_IsCallableWhitelisted(PyObject *func) {
    if (func == NULL) return 0;
    _Py_PyFEX_InitWhitelist();
    for (int i = 0; i < PYFEX_WHITELIST_NAMES_COUNT; i++) {
        if (_Py_PyFEX_WhitelistCache[i] == func) return 1;
    }
    return 0;
}

/* ========== Logging ========== */

static int
_Py_PyFEX_EnvEnabled(const char *name)
{
    const char *value = getenv(name);
    return value != NULL && value[0] != '\0';
}

static void
_Py_PyFEX_LockLog(FILE *fp)
{
    if (fp != NULL) {
        (void)flock(fileno(fp), LOCK_EX);
    }
}

static void
_Py_PyFEX_UnlockLog(FILE *fp)
{
    if (fp != NULL) {
        (void)flock(fileno(fp), LOCK_UN);
    }
}

static const char *
_Py_PyFEX_RuntimeLogPath(const char *legacy_env, const char *legacy_default,
                         int *using_unified)
{
    const char *path = getenv("PYFEX_RUNTIME_LOG_FILE");
    if (path != NULL && path[0] != '\0') {
        if (using_unified != NULL) *using_unified = 1;
        return path;
    }

    if (using_unified != NULL) *using_unified = 0;
    if (legacy_env != NULL) {
        path = getenv(legacy_env);
        if (path != NULL && path[0] != '\0') {
            return path;
        }
    }
    return legacy_default;
}

static int
_Py_PyFEX_RuntimeLogEnabled(const char *legacy_env, const char *legacy_default)
{
    return _Py_PyFEX_EnvEnabled("PYFEX_RUNTIME_LOG_FILE")
        || (legacy_env != NULL && _Py_PyFEX_EnvEnabled(legacy_env))
        || legacy_default != NULL;
}

static void
_Py_PyFEX_RuntimeLogV(const char *component,
                      const char *legacy_env,
                      const char *legacy_default,
                      const char *fmt,
                      va_list args)
{
    int using_unified = 0;
    const char *log_file = _Py_PyFEX_RuntimeLogPath(
        legacy_env, legacy_default, &using_unified);
    if (log_file == NULL) return;

    FILE *f = fopen(log_file, "a");
    if (f == NULL) return;

    _Py_PyFEX_LockLog(f);
    if (using_unified) {
        fprintf(f, "[pid=%ld component=%s] ",
                (long)getpid(), component ? component : "runtime");
    }
    vfprintf(f, fmt, args);
    _Py_PyFEX_UnlockLog(f);
    fclose(f);
}

static void
_Py_PyFEX_RuntimeOnlyLog(const char *component, const char *fmt, ...)
{
    if (!_Py_PyFEX_EnvEnabled("PYFEX_RUNTIME_LOG_FILE")) return;

    va_list args;
    va_start(args, fmt);
    _Py_PyFEX_RuntimeLogV(component, NULL, NULL, fmt, args);
    va_end(args);
}

void _Py_ForceExec_Log(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    _Py_PyFEX_RuntimeLogV("force_exec", "FORCE_EXEC_LOG_FILE",
                          "force_exec.log", fmt, args);
    va_end(args);
}

void _Py_CrashRecovery_Log(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    _Py_PyFEX_RuntimeLogV("crash_recovery", "CRASH_RECOVERY_LOG_FILE",
                          NULL, fmt, args);
    va_end(args);
}

/* ========== Structured Trace Reporter ==========
 *
 * PYFEX_TRACE_LOG_FILE enables behavior-profile JSONL independent of forced
 * execution. The trace reporter is intentionally limited to function-call
 * events and argument values. Runtime/debug events stay in the existing log
 * path, unified by PYFEX_RUNTIME_LOG_FILE when set.
 */

static int _Py_PyFEX_TraceBusy = 0;

static const char *
_Py_PyFEX_TracePath(void)
{
    const char *path = getenv("PYFEX_TRACE_LOG_FILE");
    if (path == NULL || path[0] == '\0') {
        return NULL;
    }
    return path;
}

static void
_Py_PyFEX_JsonString(FILE *fp, const char *s)
{
    fputc('"', fp);
    if (s != NULL) {
        for (const unsigned char *p = (const unsigned char *)s; *p != '\0'; p++) {
            switch (*p) {
                case '"': fputs("\\\"", fp); break;
                case '\\': fputs("\\\\", fp); break;
                case '\b': fputs("\\b", fp); break;
                case '\f': fputs("\\f", fp); break;
                case '\n': fputs("\\n", fp); break;
                case '\r': fputs("\\r", fp); break;
                case '\t': fputs("\\t", fp); break;
                default:
                    if (*p < 0x20) {
                        fprintf(fp, "\\u%04x", *p);
                    } else {
                        fputc(*p, fp);
                    }
                    break;
            }
        }
    }
    fputc('"', fp);
}

static void
_Py_PyFEX_JsonUnicode(FILE *fp, PyObject *obj)
{
    if (obj != NULL && PyUnicode_Check(obj)) {
        const char *s = PyUnicode_AsUTF8(obj);
        if (s != NULL) {
            _Py_PyFEX_JsonString(fp, s);
            return;
        }
        PyErr_Clear();
    }
    _Py_PyFEX_JsonString(fp, "");
}

static PyObject *
_Py_PyFEX_SafeRepr(PyObject *obj)
{
    if (obj == NULL) {
        return PyUnicode_FromString("<null>");
    }

    PyObject *repr = PyObject_Repr(obj);
    if (repr != NULL && PyUnicode_Check(repr)) {
        return repr;
    }
    Py_XDECREF(repr);
    PyErr_Clear();

    const char *type_name = Py_TYPE(obj) ? Py_TYPE(obj)->tp_name : "unknown";
    PyObject *fallback = PyUnicode_FromFormat("<%s repr failed>", type_name);
    if (fallback == NULL) {
        PyErr_Clear();
        fallback = PyUnicode_FromString("<repr failed>");
    }
    return fallback;
}

static PyObject *
_Py_PyFEX_DummyTrace(PyObject *obj)
{
    if (obj == NULL || !PyDummy_Check(obj)) {
        Py_RETURN_NONE;
    }
    PyObject *trace = PyObject_GetAttrString(obj, "trace");
    if (trace == NULL) {
        PyErr_Clear();
        Py_RETURN_NONE;
    }
    if (PyUnicode_Check(trace)) {
        return trace;
    }
    PyObject *trace_str = PyObject_Str(trace);
    Py_DECREF(trace);
    if (trace_str == NULL) {
        PyErr_Clear();
        Py_RETURN_NONE;
    }
    return trace_str;
}

static const char *
_Py_PyFEX_FuncKind(PyObject *func)
{
    PyObject *target = func;
    if (PyMethod_Check(target)) {
        target = PyMethod_GET_FUNCTION(target);
    }
    if (target != NULL && PyFunction_Check(target)) return "python";
    if (target != NULL && (PyCFunction_Check(target) || PyCMethod_Check(target))) return "builtin";
    if (target != NULL && PyDummy_Check(target)) return "dummy";
    if (target != NULL && PyType_Check(target)) return "type";
    return "callable";
}

static void
_Py_PyFEX_WriteFuncName(FILE *fp, PyObject *func)
{
    PyObject *target = func;
    if (PyMethod_Check(target)) {
        target = PyMethod_GET_FUNCTION(target);
    }

    if (target != NULL && PyFunction_Check(target)) {
        PyFunctionObject *pyfunc = (PyFunctionObject *)target;
        if (pyfunc->func_qualname && PyUnicode_Check(pyfunc->func_qualname)) {
            _Py_PyFEX_JsonUnicode(fp, pyfunc->func_qualname);
            return;
        }
        if (pyfunc->func_name && PyUnicode_Check(pyfunc->func_name)) {
            _Py_PyFEX_JsonUnicode(fp, pyfunc->func_name);
            return;
        }
    }

    if (target != NULL && (PyCFunction_Check(target) || PyCMethod_Check(target))) {
        const char *name = ((PyCFunctionObject *)target)->m_ml->ml_name;
        _Py_PyFEX_JsonString(fp, name ? name : "unknown");
        return;
    }

    if (target != NULL && PyType_Check(target)) {
        _Py_PyFEX_JsonString(fp, ((PyTypeObject *)target)->tp_name);
        return;
    }

    _Py_PyFEX_JsonString(fp, target && Py_TYPE(target) ? Py_TYPE(target)->tp_name : "unknown");
}

static void
_Py_PyFEX_WriteFrame(FILE *fp, PyFrameObject *frame)
{
    fputs("\"caller\":{", fp);
    if (frame != NULL && frame->f_code != NULL) {
        fputs("\"file\":", fp);
        _Py_PyFEX_JsonUnicode(fp, frame->f_code->co_filename);
        fputs(",\"function\":", fp);
        _Py_PyFEX_JsonUnicode(fp, frame->f_code->co_name);
        fprintf(fp, ",\"line\":%d", PyFrame_GetLineNumber(frame));
    } else {
        fputs("\"file\":\"\",\"function\":\"\",\"line\":0", fp);
    }
    fputc('}', fp);
}

static void
_Py_PyFEX_WriteArg(FILE *fp, PyObject *obj)
{
    PyObject *repr = _Py_PyFEX_SafeRepr(obj);
    PyObject *dummy_trace = _Py_PyFEX_DummyTrace(obj);

    fputc('{', fp);
    fputs("\"type\":", fp);
    _Py_PyFEX_JsonString(fp, obj && Py_TYPE(obj) ? Py_TYPE(obj)->tp_name : "unknown");
    fputs(",\"repr\":", fp);
    _Py_PyFEX_JsonUnicode(fp, repr);
    if (obj != NULL && PyDummy_Check(obj) && dummy_trace != NULL && PyUnicode_Check(dummy_trace)) {
        fputs(",\"dummy_trace\":", fp);
        _Py_PyFEX_JsonUnicode(fp, dummy_trace);
    }
    fputc('}', fp);

    Py_XDECREF(repr);
    Py_XDECREF(dummy_trace);
}

static void
_Py_PyFEX_WriteVectorArgs(FILE *fp, PyObject **args, Py_ssize_t nargs, PyObject *kwnames)
{
    fputs("\"args\":[", fp);
    for (Py_ssize_t i = 0; i < nargs; i++) {
        if (i) fputc(',', fp);
        _Py_PyFEX_WriteArg(fp, args[i]);
    }
    fputc(']', fp);

    fputs(",\"kwargs\":{", fp);
    if (kwnames != NULL && PyTuple_Check(kwnames)) {
        Py_ssize_t nkwargs = PyTuple_GET_SIZE(kwnames);
        for (Py_ssize_t i = 0; i < nkwargs; i++) {
            if (i) fputc(',', fp);
            PyObject *key = PyTuple_GET_ITEM(kwnames, i);
            _Py_PyFEX_JsonUnicode(fp, key);
            fputc(':', fp);
            _Py_PyFEX_WriteArg(fp, args[nargs + i]);
        }
    }
    fputc('}', fp);
}

static void
_Py_PyFEX_WriteTupleArgs(FILE *fp, PyObject *args, PyObject *kwargs)
{
    fputs("\"args\":[", fp);
    if (args != NULL && PyTuple_Check(args)) {
        Py_ssize_t nargs = PyTuple_GET_SIZE(args);
        for (Py_ssize_t i = 0; i < nargs; i++) {
            if (i) fputc(',', fp);
            _Py_PyFEX_WriteArg(fp, PyTuple_GET_ITEM(args, i));
        }
    }
    fputc(']', fp);

    fputs(",\"kwargs\":{", fp);
    if (kwargs != NULL && PyDict_Check(kwargs)) {
        PyObject *key, *value;
        Py_ssize_t pos = 0;
        int first = 1;
        while (PyDict_Next(kwargs, &pos, &key, &value)) {
            if (!first) fputc(',', fp);
            first = 0;
            PyObject *key_repr = PyObject_Str(key);
            if (key_repr == NULL) {
                PyErr_Clear();
                key_repr = PyUnicode_FromString("<key>");
            }
            _Py_PyFEX_JsonUnicode(fp, key_repr);
            Py_XDECREF(key_repr);
            fputc(':', fp);
            _Py_PyFEX_WriteArg(fp, value);
        }
    }
    fputc('}', fp);
}

static FILE *
_Py_PyFEX_OpenTraceLog(PyFrameObject *frame)
{
    const char *path = _Py_PyFEX_TracePath();
    if (path == NULL) return NULL;
    if (frame != NULL && !_Py_PyFEX_FrameInScope(frame)) return NULL;
    return fopen(path, "a");
}

static void
_Py_PyFEX_SaveError(PyObject **type, PyObject **value, PyObject **tb)
{
    *type = *value = *tb = NULL;
    if (PyErr_Occurred()) {
        PyErr_Fetch(type, value, tb);
    }
}

static void
_Py_PyFEX_RestoreError(PyObject *type, PyObject *value, PyObject *tb)
{
    if (PyErr_Occurred()) {
        PyErr_Clear();
    }
    if (type != NULL) {
        PyErr_Restore(type, value, tb);
    } else {
        Py_XDECREF(value);
        Py_XDECREF(tb);
    }
}

void
_Py_PyFEX_TraceLogCall(PyObject *func, PyFrameObject *caller,
                       PyObject **args, Py_ssize_t nargs, PyObject *kwnames)
{
    if (_Py_PyFEX_TraceBusy) return;
    FILE *fp = _Py_PyFEX_OpenTraceLog(caller);
    if (fp == NULL) return;

    PyObject *save_type, *save_value, *save_tb;
    _Py_PyFEX_SaveError(&save_type, &save_value, &save_tb);
    _Py_PyFEX_TraceBusy = 1;
    _Py_PyFEX_LockLog(fp);

    fprintf(fp, "{\"event\":\"function_call\",\"pid\":%ld,", (long)getpid());
    _Py_PyFEX_WriteFrame(fp, caller);
    fputs(",\"function\":", fp);
    _Py_PyFEX_WriteFuncName(fp, func);
    fputs(",\"kind\":", fp);
    _Py_PyFEX_JsonString(fp, _Py_PyFEX_FuncKind(func));
    fputc(',', fp);
    _Py_PyFEX_WriteVectorArgs(fp, args, nargs, kwnames);
    fputs("}\n", fp);

    _Py_PyFEX_UnlockLog(fp);
    fclose(fp);
    _Py_PyFEX_TraceBusy = 0;
    _Py_PyFEX_RestoreError(save_type, save_value, save_tb);
}

void
_Py_PyFEX_TraceLogCallTuple(PyObject *func, PyFrameObject *caller,
                            PyObject *args, PyObject *kwargs)
{
    if (_Py_PyFEX_TraceBusy) return;
    FILE *fp = _Py_PyFEX_OpenTraceLog(caller);
    if (fp == NULL) return;

    PyObject *save_type, *save_value, *save_tb;
    _Py_PyFEX_SaveError(&save_type, &save_value, &save_tb);
    _Py_PyFEX_TraceBusy = 1;
    _Py_PyFEX_LockLog(fp);

    fprintf(fp, "{\"event\":\"function_call\",\"pid\":%ld,", (long)getpid());
    _Py_PyFEX_WriteFrame(fp, caller);
    fputs(",\"function\":", fp);
    _Py_PyFEX_WriteFuncName(fp, func);
    fputs(",\"kind\":", fp);
    _Py_PyFEX_JsonString(fp, _Py_PyFEX_FuncKind(func));
    fputc(',', fp);
    _Py_PyFEX_WriteTupleArgs(fp, args, kwargs);
    fputs("}\n", fp);

    _Py_PyFEX_UnlockLog(fp);
    fclose(fp);
    _Py_PyFEX_TraceBusy = 0;
    _Py_PyFEX_RestoreError(save_type, save_value, save_tb);
}

void
_Py_PyFEX_RuntimeLogRecovery(const char *opcode_name, PyFrameObject *frame, PyObject *recovered)
{
    if (!_Py_PyFEX_RuntimeLogEnabled("CRASH_RECOVERY_LOG_FILE", NULL)) {
        return;
    }

    PyObject *save_type, *save_value, *save_tb;
    _Py_PyFEX_SaveError(&save_type, &save_value, &save_tb);

    const char *filename = "";
    const char *function = "";
    int line = 0;
    if (frame != NULL && frame->f_code != NULL) {
        if (frame->f_code->co_filename != NULL && PyUnicode_Check(frame->f_code->co_filename)) {
            const char *s = PyUnicode_AsUTF8(frame->f_code->co_filename);
            if (s != NULL) filename = s;
            else PyErr_Clear();
        }
        if (frame->f_code->co_name != NULL && PyUnicode_Check(frame->f_code->co_name)) {
            const char *s = PyUnicode_AsUTF8(frame->f_code->co_name);
            if (s != NULL) function = s;
            else PyErr_Clear();
        }
        line = PyFrame_GetLineNumber(frame);
    }

    if (recovered != NULL) {
        PyObject *repr = _Py_PyFEX_SafeRepr(recovered);
        const char *repr_s = "";
        if (repr != NULL && PyUnicode_Check(repr)) {
            repr_s = PyUnicode_AsUTF8(repr);
            if (repr_s == NULL) {
                PyErr_Clear();
                repr_s = "";
            }
        }
        _Py_CrashRecovery_Log(
            "RECOVERY: opcode=%s file=%s function=%s line=%d recovered_type=%s recovered=%s\n",
            opcode_name ? opcode_name : "",
            filename,
            function,
            line,
            Py_TYPE(recovered) ? Py_TYPE(recovered)->tp_name : "unknown",
            repr_s);
        Py_XDECREF(repr);
    } else {
        _Py_CrashRecovery_Log(
            "RECOVERY: opcode=%s file=%s function=%s line=%d recovered_type=null recovered=null\n",
            opcode_name ? opcode_name : "",
            filename,
            function,
            line);
    }

    _Py_PyFEX_RestoreError(save_type, save_value, save_tb);
}

void _Py_ForceExec_LogCall(PyObject *func, PyObject **args, Py_ssize_t nargs) {
    PyObject *name_attr = PyObject_GetAttrString(func, "__name__");
    const char *name = "unknown";
    if (name_attr && PyUnicode_Check(name_attr)) {
        name = PyUnicode_AsUTF8(name_attr);
    }

    _Py_ForceExec_Log("CALL: %s(", name);
    for (Py_ssize_t i = 0; i < nargs; i++) {
        PyObject *repr = PyObject_Repr(args[i]);
        const char *arg_str = repr ? PyUnicode_AsUTF8(repr) : "?";
        _Py_ForceExec_Log("%s%s", arg_str, (i < nargs - 1) ? ", " : "");
        Py_XDECREF(repr);
    }
    _Py_ForceExec_Log(")\n");

    Py_XDECREF(name_attr);
}

void _Py_ForceExec_LogCallTuple(PyObject *func, PyObject *args, PyObject *kwargs) {
    PyObject *name_attr = PyObject_GetAttrString(func, "__name__");
    const char *name = "unknown";
    if (name_attr && PyUnicode_Check(name_attr)) {
        name = PyUnicode_AsUTF8(name_attr);
    }

    _Py_ForceExec_Log("CALL: %s(", name);
    if (args && PyTuple_Check(args)) {
        Py_ssize_t nargs = PyTuple_GET_SIZE(args);
        for (Py_ssize_t i = 0; i < nargs; i++) {
            PyObject *repr = PyObject_Repr(PyTuple_GET_ITEM(args, i));
            const char *arg_str = repr ? PyUnicode_AsUTF8(repr) : "?";
            _Py_ForceExec_Log("%s%s", arg_str, (i < nargs - 1) ? ", " : "");
            Py_XDECREF(repr);
        }
    }
    if (kwargs && PyDict_Check(kwargs)) {
        _Py_ForceExec_Log(", **kwargs"); // Simplified for now
    }
    _Py_ForceExec_Log(")\n");

    Py_XDECREF(name_attr);
}

/* ========== Dormant Function Analysis ========== */

void _Py_DormantFunc_Log(const char *prefix, PyObject *func, PyFrameObject *f) {
    char *log_file = getenv("DORMANT_FUNC_LOG_FILE");
    if (log_file == NULL) return;

    /* Handle bound methods: extract the underlying function */
    if (PyMethod_Check(func)) {
        func = PyMethod_GET_FUNCTION(func);
        if (func == NULL) return;
    }

    /* Only log user-defined Python functions, not builtins/C functions */
    if (!PyFunction_Check(func)) return;

    /* Only log when the calling frame is in target scope */
    if (f != NULL && !_Py_PyFEX_FrameInScope(f)) return;

    FILE *fp = fopen(log_file, "a");
    if (fp == NULL) return;

    const char *name = "unknown";
    const char *qualname = "unknown";
    const char *filename = "unknown";
    int lineno = 0;

    PyFunctionObject *pyfunc = (PyFunctionObject *)func;
    if (pyfunc->func_name && PyUnicode_Check(pyfunc->func_name))
        name = PyUnicode_AsUTF8(pyfunc->func_name);
    if (pyfunc->func_qualname && PyUnicode_Check(pyfunc->func_qualname))
        qualname = PyUnicode_AsUTF8(pyfunc->func_qualname);

    if (f && f->f_code && f->f_code->co_filename) {
        const char *fn = PyUnicode_AsUTF8(f->f_code->co_filename);
        if (fn) filename = fn;
        lineno = PyFrame_GetLineNumber(f);
    }

    fprintf(fp, "%s %s %s %s:%d\n", prefix, qualname, name, filename, lineno);
    fclose(fp);

    _Py_PyFEX_RuntimeOnlyLog(
        "dfa", "DFA: %s qualname=%s name=%s location=%s:%d\n",
        prefix, qualname, name, filename, lineno);
}

/* ========== Force Execution ========== */

static int *_Py_ForceExec_GlobalForkCount = NULL;
static PyObject *_Py_ForceExec_LocationCounts = NULL;
int _Py_ForceExec_IsForcedChildProcess = 0;

/* ===== Concurrent live-process cap (memory safety) =====
 *
 * Forced execution forks a child at every explored branch. The global
 * fork counter bounds the *total* number of forks, but on a branch- or
 * loop-heavy target -- especially when branch merging is not enabled or
 * cannot consolidate the paths -- up to that many CPython interpreters
 * can be alive *at once*, each running the whole remaining program. That
 * is enough to exhaust system memory.
 *
 * This cap bounds the number of *live* forced children regardless of
 * merge state or loop shape. A small fixed-size PID registry lives in
 * shared memory so every forked process sees the same set. Liveness is
 * tested directly with kill(pid, 0); dead children are reaped
 * (waitpid WNOHANG) and their slots reclaimed, so the count can never
 * leak -- a crashed or SIGKILL'd child frees its slot automatically. */

static pid_t *_Py_ForceExec_LivePids = NULL;
static int _Py_ForceExec_MaxProcs = -1;

/* Absolute ceiling the configurable hard cap is itself clamped to, so a
 * typo in FORCE_EXEC_MAX_PROCS_HARD_CAP cannot request a multi-GB PID
 * registry mmap. 65536 pids == 256 KB. */
#define FORCE_EXEC_MAX_PROCS_REGISTRY_LIMIT 65536

/* Upper bound on the operative cap. Env FORCE_EXEC_MAX_PROCS_HARD_CAP
 * (default FORCE_EXEC_MAX_PROCS_HARD_CAP_DEFAULT) lets an operator raise
 * or lower the ceiling that FORCE_EXEC_MAX_PROCS is clamped to. */
static int _Py_ForceExec_GetMaxProcsHardCap(void) {
    char *s = getenv("FORCE_EXEC_MAX_PROCS_HARD_CAP");
    int v = s ? atoi(s) : FORCE_EXEC_MAX_PROCS_HARD_CAP_DEFAULT;
    if (v < 1) v = 1;
    if (v > FORCE_EXEC_MAX_PROCS_REGISTRY_LIMIT) v = FORCE_EXEC_MAX_PROCS_REGISTRY_LIMIT;
    return v;
}

/* Operative concurrent live-process cap. Env FORCE_EXEC_MAX_PROCS
 * (default FORCE_EXEC_MAX_PROCS_DEFAULT), clamped to [1, hard cap]. */
static int _Py_ForceExec_GetMaxProcs(void) {
    if (_Py_ForceExec_MaxProcs > 0) {
        return _Py_ForceExec_MaxProcs;
    }
    int hard = _Py_ForceExec_GetMaxProcsHardCap();
    char *s = getenv("FORCE_EXEC_MAX_PROCS");
    int v = s ? atoi(s) : FORCE_EXEC_MAX_PROCS_DEFAULT;
    if (v < 1) v = 1;
    if (v > hard) v = hard;
    _Py_ForceExec_MaxProcs = v;
    return v;
}

static int _Py_ForceExec_InitLivePids(void) {
    if (_Py_ForceExec_LivePids != NULL) {
        return 1;
    }
    int cap = _Py_ForceExec_GetMaxProcs();
    _Py_ForceExec_LivePids = mmap(NULL, sizeof(pid_t) * cap,
        PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    if (_Py_ForceExec_LivePids == MAP_FAILED) {
        _Py_ForceExec_LivePids = NULL;
        return 0;
    }
    for (int i = 0; i < cap; i++) {
        _Py_ForceExec_LivePids[i] = 0;
    }
    return 1;
}

/* Reserved-slot sentinel: a slot claimed by a pending fork that has not yet
 * recorded its child PID. Counts as live so concurrent forkers see it. */
#define FORCE_EXEC_SLOT_RESERVED ((pid_t)-1)

/* Count live + reserved forced children, reclaiming slots whose child has
 * exited.
 *
 * Liveness is tested with kill(pid, 0), which works across processes (the
 * registry holds children forked by every PyFEX process, not just this
 * one). For a slot whose process is OUR OWN child we additionally reap it
 * with waitpid(pid, WNOHANG) if it has become a zombie -- using the
 * specific pid, NEVER waitpid(-1), so we never reap a child that Python's
 * subprocess/os machinery owns. A child owned by another PyFEX process is
 * reaped by that process; here it simply counts as live until then. A
 * RESERVED slot is a pending fork and always counts as live. */
static int _Py_ForceExec_LiveCount(void) {
    if (!_Py_ForceExec_InitLivePids()) {
        return 0;  /* cannot track -> fail open (preserve old behaviour) */
    }
    int cap = _Py_ForceExec_GetMaxProcs();
    int live = 0;
    for (int i = 0; i < cap; i++) {
        pid_t p = _Py_ForceExec_LivePids[i];
        if (p == 0) {
            continue;
        }
        if (p == FORCE_EXEC_SLOT_RESERVED) {
            live++;  /* pending fork */
            continue;
        }
        if (kill(p, 0) != 0) {
            _Py_ForceExec_LivePids[i] = 0;  /* gone -> reclaim slot */
            continue;
        }
        /* Exists: alive or a zombie. Reap only if our own child, by its
         * specific pid (never waitpid(-1)). */
        if (waitpid(p, NULL, WNOHANG) == p) {
            _Py_ForceExec_LivePids[i] = 0;  /* our zombie, now reaped */
        } else {
            live++;  /* our running child, or another process's child */
        }
    }
    return live;
}

/* fork() wrapper used at every PyFEX fork site -- the ONLY place a
 * concurrency slot is claimed, so a slot is consumed if and only if a fork
 * is actually attempted (predicates that merely gate logging never touch
 * the registry). Atomically reserves a free slot with CAS immediately
 * before fork() -- bounding the check-then-fork race because concurrent
 * forkers see the reservation at once -- records the child PID in it (or
 * releases it on fork failure). Returns the child's PID in the parent, 0
 * in the child, -1 on fork failure, and -2 (without forking) when the
 * concurrent live-process cap is already reached. Callers treat -2/-1
 * exactly like "no child forked": the `if (pid == 0)` branch is skipped
 * and the parent simply continues. */
pid_t _Py_ForceExec_Fork(void) {
    int slot = -1;
    if (_Py_ForceExec_InitLivePids()) {
        int cap = _Py_ForceExec_GetMaxProcs();
        if (_Py_ForceExec_LiveCount() < cap) {
            for (int i = 0; i < cap; i++) {
                if (__sync_bool_compare_and_swap(
                        &_Py_ForceExec_LivePids[i], 0, FORCE_EXEC_SLOT_RESERVED)) {
                    slot = i;
                    break;
                }
            }
        }
        if (slot < 0) {
            return (pid_t)-2;  /* at cap / no free slot: do not fork */
        }
    }
    pid_t pid = fork();
    if (_Py_ForceExec_LivePids != NULL && slot >= 0) {
        if (pid > 0) {
            _Py_ForceExec_LivePids[slot] = pid;  /* register child */
        } else if (pid < 0) {
            _Py_ForceExec_LivePids[slot] = 0;    /* fork failed -> release */
        }
        /* child (pid == 0): the parent records the PID; nothing to do. */
    }
    return pid;
}

/* Defined further down (before ShouldFork); forward-declared so the
 * logging predicate below can reach it. */
static int _Py_PyFEX_DisabledForCoroutineFrame(PyFrameObject *f);

/* Lightweight predicate for the call-logging sites (call_function /
 * do_call_core): forced execution is enabled and the frame is in target
 * scope. Unlike ShouldFork it has NO side effects -- it never touches the
 * fork counters or the concurrency registry -- so gating call logging does
 * not consume fork budget or leak a concurrency slot. */
int _Py_ForceExec_ShouldLogCall(PyFrameObject *f) {
    char *enable_env = getenv("FORCE_EXEC_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        return 0;
    }
    if (_Py_PyFEX_DisabledForCoroutineFrame(f)) {
        return 0;
    }
    return _Py_ForceExec_ShouldTrackScope(f);
}

int _Py_ForceExec_ShouldTrackScope(PyFrameObject *f) {
    if (_Py_ForceExec_SharedMemIOInProgress > 0) {
        return 0;
    }
    return _Py_PyFEX_FrameInScope(f);
}

/* By default PyFEX does NOT fire inside generator / coroutine /
 * async-generator frames: forking and crash recovery inside those
 * frames can duplicate event-loop state and other fragile machinery.
 * Set PYFEX_ENABLE_IN_COROUTINES=1 to opt back in.
 *
 * Returns 1 when the frame is a coroutine frame AND async is not
 * explicitly enabled. Callers skip all PyFEX behaviour in that case. */
static int _Py_PyFEX_DisabledForCoroutineFrame(PyFrameObject *f) {
    if (f == NULL || f->f_code == NULL) return 0;
    int flags = f->f_code->co_flags;
    if ((flags & (CO_GENERATOR | CO_COROUTINE | CO_ASYNC_GENERATOR)) == 0) {
        return 0;
    }
    char *env = getenv("PYFEX_ENABLE_IN_COROUTINES");
    if (env != NULL && strcmp(env, "1") == 0) return 0;
    return 1;
}

int _Py_ForceExec_ShouldFork(PyFrameObject *f) {
    // Check for environment variable
    char *enable_env = getenv("FORCE_EXEC_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        return 0;
    }
    if (_Py_PyFEX_DisabledForCoroutineFrame(f)) {
        return 0;
    }

    // Initialize shared memory before fork so parent and child inherit
    // the same mapping for live peer-state sharing and branch snapshots.
    char *peer_env = getenv("CRASH_RECOVERY_PEER_QUERY");
    if (peer_env == NULL || strcmp(peer_env, "0") != 0) {
        _Py_ForceExec_InitSharedMem();
    }

    // Initialize Global Counter (Shared Memory)
    if (_Py_ForceExec_GlobalForkCount == NULL) {
        _Py_ForceExec_GlobalForkCount = mmap(NULL, sizeof(int), PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
        if (_Py_ForceExec_GlobalForkCount == MAP_FAILED) {
            _Py_ForceExec_GlobalForkCount = NULL; // Failed to init
            return 0;
        }
        *_Py_ForceExec_GlobalForkCount = 0;
    }

    // Check Global Limit
    char *global_limit_str = getenv("FORCE_EXEC_GLOBAL_LIMIT");
    int global_limit = global_limit_str ? atoi(global_limit_str) : FORCE_EXEC_GLOBAL_LIMIT_DEFAULT;

    if (*_Py_ForceExec_GlobalForkCount >= global_limit) {
        return 0;
    }

    // Initialize Location Counts (Per-Process Dict)
    if (_Py_ForceExec_LocationCounts == NULL) {
        _Py_ForceExec_LocationCounts = PyDict_New();
        if (_Py_ForceExec_LocationCounts == NULL) return 0;
    }

    // Check Location Limit
    PyObject *filename = f->f_code->co_filename;
    if (filename == NULL) return 0;

    // Use (filename, instr_index) as key
    PyObject *key = PyTuple_Pack(2, filename, PyLong_FromLong(f->f_lasti));
    if (key == NULL) return 0;

    long count = 0;
    PyObject *count_obj = PyDict_GetItem(_Py_ForceExec_LocationCounts, key); // Borrowed ref
    if (count_obj) {
        count = PyLong_AsLong(count_obj);
    }

    char *location_limit_str = getenv("FORCE_EXEC_LOCATION_LIMIT");
    int location_limit = location_limit_str ? atoi(location_limit_str) : FORCE_EXEC_LOCATION_LIMIT_DEFAULT;

    if (count >= location_limit) {
        Py_DECREF(key);
        return 0;
    }

    if (_Py_ForceExec_ShouldTrackScope(f)) {
        // Hard concurrent-process cap (memory safety): if the live-process
        // cap is already reached, don't fork (and don't consume fork
        // budget). This is a read-only pre-check; the authoritative slot
        // reservation happens in _Py_ForceExec_Fork at the actual fork, so a
        // slot is never consumed by a caller that only gates logging or by a
        // branch whose fork is later skipped.
        if (_Py_ForceExec_LiveCount() >= _Py_ForceExec_GetMaxProcs()) {
            Py_DECREF(key);
            return 0;
        }
        // Reserve a global fork slot ATOMICALLY so FORCE_EXEC_GLOBAL_LIMIT is
        // enforced precisely even under concurrent forking. A plain ++ races:
        // many forks pass the earlier read-check before any increments land,
        // overshooting the limit (worsened by the LiveCount() latency above).
        // Refund and bail if this increment just exceeded the limit.
        if (__sync_add_and_fetch(_Py_ForceExec_GlobalForkCount, 1) > global_limit) {
            __sync_sub_and_fetch(_Py_ForceExec_GlobalForkCount, 1);
            Py_DECREF(key);
            return 0;
        }

        PyObject *new_count = PyLong_FromLong(count + 1);
        if (new_count) {
            PyDict_SetItem(_Py_ForceExec_LocationCounts, key, new_count);
            Py_DECREF(new_count);
        }
        Py_DECREF(key);
        return 1;
    }

    Py_DECREF(key);
    return 0;
}

/* ========== Synthetic awaitable / async iterator ==========
 *
 * Lazily-built Python helpers that let the async-opcode forks substitute
 * objects which resolve without touching the real event loop.
 *
 * _pyfex_resolve(v)      - zero-yield generator returning v; awaiting it
 *                          produces v synchronously.
 * _PyfexAsyncIter(v)     - async iterator yielding a single resolve(v)
 *                          awaitable then raising StopAsyncIteration.
 */

static PyObject *_Py_ForceExec_AsyncHelpers = NULL;

static int _Py_ForceExec_InitAsyncHelpers(void) {
    if (_Py_ForceExec_AsyncHelpers != NULL) return 1;

    const char *src =
        "def _pyfex_resolve(v):\n"
        "    if False:\n"
        "        yield\n"
        "    return v\n"
        "class _PyfexAsyncIter:\n"
        "    def __init__(self, v):\n"
        "        self._v = v\n"
        "        self._done = False\n"
        "    def __aiter__(self):\n"
        "        return self\n"
        "    def __anext__(self):\n"
        "        if self._done:\n"
        "            raise StopAsyncIteration\n"
        "        self._done = True\n"
        "        return _pyfex_resolve(self._v)\n";

    PyObject *globals = PyDict_New();
    if (globals == NULL) { PyErr_Clear(); return 0; }
    PyObject *builtins = PyEval_GetBuiltins();
    if (builtins != NULL) {
        PyDict_SetItemString(globals, "__builtins__", builtins);
    }
    PyObject *r = PyRun_String(src, Py_file_input, globals, globals);
    if (r == NULL) {
        PyErr_Clear();
        Py_DECREF(globals);
        return 0;
    }
    Py_DECREF(r);
    _Py_ForceExec_AsyncHelpers = globals;  /* keep strong ref */
    return 1;
}

PyObject *_Py_ForceExec_MakeSyntheticAwaitable(PyObject *value) {
    if (value == NULL) return NULL;
    if (!_Py_ForceExec_InitAsyncHelpers()) return NULL;
    PyObject *fn = PyDict_GetItemString(_Py_ForceExec_AsyncHelpers, "_pyfex_resolve");
    if (fn == NULL) return NULL;
    PyObject *r = PyObject_CallOneArg(fn, value);
    if (r == NULL) { PyErr_Clear(); }
    return r;
}

PyObject *_Py_ForceExec_MakeSyntheticAsyncIter(PyObject *value) {
    if (value == NULL) return NULL;
    if (!_Py_ForceExec_InitAsyncHelpers()) return NULL;
    PyObject *cls = PyDict_GetItemString(_Py_ForceExec_AsyncHelpers, "_PyfexAsyncIter");
    if (cls == NULL) return NULL;
    PyObject *r = PyObject_CallOneArg(cls, value);
    if (r == NULL) { PyErr_Clear(); }
    return r;
}

/* ========== Loop iteration cap ==========
 *
 * Per-(frame, bytecode-offset) iteration counter stored in a process-local
 * dict. The dict is inherited by forked children (CoW), so a child continues
 * counting from the parent's state at fork time.
 *
 * The counter leaks entries for dead frames; for a bounded analysis run
 * this is acceptable. A future pass can prune stale entries.
 */

static PyObject *_Py_ForceExec_LoopIterCounts = NULL;

int _Py_ForceExec_LoopIterCapHit(PyFrameObject *f, int offset) {
    char *enable_env = getenv("FORCE_EXEC_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        return 0;
    }
    if (f == NULL) return 0;
    if (!_Py_PyFEX_FrameInScope(f)) return 0;

    char *limit_str = getenv("FORCE_EXEC_LOOP_ITER_LIMIT");
    int limit = limit_str ? atoi(limit_str) : FORCE_EXEC_LOOP_ITER_LIMIT_DEFAULT;
    if (limit <= 0) return 0;

    if (_Py_ForceExec_LoopIterCounts == NULL) {
        _Py_ForceExec_LoopIterCounts = PyDict_New();
        if (_Py_ForceExec_LoopIterCounts == NULL) {
            PyErr_Clear();
            return 0;
        }
    }

    PyObject *fid = PyLong_FromVoidPtr((void *)f);
    PyObject *off = PyLong_FromLong(offset);
    if (fid == NULL || off == NULL) {
        Py_XDECREF(fid); Py_XDECREF(off);
        PyErr_Clear();
        return 0;
    }
    PyObject *key = PyTuple_Pack(2, fid, off);
    Py_DECREF(fid);
    Py_DECREF(off);
    if (key == NULL) { PyErr_Clear(); return 0; }

    long count = 0;
    PyObject *cur = PyDict_GetItem(_Py_ForceExec_LoopIterCounts, key); /* borrowed */
    if (cur != NULL) {
        count = PyLong_AsLong(cur);
        if (count < 0 && PyErr_Occurred()) { PyErr_Clear(); count = 0; }
    }
    count++;
    PyObject *new_val = PyLong_FromLong(count);
    if (new_val != NULL) {
        if (PyDict_SetItem(_Py_ForceExec_LoopIterCounts, key, new_val) < 0) {
            PyErr_Clear();
        }
        Py_DECREF(new_val);
    } else {
        PyErr_Clear();
    }
    Py_DECREF(key);

    if (count >= limit) {
        _Py_ForceExec_Log("LOOP_CAP: frame=%p offset=%d count=%ld limit=%d\n",
                          (void *)f, offset, count, limit);
        return 1;
    }
    return 0;
}

/* Drop from `dict` all entries whose key is a (fid, offset) tuple with
 * fid == target_fid. Silently no-ops on failure. */
static void _Py_ForceExec_DictForgetFrame(PyObject *dict, PyObject *target_fid) {
    if (dict == NULL || target_fid == NULL) return;

    PyObject *to_remove = PyList_New(0);
    if (to_remove == NULL) { PyErr_Clear(); return; }

    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next(dict, &pos, &key, &value)) {
        if (PyTuple_Check(key) && PyTuple_GET_SIZE(key) == 2) {
            PyObject *kfid = PyTuple_GET_ITEM(key, 0);  /* borrowed */
            if (PyObject_RichCompareBool(kfid, target_fid, Py_EQ) == 1) {
                if (PyList_Append(to_remove, key) < 0) {
                    PyErr_Clear();
                    break;
                }
            }
        }
    }

    Py_ssize_t n = PyList_GET_SIZE(to_remove);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *k = PyList_GET_ITEM(to_remove, i);
        if (PyDict_DelItem(dict, k) < 0) {
            PyErr_Clear();
        }
    }
    Py_DECREF(to_remove);
    PyErr_Clear();
}

/* Per-(frame, offset) flag: 1 once this FOR_ITER has yielded an item. */
static PyObject *_Py_ForceExec_ForIterYieldedFlags = NULL;

static PyObject *_Py_ForceExec_BuildKey(PyFrameObject *f, int offset) {
    PyObject *fid = PyLong_FromVoidPtr((void *)f);
    PyObject *off = PyLong_FromLong(offset);
    if (fid == NULL || off == NULL) {
        Py_XDECREF(fid); Py_XDECREF(off);
        PyErr_Clear();
        return NULL;
    }
    PyObject *key = PyTuple_Pack(2, fid, off);
    Py_DECREF(fid);
    Py_DECREF(off);
    if (key == NULL) PyErr_Clear();
    return key;
}

void _Py_ForceExec_ForIterMarkYielded(PyFrameObject *f, int offset) {
    if (f == NULL) return;
    if (_Py_ForceExec_ForIterYieldedFlags == NULL) {
        _Py_ForceExec_ForIterYieldedFlags = PyDict_New();
        if (_Py_ForceExec_ForIterYieldedFlags == NULL) { PyErr_Clear(); return; }
    }
    PyObject *key = _Py_ForceExec_BuildKey(f, offset);
    if (key == NULL) return;
    if (PyDict_SetItem(_Py_ForceExec_ForIterYieldedFlags, key, Py_True) < 0) {
        PyErr_Clear();
    }
    Py_DECREF(key);
}

int _Py_ForceExec_ForIterHasYielded(PyFrameObject *f, int offset) {
    if (f == NULL || _Py_ForceExec_ForIterYieldedFlags == NULL) return 0;
    PyObject *key = _Py_ForceExec_BuildKey(f, offset);
    if (key == NULL) return 0;
    int rv = PyDict_Contains(_Py_ForceExec_ForIterYieldedFlags, key);
    Py_DECREF(key);
    if (rv < 0) { PyErr_Clear(); return 0; }
    return rv;
}

void _Py_ForceExec_LoopIterCapForgetFrame(PyFrameObject *f) {
    if (f == NULL) return;
    PyObject *target_fid = PyLong_FromVoidPtr((void *)f);
    if (target_fid == NULL) { PyErr_Clear(); return; }
    _Py_ForceExec_DictForgetFrame(_Py_ForceExec_LoopIterCounts, target_fid);
    _Py_ForceExec_DictForgetFrame(_Py_ForceExec_ForIterYieldedFlags, target_fid);
    Py_DECREF(target_fid);
}

/* ========== Crash Recovery ========== */

static int *_Py_CrashRecovery_GlobalCount = NULL;
static PyObject *_Py_CrashRecovery_LocationCounts = NULL;

int _Py_CrashRecovery_ShouldRecover(PyFrameObject *f) {
    if (_Py_ForceExec_SharedMemIOInProgress > 0) {
        return 0;
    }
    // Check for environment variable
    char *enable_env = getenv("CRASH_RECOVERY_ENABLE");
    if (enable_env == NULL || strcmp(enable_env, "1") != 0) {
        return 0;
    }
    if (_Py_PyFEX_DisabledForCoroutineFrame(f)) {
        return 0;
    }

    // Initialize Global Counter (Shared Memory)
    if (_Py_CrashRecovery_GlobalCount == NULL) {
        _Py_CrashRecovery_GlobalCount = mmap(NULL, sizeof(int), PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
        if (_Py_CrashRecovery_GlobalCount == MAP_FAILED) {
            _Py_CrashRecovery_GlobalCount = NULL; // Failed to init
            return 0;
        }
        *_Py_CrashRecovery_GlobalCount = 0;
    }

    // Check Global Limit
    char *global_limit_str = getenv("CRASH_RECOVERY_GLOBAL_LIMIT");
    int global_limit = global_limit_str ? atoi(global_limit_str) : CRASH_RECOVERY_GLOBAL_LIMIT_DEFAULT;

    _Py_CrashRecovery_Log("DEBUG: Global Count: %d, Limit: %d\n", *_Py_CrashRecovery_GlobalCount, global_limit);

    if (*_Py_CrashRecovery_GlobalCount >= global_limit) {
        _Py_CrashRecovery_Log("DEBUG: Global Limit Reached\n");
        return 0;
    }

    // Initialize Location Counts (Per-Process Dict)
    if (_Py_CrashRecovery_LocationCounts == NULL) {
        _Py_CrashRecovery_LocationCounts = PyDict_New();
        if (_Py_CrashRecovery_LocationCounts == NULL) return 0;
    }

    // Check Location Limit
    PyObject *filename = f->f_code->co_filename;
    if (filename == NULL) return 0;

    // Use (filename, instr_index) as key
    PyObject *key = PyTuple_Pack(2, filename, PyLong_FromLong(f->f_lasti));
    if (key == NULL) return 0;

    long count = 0;
    PyObject *count_obj = PyDict_GetItem(_Py_CrashRecovery_LocationCounts, key); // Borrowed ref
    if (count_obj) {
        count = PyLong_AsLong(count_obj);
    }

    char *location_limit_str = getenv("CRASH_RECOVERY_LOCATION_LIMIT");
    int location_limit = location_limit_str ? atoi(location_limit_str) : CRASH_RECOVERY_LOCATION_LIMIT_DEFAULT;

    if (count >= location_limit) {
        Py_DECREF(key);
        return 0;
    }

    /* Shared scope check: main-script path/basename match or PYFEX_SCOPE_DIR,
       with f_back walk for dynamic code. */
    int match = _Py_PyFEX_FrameInScope(f);

    if (match) {
        // Update Counts
        (*_Py_CrashRecovery_GlobalCount)++;

        PyObject *new_count = PyLong_FromLong(count + 1);
        if (new_count) {
            PyDict_SetItem(_Py_CrashRecovery_LocationCounts, key, new_count);
            Py_DECREF(new_count);
        }
        Py_DECREF(key);

        _Py_CrashRecovery_Log("DEBUG: Crash recovery approved at %s:%d\n",
                              PyUnicode_AsUTF8(filename), f->f_lineno);
        return 1;
    }

    Py_DECREF(key);
    return 0;
}

/* ========== Peer Recovery from Merged State ========== */

static PyObject *_Py_ForceExec_GetRecoveryVarName(PyFrameObject *f, int opcode, int oparg) {
    PyCodeObject *co = f->f_code;

    if (opcode == LOAD_FAST) {
        if (oparg < PyTuple_GET_SIZE(co->co_varnames)) {
            return PyTuple_GET_ITEM(co->co_varnames, oparg);
        }
    } else if (opcode == LOAD_DEREF || opcode == LOAD_CLASSDEREF ||
               opcode == STORE_DEREF || opcode == DELETE_DEREF) {
        Py_ssize_t cell_count = PyTuple_GET_SIZE(co->co_cellvars);
        if (oparg < cell_count) {
            return PyTuple_GET_ITEM(co->co_cellvars, oparg);
        }
        oparg -= (int)cell_count;
        if (oparg >= 0 && oparg < PyTuple_GET_SIZE(co->co_freevars)) {
            return PyTuple_GET_ITEM(co->co_freevars, oparg);
        }
    } else if (opcode == LOAD_NAME || opcode == LOAD_GLOBAL || opcode == LOAD_ATTR) {
        if (oparg < PyTuple_GET_SIZE(co->co_names)) {
            return PyTuple_GET_ITEM(co->co_names, oparg);
        }
    }

    return NULL;
}

static PyObject *_Py_ForceExec_FindMergedConcreteValue(PyObject *var_name, int *branch_id,
                                                       const char **location) {
    for (int i = _Py_ForceExec_MergedStateStackTop - 1; i >= 0; i--) {
        MergedStateEntry *entry = &_Py_ForceExec_MergedStateStack[i];
        if (!entry->valid) continue;

        if (entry->merged_locals) {
            PyObject *val = PyDict_GetItem(entry->merged_locals, var_name);
            if (val != NULL && !Py_IS_TYPE(val, &PyDummy_Type)) {
                if (branch_id) {
                    *branch_id = entry->branch_id;
                }
                if (location) {
                    *location = "locals";
                }
                Py_INCREF(val);
                return val;
            }
        }

        if (entry->merged_globals) {
            PyObject *val = PyDict_GetItem(entry->merged_globals, var_name);
            if (val != NULL && !Py_IS_TYPE(val, &PyDummy_Type)) {
                if (branch_id) {
                    *branch_id = entry->branch_id;
                }
                if (location) {
                    *location = "globals";
                }
                Py_INCREF(val);
                return val;
            }
        }
    }

    return NULL;
}

static PyObject *
_Py_ForceExec_RecoverConcreteValueByName(PyFrameObject *f, PyObject *var_name,
                                         int *branch_id, const char **location)
{
    PyObject *recovered = _Py_ForceExec_FindMergedConcreteValue(
        var_name, branch_id, location);
    if (recovered != NULL) {
        return recovered;
    }

    recovered = _Py_ForceExec_SharedMem_RecoverLivePeerValue(f, var_name);
    if (recovered != NULL) {
        if (branch_id) {
            *branch_id = -1;
        }
        if (location) {
            *location = "live peer";
        }
        return recovered;
    }

    recovered = _Py_ForceExec_SharedMem_RecoverPeerSnapshot(f, var_name);
    if (recovered != NULL) {
        if (branch_id) {
            *branch_id = -1;
        }
        if (location) {
            *location = "peer snapshot";
        }
        return recovered;
    }

    if (_Py_ForceExec_SharedMem != NULL) {
        const char *name_str = PyUnicode_AsUTF8(var_name);
        if (name_str != NULL) {
            PyCodeObject *co = f->f_code;
            const char *filename = PyUnicode_AsUTF8(co->co_filename);
            const char *funcname = PyUnicode_AsUTF8(co->co_name);
            char scope[512];

            snprintf(scope, sizeof(scope), "%s:%s",
                     filename ? filename : "?", funcname ? funcname : "?");

            recovered = _Py_ForceExec_SharedMem_Recover(name_str, scope);
            if (recovered != NULL && !Py_IS_TYPE(recovered, &PyDummy_Type)) {
                if (branch_id) {
                    *branch_id = -1;
                }
                if (location) {
                    *location = "manual shared memory";
                }
                return recovered;
            }
            PyErr_Clear();
            Py_XDECREF(recovered);
        }
    }

    return NULL;
}

static PyObject *
_Py_ForceExec_FindNameForOperand(PyFrameObject *f, PyObject *operand)
{
    PyObject *key;
    PyObject *value;
    Py_ssize_t pos = 0;

    if (f == NULL || operand == NULL) {
        return NULL;
    }

    if (PyFrame_FastToLocalsWithError(f) < 0) {
        PyErr_Clear();
    }

    if (f->f_locals != NULL && PyDict_Check(f->f_locals)) {
        while (PyDict_Next(f->f_locals, &pos, &key, &value)) {
            if (value == operand && PyUnicode_Check(key)) {
                Py_INCREF(key);
                return key;
            }
        }
    }

    pos = 0;
    if (f->f_globals != NULL && PyDict_Check(f->f_globals)) {
        while (PyDict_Next(f->f_globals, &pos, &key, &value)) {
            if (value == operand && PyUnicode_Check(key)) {
                Py_INCREF(key);
                return key;
            }
        }
    }

    return NULL;
}

// Recover a concrete value from merged peer state for a variable lookup.
PyObject *_Py_ForceExec_RecoverFromMergedState(
    PyThreadState *tstate, PyFrameObject *f,
    const char *opcode_name, int opcode, int oparg)
{
    (void)opcode_name;

    // Check env var gate
    char *peer_env = getenv("CRASH_RECOVERY_PEER_QUERY");
    if (peer_env && strcmp(peer_env, "0") == 0) return NULL;

    // Determine variable name from opcode
    PyObject *var_name = _Py_ForceExec_GetRecoveryVarName(f, opcode, oparg);
    if (var_name == NULL) return NULL;

    int branch_id = -1;
    const char *location = NULL;
    PyObject *recovered = _Py_ForceExec_RecoverConcreteValueByName(
        f, var_name, &branch_id, &location);
    if (recovered != NULL) {
        if (branch_id >= 0) {
            _Py_CrashRecovery_Log(
                "PEER_RECOVERY: found concrete value for '%s' from branch %d (%s)\n",
                PyUnicode_AsUTF8(var_name), branch_id, location ? location : "?");
        } else {
            _Py_CrashRecovery_Log(
                "PEER_RECOVERY: found concrete value for '%s' from %s\n",
                PyUnicode_AsUTF8(var_name), location ? location : "?");
        }
        return recovered;
    }

    return NULL;
}

// Try alternative values from merged peer state when an operation crashes.
PyObject *_Py_ForceExec_TryAlternativeValues(
    PyThreadState *tstate, PyFrameObject *f,
    int opcode, int oparg,
    PyObject *original_operand)
{
    // Check env var gate
    char *peer_env = getenv("CRASH_RECOVERY_PEER_QUERY");
    if (peer_env && strcmp(peer_env, "0") == 0) return NULL;

    // For variable-loading opcodes, delegate to the simpler recovery function
    if (opcode == LOAD_FAST || opcode == LOAD_NAME || opcode == LOAD_GLOBAL ||
        opcode == LOAD_DEREF || opcode == LOAD_CLASSDEREF) {
        return _Py_ForceExec_RecoverFromMergedState(tstate, f, "", opcode, oparg);
    }

    PyObject *var_name = NULL;
    if (original_operand != NULL) {
        var_name = _Py_ForceExec_FindNameForOperand(f, original_operand);
    }

    if (var_name == NULL) {
        return NULL;
    }

    int branch_id = -1;
    const char *location = NULL;
    PyObject *val = _Py_ForceExec_RecoverConcreteValueByName(
        f, var_name, &branch_id, &location);

    if (val != NULL) {
        if (original_operand == NULL || val != original_operand) {
            char source[64];
            if (branch_id >= 0) {
                snprintf(source, sizeof(source), "branch %d (%s)",
                         branch_id, location ? location : "?");
            } else {
                snprintf(source, sizeof(source), "%s", location ? location : "?");
            }
            _Py_CrashRecovery_Log(
                "PEER_RETRY: trying alternative value for '%s' from %s\n",
                PyUnicode_AsUTF8(var_name), source);

            // Clear the current error before retry
            _PyErr_Clear(tstate);

            if (opcode == LOAD_ATTR) {
                PyCodeObject *co = f->f_code;
                PyObject *attr_name = NULL;
                PyObject *result = NULL;
                if (oparg < PyTuple_GET_SIZE(co->co_names)) {
                    attr_name = PyTuple_GET_ITEM(co->co_names, oparg);
                }
                if (attr_name != NULL) {
                    result = PyObject_GetAttr(val, attr_name);
                }
                Py_DECREF(val);
                if (result != NULL) {
                    Py_DECREF(var_name);
                    return result;
                }
                _PyErr_Clear(tstate);
            }
        }
        Py_DECREF(val);
    }

    Py_DECREF(var_name);
    return NULL;
}
