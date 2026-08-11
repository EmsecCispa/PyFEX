# PyFEX — Forced-Execution CPython for Uncovering Evasive Python Threats

PyFEX is a modified CPython 3.10 interpreter that instruments the bytecode
evaluation loop to expose behavior that evasive, malicious Python packages hide
from ordinary dynamic analysis. It drives execution down branches that would
normally stay dormant, survives deliberately broken or offline code, and
records a precise trace of what the sample tried to do.

This repository is a self-contained artifact: the instrumented interpreter, a
test suite, runnable feature demos, the analysis pipeline, **PyFEXScan** (a
proof-of-concept LLM-backed malware detector built on top of PyFEX — see §6),
and corpora of real malicious samples to analyze.

---

> ## ⚠️ SAFETY: this artifact contains REAL MALWARE
>
> `Dataset/` and `artifact_eval/samples/packages/` are **real
> malicious PyPI packages**. They can steal credentials, contact
> command-and-control servers, and drop or run further payloads.
>
> - **Never** `pip install`, import, or run these packages outside PyFEX.
> - Work only inside a **disposable, network-isolated VM**.
> - The analysis pipeline runs samples under PyFEX with an OS network sandbox
>   enabled by default (not reliable at all), but host isolation remains your responsibility.

---

## Capabilities

1. **Forced Execution** — forks a child process at conditional, loop, and
   exception bytecodes so *both* sides of a branch are explored. Payloads gated
   behind anti-analysis checks, kill dates, or C2 commands are reached anyway.
2. **Resilient Crash Recovery** — on a runtime error (missing import, undefined
   name, failed call, bad attribute) PyFEX substitutes a `DummyObject` and keeps
   going. The dummy proxies any further operation, so a broken or offline sample
   still reveals its downstream behavior instead of dying at the first error.
3. **Branch Merging** — forked paths reconverge at the branch's post-dominator,
   where a child publishes its state to shared memory and exits, so whole-program
   forced execution stays bounded instead of exploding into processes.
4. **State Sharing** — cross-process shared memory lets a path borrow a concrete
   value (locals, globals, closure cells) that a sibling path has already
   computed, improving recovery quality.
5. **Dormant Function Analysis** — logs every defined-vs-called function and then
   proactively invokes the never-called ("dormant") ones in fresh processes, so
   code that the sample never triggers on its own is still executed and observed.

Every feature is **off by default** (zero overhead) and enabled purely through
environment variables (see the table below).

## Layout

```
PyFEX-CCS-Artifact/
  PyFEX-core/            the instrumented CPython 3.10 interpreter (build this)
  samples_usage/        small runnable demos, one per capability (start here)
  tests/                the interpreter test suite (tests/general/)
  artifact_eval/        the analysis pipeline + smoke tests + prepared samples
    run_pyfex_program.py        run any target under PyFEX with chosen features
    run_one_calibrated_sample.py  run one malicious package end-to-end
    pyfexscan.py                PyFEXScan: LLM-backed detector (PyFEX trace -> verdict)
    run_artifact_tests.py       the test runner
    tests/                      artifact smoke tests
    samples/                    prepared 100-package analysis input
  tools/                helper tools
    dfa_driver.py               dormant-function replay driver
    extract_pyinstaller.py      statically unpack files from a PyInstaller ELF/exe
  Dataset/              the malicious-sample corpora (real malware)
    D1/                 calibrated malicious PyPI packages, extracted source
    D2                  compressed_malicious Python executables (PyInstaller Linux ELF, md5-named)
    D3/                 wild PyPI package archives collected from the live crawl
```

## 1. Build the interpreter

PyFEX-core is a complete CPython 3.10 source tree, so it needs the standard
CPython build toolchain plus the development headers for the optional C
extension modules. Installing all of them yields a *complete* build (no
"necessary bits to build these optional modules were not found" warnings).

Ubuntu / Debian (incl. WSL):

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential pkg-config \
    libssl-dev zlib1g-dev libbz2-dev liblzma-dev \
    libffi-dev libsqlite3-dev \
    libreadline-dev libncursesw5-dev \
    libgdbm-dev libgdbm-compat-dev \
    tk-dev uuid-dev libnsl-dev
```

What each provides: `build-essential` → the compiler and `make`;
`libssl` → `ssl`/`hashlib`; `zlib`/`libbz2`/`liblzma` → compression
(`zlib`/`bz2`/`lzma`); `libffi` → `ctypes`; `libsqlite3` → `sqlite3`;
`libreadline`/`libncursesw` → interactive `readline`/`curses`;
`libgdbm`(+`compat`) → `dbm`/`gdbm`/`_dbm`; `tk` → `tkinter`; `uuid` → `uuid`;
`libnsl` → `nis`. Only the compiler, `libssl`, `zlib`, and `libffi` are strictly
required to run PyFEX; the rest just complete the standard library.

Then build (run all commands from the artifact root; the subshell keeps your
working directory at the root):

```bash
( cd PyFEX-core && ./configure && make -j"$(nproc)" )   # produces PyFEX-core/python
```

## 2. See the features in action

```bash
samples_usage/run.sh        # runs all five feature demos
```

Each demo is a tiny, readable, evasive-malware-style script; see
`samples_usage/README.md` for the per-feature commands and expected output.

## 3. Run the test suite

```bash
python3 artifact_eval/run_artifact_tests.py --pyfex PyFEX-core/python --include-unit-tests
```

Expected final line: `SUMMARY PASS`. See `tests/README.md` for details and for
running individual integration tests.

## 4. Analyze a malicious package end-to-end

```bash
# Runs sample #1 under PyFEX (crash recovery + forced execution), with the
# network blocked by default, and writes traces + coverage under
# artifact_eval/samples/logs/<sample_id>/.
python3 artifact_eval/run_one_calibrated_sample.py --rank 1
```

Add `--dfa-invoke` to also replay the package's dormant functions. See
`artifact_eval/samples/README.md` for the safety notes and options.

## 5. Run your own target

```bash
python3 artifact_eval/run_pyfex_program.py \
    --crash-recovery-enable 1 --force-exec-enable 1 --force-exec-merge-enable 1 \
    --pyfex-trace-log-file /tmp/trace.jsonl \
    your_script.py
