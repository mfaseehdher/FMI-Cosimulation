# Algebraic-Loop Experiments With Adder FMUs

These experiments test how the Python master algorithm handles connected FMUs,
particularly when two FMUs need each other's output during the same step. The
aim is to solve that dependency without adding an artificial delay.

The models are deliberately simple. Each adder calculates:

```text
Out = Bias + Gain * Feedback
```

This makes the expected answers easy to check by hand. It also makes it easier
to tell whether a problem comes from the coupling or from the model itself.

MATLAB runs the connected Simulink models to produce reference results. The
Python master then runs the exported FMUs with the same connections, and the
results are compared. This has been tested locally; the GitHub workflows have
not been run yet. The local results are recorded in
[LOCAL_VERIFICATION.md](docs/LOCAL_VERIFICATION.md).

## Experiments

| Folder | What It Tests | Expected Master Result |
| --- | --- | --- |
| `01_two_fmu_convergent` | Two adders connected in a loop: `a = 1 + 0.5*b`, `b = 0.2*a` | Converges |
| `02_changing_input` | The same loop, with A's bias changing from 1 to 3 at 0.2 s | Converges again after the change |
| `03_negative_feedback` | A loop with a negative gain | Converges |
| `04_chain_loop_and_merge` | Components before and after an algebraic loop | Runs the groups in dependency order |
| `05_two_coupled_loops` | Two algebraic-loop groups, with one feeding the other | Solves both groups in order |
| `06_unit_gain_inconsistent` | Equations that have no solution | Reports nonconvergence |
| `07_divergent_fixed_point` | Equations with a solution that this fixed-point iteration cannot reach | Reports nonconvergence |
| `08_explicit_delay_comparison` | Feedback with an intentionally configured one-step delay | Uses the previous accepted value |

Cases 06 and 07 are expected failure cases. Case 07 is important: MATLAB finds
the solution `a = b = -1`, but the master's current iteration diverges. Rejecting
that case is correct failure handling, not a claim that the loop was solved.
Only case 08 includes a delay in the model.

## Files

```text
.github/workflows/   MATLAB build and Python validation workflows
experiments/        One folder for each experiment
matlab/             Model preparation, FMU export and reference simulation
src/ci_fmi/         The Python master algorithm
scripts/            Packaging, validation and comparison scripts
tests/              Tests for comparison and artifact checks
docs/               Local verification record
```

Each experiment folder contains its configuration, a diagram, a `setup.m` file
and the saved Simulink models. There are 20 individual adder models and eight
connected reference models. The reference models connect the adders directly
inside Simulink; they do not use outputs from the Python master.

The repository contains source files only. FMUs, reference CSVs and validation
results are generated during a run and uploaded as GitHub artifacts. Earlier
local outputs remain in the sibling `Adder` folder and are not included here.

## GitHub Setup

See [GITHUB_SETUP.md](GITHUB_SETUP.md) for the commit and upload commands. The
contents of this folder should be at the repository root, so that GitHub can
find `.github/workflows/`.

There are two workflows:

1. **[MATLAB - Build Adder Artifacts](.github/workflows/matlab-build.yml)** runs on
   a Windows x64 self-hosted runner. It exports the saved models as FMUs, runs
   the MATLAB references and uploads the generated files.
2. **[Master - Validate Adder Artifacts](.github/workflows/master-validate.yml)**
   runs on a GitHub-hosted Windows runner. It downloads those files, runs the
   master without launching MATLAB, and saves the comparisons and plots.

The first runner needs MATLAB, Simulink, Simulink FMU Builder and a supported
C compiler. It must be registered with this repository and run under the
Windows account where MATLAB is licensed. The local setup uses MATLAB R2026b,
Python 3.13 and a 64-bit MinGW compiler. Windows is needed because the exported
FMUs contain Windows x64 binaries.

In **Settings > Secrets and variables > Actions > Variables**, set the paths
for the runner. On the machine used for the local tests, they are:

| Variable | Value |
| --- | --- |
| `MATLAB_ROOT` | `C:\Program Files\MATLAB\R2026b` |
| `MINGW64_ROOT` | `D:\thesis\ci-fmi\docs\experiments\matlab_algebraic_adder_loops\build\toolchain\mingw64` |

Use the corresponding installation paths on another machine. `MINGW64_ROOT`
can be left unset if MATLAB already has a working compiler configured.
Compiler binaries and license credentials should not be committed.

With the self-hosted runner online, open **Actions > MATLAB - Build Adder
Artifacts > Run workflow** and select the default branch. This runs all eight
experiments. The validation workflow starts automatically after a successful
build. Both workflow files must be on the default branch.

