/* Dummy object implementation for crash recovery */

#include "Python.h"
#include "pycore_pystate.h"
#include "frameobject.h"
#include "dummyobject.h"

#include <ctype.h>

/*[clinic input]
class DummyObject "PyDummyObject *" "&PyDummy_Type"
[clinic start generated code]*/
/*[clinic end generated code: output=da39a3ee5e6b4b0d input=4935534c8a9413c5]*/

/* Forward declarations */
static PyObject *dummy_get_trace(PyDummyObject *self, void *closure);
static PyObject *dummy_get_error_reason(PyDummyObject *self, void *closure);
static PyObject *dummy_get_location(PyDummyObject *self, void *closure);
static PyObject *dummy_get_operations_history(PyDummyObject *self, void *closure);

/* Helper macro to check if an object is a dummy */
#define IS_DUMMY(obj) (Py_TYPE(obj) == &PyDummy_Type)

/* ==================== Provenance Mode ==================== */

/* PYFEX_PROVENANCE_MODE selects how a dummy records where it came from:
 *   flat (default) -- the historical behavior: a flat append-log in
 *                     ->operations; ->original_operands stays None; no
 *                     operand references retained; zero added overhead.
 *   recursive      -- additionally retain, per propagation, a symbolic
 *                     operand record in ->original_operands so the lineage can
 *                     be rendered as a nested expression, e.g.
 *                     SUBSCRIPT(ADD(dummy, 1), 2). The flat ->operations log is
 *                     still maintained for back-compat.
 * Read once (lazily) and cached; all dummy work runs under the GIL. */
static int _dummy_provenance_mode = -1;  /* -1 unread, 0 flat, 1 recursive */

static int
dummy_provenance_recursive(void)
{
    if (_dummy_provenance_mode < 0) {
        const char *m = getenv("PYFEX_PROVENANCE_MODE");
        _dummy_provenance_mode = (m != NULL && strcmp(m, "recursive") == 0) ? 1 : 0;
    }
    return _dummy_provenance_mode;
}

/* Cap recursion when rendering a (possibly deep) provenance DAG so a long
 * recovery chain cannot overflow the C stack or emit unbounded text. */
#define DUMMY_PROV_MAX_DEPTH 100

/* Render the symbolic provenance expression rooted at obj. A dummy with a
 * populated ->original_operands tuple (LABEL, operand...) renders as
 * LABEL(render(operand), ...); a dummy without one is a leaf "dummy"; a
 * concrete operand (stored as its repr string by dummy_set_provenance) prints
 * verbatim. Never returns NULL; falls back to "dummy"/"?" on any error. */
static PyObject *
dummy_render_provenance(PyObject *obj, int depth)
{
    if (depth > DUMMY_PROV_MAX_DEPTH) {
        return PyUnicode_FromString("...");
    }
    if (!IS_DUMMY(obj)) {
        if (PyUnicode_Check(obj)) {
            Py_INCREF(obj);
            return obj;
        }
        PyObject *r = PyObject_Repr(obj);
        if (r == NULL) {
            PyErr_Clear();
            return PyUnicode_FromString("?");
        }
        return r;
    }

    PyDummyObject *d = (PyDummyObject *)obj;
    PyObject *ops = d->original_operands;
    if (ops == NULL || !PyTuple_Check(ops) || PyTuple_GET_SIZE(ops) < 2) {
        return PyUnicode_FromString("dummy");
    }

    PyObject *label = PyTuple_GET_ITEM(ops, 0);  /* borrowed, already uppercase */
    Py_ssize_t n = PyTuple_GET_SIZE(ops);
    PyObject *parts = PyList_New(0);
    if (parts == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("dummy");
    }
    for (Py_ssize_t i = 1; i < n; i++) {
        PyObject *child = dummy_render_provenance(PyTuple_GET_ITEM(ops, i), depth + 1);
        if (child != NULL) {
            if (PyList_Append(parts, child) < 0) {
                PyErr_Clear();
            }
            Py_DECREF(child);
        } else {
            PyErr_Clear();
        }
    }

    PyObject *comma = PyUnicode_FromString(", ");
    PyObject *joined = comma ? PyUnicode_Join(comma, parts) : NULL;
    Py_XDECREF(comma);
    Py_DECREF(parts);

    PyObject *result = NULL;
    if (joined != NULL && PyUnicode_Check(label)) {
        result = PyUnicode_FromFormat("%S(%S)", label, joined);
    }
    Py_XDECREF(joined);
    if (result == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("dummy");
    }
    return result;
}

/* ==================== Allocation and Deallocation ==================== */

static PyDummyObject *
dummy_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyDummyObject *self;
    self = (PyDummyObject *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->error_type = Py_None;
        Py_INCREF(Py_None);
        self->error_message = PyUnicode_FromString("");
        self->filename = PyUnicode_FromString("");
        self->function_name = PyUnicode_FromString("");
        self->lineno = 0;
        self->bytecode_offset = -1;
        self->operations = PyList_New(0);
        self->traceback_str = Py_None;
        Py_INCREF(Py_None);
        self->original_operands = Py_None;
        Py_INCREF(Py_None);
    }
    return self;
}

static void
dummy_dealloc(PyDummyObject *self)
{
    PyObject_GC_UnTrack(self);
    /* In recursive provenance mode, ->original_operands chains a dummy to the
     * dummies it was derived from. Freeing the head of a long lineage would
     * otherwise recurse tp_dealloc C-stack-deep; the trashcan bounds it. */
    Py_TRASHCAN_BEGIN(self, dummy_dealloc)
    Py_XDECREF(self->error_type);
    Py_XDECREF(self->error_message);
    Py_XDECREF(self->filename);
    Py_XDECREF(self->function_name);
    Py_XDECREF(self->operations);
    Py_XDECREF(self->traceback_str);
    Py_XDECREF(self->original_operands);
    Py_TYPE(self)->tp_free((PyObject *)self);
    Py_TRASHCAN_END
}

/* ==================== Garbage Collection Support ==================== */

