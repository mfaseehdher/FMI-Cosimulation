# Commit And Run On GitHub

Use this folder as the repository root:

```text
D:\thesis\master-algorithm-work\Experiment\Adders
```

Do not put it inside an extra `Adders` directory in the remote repository.
The remote must have `.github/workflows` directly at its root.

## What Is Included

| Folder | Contents |
| --- | --- |
| `.github/workflows/` | The two GitHub pipelines |
| `experiments/` | Eight separate cases, configurations, diagrams and 28 SLX models |
| `matlab/` | Shared model creation, FMU export and reference simulation |
| `src/ci_fmi/` | The tested master algorithm |
| `scripts/` | Artifact packaging, master execution and comparison |
| `tests/` | Portable validation tests |
| `docs/` | Record of the earlier local verification |

Root files include requirements, the license, provenance and Git ignore rules.
Generated FMUs, references, results, compiler binaries and caches are excluded.
They remain in the original sibling `Adder` folder and were not deleted.

## One Source Commit

This folder has a local Git repository on branch `main`. The selected GitHub
repository is [FMI-Cosimulation](https://github.com/mfaseehdher/FMI-Cosimulation).
It is public so supervisors can view the work without invitations. Keep the
MATLAB workflow manually triggered and give write access only to trusted users.

The following commands are for the first upload to the empty repository.

In Windows CMD:

```bat
cd /d D:\thesis\master-algorithm-work\Experiment\Adders
git status
git add .
git commit -m "feat(experiments): add MATLAB adder cases and two-stage validation pipelines"
```

Connect the local repository to GitHub and upload the commit:

```bat
git remote add origin https://github.com/mfaseehdher/FMI-Cosimulation.git
git push -u origin main
```

These commands assume a new, empty remote repository. Do not force-push over an
existing project; integrate its files and history separately instead.

## Configure The MATLAB Runner

The first workflow needs your Windows x64 self-hosted runner registered with
this GitHub repository and online. Use the Windows account where MATLAB is
licensed and working. MATLAB, Simulink, Simulink FMU Builder and a supported C
compiler must be installed on that machine.

In **Settings > Secrets and variables > Actions > Variables**, add:

| Variable | Value On This Machine |
| --- | --- |
| `MATLAB_ROOT` | `C:\Program Files\MATLAB\R2026b` |
| `MINGW64_ROOT` | `D:\thesis\ci-fmi\docs\experiments\matlab_algebraic_adder_loops\build\toolchain\mingw64` |

These are paths, not passwords. Do not upload the compiler or license credentials.
See [README.md](README.md#github-setup) for other supported compiler setups.

## Run Both Stages

1. Open **Actions > MATLAB - Build Adder Artifacts > Run workflow**.
2. Select the default branch, `main` for the new repository, and start the run.
3. The MATLAB stage runs all eight cases, exports FMUs and uploads references.
4. After a successful build, **Master - Validate Adder Artifacts** starts
   automatically. It downloads that build, runs the master without MATLAB and
   publishes comparisons, iteration traces and plots.

Uploading source files alone does not start the MATLAB workflow; its trigger is
manual. Both workflow files must be on the default branch.

Cases 06 and 07 deliberately test rejection. Their expected rejection is not
claimed as a successfully solved loop. See the README for exact scope and limits.
