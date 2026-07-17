# PyFEX-core-3.10

Modified CPython 3.10 interpreter for uncovering evasive Python-based threats through forced execution, crash recovery, branch merging, state sharing, and dormant function analysis. This is the **reference implementation**.

## Build

```bash
cd PyFEX-core-3.10/
./configure
make -j$(nproc)
```

This produces `./python` in the current directory.

## Features Overview

All features are **disabled by default** (zero overhead when off). Enable via environment variables.

| Feature | Environment Variable | Purpose |
|---------|---------------------|---------|
| Crash Recovery | `CRASH_RECOVERY_ENABLE=1` | Intercept exceptions, substitute DummyObjects to continue execution |
| Forced Execution | `FORCE_EXEC_ENABLE=1` | Fork at control flow points to explore alternative paths |
| Branch Merging | `FORCE_EXEC_MERGE_ENABLE=1` | Save branch snapshots at reconvergence points and merge concrete state |
| State Sharing | `FORCE_EXEC_SHARED_OBJECT_ENABLE=1` | Cross-process shared memory for branch snapshots and explicit object exchange |
| Dormant Function Analysis | `DORMANT_FUNC_LOG_FILE=/path` | Log defined vs. called functions |
| Trace Reporter | `PYFEX_TRACE_LOG_FILE=/path` | Emit JSONL function-call and argument traces |
| Runtime Debug Log | `PYFEX_RUNTIME_LOG_FILE=/path` | Collect FE/CR/DFA/runtime debug events in one file |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CRASH_RECOVERY_ENABLE` | off | Enable crash recovery with DummyObjects |
| `CRASH_RECOVERY_GLOBAL_LIMIT` | 1000 | Cap total crash recoveries |
| `CRASH_RECOVERY_LOCATION_LIMIT` | 50 | Cap recoveries per bytecode location |
| `CRASH_RECOVERY_LOG_FILE` | none | Crash recovery debug log path |
| `FORCE_EXEC_ENABLE` | off | Enable forced execution (forking at conditionals) |
| `FORCE_EXEC_MERGE_ENABLE` | off | Enable branch merging at reconvergence points |
| `FORCE_EXEC_GLOBAL_LIMIT` | 100 | Cap total number of forks |
| `FORCE_EXEC_LOCAL_LIMIT` | 10 | Cap forks per bytecode location |
| `FORCE_EXEC_LOG_FILE` | `force_exec.log` | Forced execution debug log path |
| `FORCE_EXEC_SHARED_OBJECT_ENABLE` | off | Enable shared object builtins |
| `FORCE_EXEC_MERGE_SCOPE_FILE` | unset | Restrict merge handling to specific script basenames or paths |
| `FORCE_EXEC_MERGE_SCOPE_FUNC` | unset | Restrict merge handling to specific function names |
| `FORCE_EXEC_RETAIN_SHARED_STATE` | off | Keep absorbed branch snapshots/live peer-state entries instead of reclaiming them after merge |
| `CRASH_RECOVERY_PEER_QUERY` | on | Allow crash recovery to query merged state and peer branch snapshots first |
| `DORMANT_FUNC_LOG_FILE` | none | DFA log output path (enables DFA when set) |
| `PYFEX_TRACE_LOG_FILE` | none | JSONL behavior trace path for in-scope function calls, arguments, and dummy argument provenance |
| `PYFEX_RUNTIME_LOG_FILE` | none | Unified runtime debug log path for forced-exec, crash-recovery, DFA, and peer-state events |

## Running Tests

```bash
# Forced execution
FORCE_EXEC_ENABLE=1 FORCE_EXEC_GLOBAL_LIMIT=20 ./python tests/test_force_exec.py

# Branch merging and snapshot recovery
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_SHARED_OBJECT_ENABLE=1 \
  ./python tests/test_branch_merge.py
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_SHARED_OBJECT_ENABLE=1 \
  ./python tests/test_branch_state_capture_regression.py
FORCE_EXEC_ENABLE=1 FORCE_EXEC_MERGE_ENABLE=1 FORCE_EXEC_SHARED_OBJECT_ENABLE=1 \
  ./python tests/test_non_picklable_snapshot_regression.py