static int
dummy_traverse(PyDummyObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->error_type);
    Py_VISIT(self->error_message);
    Py_VISIT(self->filename);
    Py_VISIT(self->function_name);
    Py_VISIT(self->operations);
    Py_VISIT(self->traceback_str);
    Py_VISIT(self->original_operands);
    return 0;
}

static int
dummy_clear(PyDummyObject *self)
{
    Py_CLEAR(self->error_type);
    Py_CLEAR(self->error_message);
    Py_CLEAR(self->filename);
    Py_CLEAR(self->function_name);
    Py_CLEAR(self->operations);
    Py_CLEAR(self->traceback_str);
    Py_CLEAR(self->original_operands);
    return 0;
}

/* ==================== String Representation ==================== */

/* Return a new Unicode with the basename of the given path-like Unicode, or
 * "?" if anything goes wrong. Never returns NULL. */
static PyObject *
dummy_basename(PyObject *path_obj)
{
    if (path_obj != NULL && PyUnicode_Check(path_obj)) {
        const char *s = PyUnicode_AsUTF8(path_obj);
        if (s != NULL) {
            const char *slash = strrchr(s, '/');
            PyObject *r = PyUnicode_FromString(slash ? slash + 1 : s);
            if (r != NULL) return r;
        }
        PyErr_Clear();
    }
    PyObject *fallback = PyUnicode_FromString("?");
    if (fallback == NULL) {
        PyErr_Clear();
    }
    return fallback;
}

static int
dummy_unicode_eq(PyObject *obj, const char *literal)
{
    if (obj == NULL || !PyUnicode_Check(obj)) {
        return 0;
    }
    const char *s = PyUnicode_AsUTF8(obj);
    if (s == NULL) {
        PyErr_Clear();
        return 0;
    }
    return strcmp(s, literal) == 0;
}

/* Compact one-line label for str(dummy)'s lineage tail. */
static PyObject *
dummy_operation_label(PyObject *op)
{
    if (!PyDict_Check(op)) {
        return PyUnicode_FromString("unknown");
    }

    PyObject *type_str = PyDict_GetItemString(op, "type");
    PyObject *op_str = PyDict_GetItemString(op, "operation");
    PyObject *info = PyDict_GetItemString(op, "info");

    if (dummy_unicode_eq(type_str, "CRASH") && dummy_unicode_eq(op_str, "initial_error")) {
        return PyUnicode_FromString("runtime_error");
    }
    if (dummy_unicode_eq(type_str, "CRASH")) {
        return PyUnicode_FromFormat("recover(%S)", op_str ? op_str : Py_None);
    }
    if (dummy_unicode_eq(type_str, "GETATTR")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat("getattr(%S)", info);
        }
        return PyUnicode_FromString("getattr");
    }
    if (dummy_unicode_eq(type_str, "GETITEM")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat("getitem(%S)", info);
        }
        return PyUnicode_FromString("getitem");
    }
    if (dummy_unicode_eq(type_str, "CALL")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat("call(%S)", info);
        }
        return PyUnicode_FromString("call");
    }
    if (dummy_unicode_eq(type_str, "PROPAGATION")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat("%S(%S)", op_str ? op_str : Py_None, info);
        }
        return PyUnicode_FromFormat("%S", op_str ? op_str : Py_None);
    }
    if (op_str != NULL && PyUnicode_Check(op_str)) {
        Py_INCREF(op_str);
        return op_str;
    }
    return PyUnicode_FromString("unknown");
}

/* Full human-readable operation line for dummy.trace. */
static PyObject *
dummy_operation_line(PyObject *op, Py_ssize_t index)
{
    if (!PyDict_Check(op)) {
        return PyUnicode_FromFormat("  %zd. unknown operation\n", index + 1);
    }

    PyObject *type_str = PyDict_GetItemString(op, "type");
    PyObject *op_str = PyDict_GetItemString(op, "operation");
    PyObject *info = PyDict_GetItemString(op, "info");

    if (dummy_unicode_eq(type_str, "CRASH") && dummy_unicode_eq(op_str, "initial_error")) {
        return PyUnicode_FromFormat(
            "  %zd. CRASH: captured the original runtime failure\n", index + 1);
    }
    if (dummy_unicode_eq(type_str, "CRASH")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat(
                "  %zd. CRASH: recovered failed bytecode %S (%S)\n",
                index + 1, op_str ? op_str : Py_None, info);
        }
        return PyUnicode_FromFormat(
            "  %zd. CRASH: recovered failed bytecode %S\n",
            index + 1, op_str ? op_str : Py_None);
    }
    if (dummy_unicode_eq(type_str, "GETATTR")) {
        return PyUnicode_FromFormat(
            "  %zd. GETATTR: accessed attribute %S on the synthetic value\n",
            index + 1, info ? info : Py_None);
    }
    if (dummy_unicode_eq(type_str, "GETITEM")) {
        return PyUnicode_FromFormat(
            "  %zd. GETITEM: subscripted the synthetic value with key %S\n",
            index + 1, info ? info : Py_None);
    }
    if (dummy_unicode_eq(type_str, "CALL")) {
        return PyUnicode_FromFormat(
            "  %zd. CALL: propagated through call target %S\n",
            index + 1, info ? info : Py_None);
    }
    if (dummy_unicode_eq(type_str, "PROPAGATION")) {
        if (info != NULL && info != Py_None) {
            return PyUnicode_FromFormat(
                "  %zd. PROPAGATION: used in %S with %S\n",
                index + 1, op_str ? op_str : Py_None, info);
        }
        return PyUnicode_FromFormat(
            "  %zd. PROPAGATION: used in %S\n",
            index + 1, op_str ? op_str : Py_None);
    }

    if (info != NULL && info != Py_None) {
        return PyUnicode_FromFormat(
            "  %zd. %S: %S (%S)\n",
            index + 1, type_str ? type_str : Py_None, op_str ? op_str : Py_None, info);
    }
    return PyUnicode_FromFormat(
        "  %zd. %S: %S\n",
        index + 1, type_str ? type_str : Py_None, op_str ? op_str : Py_None);
}

