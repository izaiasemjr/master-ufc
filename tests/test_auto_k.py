"""Check adaptive matching against an independent population-stddev oracle."""
import csv
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/classification'))
sys.path.insert(0, str(ROOT / 'src/evaluation'))
sys.path.insert(0, str(ROOT / 'src/matching'))
from run_classification import read_predictions
from run_evaluation import evaluate_variant
from run_matching import validate_scores


class AutoKTest(unittest.TestCase):
    def match(self, values, dps=None, correspondence='fixed', aggregation='mean', incremental=False, corr_min=1, expected_error=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def pcd(name, numbers):
                path = root / name
                path.write_text('VERSION .7\nFIELDS fpfh\nSIZE 4\nTYPE F\nCOUNT 33\n'
                                f'WIDTH {len(numbers)}\nHEIGHT 1\nPOINTS {len(numbers)}\nDATA ascii\n' +
                                ''.join(str(v) + ' 0' * 32 + '\n' for v in numbers))
                return path
            gallery = pcd('gallery.pcd', [0] * len(values))
            probe = pcd('probe.pcd', values)
            manifest = root / 'inputs.tsv'
            manifest.write_text(f'gallery\tbs000\tN\tN\t0\t{gallery}\nprobe\tbs000\tN\tN\t1\t{probe}\n')
            output = root / 'scores.csv'
            command = [str(ROOT / 'src/matching/build/matching_batch'), '--input', str(manifest),
                       '--output', str(output), '--timing-output', str(root / 'time.csv'),
                       '--correspondence', correspondence, '--aggregation', aggregation]
            command += ['--dp-thresholds' if incremental else '--dps', ','.join(map(str, dps))] if dps else ['--ks', '1,2,1000000']
            if dps and not incremental:
                command += ['--corr-min', str(corr_min)]
            result = subprocess.run(command, capture_output=True, text=True)
            if expected_error is not None:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)
                return
            self.assertEqual(result.returncode, 0, result.stderr)
            with output.open() as handle:
                rows = list(csv.DictReader(handle))
            settings = {'aggregation': aggregation, 'gallery': {}, 'probes': {'categories': {'N': {'type': 'N'}}},
                        'selection': 'auto_k_increment' if incremental else ('auto_k' if dps else 'fixed_k'),
                        ('dp_threshold_values' if incremental else ('dp_values' if dps else 'k_values')): dps or [1,2,1000000]}
            if dps and not incremental:
                settings['corr_min'] = corr_min
                gallery = [{'subject': 'bs000', 'type': 'N', 'expression': 'N', 'sample': '0'}]
                probes = [dict(gallery[0], sample='1')]
                validate_scores(output, probes, gallery, dps, 'dp', corr_min)
            predictions = read_predictions(output, settings, 'test')
            self.assertEqual(len(predictions), len(rows))
            pred_path = root / 'predictions.csv'
            with pred_path.open('w') as handle:
                writer = csv.DictWriter(handle, list(predictions[0]))
                writer.writeheader(); writer.writerows(predictions)
            accuracy, cmc = evaluate_variant(pred_path, 'test', settings)
            self.assertTrue(all(float(row['accuracy_percent']) == 100 for row in accuracy + cmc))
            return rows

    def test_nonmonotonic_prefix_and_strict_boundary(self):
        self.assertEqual(int(self.match([0, 10, 10], [4.8])[0]['selected_count']), 3)
        self.assertEqual(float(self.match([0, 1], [1e-30])[0]['dp']), 1e-30)
        rows = self.match([2, 0], [1, 1.01])
        self.assertEqual([int(row['selected_count']) for row in rows], [1, 2])
        self.assertEqual(int(self.match([7, 7, 7], [0.001])[0]['selected_count']), 3)
        self.assertEqual(int(self.match([7], [0.001])[0]['selected_count']), 1)

    def test_against_independent_oracle(self):
        rng = random.Random(42)
        values = [rng.randrange(100) for _ in range(50)]
        dps = [0.01, 0.5, 2, 4.8, 10, 25, 100]
        ordered = sorted(values)
        for correspondence, aggregation in [('fixed', 'mean'), ('dynamic', 'median')]:
            for row in self.match(values, dps, correspondence, aggregation):
                dp = float(row['dp'])
                selected = max(n for n in range(1, len(ordered)+1) if statistics.pstdev(ordered[:n]) < dp)
                self.assertEqual(int(row['selected_count']), selected)
                self.assertAlmostEqual(float(row['selected_stddev']), statistics.pstdev(ordered[:selected]))
                expected = statistics.mean(ordered[:selected]) if aggregation == 'mean' else statistics.median(ordered[:selected])
                self.assertAlmostEqual(float(row[f'distance_{aggregation}_l1']), expected)

    def test_corr_min_forced_floor_and_nonmonotonic_prefix(self):
        row = self.match([0,10,20,30,40,50], [0.1], corr_min=5)[0]
        self.assertEqual(int(row['selected_count']), 5)
        self.assertGreater(float(row['selected_stddev']), float(row['dp']))
        self.assertEqual(int(row['corr_min']), 5)
        # Even when the floor violates DP, a later prefix may satisfy it.
        row = self.match([0,10,10], [4.8], corr_min=2)[0]
        self.assertEqual(int(row['selected_count']), 3)
        self.match([0,1], [1], corr_min=5, expected_error='Not enough correspondences')

    def test_corr_min_sweep_against_oracle(self):
        rng = random.Random(87)
        values = [rng.randrange(100) for _ in range(40)]
        ordered = sorted(values)
        dps = [0.1, 2, 5, 7.5, 10, 20, 100]
        for corr_min in [5,7,9,12]:
            for correspondence, aggregation in [('fixed', 'mean'), ('dynamic', 'median')]:
                for row in self.match(values, dps, correspondence, aggregation, corr_min=corr_min):
                    dp = float(row['dp'])
                    k = max([corr_min] + [n for n in range(corr_min, len(values)+1)
                                        if statistics.pstdev(ordered[:n]) < dp])
                    self.assertEqual(int(row['selected_count']), k)
                    self.assertAlmostEqual(float(row['selected_stddev']), statistics.pstdev(ordered[:k]))
                    expected = statistics.mean(ordered[:k]) if aggregation == 'mean' else statistics.median(ordered[:k])
                    self.assertAlmostEqual(float(row[f'distance_{aggregation}_l1']), expected)

    def test_invalid_corr_min(self):
        for value in ['0','-1','2.5','nan','inf']:
            result = subprocess.run([str(ROOT / 'src/matching/build/matching_batch'),
                                     '--dps','1','--corr-min',value], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('corr-min', result.stderr)

    def test_incremental_strict_stop_and_zero_variance(self):
        # Ratio sigma(0,2,4) / sigma(0,2) = sqrt(8/3).
        row = self.match([4, 0, 2], [1.5], incremental=True)[0]
        self.assertEqual(int(row['selected_count']), 2)
        self.assertGreater(float(row['next_stddev_ratio']), 1.5)
        self.assertAlmostEqual(float(row['next_stddev']), statistics.pstdev([0,2,4]))
        # Stop at the FIRST violation; identical prefixes test strict equality.
        row = self.match([0, 2, 4, 4], [1], incremental=True)[0]
        self.assertEqual(int(row['selected_count']), 2)  # first next ratio > 1
        row = self.match([7, 7, 7], [1], incremental=True)[0]
        self.assertEqual(int(row['selected_count']), 3)  # 0/0 = 1 == threshold
        self.assertEqual(row['next_stddev_ratio'], '')
        row = self.match([0, 0, 10], [1.5], incremental=True)[0]
        self.assertEqual(int(row['selected_count']), 2)
        self.assertEqual(float(row['next_stddev_ratio']), math.inf)
        for values in [[4], [4,8]]:
            row = self.match(values, [1.5], incremental=True)[0]
            self.assertEqual(int(row['selected_count']), len(values))
            self.assertEqual(row['next_stddev'], '')

    def test_incremental_against_sequential_oracle(self):
        values = [0,2,3,4,5,6,7,8,9,10,100,101]
        thresholds = [1.01, 1.1, 1.5, 2, 3, 100]
        for correspondence, aggregation in [('fixed', 'mean'), ('dynamic', 'median')]:
            for row in self.match(values[::-1], thresholds, correspondence, aggregation, incremental=True):
                threshold = float(row['dp_threshold'])
                k = 2
                while k < len(values):
                    current = statistics.pstdev(values[:k])
                    next_dp = statistics.pstdev(values[:k+1])
                    ratio = next_dp/current if current else (math.inf if next_dp else 1)
                    if ratio > threshold:
                        break
                    k += 1
                self.assertEqual(int(row['selected_count']), k)
                expected = statistics.mean(values[:k]) if aggregation == 'mean' else statistics.median(values[:k])
                self.assertAlmostEqual(float(row[f'distance_{aggregation}_l1']), expected)
                self.assertAlmostEqual(float(row['selected_stddev']), statistics.pstdev(values[:k]))
                if k < len(values):
                    self.assertAlmostEqual(float(row['next_stddev_ratio']), ratio)
                else:
                    self.assertEqual(row['next_stddev_ratio'], '')

    def test_fixed_k_unchanged(self):
        rows = self.match([10, 0, 2])
        self.assertEqual([int(row['selected_count']) for row in rows], [1, 2, 3])
        self.assertEqual([float(row['distance_mean_l1']) for row in rows], [0, 1, 4])
        self.assertNotIn('dp', rows[0])

    def test_invalid_thresholds(self):
        for dp in [0, -1, math.nan, math.inf]:
            result = subprocess.run([str(ROOT / 'src/matching/build/matching_batch'), '--dps', str(dp)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