# Explicit shared-memory API
FORCE_EXEC_SHARED_OBJECT_ENABLE=1 ./python tests/test_no_pickle.py

# Dormant Function Analysis
DORMANT_FUNC_LOG_FILE=/tmp/dfa.log ./python ../tests/test_dormant_function_analysis.py

# Focused bytecode/feature unit tests
./python ../unit-test/basic-general/disabled_by_default.py
./python ../unit-test/live-peer-state/store_fast_load_fast_recovery.py
./python ../unit-test/crash-recovery/load_fast_dummy_recovery.py
```

The two regression tests added for the merge fix set cover the behavior that is expected to remain stable:

- `tests/test_branch_state_capture_regression.py` verifies that merge-enabled execution produces recoverable parent/child branch snapshots with metadata such as `pid`, `fork_offset`, `merge_offset`, and `scope`.
- `tests/test_non_picklable_snapshot_regression.py` verifies that branch snapshots keep picklable locals while filtering non-picklable ones and recording `skipped_locals`.

The standalone `../unit-test/` tree complements `tests/` with one-file-per-behavior checks. It now covers:

- basic general behavior such as default-off execution and merge scope control,
- forced-execution hooks by bytecode family,
- crash-recovery hooks across variable loads, arithmetic, calls, imports, formatting, and suppression paths,
- `DummyObject` propagation and provenance,
- merge snapshot recovery,
- live peer-state publication and downstream retry paths,
- explicit shared-object builtins,
- and DFA logging.

---

## Instrumented Bytecodes

### Forced Execution

The parent process takes the original path; a forked child explores the alternative.

| Bytecode | Python Construct | Behavior |
|----------|-----------------|----------|
| `POP_JUMP_IF_FALSE` | `if`/`elif`/`while` conditionals | Parent takes true branch, child takes false branch |
| `POP_JUMP_IF_TRUE` | `if not`, short-circuit `or` | Parent takes false branch, child takes true branch |
| `JUMP_IF_FALSE_OR_POP` | Short-circuit `and` | Parent continues, child takes the jump path |
| `JUMP_IF_TRUE_OR_POP` | Short-circuit `or` | Parent continues, child takes the jump path |
| `JUMP_IF_NOT_EXC_MATCH` | `except ExcType:` matching | Parent matches, child takes the non-match path |
| `FOR_ITER` | `for`/`while` loop iteration | Parent continues loop, child forces premature exit |
| `SETUP_FINALLY` | `try`/`except`/`finally` blocks | Parent enters try body, child jumps to handler with synthetic `RuntimeError` |
| `RAISE_VARARGS` | `raise` statements | Parent raises normally, child suppresses the raise |

### Crash Recovery

When an operation fails, a DummyObject is substituted and execution continues. Recovery first tries concrete values from merged in-process state, then compatible peer branch snapshots in shared memory, and finally falls back to DummyObject creation.

Current concrete recovery order in the artifact is:

1. merged in-process state,
2. live peer-state from still-running sibling paths,
3. peer branch snapshots,
4. manual shared objects,
5. `DummyObject` fallback.

**Variable/Attribute Access:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `LOAD_FAST` | Local variable access | Peer recovery, then DummyObject on unbound local |
| `LOAD_NAME` | Name lookup (locals/globals/builtins) | Peer recovery, then DummyObject on `NameError` |
| `LOAD_GLOBAL` | Global/builtin lookup | Peer recovery, then DummyObject on `NameError` |
| `LOAD_ATTR` | `obj.attr` | DummyObject on `AttributeError` |
| `LOAD_METHOD` | `obj.method` | DummyObject when method not found |
| `LOAD_DEREF` | Closure variable access | Peer recovery, then DummyObject on unbound cell |
| `LOAD_CLASSDEREF` | Class closure variable | Peer recovery, then DummyObject on unbound |

Live peer-state publication currently feeds these recovery paths from serializable sibling values published on:

- `STORE_FAST`
- `STORE_NAME`
- `STORE_GLOBAL`
- `STORE_DEREF`
- `DELETE_FAST`
- `DELETE_NAME`
- `DELETE_GLOBAL`
- `DELETE_DEREF`

The same peer publication layer is also used for downstream retries on `LOAD_ATTR` and `LOAD_METHOD` when the failing operand can be mapped back to a variable name.

**Binary Arithmetic:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `BINARY_ADD` | `a + b` | DummyObject on `TypeError` |
| `BINARY_SUBTRACT` | `a - b` | DummyObject on `TypeError` |
| `BINARY_MULTIPLY` | `a * b` | DummyObject on `TypeError` |
| `BINARY_MATRIX_MULTIPLY` | `a @ b` | DummyObject on `TypeError` |
| `BINARY_TRUE_DIVIDE` | `a / b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `BINARY_FLOOR_DIVIDE` | `a // b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `BINARY_MODULO` | `a % b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `BINARY_POWER` | `a ** b` | DummyObject on `TypeError` |
| `BINARY_SUBSCR` | `a[b]` | DummyObject on `IndexError`/`KeyError`/`TypeError` |
| `BINARY_LSHIFT` | `a << b` | DummyObject on `TypeError` |
| `BINARY_RSHIFT` | `a >> b` | DummyObject on `TypeError` |
| `BINARY_AND` | `a & b` | DummyObject on `TypeError` |
| `BINARY_XOR` | `a ^ b` | DummyObject on `TypeError` |
| `BINARY_OR` | `a \| b` | DummyObject on `TypeError` |

