/* Dummy object interface */

#ifndef Py_DUMMYOBJECT_H
#define Py_DUMMYOBJECT_H
#ifdef __cplusplus
extern "C" {
#endif

/* PyDummyObject
 *
 * Represents a "dummy object" created when an operation fails during
 * crash recovery mode. Instead of raising an exception and halting,
 * the interpreter creates a dummy object that records what went wrong
 * and allows execution to continue.
 *
 * Dummy objects propagate through subsequent operations: any operation
 * that receives a dummy operand returns a new dummy object with the
 * operation recorded in its trace.
 */

typedef struct {
    PyObject_HEAD
    PyObject *error_type;        /* Exception type (TypeError, ValueError, etc.) */
    PyObject *error_message;     /* Error message string */
    PyObject *filename;          /* Source file where error occurred */
    PyObject *function_name;     /* Function name where error occurred */
    int lineno;                  /* Line number */
    int bytecode_offset;         /* Bytecode offset (f_lasti value) */
    PyObject *operations;        /* List of dict entries for each operation */
    PyObject *traceback_str;     /* Full traceback string (optional) */
    PyObject *original_operands; /* Tuple of original operands (optional) */
} PyDummyObject;

PyAPI_DATA(PyTypeObject) PyDummy_Type;

#define PyDummy_Check(op) Py_IS_TYPE(op, &PyDummy_Type)
#define PyDummy_CheckExact(op) (Py_TYPE(op) == &PyDummy_Type)

/* Create a new dummy object from the current exception state.
 * This should be called when an exception has been raised but we want
 * to continue execution instead of propagating the exception.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_New(PyThreadState *tstate, PyFrameObject *frame);

/* Create a new dummy object from bytecode operation.
 * This is a convenience wrapper around _PyDummy_New that includes
 * bytecode-specific information.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_NewFromBytecode(
    PyThreadState *tstate,
    PyFrameObject *frame,
    const char *opcode_name,
    int opcode,
    int oparg
);

/* Create a new dummy object representing an operation on dummy operands.
 * This propagates crash information through subsequent operations.
 *
 * At least one of left or right must be a dummy object.
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_PropagateOperation(
    PyObject *left,
    PyObject *right,
    const char *operation_name
);

/* Create a new dummy object representing a unary operation on a dummy operand.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_PropagateUnaryOp(
    PyObject *operand,
    const char *operation_name
);

/* Create a new dummy object representing a function call with dummy operands.
 * Either the callable or one of the arguments must be a dummy object.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_PropagateCall(
    PyObject *callable,
    PyObject **args,
    Py_ssize_t nargs,
    PyObject *kwnames
);

/* Create a new dummy object representing an attribute access on a dummy object.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_PropagateGetAttr(
    PyObject *obj,
    PyObject *name
);

/* Create a new dummy object representing a subscript operation on a dummy object.
 *
 * Returns a new reference to a PyDummyObject, or NULL on error.
 */
PyAPI_FUNC(PyObject *) _PyDummy_PropagateGetItem(
    PyObject *obj,
    PyObject *key
);

#ifdef __cplusplus
}
#endif
#endif /* !Py_DUMMYOBJECT_H */