The validation workflow uses the source revision from that build and checks
the downloaded files before loading the FMUs. It can also be started manually
with the build run ID: the number after `/actions/runs/` in the MATLAB run's
URL. The build must be successful and its artifacts must still be available.

The repository is public so supervisors can view the work without invitations.
The MATLAB workflow is manually triggered; it does not run pull-request code.
Only trusted collaborators should have write access. The validation workflow
accepts builds from this repository's default branch, not forks or other
branches. These restrictions reduce the risks of a self-hosted runner but do
not remove them. No personal access token is stored in the workflow files.

## Running Locally

The following commands are for Windows CMD. Adjust the installation paths if
needed. First, export the FMUs and run the MATLAB references:

```bat
cd /d D:\thesis\master-algorithm-work\Experiment\Adders
if not exist build mkdir build
set "MW_MINGW64_LOC=D:\thesis\ci-fmi\docs\experiments\matlab_algebraic_adder_loops\build\toolchain\mingw64"
"C:\Program Files\MATLAB\R2026b\bin\matlab.exe" -wait -logfile build\matlab_build.log -batch "mex('-setup','C'); addpath(fullfile(pwd,'matlab')); build_all;"
py -3.13 scripts\package_matlab.py --output-dir build\new_matlab_bundle
```

Then run the Python tests and the master validation:

```bat
py -3.13 -m pip install -r requirements.txt
py -3.13 -m unittest discover -s tests -v
py -3.13 scripts\run_validation.py --artifact-dir build\new_matlab_bundle --output-dir results\new_validation
```

Use new bundle and result directory names when repeating a run. The scripts
refuse non-empty output directories so that old results are not mixed with a
new run. Each experiment also has a `setup.m` file for building and simulating
that case locally; packaging for the pipelines requires all eight cases.

`build_all` uses the saved SLX files. `prepare_models` only creates missing
models and does not overwrite changes made in Simulink. If the equations or
connections are changed, the configuration and reference models need to be
updated together.

## Comparing Results

Each successful MATLAB reference run produces:

- `matlab_trace.csv`: the logged values with their original MATLAB timestamps.
- `reference.csv`: the values used for the communication-interval comparison.
- `reference_status.json`: the outcome of the reference run.

The master logs an accepted result at the end of each communication interval.
For these experiments, the reference value stays constant within that interval.
The comparison CSV therefore keeps both the interval end in `time` and the
actual MATLAB sample time in `reference_sample_time`. Validation checks the
values against the raw trace and checks that they stay constant within the
interval.

For example, the input change at 0.2 s affects the interval from 0.2 to 0.3 s.
The master logs that result at 0.3 s. The comparison reference records
`time = 0.3` and `reference_sample_time = 0.2`. This sampling rule is specific
to these experiments; it should not be reused unchanged for a motor or an
integrator.

Successful simulations must pass both RMSE and maximum absolute error checks,
using a tolerance of `1e-8` per signal. Their values are also checked against
the adder equations independently. The comparison checks timestamps, sample
counts and finite values. It does not use interpolation or DTW. The tolerance
is chosen for these adder signals, not for every possible physical model.

Case 06 has no solution, so its expected MATLAB error is recorded instead of
producing a reference CSV. Case 07 has a valid MATLAB reference, but the master
is expected to report that its iteration did not converge.

## Current Limits

These tests cover the eight adder networks, not every type of FMU. The adders
have no internal physical dynamics. Their exported Co-Simulation FMUs refresh
their outputs through `doStep`, so the master saves and restores FMU state
between loop trials.

The results do not yet establish general initialization of physical states,
rollback correctness for arbitrary dynamic models, adaptive communication
steps, or convergence for every algebraic loop.

## AI Assistance

OpenAI Codex was used to help prepare the models, scripts, workflows, tests
and documentation. The master algorithm was copied unchanged from the local
implementation; its source and SHA-256 are recorded in `provenance.json`.
The original project license is included in `LICENSE`.

## References

- [MathWorks: starting MATLAB from the command line](https://www.mathworks.com/help/matlab/matlab_env/start-matlab-on-windows-platforms.html)
- [MathWorks: exporting Simulink models as FMUs](https://www.mathworks.com/help/fmuexport/ref/exporttofmu.html)
- [MathWorks: algebraic loops in Simulink](https://www.mathworks.com/help/simulink/ug/algebraic-loops.html)
- [GitHub: downloading artifacts from another workflow run](https://github.com/actions/download-artifact/blob/v4/action.yml)
- [GitHub: triggering a workflow after another workflow](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)