**Inplace Operations:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `INPLACE_ADD` | `a += b` | DummyObject on `TypeError` |
| `INPLACE_SUBTRACT` | `a -= b` | DummyObject on `TypeError` |
| `INPLACE_MULTIPLY` | `a *= b` | DummyObject on `TypeError` |
| `INPLACE_MATRIX_MULTIPLY` | `a @= b` | DummyObject on `TypeError` |
| `INPLACE_TRUE_DIVIDE` | `a /= b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `INPLACE_FLOOR_DIVIDE` | `a //= b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `INPLACE_MODULO` | `a %= b` | DummyObject on `ZeroDivisionError`/`TypeError` |
| `INPLACE_POWER` | `a **= b` | DummyObject on `TypeError` |
| `INPLACE_LSHIFT` | `a <<= b` | DummyObject on `TypeError` |
| `INPLACE_RSHIFT` | `a >>= b` | DummyObject on `TypeError` |
| `INPLACE_AND` | `a &= b` | DummyObject on `TypeError` |
| `INPLACE_XOR` | `a ^= b` | DummyObject on `TypeError` |
| `INPLACE_OR` | `a \|= b` | DummyObject on `TypeError` |

**Unary Operations:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `UNARY_POSITIVE` | `+a` | DummyObject on `TypeError` |
| `UNARY_NEGATIVE` | `-a` | DummyObject on `TypeError` |
| `UNARY_INVERT` | `~a` | DummyObject on `TypeError` |
| `UNARY_NOT` | `not a` | Default `True` on `TypeError` |

**Comparison/Containment:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `COMPARE_OP` | `==`, `<`, `>`, etc. | DummyObject on comparison failure |
| `CONTAINS_OP` | `x in y` / `x not in y` | Default result on `TypeError` |

**Sequence/Iteration:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `UNPACK_SEQUENCE` | `a, b = iterable` | Pushes N DummyObjects when unpacking fails |
| `UNPACK_EX` | `a, *b = iterable` | Pushes DummyObjects when unpacking fails |
| `GET_ITER` | `iter(obj)` in `for` loops | DummyObject iterator on non-iterable |
| `FOR_ITER` | Loop iteration | DummyObject on non-`StopIteration` error |

**Function Calls:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `CALL_FUNCTION` | `func(args)` | Peer recovery, then DummyObject on call failure |
| `CALL_FUNCTION_KW` | `func(a=1)` | Peer recovery, then DummyObject on call failure |
| `CALL_FUNCTION_EX` | `func(*args, **kwargs)` | Peer recovery, then DummyObject on call failure |
| `CALL_METHOD` | `obj.method(args)` | Peer recovery, then DummyObject on call failure |

