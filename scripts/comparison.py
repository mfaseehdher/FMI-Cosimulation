"""Strict timestamp comparisons and independent linear-adder equation checks."""
from __future__ import annotations

import csv
import math

import numpy as np


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if 'time' not in fields or len(fields) != len(set(fields)):
            raise ValueError('CSV must have a unique time column and unique headers')
        rows = []
        for raw in reader:
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError('CSV row has the wrong number of fields')
            row = {key: float(value) for key, value in raw.items()}
            if not all(math.isfinite(value) for value in row.values()):
                raise ValueError('CSV contains non-finite values')
            rows.append(row)
    if not rows or any(b['time'] <= a['time'] + 1e-12 for a, b in zip(rows, rows[1:])):
        raise ValueError('CSV must contain strictly increasing, nonempty time samples')
    return rows


def check_times(rows, cfg, reference=False):
    count = round((cfg['stop'] - cfg['start']) / cfg['dt'])
    expected = [round(cfg['start'] + (i + 1) * cfg['dt'], 12) for i in range(count)]
    if len(rows) != count or any(not math.isclose(r['time'], t, abs_tol=1e-12, rel_tol=0)
                                 for r, t in zip(rows, expected)):
        raise ValueError('CSV communication points do not match the configured intervals')
    if reference:
        for row in rows:
            if not math.isclose(row['reference_sample_time'], row['time'] - cfg['dt'], abs_tol=1e-12, rel_tol=0):
                raise ValueError('Reference sample-time semantics do not match the interval start')


def compare_rows(reference, actual, signals, absolute_tolerance, rmse_tolerance):
    if any(not math.isfinite(t) or t < 0 for t in (absolute_tolerance, rmse_tolerance)):
        raise ValueError('Comparison tolerances must be finite and nonnegative')
    if not signals or len(reference) != len(actual) or not reference:
        raise ValueError('Both traces must contain the same nonzero sample count and signals')
    if any(not math.isclose(a['time'], b['time'], abs_tol=1e-12, rel_tol=0) for a, b in zip(reference, actual)):
        raise ValueError('Refusing an index-based comparison of different timestamps')
    metrics = {}
    for signal in signals:
        error = [a[signal] - b[signal] for a, b in zip(actual, reference)]
        if not all(math.isfinite(v) for v in error):
            raise ValueError('Non-finite comparison error')
        rmse = math.sqrt(math.fsum(v * v for v in error) / len(error))
        maximum = max(abs(v) for v in error)
        metrics[signal] = {'rmse': rmse, 'max_absolute_error': maximum,
                           'passed': rmse <= rmse_tolerance and maximum <= absolute_tolerance}
    return metrics


def check_reference_samples(reference, raw, signals, cfg, tolerance):
    for row in reference:
        start = row['reference_sample_time']
        matches = [r for r in raw if math.isclose(r['time'], start, abs_tol=1e-12, rel_tol=0)]
        if len(matches) != 1:
            raise ValueError('Comparison reference is not traceable to a unique raw MATLAB sample')
        held = [r for r in raw if start - 1e-12 <= r['time'] < row['time'] - 1e-12]
        if not held:
            raise ValueError('No raw samples cover the reference interval')
        for signal in signals:
            if abs(row[signal] - matches[0][signal]) > 1e-12:
                raise ValueError('Comparison reference differs from its raw MATLAB sample')
            if any(abs(r[signal] - row[signal]) > tolerance for r in held):
                raise ValueError('Stateless interval-hold reference assumption is not valid')


def source_value(cfg, port, time):
    source = cfg['components']['source']
    if source['type'] == 'const':
        return float(source['values'][port])
    if source['type'] == 'step':
        signal = source['ports'][port]
        return float(signal['step'] if time >= signal.get('step_time', 0) - 1e-12 else signal['initial'])
    raise ValueError('The adder reference audit only supports constant and step sources')


def linear_system(cfg, time, previous):
    names = [name for name, spec in cfg['components'].items() if spec['type'] == 'fmu']
    positions = {name: i for i, name in enumerate(names)}
    matrix = np.eye(len(names))
    rhs = np.zeros(len(names))
    for link in cfg['connections']:
        if link['dst_comp'] not in positions:
            continue
        row = positions[link['dst_comp']]
        spec = cfg['components'][link['dst_comp']]
        if link['dst_port'] not in ('Bias', 'Feedback'):
            raise ValueError('Unknown adder input')
        weight = 1 if link['dst_port'] == 'Bias' else float(spec['parameters']['Gain'])
        if link['src_comp'] == 'source':
            rhs[row] += weight * source_value(cfg, link['src_port'], time)
        elif link.get('delayed', False):
            rhs[row] += weight * previous[link['src_comp']]
        else:
            matrix[row, positions[link['src_comp']]] -= weight
    return names, matrix, rhs


def audit_equations(rows, cfg, tolerance):
    mapping = {c['src_comp']: c['dst_port'] for c in cfg['connections']
               if c['dst_comp'] == 'log' and c['src_comp'] != 'source'}
    previous = {name: float(cfg.get('initial_values', {}).get(f'{name}.Out', 0)) for name in mapping}
    maximum_error = maximum_residual = 0.0
    for row in rows:
        names, matrix, rhs = linear_system(cfg, row['time'] - cfg['dt'], previous)
        expected = np.linalg.solve(matrix, rhs)
        actual = np.array([row[mapping[name]] for name in names])
        maximum_error = max(maximum_error, float(np.max(np.abs(actual - expected))))
        maximum_residual = max(maximum_residual, float(np.max(np.abs(matrix @ actual - rhs))))
        for link in cfg['connections']:
            if link['dst_comp'] == 'log' and link['src_comp'] == 'source':
                expected_source = source_value(cfg, link['src_port'], row['time'] - cfg['dt'])
                maximum_error = max(maximum_error, abs(row[link['dst_port']] - expected_source))
        previous.update(zip(names, actual))
    if max(maximum_error, maximum_residual) > tolerance:
        raise AssertionError(f'Independent equation check failed: error={maximum_error}, residual={maximum_residual}')
    return {'max_analytic_error': maximum_error, 'max_equation_residual': maximum_residual}
