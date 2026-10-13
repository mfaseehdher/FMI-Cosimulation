"""Pipeline 2: consume a build artifact without MATLAB, simulate and compare."""
from __future__ import annotations

import argparse
import contextlib
import copy
import math
import os
import platform
import sys
import traceback
from pathlib import Path

import numpy as np

from artifact_tools import ROOT, cases, contained, read_json, verify_bundle, write_json
from comparison import (audit_equations, check_reference_samples, check_times,
                        compare_rows, linear_system, read_csv)

sys.path.insert(0, str(ROOT / 'src'))
from ci_fmi.master_algorithm import AlgebraicLoopConvergenceError, FMUComponent, run_case


def native_restore_probe(file):
    comp = FMUComponent('restore_probe', str(file))
    snapshot = None
    try:
        comp.instantiate(0, {'Gain': 0.5})
        comp.configure_stepping(0.1)
        baseline = comp._fmu_get('Out')
        snapshot = comp.save_state()
        actual, restored = [], []
        for bias, feedback in ((1, 2), (3, 4), (1, 2)):
            comp.restore_state(snapshot)
            restored.append(comp._fmu_get('Out'))
            comp.set_input('Bias', bias)
            comp.set_input('Feedback', feedback)
            comp.trial_step(0, 0.1)
            actual.append(comp._fmu_get('Out'))
        if any(not math.isclose(v, baseline, abs_tol=1e-12) for v in restored) or actual != [2, 5, 2]:
            raise AssertionError('Native FMU state restoration/replay failed')
        return {'baseline_output': baseline, 'restored_outputs': restored, 'trial_outputs': actual}
    finally:
        try:
            if snapshot is not None:
                comp.free_state(snapshot)
        finally:
            comp.terminate()


def check_trace(trace, cfg, expected_failure):
    for row in trace:
        for value in row['trial_start_times'].values():
            if not math.isclose(value, row['time_start'], abs_tol=1e-12, rel_tol=0):
                raise AssertionError('A trial did not restart at the interval start')
        for value in row['trial_end_times'].values():
            if not math.isclose(value, row['time_end'], abs_tol=1e-12, rel_tol=0):
                raise AssertionError('Trial members did not reach the same interval end')
    accepted = [row for row in trace if row['accepted']]
    if expected_failure:
        if not trace or accepted or trace[-1]['iteration'] != cfg['algebraic_loop']['max_iterations']:
            raise AssertionError('Unexpected nonconvergence trace or accepted failed trial')
    elif trace:
        groups = {tuple(row['components']) for row in trace}
        steps = round((cfg['stop'] - cfg['start']) / cfg['dt'])
        if len(accepted) != len(groups) * steps:
            raise AssertionError('Wrong number of accepted loop steps')
    return {'accepted_loop_steps': len(accepted),
            'max_iterations_used': max((r['iteration'] for r in trace), default=0),
            'loop_groups': sorted({tuple(r['components']) for r in trace})}


def draw_results(folder, reference, actual, signals, trace):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    if actual:
        for signal in signals:
            fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                     gridspec_kw={'height_ratios': [3, 1]})
            times = [r['time'] for r in actual]
            axes[0].plot(times, [r[signal] for r in reference], drawstyle='steps-post',
                         marker='o', markersize=3, label='MATLAB interval reference')
            axes[0].plot(times, [r[signal] for r in actual], '--', drawstyle='steps-post',
                         marker='x', markersize=3, label='Master / FMUs')
            axes[0].set_ylabel(signal)
            axes[0].legend()
            axes[1].plot(times, [abs(a[signal] - b[signal]) for a, b in zip(actual, reference)], color='#b22222')
            axes[1].set_ylabel('|error|')
            axes[1].set_xlabel('Communication interval end (s)')
            for ax in axes:
                ax.grid(alpha=0.25)
            fig.tight_layout()
            fig.savefig(folder / f'{signal}_comparison.png', dpi=150)
            plt.close(fig)
    if trace:
        fig, ax = plt.subplots(figsize=(8, 4))
        first = min(r['time_start'] for r in trace)
        groups = sorted({tuple(r['components']) for r in trace})
        for group in groups:
            rows = [r for r in trace if r['time_start'] == first and tuple(r['components']) == group]
            ax.semilogy([r['iteration'] for r in rows], [max(r['max_residual'], 1e-16) for r in rows], label='/'.join(group))
        ax.set_xlabel('Trial number in the first interval')
        ax.set_ylabel('Largest change from previous trial')
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(folder / 'iteration_residual.png', dpi=150)
        plt.close(fig)