```

## 6. Detect malware with PyFEXScan (LLM classifier)

`artifact_eval/pyfexscan.py` is the paper's proof-of-concept detector. It has two
cooperating roles: **PyFEX** runs the target and produces a structured,
strace-style behavior trace whose synthetic values carry a
symbolic provenance lineage; an **LLM** then reads *only* that trace and returns a
`{result, confidence, reason}` verdict.


### Setup (LLM backend)

The default backend is OpenAI. Install the SDK in a
virtualenv and export a key:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install openai      # or: anthropic
export OPENAI_API_KEY=sk-...
```

Run `pyfexscan.py` with that interpreter (`./.venv/bin/python`). The `--no-llm`
mode needs no key or SDK — it builds the trace and prompt only.

### Three ways to supply a trace

```bash
# a) Offline: classify an existing PyFEX trace — no interpreter build, no network
./.venv/bin/python artifact_eval/pyfexscan.py \
    --trace artifact_eval/samples/logs/<sample_id>/*/behavior_trace.jsonl -o report.json

# b) Run a prepared calibrated sample end-to-end, then classify  (⚠ executes malware)
./.venv/bin/python artifact_eval/pyfexscan.py --sample 97 -o report.json

# c) Run your own target under PyFEX, then classify
./.venv/bin/python artifact_eval/pyfexscan.py --program your_script.py --scope-dir .
```

Modes (b) and (c) execute the target, so they require the interpreter built (§1)
and should run in the isolated VM/container; the network is blocked by default.
Mode (a) only reads a trace and works anywhere.

### Model selection and output

- `--model` picks the model; shorthands `gpt4.1mini` -> `gpt-4.1-mini` and
  `gpt5.4mini` -> `gpt-5.4-mini` are provided, and any exact id passes through.
  GPT-5-class models that reject `temperature`/`response_format` are retried
  automatically.
- `--no-llm` / `--print-prompt` / `--save-prompt FILE` inspect the trace and prompt
  without calling any model.
- Prints and (with `-o`) writes a JSON report `{result, confidence, reason}`; the
  process exits `1` when the verdict is **Malicious**, `0` otherwise.

## Environment variables

All features default to off. Enable them with these variables (or the
equivalent `run_pyfex_program.py` flags):

| Variable | Default | Purpose |
|---|---|---|
| `CRASH_RECOVERY_ENABLE` | off | substitute a `DummyObject` on runtime errors and continue |
| `CRASH_RECOVERY_GLOBAL_LIMIT` | `1000` | cap total recoveries |
| `CRASH_RECOVERY_LOCATION_LIMIT` | `50` | cap recoveries per bytecode location |
| `CRASH_RECOVERY_LOG_FILE` | unset | crash-recovery debug log path |
| `FORCE_EXEC_ENABLE` | off | fork at branch / loop / exception bytecodes |
| `FORCE_EXEC_MERGE_ENABLE` | off | merge forked paths at their post-dominator |
| `FORCE_EXEC_GLOBAL_LIMIT` | `100` | cap total forks |
| `FORCE_EXEC_LOCATION_LIMIT` | `10` | cap forks per bytecode location |
| `FORCE_EXEC_LOOP_ITER_LIMIT` | `200` | per-loop iteration cap (`0` disables) |
| `FORCE_EXEC_MAX_PROCS` | `8` | concurrent live forked processes allowed |
| `FORCE_EXEC_MAX_PROCS_HARD_CAP` | `256` | hard ceiling for `FORCE_EXEC_MAX_PROCS` |
| `FORCE_EXEC_LOG_FILE` | unset | forced-execution debug log path |
| `PYFEX_PROVENANCE_MODE` | `flat` | `recursive` records a nested symbolic provenance expression on each `DummyObject` (`.provenance` / `.trace`) |
| `PYFEX_SCOPE_DIR` | unset | treat every file under this directory as in-scope |
| `PYFEX_TRACE_LOG_FILE` | unset | JSONL behavior-trace output path |
| `PYFEX_RUNTIME_LOG_FILE` | unset | unified runtime debug log path |
| `DORMANT_FUNC_LOG_FILE` | unset | dormant-function `DEFINED`/`CALLED` log path |
| `DFA_INVOKE_CAP` | `32` | max dormant functions the driver invokes per run |

When running forced execution, keep `FORCE_EXEC_MERGE_ENABLE=1` and a fork
budget (e.g. `FORCE_EXEC_GLOBAL_LIMIT=20`) so exploration stays bounded.