**Context Managers:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `SETUP_WITH` | `with obj as x:` | DummyObject for `__enter__`/`__exit__` lookup and call failures |
| `WITH_EXCEPT_START` | Context manager `__exit__()` | DummyObject when `__exit__()` call fails |

**Store/Delete (error suppression — operation skipped):**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `STORE_ATTR` | `obj.attr = val` | Suppress `AttributeError`, skip |
| `DELETE_ATTR` | `del obj.attr` | Suppress `AttributeError`, skip |
| `STORE_SUBSCR` | `obj[key] = val` | Suppress `TypeError`/`KeyError`, skip |
| `DELETE_SUBSCR` | `del obj[key]` | Suppress `TypeError`/`KeyError`, skip |
| `STORE_NAME` | Name binding | Suppress error, skip |
| `DELETE_NAME` | `del name` | Suppress `NameError`, skip |
| `STORE_GLOBAL` | Global assignment | Suppress error, skip |
| `DELETE_GLOBAL` | `del global_name` | Suppress `NameError`, skip |
| `DELETE_FAST` | `del local_var` | Suppress `UnboundLocalError`, skip |
| `DELETE_DEREF` | `del closure_var` | Suppress unbound error, skip |

**Import Operations:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `IMPORT_NAME` | `import module` | DummyObject module on `ImportError` |
| `IMPORT_FROM` | `from module import name` | DummyObject on `ImportError`/`AttributeError` |
| `IMPORT_STAR` | `from module import *` | Suppress error, continue |

**Collection Building (partial results preserved):**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `BUILD_SET` | `{a, b, c}` | Skip unhashable items, keep valid ones |
| `BUILD_MAP` | `{k: v}` | Skip failed entries, keep valid ones |
| `BUILD_CONST_KEY_MAP` | `{const_key: v}` | Skip failed entries, keep valid ones |
| `LIST_EXTEND` | `[*iterable]` | Suppress `TypeError`, continue |
| `DICT_UPDATE` | `{**mapping}` | Suppress `TypeError`, continue |
| `DICT_MERGE` | `f(**mapping)` | Suppress error, continue |
| `SET_UPDATE` | `{*iterable}` | Suppress error, continue |
| `LIST_TO_TUPLE` | Internal list→tuple | DummyObject on failure |

**String Formatting:**

| Bytecode | Python Construct | Recovery Behavior |
|----------|-----------------|-------------------|
| `FORMAT_VALUE` | f-string `f"{expr}"` | `"<DummyObject>"` string on format failure |

### Branch Merging

Branch merge logic is checked at every dispatch via `_Py_ForceExec_HandleMergePoint()`. When the current instruction offset matches a merge point, the child process saves a branch snapshot to shared memory and exits; the parent loads and merges the child's concrete state.

| Bytecode | Merge Behavior |
|----------|---------------|
| `POP_JUMP_IF_FALSE` | Computes post-dominator, sets up merge point; child saves state and exits at merge |
| `POP_JUMP_IF_TRUE` | Same |
| `JUMP_IF_FALSE_OR_POP` | Sets up merge point at post-dominator |
| `JUMP_IF_TRUE_OR_POP` | Sets up merge point at post-dominator |
| `SETUP_FINALLY` | Sets up merge point past exception handler |

Saved branch snapshots include:

- filtered `locals` and `globals`
- `branch_id`
- `is_child`
- `pid`
- `fork_offset`
- `merge_offset`
- `scope`
- `skipped_locals`
- `skipped_globals`

Snapshotting is resilient per item: values are tested for picklability one by one, so one non-picklable local does not discard the whole branch state.

Post-dominator computation uses two-pass bytecode analysis: scanning for `JUMP_FORWARD`/`JUMP_ABSOLUTE` instructions that skip the else block to find where branches reconverge. Conflict resolution prefers concrete values over DummyObjects. Crash recovery can also query these saved peer branch snapshots automatically before falling back to the manual `share_object()` / `recover_object()` API.

After a child snapshot has been absorbed, the parent now reclaims the child's merge-owned shared-memory state by default:

