#!/usr/bin/env python3
"""Replay only deterministic operations on preserved M33 radial observations.

No main() of the original analysis is invoked: that entry point also bootstraps.
Original modules are copied byte-for-byte to a separate working directory.
Random sampling, including accidental calls through an initialized RNG, is blocked.
"""
from pathlib import Path
import argparse
import hashlib
import importlib
import json
import os
import platform
import shutil
import sys

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ['MPLBACKEND'] = 'Agg'
    os.environ['MPLCONFIGDIR'] = str(out / 'mplconfig')
    import numpy as np
    import pandas as pd
    import scipy
    # Initialize third-party libraries before instrumenting task-level sampling.
    # Recent SciPy builds generate documentation examples at import time; those
    # internals are unrelated to the archived observations or scientific replay.
    import scipy.stats
    import scipy.optimize
    import matplotlib.pyplot
    rng_calls = []
    def forbidden(*args, **kwargs):
        rng_calls.append('blocked_random_sampling_attempt')
        raise RuntimeError('Random generation/resampling is prohibited in this deterministic replay')
    class DisabledRNG:
        def __getattr__(self, name):
            return forbidden
    # Original v2 allocates an unused module-global RNG. Supply an inert object.
    np.random.default_rng = lambda *args, **kwargs: DisabledRNG()
    for name in ('normal', 'uniform', 'rand', 'randn', 'randint', 'choice', 'random', 'random_sample', 'permutation', 'shuffle', 'multivariate_normal'):
        setattr(np.random, name, forbidden)
    names = ['m33_empirical_pilot.py', 'm33_empirical_v2.py', 'm33_radial_robustness_v3.py', 'data/m33_koch2018_table_c1_corrected.csv']
    replay = out / 'source_exact_copies'
    copied = []
    for name in names:
        target = replay / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        assert digest(target) == digest(source / name)
        copied.append({'path': name, 'sha256': digest(target), 'bytes': target.stat().st_size})
    sys.path.insert(0, str(replay))
    r3 = importlib.import_module('m33_radial_robustness_v3')
    archived = json.loads((source / 'm33_radial_robustness_v3.json').read_text())
    concise = json.loads((source / 'm33_radial_robustness_v3_concise.json').read_text())
    checks = []
    def compare(name, actual, expected, atol=1e-10, rtol=1e-11):
        aa, ee = np.asarray(actual), np.asarray(expected)
        passed = bool(aa.shape == ee.shape and np.allclose(aa, ee, atol=atol, rtol=rtol))
        diff = float(np.max(np.abs(aa-ee))) if aa.shape == ee.shape and aa.size else None
        checks.append({'name': name, 'passed': passed, 'atol': atol, 'rtol': rtol, 'max_absolute_difference': diff})
    koch, halpha = r3.load_koch(), r3.load_halpha()
    bins = r3.common_bins(halpha, koch)
    compare('counts_halpha_hi_common', [len(halpha), len(koch), len(bins)], [396, 102, 28], 0, 0)
    koch_expected = archived['data_integrity']['koch_table_sha256']
    checks.append({'name': 'koch_source_sha256', 'passed': digest(replay / names[-1]) == koch_expected, 'expected': koch_expected, 'actual': digest(replay / names[-1])})
    previous_bins = pd.read_csv(source / 'outputs/m33_common_bins_025kpc_v3.csv')
    checks.append({'name': 'common_bins_columns', 'passed': bins.columns.tolist() == previous_bins.columns.tolist()})
    compare('all_common_bin_numeric_values', bins.to_numpy(), previous_bins.to_numpy())
    bins.to_csv(out / 'M33_REPLAY_COMMON_BINS_28.csv', index=False)
    scenarios = {}
    for scenario in r3.SCENARIOS:
        covariance = r3.covariance_matrix(bins, scenario)
        result = r3.ring_result(bins, covariance)
        original = archived['covariance_scenarios'][scenario.name]
        for name in ['ring_means_kms', 'ring_covariance_kms2', 'ring_se_kms', 'chi2_null', 'p_null', 'effective_covariance_dimension']:
            compare(f'{scenario.name}/{name}', result[name], original[name])
        scenarios[scenario.name] = {
            'ring_means_kms': result['ring_means_kms'], 'ring_se_kms': result['ring_se_kms'],
            'chi2_null': result['chi2_null'], 'p_null': result['p_null'],
            'min_covariance_eigenvalue': float(np.linalg.eigvalsh(covariance).min()),
        }
    primary = next(x for x in r3.SCENARIOS if x.name == r3.PRIMARY_SCENARIO)
    primary_result = r3.ring_result(bins, r3.covariance_matrix(bins, primary))
    references = {
        'Koch corrected table': primary_result['ring_means_kms'],
        'Koch Brandt fit': r3.smooth_reference_ring_means(halpha, 'brandt', r3.brandt_curve, r3.I_KOCH_DEG).tolist(),
        'Corbelli/Sellwood fit': r3.smooth_reference_ring_means(halpha, 'sellwood', r3.sellwood_curve, 52.0).tolist(),
    }
    for name, value in references.items():
        compare('reference/'+name, value, archived['reference_ring_means_kms'][name])
    spread = np.ptp(np.asarray(list(references.values())), axis=0)
    natural = r3.natural_response()
    X = np.asarray(natural['response_matrix_kms_per_eta'])
    eta, pred, rank, singular = r3.v2.min_norm_exact(X, np.asarray(primary_result['ring_means_kms']))
    for name in ['response_matrix_kms_per_eta', 'rank', 'singular_values', 'ring_envelope_eta_norm_le_1_kms']:
        compare('natural_response/'+name, natural[name], archived['natural_mhd_response'][name])
    eta_norm = float(np.linalg.norm(eta))
    compare('minimum_eta_norm', eta_norm, concise['minimum_eta_norm'], 1e-9, 1e-11)
    compare('reference_spread', spread, archived['reference_spread_kms'])
    ratio = spread / np.asarray(natural['ring_envelope_eta_norm_le_1_kms'])
    compare('reference_to_natural_ratio', ratio, concise['spread_to_natural_ratio'])
    loo = r3.leave_one_bin_out(bins, primary)
    for name, value in loo.items():
        compare('leave_one_bin_out/'+name, value, archived['leave_one_bin_out_primary'][name])
    hashes = []
    for line in (source / 'SHA256SUMS.txt').read_text().splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        path = source / name
        actual = digest(path) if path.is_file() else None
        hashes.append({'path': name, 'expected': expected, 'actual': actual, 'passed': actual == expected})
    prereg_names = ['PREREGISTRATION_M33_2D.md', 'm33_2d_run_manifest.json', 'DATA_MANIFEST.yml']
    result = {
        'audit_id': 'M33_RADIAL_DETERMINISTIC_REPLAY_20261013',
        'status': 'PASS_DETERMINISTIC_RADIAL_REPLAY' if all(x['passed'] for x in checks) and not rng_calls else 'REPLAY_MISMATCH',
        'source_archive_sha256_reported_by_recovery': '59d7011fa5288a483aa5197b29eac9f57048c5ce03bc1090857e8a85b6a0764b',
        'archive_sha256_recomputed_here': False,
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__, 'scipy': scipy.__version__},
        'code_and_observation_copies': copied,
        'input_status': {'halpha_rows': len(halpha), 'hi_rows': len(koch), 'common_bins': len(bins), 'public_tables_independently_refetched': False, 'provenance_level': 'archived_public_table_transcription_and_corrected_csv; bytes_verified_against_preserved_manifest'},
        'deterministic_primary': {'scenario': r3.PRIMARY_SCENARIO, **scenarios[r3.PRIMARY_SCENARIO], 'minimum_eta_norm': eta_norm, 'natural_response': natural, 'reference_means_kms': references, 'reference_spread_kms': spread.tolist(), 'reference_to_natural_ratio': ratio.tolist(), 'leave_one_bin_out': loo},
        'covariance_scenarios': scenarios,
        'numeric_comparisons': checks,
        'source_manifest': {'listed_files': len(hashes), 'passed': sum(x['passed'] for x in hashes), 'failed': [x for x in hashes if not x['passed']], 'entries': hashes},
        'preregistration_untouched_hashes': {n: digest(source / n) for n in prereg_names},
        'historical_only_not_reexecuted': ['observed_moving_block_bootstrap', 'JAX benchmarks and checks', '2D FITS inference', 'full main() analysis entry points'],
        'random_sampling_attempts': rng_calls,
        'sampling_guard_scope': 'active for imports and calls of all archived analysis modules, after third-party library initialization',
        'synthetic_observations_created': False,
        'interpretation': ['No robust radial detection under the declared primary covariance scenario.', 'Small p under published-diagonal sensitivity is not robust to declared inclination/covariance treatment.', 'Coefficient norm is required to reproduce the point residual vector under the stated response normalization; it is not a calibrated confidence bound or exclusion.', 'No new FITS inference, physical helicity measurement, or calibration of covariance assumptions is established.'],
    }
    (out / 'M33_RADIAL_VERIFICATION.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({k: result[k] for k in ['status', 'input_status', 'random_sampling_attempts']}, ensure_ascii=False))
    print(json.dumps({'p': primary_result['p_null'], 'minimum_eta_norm': eta_norm, 'comparisons': len(checks), 'failed_numeric': [x for x in checks if not x['passed']], 'manifest_passed': sum(x['passed'] for x in hashes), 'manifest_entries': len(hashes), 'manifest_failed': result['source_manifest']['failed']}, ensure_ascii=False))
    if result['status'] != 'PASS_DETERMINISTIC_RADIAL_REPLAY':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