/* Build a compact summary of the operation history, using readable labels for
 * the last 3 operations. Returns empty string if history is empty. Never
 * returns NULL; falls back to "". */
static PyObject *
dummy_ops_suffix(PyDummyObject *self)
{
    if (self->operations == NULL || !PyList_Check(self->operations)) {
        return PyUnicode_FromString("");
    }
    Py_ssize_t n = PyList_GET_SIZE(self->operations);
    if (n == 0) {
        return PyUnicode_FromString("");
    }

    const Py_ssize_t TAIL = 3;
    Py_ssize_t start = n > TAIL ? n - TAIL : 0;

    PyObject *parts = PyList_New(0);
    if (parts == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("");
    }
    for (Py_ssize_t i = start; i < n; i++) {
        PyObject *op = PyList_GET_ITEM(self->operations, i);
        PyObject *label = dummy_operation_label(op);
        if (label != NULL) {
            if (PyList_Append(parts, label) < 0) {
                PyErr_Clear();
            }
            Py_DECREF(label);
        } else {
            PyErr_Clear();
        }
    }

    PyObject *arrow = PyUnicode_FromString("->");
    PyObject *chain = arrow ? PyUnicode_Join(arrow, parts) : NULL;
    Py_XDECREF(arrow);
    Py_DECREF(parts);

    PyObject *suffix;
    if (chain != NULL) {
        suffix = PyUnicode_FromFormat("; lineage[%zd] ops: %S", n, chain);
        Py_DECREF(chain);
    } else {
        PyErr_Clear();
        suffix = PyUnicode_FromFormat("; lineage[%zd] ops", n);
    }
    if (suffix == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("");
    }
    return suffix;
}

static PyObject *
dummy_repr(PyDummyObject *self)
{
    PyObject *base = dummy_basename(self->filename);
    PyObject *result;
    if (self->error_message != NULL && PyUnicode_Check(self->error_message)) {
        result = PyUnicode_FromFormat("<DummyObject %S@%S:%d>",
                                      self->error_message, base, self->lineno);
    } else {
        result = PyUnicode_FromFormat("<DummyObject @%S:%d>",
                                      base, self->lineno);
    }
    Py_XDECREF(base);
    if (result == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("<DummyObject>");
    }
    return result;
}

static PyObject *
dummy_str(PyDummyObject *self)
{
    PyObject *base = dummy_basename(self->filename);
    /* In recursive provenance mode, show the nested symbolic expression;
     * otherwise fall back to the compact flat lineage suffix. */
    PyObject *ops = NULL;
    if (dummy_provenance_recursive()
        && self->original_operands != NULL
        && PyTuple_Check(self->original_operands)) {
        PyObject *expr = dummy_render_provenance((PyObject *)self, 0);
        if (expr != NULL) {
            ops = PyUnicode_FromFormat("; provenance: %S", expr);
            Py_DECREF(expr);
        }
        if (ops == NULL) {
            PyErr_Clear();
        }
    }
    if (ops == NULL) {
        ops = dummy_ops_suffix(self);
    }
    PyObject *result;
    if (self->error_message != NULL && PyUnicode_Check(self->error_message)) {
        result = PyUnicode_FromFormat("DummyObject(%S@%S:%d%S)",
                                      self->error_message, base, self->lineno, ops);
    } else {
        result = PyUnicode_FromFormat("DummyObject(@%S:%d%S)",
                                      base, self->lineno, ops);
    }
    Py_XDECREF(base);
    Py_XDECREF(ops);
    if (result == NULL) {
        PyErr_Clear();
        return PyUnicode_FromString("DummyObject");
    }
    return result;
}

/* ==================== Propagation Helper Functions ==================== */

/* Copy operations history from source dummy to target dummy */
static int
copy_operations(PyDummyObject *target, PyDummyObject *source)
{
    if (source->operations == NULL || !PyList_Check(source->operations)) {
        return 0;
    }

    Py_ssize_t n = PyList_GET_SIZE(source->operations);
    for (Py_ssize_t i = 0; i < n; i++) {
        PyObject *op = PyList_GET_ITEM(source->operations, i);
        Py_INCREF(op);
        if (PyList_Append(target->operations, op) < 0) {
            Py_DECREF(op);
            return -1;
        }
        Py_DECREF(op);
    }
    return 0;
}

/* Add an operation to the dummy's history */
static int
add_operation(PyDummyObject *dummy, const char *op_type, const char *operation, PyObject *extra_info)
{
    PyObject *op_dict = PyDict_New();
    if (op_dict == NULL) {
        return -1;
    }

    PyObject *type_str = PyUnicode_FromString(op_type);
    PyObject *op_str = PyUnicode_FromString(operation);

    if (type_str == NULL || op_str == NULL) {
        Py_XDECREF(type_str);
        Py_XDECREF(op_str);
        Py_DECREF(op_dict);
        return -1;
    }

    PyDict_SetItemString(op_dict, "type", type_str);
    PyDict_SetItemString(op_dict, "operation", op_str);

    if (extra_info != NULL) {
        PyDict_SetItemString(op_dict, "info", extra_info);
    }

    int result = PyList_Append(dummy->operations, op_dict);

    Py_DECREF(type_str);
    Py_DECREF(op_str);
    Py_DECREF(op_dict);

    return result;
}

/* Record the symbolic operand structure for recursive provenance mode.
 * Stores new_dummy->original_operands = (UPPERCASE_LABEL, slot...) where a
 * dummy operand is kept by reference (so it can be rendered recursively) and a
 * concrete operand is stored as its repr string -- a printable leaf that also
 * bounds memory by not retaining arbitrary live objects. No-op (and no operand
 * refs retained) in flat mode. Best-effort: any failure leaves the existing
 * None in place rather than raising. */