def validate_case(folder, source_cfg, meta, output):
    cfg = copy.deepcopy(source_cfg)
    for spec in cfg['components'].values():
        if spec['type'] == 'fmu':
            spec['file'] = str(contained(folder, spec['file']))
    cfg['components']['log']['file'] = str(output / 'actual.csv')
    trace = []
    result = {'id': meta['id'], 'status': 'FAIL', 'master_expectation': meta['master_expectation']}
    reference = actual = None
    signals = [c['dst_port'] for c in cfg['connections'] if c['dst_comp'] == 'log']
    try:
        status = read_json(folder / 'reference' / 'reference_status.json')
        expected_reference = 'SUCCESS' if meta['matlab_expectation'] == 'success' else 'EXPECTED_ALGEBRAIC_FAILURE'
        if status['status'] != expected_reference:
            raise AssertionError('Unexpected MATLAB reference status')
        result['matlab_status'] = status['status']
        tolerance = meta['comparison']['absolute_tolerance']
        if status['status'] == 'SUCCESS':
            reference = read_csv(folder / 'reference' / 'reference.csv')
            check_times(reference, cfg, reference=True)
            raw = read_csv(folder / 'reference' / 'matlab_trace.csv')
            check_reference_samples(reference, raw, signals, cfg, tolerance)
            result['matlab_equation_audit'] = audit_equations(reference, cfg, tolerance)
        else:
            names, matrix, rhs = linear_system(cfg, cfg['start'], {name: 0 for name in cfg['components']})
            if np.linalg.matrix_rank(np.column_stack((matrix, rhs))) <= np.linalg.matrix_rank(matrix):
                raise AssertionError('Expected no-solution case does not have inconsistent equations')
            result['matlab_error_identifier'] = status['error_identifier']
        failed_as_expected = False
        try:
            with (output / 'master.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
                run_case(cfg, loop_trace=trace)
        except AlgebraicLoopConvergenceError as error:
            if meta['master_expectation'] != 'nonconvergence':
                raise
            failed_as_expected = True
            result['reason'] = str(error)
            result['status'] = 'PASS_EXPECTED_NONCONVERGENCE'
        else:
            if meta['master_expectation'] == 'nonconvergence':
                raise AssertionError('A deliberately nonconvergent iteration was accepted')
            actual = read_csv(output / 'actual.csv')
            check_times(actual, cfg)
            result['metrics'] = compare_rows(reference, actual, signals, tolerance, meta['comparison']['rmse_tolerance'])
            if not all(m['passed'] for m in result['metrics'].values()):
                raise AssertionError('MATLAB versus master comparison exceeded its tolerance')
            result['master_equation_audit'] = audit_equations(actual, cfg, tolerance)
            result['status'] = 'PASS'
        result['iteration'] = check_trace(trace, cfg, failed_as_expected)
        result['configured_delays'] = sum(c.get('delayed', False) for c in cfg['connections'])
    except Exception as error:
        result['status'] = 'FAIL'
        result['reason'] = str(error)
        (output / 'validation_error.log').write_text(traceback.format_exc(), encoding='utf-8')
    finally:
        write_json(output / 'iterations.json', trace)
    try:
        draw_results(output, reference, actual, signals, trace)
    except Exception as error:
        result['status'] = 'FAIL'
        result['plot_error'] = str(error)
    write_json(output / 'comparison.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact-dir', type=Path, default=ROOT / 'build' / 'matlab_bundle')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--expected-revision')
    parser.add_argument('--expected-run-id')
    parser.add_argument('--expected-run-attempt')
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError('Validation output must be empty; use a fresh output directory')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = verify_bundle(args.artifact_dir, args.expected_revision, args.expected_run_id, args.expected_run_attempt)
    experiments = cases(args.artifact_dir)
    first_folder, first_cfg, _ = experiments[0]
    first_fmu = next(s for s in first_cfg['components'].values() if s['type'] == 'fmu')
    write_json(args.output_dir / 'native_restore_probe.json', native_restore_probe(contained(first_folder, first_fmu['file'])))
    results = []
    for folder, cfg, meta in experiments:
        output = args.output_dir / meta['id']
        output.mkdir()
        result = validate_case(folder, cfg, meta, output)
        results.append(result)
        print(f"{result['status']}: {meta['id']}")
    write_json(args.output_dir / 'summary.json', {'source_revision': manifest['source_revision'],
               'build_run_id': manifest['run_id'], 'build_run_attempt': manifest['run_attempt'],
               'python_version': platform.python_version(), 'results': results})
    report = ['# Master / MATLAB Validation', '', f"Build run: `{manifest['run_id']}`; revision: `{manifest['source_revision']}`.", '',
              '| Experiment | MATLAB | Master Check | Largest Comparison Error |', '| --- | --- | --- | --- |']
    for r in results:
        maximum = max((m['max_absolute_error'] for m in r.get('metrics', {}).values()), default=None)
        report.append(f"| {r['id']} | {r.get('matlab_status', 'not checked')} | {r['status']} | {maximum if maximum is not None else 'not applicable'} |")
    report += ['', 'Expected rejection is not a successful simulation. Case 07 demonstrates a solver limitation, not an inconsistent system.',
               'The reference protocol is documented stateless interval hold, not an arbitrary one-step shift.', '']
    text = '\n'.join(report)
    (args.output_dir / 'summary.md').write_text(text, encoding='utf-8')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write(text)
    return 0 if all(r['status'].startswith('PASS') for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
