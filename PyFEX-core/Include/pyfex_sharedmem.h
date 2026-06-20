/* PyFEX Shared Memory Infrastructure
 *
 * Provides process-shared memory for inter-process communication
 * during forced execution (fork-based path exploration).
 * Also contains pickle helpers and builtin function declarations.
 */

#ifndef Py_PYFEX_SHAREDMEM_H
#define Py_PYFEX_SHAREDMEM_H

#include "Python.h"
#include "frameobject.h"
#include <pthread.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SHARED_MEM_SIZE (10 * 1024 * 1024) /* 10MB */

typedef struct {
    pthread_mutex_t lock;
    size_t offset;
    char data[]; /* Flexible array member */
} SharedMem;

/* Shared memory global -- defined in pyfex_sharedmem.c */
extern SharedMem *_Py_ForceExec_SharedMem;
extern int _Py_ForceExec_SharedMemIOInProgress;

/* Initialize shared memory region (idempotent). Returns 1 on success, 0 on failure. */
int _Py_ForceExec_InitSharedMem(void);

/* Pickle/unpickle helpers */
PyObject *_Py_PickleObject(PyObject *obj);
PyObject *_Py_UnpickleObject(const char *data, Py_ssize_t size);

/* Shared memory entry operations */
int _Py_ForceExec_SharedMem_HasEntry(const char *target_name, const char *target_scope);
PyObject *_Py_ForceExec_SharedMem_Recover(const char *target_name, const char *target_scope);
PyObject *_Py_ForceExec_SharedMem_RecoverPeerSnapshot(PyFrameObject *f, PyObject *var_name);
int _Py_ForceExec_SharedMem_PublishLiveValue(PyFrameObject *f, PyObject *var_name, PyObject *value);
int _Py_ForceExec_SharedMem_PublishLiveDelete(PyFrameObject *f, PyObject *var_name);
PyObject *_Py_ForceExec_SharedMem_RecoverLivePeerValue(PyFrameObject *f, PyObject *var_name);
int _Py_ForceExec_SharedMem_RemoveEntry(const char *target_name, const char *target_scope);
int _Py_ForceExec_SharedMem_RemoveLiveEntriesByPid(pid_t pid);

/* Builtin functions exposed to Python (registered in bltinmodule.c) */
PyObject *builtin_get_scope(PyObject *self, PyObject *args);
PyObject *builtin_share_object(PyObject *self, PyObject *args);
PyObject *builtin_recover_object(PyObject *self, PyObject *args);
PyObject *builtin_has_object(PyObject *self, PyObject *args);
PyObject *builtin_recover_branch_states(PyObject *self, PyObject *args);
PyObject *builtin_get_last_branch_id(PyObject *self, PyObject *args);

#ifdef __cplusplus
}
#endif
#endif /* !Py_PYFEX_SHAREDMEM_H */