static void
dummy_set_provenance(PyDummyObject *new_dummy, const char *op_label,
                     PyObject **operands, Py_ssize_t n)
{
    if (!dummy_provenance_recursive()) {
        return;
    }

    PyObject *tup = PyTuple_New(n + 1);
    if (tup == NULL) {
        PyErr_Clear();
        return;
    }

    char upper[48];
    size_t i = 0;
    for (; op_label[i] != '\0' && i < sizeof(upper) - 1; i++) {
        upper[i] = (char)toupper((unsigned char)op_label[i]);
    }
    upper[i] = '\0';
    PyObject *label = PyUnicode_FromString(upper);
    if (label == NULL) {
        PyErr_Clear();
        Py_DECREF(tup);
        return;
    }
    PyTuple_SET_ITEM(tup, 0, label);  /* steals */

    for (Py_ssize_t k = 0; k < n; k++) {
        PyObject *o = operands[k];
        PyObject *slot;
        if (IS_DUMMY(o)) {
            Py_INCREF(o);
            slot = o;
        } else {
            slot = PyObject_Repr(o);
            if (slot == NULL) {
                PyErr_Clear();
                slot = PyUnicode_FromString("?");
            }
            if (slot == NULL) {
                PyErr_Clear();
                slot = Py_None;
                Py_INCREF(Py_None);
            }
        }
        PyTuple_SET_ITEM(tup, k + 1, slot);  /* steals */
    }

    Py_XSETREF(new_dummy->original_operands, tup);
}

/* ==================== Core Dummy Creation Functions ==================== */

PyObject *
_PyDummy_New(PyThreadState *tstate, PyFrameObject *frame)
{
    PyDummyObject *dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (dummy == NULL) {
        return NULL;
    }

    /* Get the current exception */
    PyObject *exc_type, *exc_value, *exc_tb;
    PyErr_Fetch(&exc_type, &exc_value, &exc_tb);

    if (exc_type == NULL) {
        exc_type = Py_None;
        Py_INCREF(Py_None);
    }
    if (exc_value == NULL) {
        exc_value = PyUnicode_FromString("Unknown error");
    }

    /* Store error information */
    Py_XDECREF(dummy->error_type);
    dummy->error_type = exc_type;  /* Steal reference */

    Py_XDECREF(dummy->error_message);
    if (PyUnicode_Check(exc_value)) {
        dummy->error_message = exc_value;  /* Steal reference */
    } else {
        PyObject *str_repr = PyObject_Str(exc_value);
        if (str_repr != NULL) {
            dummy->error_message = str_repr;
        } else {
            dummy->error_message = PyUnicode_FromString("Error representation failed");
            PyErr_Clear();
        }
        Py_DECREF(exc_value);
    }

    /* Store traceback as string if available */
    if (exc_tb != NULL) {
        PyObject *tb_module = PyImport_ImportModule("traceback");
        if (tb_module != NULL) {
            PyObject *format_tb = PyObject_GetAttrString(tb_module, "format_tb");
            if (format_tb != NULL) {
                PyObject *tb_lines = PyObject_CallFunctionObjArgs(format_tb, exc_tb, NULL);
                if (tb_lines != NULL && PyList_Check(tb_lines)) {
                    PyObject *empty = PyUnicode_FromString("");
                    PyObject *tb_str = PyUnicode_Join(empty, tb_lines);
                    if (tb_str != NULL) {
                        Py_XDECREF(dummy->traceback_str);
                        dummy->traceback_str = tb_str;
                    }
                    Py_DECREF(empty);
                    Py_DECREF(tb_lines);
                }
                Py_DECREF(format_tb);
            }
            Py_DECREF(tb_module);
        }
        PyErr_Clear();  /* Ignore errors in traceback formatting */
        Py_DECREF(exc_tb);
    }

    /* Store location information from frame */
    if (frame != NULL && frame->f_code != NULL) {
        PyCodeObject *code = frame->f_code;

        Py_XDECREF(dummy->filename);
        dummy->filename = code->co_filename;
        Py_INCREF(dummy->filename);

        Py_XDECREF(dummy->function_name);
        dummy->function_name = code->co_name;
        Py_INCREF(dummy->function_name);

        dummy->lineno = PyCode_Addr2Line(code, frame->f_lasti);
        dummy->bytecode_offset = frame->f_lasti;
    }

    /* Add initial crash operation */
    add_operation(dummy, "CRASH", "initial_error", NULL);

    return (PyObject *)dummy;
}

PyObject *
_PyDummy_NewFromBytecode(PyThreadState *tstate, PyFrameObject *frame,
                         const char *opcode_name, int opcode, int oparg)
{
    PyObject *dummy = _PyDummy_New(tstate, frame);
    if (dummy == NULL) {
        return NULL;
    }

    /* Add bytecode-specific information to the operation history */
    PyDummyObject *d = (PyDummyObject *)dummy;
    PyObject *opcode_info = PyUnicode_FromFormat("%s (opcode=%d, oparg=%d)",
                                                  opcode_name, opcode, oparg);
    if (opcode_info != NULL) {
        add_operation(d, "CRASH", opcode_name, opcode_info);
        Py_DECREF(opcode_info);
    }

    return dummy;
}

/* ==================== Propagation Functions ==================== */

