"""Portable checks for comparison semantics and artifact provenance."""
import copy
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from artifact_tools import contained, digest, verify_bundle, write_json
from comparison import (audit_equations, check_reference_samples, check_times,
                        compare_rows, linear_system, read_csv)

ROOT = Path(__file__).resolve().parents[1]


class ComparisonTests(unittest.TestCase):
    def cfg(self, name='01_two_fmu_convergent'):
        from artifact_tools import read_json
        return read_json(ROOT / 'experiments' / name / 'config.json')

    def test_named_columns_are_compared(self):
        result = compare_rows([{'time': 0.1, 'a': 1}], [{'a': 1, 'time': 0.1}], ['a'], 1e-8, 1e-8)
        self.assertTrue(result['a']['passed'])

    def test_timestamp_shift_is_not_hidden(self):
        with self.assertRaises(ValueError):
            compare_rows([{'time': 0, 'a': 1}], [{'time': 0.1, 'a': 1}], ['a'], 1e-8, 1e-8)

    def test_large_local_error_fails_even_when_rmse_is_allowed(self):
        expected = [{'time': t, 'a': 0} for t in (0.1, 0.2, 0.3)]
        actual = copy.deepcopy(expected)
        actual[0]['a'] = 0.1
        result = compare_rows(expected, actual, ['a'], 0.01, 1)
        self.assertFalse(result['a']['passed'])

    def test_nonfinite_values_and_invalid_tolerances_are_rejected(self):
        for tolerance in (-1, math.inf, math.nan):
            with self.subTest(tolerance=tolerance), self.assertRaises(ValueError):
                compare_rows([{'time': 0.1, 'a': 0}], [{'time': 0.1, 'a': 0}], ['a'], tolerance, 1e-8)

    def test_missing_communication_point_is_rejected(self):
        with self.assertRaises(ValueError):
            check_times([{'time': 0.1}], self.cfg())

    def test_reference_sampling_time_is_explicit(self):
        cfg = self.cfg()
        rows = [{'time': round((i + 1) * 0.1, 12), 'reference_sample_time': round(i * 0.1, 12)} for i in range(5)]
        check_times(rows, cfg, reference=True)
        rows[0]['reference_sample_time'] = 0.1
        with self.assertRaises(ValueError):
            check_times(rows, cfg, reference=True)

    def test_a_change_inside_an_interval_rejects_hold_assumption(self):
        reference = [{'time': 0.1, 'reference_sample_time': 0, 'a': 1}]
        raw = [{'time': 0, 'a': 1}, {'time': 0.05, 'a': 2}]
        with self.assertRaises(ValueError):
            check_reference_samples(reference, raw, ['a'], self.cfg(), 1e-8)

    def test_convergent_equations_have_expected_solution(self):
        cfg = self.cfg()
        row = {'time': 0.1, 'a': 1 / 0.9, 'b': 0.2 / 0.9, 'r': 1}
        self.assertLess(audit_equations([row], cfg, 1e-8)['max_equation_residual'], 1e-12)

    def test_delayed_equations_use_previous_step_not_current_feedback(self):
        cfg = self.cfg('08_explicit_delay_comparison')
        rows = [{'time': 0.1, 'a': 1, 'b': 0.2, 'r': 1},
                {'time': 0.2, 'a': 1.1, 'b': 0.22, 'r': 1}]
        audit_equations(rows, cfg, 1e-8)

    def test_solvable_divergent_case_is_not_called_inconsistent(self):
        import numpy as np
        cfg = self.cfg('07_divergent_fixed_point')
        _, matrix, rhs = linear_system(cfg, 0, {})
        np.testing.assert_allclose(np.linalg.solve(matrix, rhs), [-1, -1])

    def test_csv_nan_and_duplicate_headers_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'bad.csv'
            for text in ('time,a\n0.1,nan\n', 'time,a,a\n0.1,1,2\n'):
                file.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    read_csv(file)


class ArtifactTests(unittest.TestCase):
    def test_parent_and_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for relative in ('../other', Path(folder).resolve()):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    contained(folder, relative)

    def test_build_identity_and_file_hashes_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            case = folder / 'experiments' / 'case'
            case.mkdir(parents=True)
            write_json(case / 'config.json', {})
            write_json(case / 'experiment.json', {'id': 'case'})
            manifest = {'schema_version': 1, 'source_revision': 'abc', 'run_id': '12', 'run_attempt': '1',
                        'source_fingerprint': {}, 'experiment_ids': ['case'],
                        'files': {'experiments/case/config.json': digest(case / 'config.json'),
                                  'experiments/case/experiment.json': digest(case / 'experiment.json')}}
            write_json(folder / 'manifest.json', manifest)
            with patch('artifact_tools.source_fingerprint', return_value={}), patch('artifact_tools.ROOT', folder):
                verify_bundle(folder, 'abc', '12', '1')
                with self.assertRaises(ValueError):
                    verify_bundle(folder, 'different-commit', '12', '1')
                write_json(case / 'config.json', {'tampered': True})
                with self.assertRaises(ValueError):
                    verify_bundle(folder, 'abc', '12', '1')


if __name__ == '__main__':
    unittest.main()