- the absorbed branch snapshot entry
- and the absorbed child's live peer-state entries

Set `FORCE_EXEC_RETAIN_SHARED_STATE=1` to keep those artifacts for debugging or inspection.

### Live Peer-State Sharing

Live peer-state sharing is the pre-merge state-borrowing layer. Instead of waiting until the post-dominator, sibling paths can publish serializable concrete values incrementally and let a crashing peer recover them immediately.

Publication currently happens on:

- `STORE_FAST`
- `STORE_NAME`
- `STORE_GLOBAL`
- `STORE_DEREF`
- `DELETE_FAST`
- `DELETE_NAME`
- `DELETE_GLOBAL`
- `DELETE_DEREF`

Each live publication records:

- variable name
- deletion marker status
- serialized value when present
- publishing PID
- branch id
- whether the publisher was the forced child path
- logical scope

The live path uses `marshal` rather than `pickle`, so it is limited to serializable values but avoids the heavier snapshot path on every update.

Recovery scans newest-to-oldest compatible entries in the same scope, ignores the current PID, respects delete markers, and prefers natural-path values over forced-child values when both exist. This same peer-recovery layer is reused for:

- missing variable loads such as `LOAD_FAST`, `LOAD_NAME`, and `LOAD_GLOBAL`
- downstream retries on `LOAD_ATTR`
- downstream retries on `LOAD_METHOD`

This is separate from manual shared objects and separate from merge snapshots. All three use shared memory, but they serve different phases of execution.

### Dormant Function Analysis

| Location | Hook | What Is Logged |
|----------|------|----------------|
| `MAKE_FUNCTION` opcode | `DEFINED` | User-defined function/method definitions |
| `call_function()` helper | `CALLED` | Function and bound method invocations |
| `do_call_core()` helper | `CALLED` | Function and bound method invocations |

Log format: `DEFINED/CALLED qualname name filename:lineno`

Only user-defined Python functions and methods (including bound methods via `PyMethod`) in the main script scope are logged. Builtins, C extensions, and stdlib are excluded. Dormant functions = DEFINED - CALLED.

### DummyObject Propagation in Function Calls

In `call_function()` and `do_call_core()`, DummyObject calls are scope-aware. Dummy callables still propagate without invocation. Dummy arguments are allowed through whitelisted observability builtins (`print`, `repr`, `str`, `type`, `isinstance`, `id`, `len`, `hash`) and in-scope Python functions, so analysis code can observe and continue through synthetic values. Out-of-scope calls with dummy arguments still short-circuit to avoid cascading failures in stdlib, third-party, or C-extension code.

---

## Changes from Standard CPython 3.10

### New Files

| File | Purpose |
|------|---------|
| `Include/pyfex.h` | Central header: `BranchMergeInfo`/`MergedStateEntry` structs, all PyFEX C API declarations |
| `Include/pyfex_sharedmem.h` | `SharedMem` struct (10MB mmap), pickle helper declarations, builtin function declarations |
| `Include/dummyobject.h` | `PyDummyObject` type definition, `PyDummy_Check` macro, creation/propagation API |
| `Objects/dummyobject.c` | DummyObject implementation with full Python protocol support (number, sequence, mapping, comparison, call, iteration, attribute access, GC) |
| `Python/pyfex_forceexec.c` | Force execution gating (`ShouldFork`), crash recovery gating (`ShouldRecover`), peer recovery (`TryAlternativeValues`, `RecoverFromMergedState`), DFA logging, call logging |
| `Python/pyfex_branchmerge.c` | Branch merge state stack, post-dominator computation via bytecode analysis, state save/load via shared memory, `LoadAndMergeChildState` with conflict resolution and merge cleanup |
| `Python/pyfex_sharedmem.c` | 10MB mmap shared memory with pthread process-shared mutexes, pickle-based branch/manual sharing, marshal-based live peer-state publication/recovery, 6 builtin Python functions |

### Modified Files