PyObject *
_PyDummy_PropagateOperation(PyObject *left, PyObject *right, const char *operation_name)
{
    /* At least one operand must be a dummy */
    if (!IS_DUMMY(left) && !IS_DUMMY(right)) {
        PyErr_SetString(PyExc_TypeError, "At least one operand must be a dummy");
        return NULL;
    }

    /* Create new dummy based on the first dummy operand */
    PyDummyObject *source = IS_DUMMY(left) ? (PyDummyObject *)left : (PyDummyObject *)right;
    PyDummyObject *new_dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (new_dummy == NULL) {
        return NULL;
    }

    /* Copy error information from source */
    Py_XDECREF(new_dummy->error_type);
    new_dummy->error_type = source->error_type;
    Py_INCREF(new_dummy->error_type);

    Py_XDECREF(new_dummy->error_message);
    new_dummy->error_message = source->error_message;
    Py_INCREF(new_dummy->error_message);

    Py_XDECREF(new_dummy->filename);
    new_dummy->filename = source->filename;
    Py_INCREF(new_dummy->filename);

    Py_XDECREF(new_dummy->function_name);
    new_dummy->function_name = source->function_name;
    Py_INCREF(new_dummy->function_name);

    new_dummy->lineno = source->lineno;
    new_dummy->bytecode_offset = source->bytecode_offset;

    Py_XDECREF(new_dummy->traceback_str);
    new_dummy->traceback_str = source->traceback_str;
    Py_INCREF(new_dummy->traceback_str);

    /* Copy operations history */
    if (copy_operations(new_dummy, source) < 0) {
        Py_DECREF(new_dummy);
        return NULL;
    }

    /* Add current operation */
    PyObject *other_operand = IS_DUMMY(left) ? right : left;
    PyObject *other_repr = PyObject_Repr(other_operand);
    if (other_repr != NULL) {
        add_operation(new_dummy, "PROPAGATION", operation_name, other_repr);
        Py_DECREF(other_repr);
    } else {
        PyErr_Clear();
        add_operation(new_dummy, "PROPAGATION", operation_name, NULL);
    }

    /* Recursive provenance: preserve both operands in source order. */
    PyObject *prov_operands[2] = {left, right};
    dummy_set_provenance(new_dummy, operation_name, prov_operands, 2);

    return (PyObject *)new_dummy;
}

PyObject *
_PyDummy_PropagateUnaryOp(PyObject *operand, const char *operation_name)
{
    if (!IS_DUMMY(operand)) {
        PyErr_SetString(PyExc_TypeError, "Operand must be a dummy");
        return NULL;
    }

    PyDummyObject *source = (PyDummyObject *)operand;
    PyDummyObject *new_dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (new_dummy == NULL) {
        return NULL;
    }

    /* Copy error information from source */
    Py_XDECREF(new_dummy->error_type);
    new_dummy->error_type = source->error_type;
    Py_INCREF(new_dummy->error_type);

    Py_XDECREF(new_dummy->error_message);
    new_dummy->error_message = source->error_message;
    Py_INCREF(new_dummy->error_message);

    Py_XDECREF(new_dummy->filename);
    new_dummy->filename = source->filename;
    Py_INCREF(new_dummy->filename);

    Py_XDECREF(new_dummy->function_name);
    new_dummy->function_name = source->function_name;
    Py_INCREF(new_dummy->function_name);

    new_dummy->lineno = source->lineno;
    new_dummy->bytecode_offset = source->bytecode_offset;

    Py_XDECREF(new_dummy->traceback_str);
    new_dummy->traceback_str = source->traceback_str;
    Py_INCREF(new_dummy->traceback_str);

    /* Copy operations history */
    if (copy_operations(new_dummy, source) < 0) {
        Py_DECREF(new_dummy);
        return NULL;
    }

    /* Add current operation */
    add_operation(new_dummy, "PROPAGATION", operation_name, NULL);

    /* Recursive provenance: the single dummy operand. */
    PyObject *prov_operands[1] = {operand};
    dummy_set_provenance(new_dummy, operation_name, prov_operands, 1);

    return (PyObject *)new_dummy;
}

PyObject *
_PyDummy_PropagateCall(PyObject *callable, PyObject **args, Py_ssize_t nargs, PyObject *kwnames)
{
    /* Check if callable is dummy */
    if (IS_DUMMY(callable)) {
        return _PyDummy_PropagateUnaryOp(callable, "call");
    }

    /* Check if any argument is dummy */
    PyDummyObject *source = NULL;
    for (Py_ssize_t i = 0; i < nargs; i++) {
        if (IS_DUMMY(args[i])) {
            source = (PyDummyObject *)args[i];
            break;
        }
    }

    if (source == NULL) {
        PyErr_SetString(PyExc_TypeError, "Either callable or an argument must be a dummy");
        return NULL;
    }

    /* Create new dummy */
    PyDummyObject *new_dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (new_dummy == NULL) {
        return NULL;
    }

    /* Copy error information from source */
    Py_XDECREF(new_dummy->error_type);
    new_dummy->error_type = source->error_type;
    Py_INCREF(new_dummy->error_type);

    Py_XDECREF(new_dummy->error_message);
    new_dummy->error_message = source->error_message;
    Py_INCREF(new_dummy->error_message);

    Py_XDECREF(new_dummy->filename);
    new_dummy->filename = source->filename;
    Py_INCREF(new_dummy->filename);

    Py_XDECREF(new_dummy->function_name);
    new_dummy->function_name = source->function_name;
    Py_INCREF(new_dummy->function_name);

    new_dummy->lineno = source->lineno;
    new_dummy->bytecode_offset = source->bytecode_offset;

    Py_XDECREF(new_dummy->traceback_str);
    new_dummy->traceback_str = source->traceback_str;
    Py_INCREF(new_dummy->traceback_str);

    /* Copy operations history */
    if (copy_operations(new_dummy, source) < 0) {
        Py_DECREF(new_dummy);
        return NULL;
    }

    /* Add current operation */
    PyObject *callable_repr = PyObject_Repr(callable);
    if (callable_repr != NULL) {
        add_operation(new_dummy, "CALL", "function_call", callable_repr);
        Py_DECREF(callable_repr);
    } else {
        PyErr_Clear();
        add_operation(new_dummy, "CALL", "function_call", NULL);
    }

    /* Recursive provenance: the dummy argument that forced the call. */
    PyObject *prov_operands[1] = {(PyObject *)source};
    dummy_set_provenance(new_dummy, "call", prov_operands, 1);

    return (PyObject *)new_dummy;
}

