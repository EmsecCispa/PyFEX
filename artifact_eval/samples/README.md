# Calibrated sample set (for the analysis pipeline)

> ## ⚠️ WARNING: REAL MALICIOUS CODE
>
> The package directories under `packages/` (and the full corpus in
> `Dataset/` at the artifact root) are **real malicious PyPI
> packages**.
> They may attempt to steal credentials, contact command-and-control hosts,
> drop or execute additional payloads, or otherwise harm the host.
>
> **Do not `pip install` them, import them outside PyFEX, or run them on a
> machine you care about.** Analyze them only inside a disposable, network-
> isolated virtual machine or container. The provided pipeline already runs
> each sample under PyFEX with an OS-level network sandbox enabled by default,
> but you remain responsible for host isolation.

This directory holds the prepared input for the one-sample-at-a-time analysis
pipeline, plus the reference results from running it on all 100 samples:

- `selection_manifest.csv` — the selected samples, their categories, and the
  entry points the pipeline runs.
- `packages/` — a deterministic, stratified 100-package subset copied from the
  full corpus, ready to analyze.
- `RESULTS.md` — a human-readable summary table (per sample: entrypoints, calls,
  recoveries, forks, network blocks, DFA coverage, duration).
- `results.csv` / `results.jsonl` — the same results in machine-readable form.
- `logs/<sample_id>/` — per-entrypoint behavior traces, runtime logs, and
  dormant-function coverage for each sample.

The result files and `logs/` are **reference outputs**; re-running the pipeline
regenerates them in place.

## Run one sample under PyFEX

From the artifact root (after building `PyFEX-core`):

```bash
python3 artifact_eval/run_one_calibrated_sample.py --rank 1
```

This discovers the package's entry points (`setup.py`, `__main__.py`,
`__init__.py`, `main.py`, and declared `setup.cfg` / `pyproject` console
scripts), runs each under PyFEX with crash recovery + forced execution, and
writes per-sample behavior traces, recovery/fork counts, and dormant-function
coverage under `logs/<sample_id>/`. Add `--dfa-invoke` to additionally replay
the package's never-called functions.

Network access is blocked by default (`--network blocked`, OS sandbox via
`unshare`); pass `--network host` only inside a throwaway, isolated environment.