| File | Changes |
|------|---------|
| `Python/ceval.c` | Bytecode evaluation loop: forced execution hooks at 8 control flow opcodes, crash recovery at 26+ opcodes, branch merge logic via `_Py_ForceExec_HandleMergePoint()`, live peer-state publication on store/delete opcodes, DFA hooks at `MAKE_FUNCTION` and `call_function`/`do_call_core`, DummyObject propagation in call helpers |
| `Python/bltinmodule.c` | Registers 6 new builtin functions: `share_object`, `recover_object`, `has_object`, `get_scope`, `recover_branch_states`, `get_last_branch_id` |
| `Makefile.pre.in` | Adds `pyfex_forceexec.o`, `pyfex_branchmerge.o`, `pyfex_sharedmem.o` to `PYTHON_OBJS` |

### DummyObject Type

The DummyObject (`Objects/dummyobject.c`) implements these Python protocols so it propagates through operations without crashing:

| Protocol | Behavior |
|----------|----------|
| Number (`nb_add`, `nb_subtract`, ..., `nb_int`, `nb_float`) | Returns new DummyObject recording the operation; `int()` returns 0, `float()` returns 0.0 |
| Sequence (`sq_length`, `sq_item`, `sq_contains`) | Returns DummyObject or safe defaults |
| Mapping (`mp_length`, `mp_subscript`) | Returns DummyObject |
| Comparison (`tp_richcompare`) | Returns DummyObject |
| Call (`tp_call`) | Returns self (DummyObject is callable) |
| Attribute (`tp_getattro`) | Returns new DummyObject for any attribute |
| Repr/Str (`tp_repr`, `tp_str`) | Returns readable origin plus compact lineage summary |
| Iterator (`tp_iter`) | Returns self (iterable, yields nothing) |
| Bool (`nb_bool`) | Always truthy |
| GC (`tp_traverse`, `tp_clear`) | Supports cyclic garbage collection |

Each DummyObject records:
- Original error type and message
- Source file, function name, line number, bytecode offset
- Chain of operations applied to it (trace history)

### Builtin Functions Added

| Function | Signature | Purpose |
|----------|-----------|---------|
| `share_object(name, obj[, scope])` | `(str, object[, str]) -> None` | Pickle and store object in shared memory |
| `recover_object(name[, scope])` | `(str[, str]) -> object` | Unpickle object from shared memory |
| `has_object(name[, scope])` | `(str[, str]) -> bool` | Check if object exists in shared memory |
| `get_scope()` | `() -> str` | Return current `filename:function` scope string |
| `recover_branch_states(branch_id)` | `(int) -> list` | Recover all saved states for a branch ID |
| `get_last_branch_id()` | `() -> int` | Return the most recently assigned branch ID |

### Unit Test Tree

In addition to `tests/`, the repository now includes a focused `../unit-test/` tree for one-file-per-behavior regression coverage.

Current groups include:

- `basic-general`
- `forced-exec`
- `crash-recovery`
- `dummy-object`
- `provenance`
- `branch-merge`
- `live-peer-state`
- `shared-object`
- `dormant-function-analysis`

Run the full unit-test tree with:

```bash
find ../unit-test -type f -name '*.py' ! -name '_helpers.py' | sort | while read -r test_file; do
  ./python "$test_file"
done
```

### Key Implementation Details

**Shared Memory**: 10MB anonymous mmap with `MAP_SHARED | MAP_ANONYMOUS`, protected by a `pthread_mutex` with `PTHREAD_PROCESS_SHARED`. Entries are stored as `[name_len][name][scope_len][scope][data_len][data]` tuples. Data is pickle-serialized.

**Branch Merging**: Post-dominator computation scans the bytecode for forward/absolute jumps to find where if/else branches reconverge. At the merge point, child saves `f_locals` + `f_globals` via pickle into shared memory and exits. Parent `waitpid()`s, then loads child state, merging variable-by-variable (concrete values preferred over DummyObjects).

**Forced Execution Scoping**: Forks only occur in the main script scope (not stdlib/site-packages). Both global and per-location fork counters prevent infinite forking.

**Crash Recovery Scoping**: Recoveries only occur in the main script scope. Both global and per-location recovery counters cap the number of recoveries.