PyObject *
_PyDummy_PropagateGetAttr(PyObject *obj, PyObject *name)
{
    if (!IS_DUMMY(obj)) {
        PyErr_SetString(PyExc_TypeError, "Object must be a dummy");
        return NULL;
    }

    PyDummyObject *source = (PyDummyObject *)obj;
    PyDummyObject *new_dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (new_dummy == NULL) {
        return NULL;
    }

    /* Copy error information from source */
    Py_XDECREF(new_dummy->error_type);
    new_dummy->error_type = source->error_type;
    Py_INCREF(new_dummy->error_type);

    Py_XDECREF(new_dummy->error_message);
    new_dummy->error_message = source->error_message;
    Py_INCREF(new_dummy->error_message);

    Py_XDECREF(new_dummy->filename);
    new_dummy->filename = source->filename;
    Py_INCREF(new_dummy->filename);

    Py_XDECREF(new_dummy->function_name);
    new_dummy->function_name = source->function_name;
    Py_INCREF(new_dummy->function_name);

    new_dummy->lineno = source->lineno;
    new_dummy->bytecode_offset = source->bytecode_offset;

    Py_XDECREF(new_dummy->traceback_str);
    new_dummy->traceback_str = source->traceback_str;
    Py_INCREF(new_dummy->traceback_str);

    /* Copy operations history */
    if (copy_operations(new_dummy, source) < 0) {
        Py_DECREF(new_dummy);
        return NULL;
    }

    /* Add current operation */
    add_operation(new_dummy, "GETATTR", "attribute_access", name);

    /* Recursive provenance: the dummy and the attribute name. */
    PyObject *prov_operands[2] = {obj, name};
    dummy_set_provenance(new_dummy, "getattr", prov_operands, 2);

    return (PyObject *)new_dummy;
}

PyObject *
_PyDummy_PropagateGetItem(PyObject *obj, PyObject *key)
{
    if (!IS_DUMMY(obj)) {
        PyErr_SetString(PyExc_TypeError, "Object must be a dummy");
        return NULL;
    }

    PyDummyObject *source = (PyDummyObject *)obj;
    PyDummyObject *new_dummy = dummy_new(&PyDummy_Type, NULL, NULL);
    if (new_dummy == NULL) {
        return NULL;
    }

    /* Copy error information from source */
    Py_XDECREF(new_dummy->error_type);
    new_dummy->error_type = source->error_type;
    Py_INCREF(new_dummy->error_type);

    Py_XDECREF(new_dummy->error_message);
    new_dummy->error_message = source->error_message;
    Py_INCREF(new_dummy->error_message);

    Py_XDECREF(new_dummy->filename);
    new_dummy->filename = source->filename;
    Py_INCREF(new_dummy->filename);

    Py_XDECREF(new_dummy->function_name);
    new_dummy->function_name = source->function_name;
    Py_INCREF(new_dummy->function_name);

    new_dummy->lineno = source->lineno;
    new_dummy->bytecode_offset = source->bytecode_offset;

    Py_XDECREF(new_dummy->traceback_str);
    new_dummy->traceback_str = source->traceback_str;
    Py_INCREF(new_dummy->traceback_str);

    /* Copy operations history */
    if (copy_operations(new_dummy, source) < 0) {
        Py_DECREF(new_dummy);
        return NULL;
    }

    /* Add current operation */
    PyObject *key_repr = PyObject_Repr(key);
    if (key_repr != NULL) {
        add_operation(new_dummy, "GETITEM", "subscript_access", key_repr);
        Py_DECREF(key_repr);
    } else {
        PyErr_Clear();
        add_operation(new_dummy, "GETITEM", "subscript_access", NULL);
    }

    /* Recursive provenance: the dummy and the subscript key. */
    PyObject *prov_operands[2] = {obj, key};
    dummy_set_provenance(new_dummy, "subscript", prov_operands, 2);

    return (PyObject *)new_dummy;
}

/* ==================== Number Protocol ==================== */

