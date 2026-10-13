# Local Verification - 12 October 2026

Both pipeline stages were executed locally in the original sibling `Adder`
folder. These are real MATLAB/FMU runs, not surrogate-only results.
**No GitHub workflow has been run.** The clean `Adder-GitHub` source copy does not
contain those generated outputs. The paths below refer to the original folder:

`D:\thesis\master-algorithm-work\Experiment\Adder`

## Build Stage

- MATLAB R2026b, headless `-batch` execution.
- 28 saved SLX source models: 20 individual adders and eight coupled references.
- 20 FMI 2.0 Co-Simulation FMUs exported with state save/restore enabled.
- Seven MATLAB references simulated successfully, with 51 raw points and five
  comparison intervals each. The inconsistent model produced its expected error.
- MATLAB found `a=b=-1` for case 07, confirming a solution exists.
- Build log: `build/matlab_build.log`.

## Artifact Handoff

The package was zipped, extracted into a fresh directory, then consumed by a
separate Python process without launching MATLAB. File/source checksums and
the expected local build identity were verified before loading FMUs.

## Validation Results

| Case | MATLAB Outcome | Master Check | Largest Comparison Error |
| --- | --- | --- | --- |
| 01 Two mutually dependent FMUs | Success | PASS | 2.22e-11 |
| 02 Changing input | Success | PASS | 4.44e-11 |
| 03 Negative feedback | Success | PASS | 2.18e-11 |
| 04 Chain, loop and merge | Success | PASS | 1.00e-10 |
| 05 Two connected loop groups | Success | PASS | 5.43e-11 |
| 06 Inconsistent equations | Expected algebraic-loop failure | Correctly rejected | Not applicable |
| 07 Solvable but divergent fixed-point iteration | Success, a=b=-1 | Correctly rejected | Not applicable |
| 08 Explicit previous-step delay | Success | PASS | 2.78e-17 |

All six numerical comparisons passed both RMSE and maximum-error gates. Their
MATLAB and master outputs also passed independent equation checks. The two
expected rejections are not claimed as successful simulations.

The native restore/replay probe produced the expected outputs `2, 5, 2`, with
the native output restored to zero before each trial. This is adder-specific
evidence, not proof of general rollback correctness for dynamic models.

## Software Checks

- 13 portable unit tests passed: timestamps, reference sampling, finite values,
  equation checks, expected solver limitation, safe paths and artifact integrity.
- Both workflow YAML files passed actionlint 1.7.7.
- The master snapshot matches its recorded original SHA-256; it was not rewritten
  to make these comparisons pass.
- No commit, remote upload or runner-registration change was made.

## Reading The Generated Files

`results/final_validation/summary.md` and `summary.json` contain the final local
report. Each experiment's result folder contains its actual CSV (successful
cases only), comparison JSON, master log, iteration trace and plots. MATLAB raw
and comparison references remain separately under each experiment's `reference/`.
Build/results files are ignored by Git; equivalent evidence will be downloadable
from the GitHub run artifacts when those workflows are executed.

## Clean GitHub Folder Check

The source-only `Adder-GitHub` folder was checked after copying and organizing it:

- All 13 portable unit tests passed.
- Both workflow definitions passed actionlint 1.7.7.
- The unchanged source fingerprint matched the earlier MATLAB artifact.
- All eight experiment checks passed using the existing native FMUs, including
  the two expected nonconvergence checks. MATLAB was not rerun for this check.
- The new validation output is in the original folder's
  `results/github_ready_verification/`; no generated files were added here.
- A local Git repository was initialized on `main`, without a commit or remote.