static PyObject *
dummy_add(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "add");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_subtract(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "subtract");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_multiply(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "multiply");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_remainder(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "remainder");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_divmod(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "divmod");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_power(PyObject *left, PyObject *right, PyObject *mod)
{
    if (IS_DUMMY(left) || IS_DUMMY(right) || (mod != Py_None && IS_DUMMY(mod))) {
        return _PyDummy_PropagateOperation(left, right, "power");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_negative(PyObject *self)
{
    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateUnaryOp(self, "negative");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_positive(PyObject *self)
{
    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateUnaryOp(self, "positive");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_absolute(PyObject *self)
{
    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateUnaryOp(self, "absolute");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static int
dummy_bool(PyObject *self)
{
    /* Dummies are always truthy to avoid breaking control flow */
    return 1;
}

static PyObject *
dummy_int(PyObject *self)
{
    return PyLong_FromLong(0);
}

static PyObject *
dummy_float(PyObject *self)
{
    return PyFloat_FromDouble(0.0);
}

static PyObject *
dummy_index(PyObject *self)
{
    /* __index__ must return a real int, so a dummy stands in as 0 wherever an
     * integer index/size is required -- list[dummy], dummy-bounded slices,
     * range(dummy), bin/hex/oct, "%d" % dummy -- instead of raising "object
     * cannot be interpreted as an integer". Mirrors dummy_int / dummy_float. */
    return PyLong_FromLong(0);
}

static PyObject *
dummy_call(PyObject *self, PyObject *args, PyObject *kwargs)
{
    /* Calling a DummyObject returns itself */
    Py_INCREF(self);
    return self;
}

static PyObject *
dummy_invert(PyObject *self)
{
    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateUnaryOp(self, "invert");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_lshift(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "lshift");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_rshift(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "rshift");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_and(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "and");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_xor(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "xor");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_or(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "or");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_floor_divide(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "floor_divide");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_true_divide(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "true_divide");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_matrix_multiply(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "matrix_multiply");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyNumberMethods dummy_as_number = {
    dummy_add,                  /* nb_add */
    dummy_subtract,             /* nb_subtract */
    dummy_multiply,             /* nb_multiply */
    dummy_remainder,            /* nb_remainder */
    dummy_divmod,               /* nb_divmod */
    dummy_power,                /* nb_power */
    dummy_negative,             /* nb_negative */
    dummy_positive,             /* nb_positive */
    dummy_absolute,             /* nb_absolute */
    dummy_bool,                 /* nb_bool */
    dummy_invert,               /* nb_invert */
    dummy_lshift,               /* nb_lshift */
    dummy_rshift,               /* nb_rshift */
    dummy_and,                  /* nb_and */
    dummy_xor,                  /* nb_xor */
    dummy_or,                   /* nb_or */
    dummy_int,                  /* nb_int */
    0,                          /* nb_reserved */
    dummy_float,                /* nb_float */
    0,                          /* nb_inplace_add */
    0,                          /* nb_inplace_subtract */
    0,                          /* nb_inplace_multiply */
    0,                          /* nb_inplace_remainder */
    0,                          /* nb_inplace_power */
    0,                          /* nb_inplace_lshift */
    0,                          /* nb_inplace_rshift */
    0,                          /* nb_inplace_and */
    0,                          /* nb_inplace_xor */
    0,                          /* nb_inplace_or */
    dummy_floor_divide,         /* nb_floor_divide */
    dummy_true_divide,          /* nb_true_divide */
    0,                          /* nb_inplace_floor_divide */
    0,                          /* nb_inplace_true_divide */
    dummy_index,                /* nb_index */
    dummy_matrix_multiply,      /* nb_matrix_multiply */
    0,                          /* nb_inplace_matrix_multiply */
};

/* ==================== Sequence Protocol ==================== */

static Py_ssize_t
dummy_length(PyObject *self)
{
    /* Return 0 to avoid breaking iteration */
    return 0;
}

static PyObject *
dummy_item(PyObject *self, Py_ssize_t i)
{
    if (IS_DUMMY(self)) {
        PyObject *idx = PyLong_FromSsize_t(i);
        if (idx == NULL) {
            return NULL;
        }
        PyObject *result = _PyDummy_PropagateGetItem(self, idx);
        Py_DECREF(idx);
        return result;
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_concat(PyObject *left, PyObject *right)
{
    if (IS_DUMMY(left) || IS_DUMMY(right)) {
        return _PyDummy_PropagateOperation(left, right, "concat");
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyObject *
dummy_repeat(PyObject *self, Py_ssize_t n)
{
    if (IS_DUMMY(self)) {
        PyObject *count = PyLong_FromSsize_t(n);
        if (count == NULL) {
            return NULL;
        }
        PyObject *result = _PyDummy_PropagateOperation(self, count, "repeat");
        Py_DECREF(count);
        return result;
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static int
dummy_contains(PyObject *self, PyObject *value)
{
    /* Return 0 (not contained) to avoid breaking membership tests */
    return 0;
}

static PySequenceMethods dummy_as_sequence = {
    dummy_length,               /* sq_length */
    dummy_concat,               /* sq_concat */
    dummy_repeat,               /* sq_repeat */
    dummy_item,                 /* sq_item */
    0,                          /* was_sq_slice */
    0,                          /* sq_ass_item */
    0,                          /* was_sq_ass_slice */
    dummy_contains,             /* sq_contains */
    0,                          /* sq_inplace_concat */
    0,                          /* sq_inplace_repeat */
};

/* ==================== Mapping Protocol ==================== */

static PyObject *
dummy_subscript(PyObject *self, PyObject *key)
{
    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateGetItem(self, key);
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static PyMappingMethods dummy_as_mapping = {
    dummy_length,               /* mp_length */
    dummy_subscript,            /* mp_subscript */
    0,                          /* mp_ass_subscript */
};

/* ==================== Rich Comparison ==================== */

static PyObject *
dummy_richcompare(PyObject *self, PyObject *other, int op)
{
    if (IS_DUMMY(self) || IS_DUMMY(other)) {
        const char *op_name;
        switch (op) {
            case Py_LT: op_name = "less_than"; break;
            case Py_LE: op_name = "less_equal"; break;
            case Py_EQ: op_name = "equal"; break;
            case Py_NE: op_name = "not_equal"; break;
            case Py_GT: op_name = "greater_than"; break;
            case Py_GE: op_name = "greater_equal"; break;
            default: op_name = "compare"; break;
        }

        if (IS_DUMMY(self)) {
            return _PyDummy_PropagateOperation(self, other, op_name);
        } else {
            return _PyDummy_PropagateOperation(other, self, op_name);
        }
    }
    Py_RETURN_NOTIMPLEMENTED;
}

static Py_hash_t
dummy_hash(PyObject *self)
{
    /* Without a tp_hash, a type that defines tp_richcompare is unhashable, so a
     * dummy could not be a dict key or set member ("unhashable type:
     * 'DummyObject'"). Every dummy hashes to the same constant: dummy_richcompare
     * propagates an always-truthy dummy for ==, so any two dummies compare
     * "equal" and therefore MUST hash equal to preserve the hash/eq invariant.
     * The consequence is that all dummies collapse to a single key -- the
     * acceptable degenerate behavior for crash-recovery placeholders. */
    return 1;  /* any fixed value != -1 (which is reserved for errors) */
}

/* ==================== Attribute Access ==================== */

static PyObject *
dummy_getattro(PyObject *self, PyObject *name)
{
    /* First try to get from the type (for properties like 'trace', 'error_reason', etc.) */
    PyObject *attr = PyObject_GenericGetAttr(self, name);
    if (attr != NULL) {
        return attr;
    }

    /* If attribute not found, clear error and propagate the dummy */
    PyErr_Clear();

    if (IS_DUMMY(self)) {
        return _PyDummy_PropagateGetAttr(self, name);
    }

    PyErr_SetObject(PyExc_AttributeError, name);
    return NULL;
}

/* ==================== Property Getters ==================== */

static PyObject *
dummy_get_trace(PyDummyObject *self, void *closure)
{
    PyObject *parts = PyList_New(0);
    if (parts == NULL) {
        return NULL;
    }

    PyObject *base = dummy_basename(self->filename);

    /* Add header */
    PyObject *header = PyUnicode_FromFormat(
        "DummyObject Trace\n"
        "Origin:\n"
        "  error: %S\n"
        "  location: %S:%d in %S (bytecode offset %d)\n",
        self->error_message,
        base,
        self->lineno,
        self->function_name,
        self->bytecode_offset
    );
    Py_XDECREF(base);
    if (header != NULL) {
        PyList_Append(parts, header);
        Py_DECREF(header);
    }

    /* Add operations history */
    if (self->operations != NULL && PyList_Check(self->operations)) {
        PyObject *ops_header = PyUnicode_FromString("Lineage:\n");
        if (ops_header != NULL) {
            PyList_Append(parts, ops_header);
            Py_DECREF(ops_header);
        }

        Py_ssize_t n = PyList_GET_SIZE(self->operations);
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *op = PyList_GET_ITEM(self->operations, i);
            PyObject *op_line = dummy_operation_line(op, i);
            if (op_line != NULL) {
                PyList_Append(parts, op_line);
                Py_DECREF(op_line);
            } else {
                PyErr_Clear();
            }
        }
    }

    /* Symbolic provenance (recursive mode only): the nested expression form. */
    if (dummy_provenance_recursive()
        && self->original_operands != NULL
        && PyTuple_Check(self->original_operands)) {
        PyObject *expr = dummy_render_provenance((PyObject *)self, 0);
        if (expr != NULL) {
            PyObject *sec = PyUnicode_FromFormat("Symbolic provenance:\n  %S\n", expr);
            if (sec != NULL) {
                PyList_Append(parts, sec);
                Py_DECREF(sec);
            }
            Py_DECREF(expr);
        } else {
            PyErr_Clear();
        }
    }

    /* Join all parts */
    PyObject *empty = PyUnicode_FromString("");
    PyObject *result = PyUnicode_Join(empty, parts);
    Py_DECREF(empty);
    Py_DECREF(parts);

    return result;
}

static PyObject *
dummy_get_error_reason(PyDummyObject *self, void *closure)
{
    Py_INCREF(self->error_message);
    return self->error_message;
}

static PyObject *
dummy_get_location(PyDummyObject *self, void *closure)
{
    PyObject *location = PyDict_New();
    if (location == NULL) {
        return NULL;
    }

    PyDict_SetItemString(location, "filename", self->filename);
    PyDict_SetItemString(location, "function", self->function_name);

    PyObject *lineno = PyLong_FromLong(self->lineno);
    if (lineno != NULL) {
        PyDict_SetItemString(location, "lineno", lineno);
        Py_DECREF(lineno);
    }

    PyObject *offset = PyLong_FromLong(self->bytecode_offset);
    if (offset != NULL) {
        PyDict_SetItemString(location, "bytecode_offset", offset);
        Py_DECREF(offset);
    }

    return location;
}

static PyObject *
dummy_get_operations_history(PyDummyObject *self, void *closure)
{
    Py_INCREF(self->operations);
    return self->operations;
}

static PyObject *
dummy_get_provenance(PyDummyObject *self, void *closure)
{
    /* Renders the nested symbolic expression in recursive mode; returns the
     * leaf "dummy" in flat mode (no operand structure is retained there). */
    return dummy_render_provenance((PyObject *)self, 0);
}

static PyObject *
dummy_iternext(PyDummyObject *self)
{
    PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}

static PyGetSetDef dummy_getsetters[] = {
    {"trace", (getter)dummy_get_trace, NULL,
     "Full trace with error information and operations history", NULL},
    {"error_reason", (getter)dummy_get_error_reason, NULL,
     "Original error message", NULL},
    {"location", (getter)dummy_get_location, NULL,
     "Dictionary with file, line, function, and bytecode offset", NULL},
    {"operations_history", (getter)dummy_get_operations_history, NULL,
     "List of all operations applied to this dummy", NULL},
    {"provenance", (getter)dummy_get_provenance, NULL,
     "Symbolic provenance expression, e.g. SUBSCRIPT(ADD(dummy, 1), 2) "
     "(PYFEX_PROVENANCE_MODE=recursive; 'dummy' in flat mode)", NULL},
    {NULL}  /* Sentinel */
};

/* ==================== Type Definition ==================== */

PyTypeObject PyDummy_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "DummyObject",                      /* tp_name */
    sizeof(PyDummyObject),              /* tp_basicsize */
    0,                                  /* tp_itemsize */
    (destructor)dummy_dealloc,          /* tp_dealloc */
    0,                                  /* tp_vectorcall_offset */
    0,                                  /* tp_getattr */
    0,                                  /* tp_setattr */
    0,                                  /* tp_as_async */
    (reprfunc)dummy_repr,               /* tp_repr */
    &dummy_as_number,                   /* tp_as_number */
    &dummy_as_sequence,                 /* tp_as_sequence */
    &dummy_as_mapping,                  /* tp_as_mapping */
    dummy_hash,                         /* tp_hash */
    dummy_call,                         /* tp_call */
    (reprfunc)dummy_str,                /* tp_str */
    dummy_getattro,                     /* tp_getattro */
    0,                                  /* tp_setattro */
    0,                                  /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
    "Dummy object for crash recovery",  /* tp_doc */
    (traverseproc)dummy_traverse,       /* tp_traverse */
    (inquiry)dummy_clear,               /* tp_clear */
    dummy_richcompare,                  /* tp_richcompare */
    0,                                  /* tp_weaklistoffset */
    PyObject_SelfIter,                  /* tp_iter */
    (iternextfunc)dummy_iternext,       /* tp_iternext */
    0,                                  /* tp_methods */
    0,                                  /* tp_members */
    dummy_getsetters,                   /* tp_getset */
    0,                                  /* tp_base */
    0,                                  /* tp_dict */
    0,                                  /* tp_descr_get */
    0,                                  /* tp_descr_set */
    0,                                  /* tp_dictoffset */
    0,                                  /* tp_init */
    0,                                  /* tp_alloc */
    (newfunc)dummy_new,                 /* tp_new */
};
