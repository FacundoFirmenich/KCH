#!/usr/bin/env python3
"""Retrospective membership audit of REAL v0.8.1/v0.8.2 records.

Reads only an explicit NPY member allowlist. Does not load angular arrays,
execute pickle, select replacement cohorts, or run any scientific model.
Both source archives are immutable, hash-pinned existing experiment evidence.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile
from collections import Counter

import numpy as np

COHORTS = {0: 'BAY_AREA_HAYWARD_CALAVERAS', 1: 'PARKFIELD_CENTRAL_SAF'}
SOURCE_HASH = 'cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb'
ARCHIVES = {
    'KCH_KWANBLOCKS_HELICAL_LIFT_v0_8_2_EVIDENCE.zip': '48e949cd1625a0f5969567fcd9da7f00f3488be3b6d7d9299e3f53032babcf69',
    'KCH_HELICAL_CONTINUATION_20261012.zip': '71d4be4b3bdfd9ab7303439c6e2f3e665804caf967afdab7b117b3fcbbc4c592',
}
CSV_HASHES = {
    'LABEL_CONTRADICTIONS_ALL_2438.csv': '74210fb4a25d950380914638f437a97c4039edaac97bfd3e9f538f0652996190',
    'UNSUPPORTED_SOURCE_TYPES_ALL_1370.csv': '3e33638de2a86ff83c6b584d16e06ef2caafaf8c4c1da34371add416684c33a6',
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def receipt_check(obj, key):
    body = dict(obj)
    identifier = body.pop(key)
    assert identifier.split(':', 1)[1] == digest(canonical(body)), key
    return identifier

def integer_codes(values):
    numeric = np.asarray(values, dtype=np.float64)
    assert np.all(np.isfinite(numeric)) and np.all(numeric == np.floor(numeric))
    return numeric.astype(np.int64)

def write_csv(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_files = []
    for name, expected in ARCHIVES.items():
        path = args.source_dir / name
        actual = digest(path.read_bytes())
        assert actual == expected, name
        source_files.append({'name': name, 'bytes': path.stat().st_size, 'sha256': actual})
    accesses = []

    def members(npz_bytes, archive_member, allowed):
        # Never use {name: z[name] for name in z.files}: some NPZs contain
        # historical angular data that are outside this audit's scope.
        with zipfile.ZipFile(io.BytesIO(npz_bytes)) as z:
            result = {}
            for field in allowed:
                name = field + '.npy'
                data = z.read(name)
                array = np.load(io.BytesIO(data), allow_pickle=False)
                assert not array.dtype.hasobject
                result[field] = array
                accesses.append({'archive_member': archive_member, 'npy_member': name,
                                 'sha256_npy_bytes': digest(data), 'dtype': str(array.dtype),
                                 'shape': list(array.shape)})
            return result

    with zipfile.ZipFile(args.source_dir / 'KCH_KWANBLOCKS_HELICAL_LIFT_v0_8_2_EVIDENCE.zip') as z:
        selected_receipt = json.loads(z.read('evidence/SELECTED_INDEX_RECEIPT_V0_8.json'))
        extraction_receipt = json.loads(z.read('evidence/SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_8.json'))
        preflight_receipt = json.loads(z.read('evidence/DIRECTIONAL_PREFLIGHT_RESULT_V0_8.json'))
        receipt_check(selected_receipt, 'receipt_id')
        receipt_check(extraction_receipt, 'receipt_id')
        receipt_check(preflight_receipt, 'preflight_result_id')
        assert extraction_receipt['source_pickle_sha256'] == SOURCE_HASH
        assert extraction_receipt['selected_indices_sha256'] == selected_receipt['selected_indices_sha256']
        selected_bytes = z.read('evidence/selected_directional_columns.npz')
        assert digest(selected_bytes) == extraction_receipt['output_sha256'] == preflight_receipt['selected_directional_sha256']
        selected = members(selected_bytes, 'evidence/selected_directional_columns.npz',
                           ('global_index', 'cohort_code', 'nc_sc', 'ev_bl', 'evid', 'event_time_epoch'))
        del selected_bytes
        preflight_bytes = z.read('evidence/directional_preflight_arrays.npz')
        assert digest(preflight_bytes) == preflight_receipt['preflight_arrays_sha256']
        preflight = members(preflight_bytes, 'evidence/directional_preflight_arrays.npz',
                            ('global_index', 'cohort_code', 'axis_observable'))
        del preflight_bytes

    prefix = 'KCH_HELICAL_CONTINUATION_20261012/'
    with zipfile.ZipFile(args.source_dir / 'KCH_HELICAL_CONTINUATION_20261012.zip') as z:
        blind_receipt = json.loads(z.read(prefix + 'remote-run9/expanded/blind/EXTRACTION_RECEIPT_V0_9.json'))
        receipt_check(blind_receipt, 'receipt_id')
        assert blind_receipt['source_sha256'] == SOURCE_HASH
        blind_bytes = z.read(prefix + 'remote-run9/expanded/blind/blind_columns.npz')
        assert digest(blind_bytes) == blind_receipt['output_sha256']
        blind = members(blind_bytes, 'remote-run9/expanded/blind/blind_columns.npz', ('nc_sc', 'ev_bl', 'evid'))
        del blind_bytes
        exceptions = {}
        for name, expected in CSV_HASHES.items():
            raw = z.read(prefix + 'corroboration/' + name)
            assert digest(raw) == expected
            exceptions[name] = list(csv.DictReader(io.StringIO(raw.decode())))
        assert len(exceptions['LABEL_CONTRADICTIONS_ALL_2438.csv']) == 2438
        assert len(exceptions['UNSUPPORTED_SOURCE_TYPES_ALL_1370.csv']) == 1370

    index = selected['global_index']
    cohort = selected['cohort_code']
    observable = preflight['axis_observable']
    n = len(index)
    assert n == selected_receipt['selected_total'] == 61555
    assert len(np.unique(index)) == n and np.all(index >= 0) and np.all(index < 1574113)
    assert np.array_equal(index, preflight['global_index'])
    assert np.array_equal(cohort, preflight['cohort_code'])
    assert observable.dtype.kind == 'b'
    assert int(observable.sum()) == preflight_receipt['axis_observable_count'] == 60577
    converted = {}
    for field in ('nc_sc', 'ev_bl', 'evid'):
        before = integer_codes(selected[field])
        after = integer_codes(blind[field])
        assert len(after) == 1574113
        assert np.array_equal(before, after[index]), field
        converted[field] = before
    assert set(converted['ev_bl']) == {0, 1}
    assert set(converted['nc_sc']) == {1, 2}
    partition = np.full(n, 'not_observable', dtype='<U14')
    counts = []
    preflight_counts = {c['cohort_code']: c for c in preflight_receipt['cohorts']}
    for code, name in COHORTS.items():
        mask = cohort == code
        chronological = np.flatnonzero(mask & observable)
        chronological = chronological[np.argsort(selected['event_time_epoch'][chronological], kind='stable')]
        length = len(chronological)
        cuts = {'train': chronological[:length // 2],
                'calibration': chronological[length // 2:(3 * length) // 4],
                'test': chronological[(3 * length) // 4:]}
        expected = preflight_counts[code]
        assert int(mask.sum()) == expected['selected_event_count']
        assert length == expected['axis_observable_count']
        for stage, indices in cuts.items():
            partition[indices] = stage
            key = 'sealed_test_count' if stage == 'test' else stage + '_count'
            assert len(indices) == expected[key]
        for stage, indices in [('selected', np.flatnonzero(mask)), ('observable', chronological),
                               ('not_observable', np.flatnonzero(mask & ~observable)), *cuts.items()]:
            codes = Counter(map(int, converted['ev_bl'][indices]))
            counts.append({'cohort': name, 'stage': stage, 'n': len(indices),
                           'ev_bl_code_0': codes.get(0, 0), 'ev_bl_code_1': codes.get(1, 0),
                           'ev_bl_code_1_fraction': codes.get(1, 0) / len(indices)})

    lookup = {int(value): position for position, value in enumerate(index)}
    exception_rows = []
    exception_summary = {}
    for file_name, rows in exceptions.items():
        intersected = []
        for row in rows:
            position = lookup.get(int(row['input_row_zero_based']))
            if position is None:
                continue
            for field in ('evid', 'nc_sc', 'ev_bl'):
                assert int(row[field]) == int(converted[field][position]), (file_name, field)
            assert float(row['absolute_time_difference_seconds']) <= 1.0
            augmented = dict(row)
            augmented.update({'evidence_group': file_name, 'cohort': COHORTS[int(cohort[position])],
                              'axis_observable': bool(observable[position]),
                              'historical_partition': str(partition[position])})
            intersected.append(augmented)
        exception_rows.extend(intersected)
        exception_summary[file_name] = {
            'selected': len(intersected),
            'observable': sum(r['axis_observable'] for r in intersected),
            'by_cohort': dict(Counter(r['cohort'] for r in intersected)),
            'by_partition': dict(Counter(r['historical_partition'] for r in intersected)),
            'by_cohort_and_partition': dict(Counter(r['cohort'] + '|' + r['historical_partition'] for r in intersected)),
            'source_types_json': dict(Counter(r['source_event_type_json'] for r in intersected)),
        }
    selected_rows = ({'input_row_zero_based': int(index[i]), 'cohort': COHORTS[int(cohort[i])],
                      'evid': int(converted['evid'][i]), 'nc_sc_code': int(converted['nc_sc'][i]),
                      'ev_bl_code': int(converted['ev_bl'][i]), 'historical_ev_bl_text': str(selected['ev_bl'][i]),
                      'axis_observable': bool(observable[i]), 'historical_partition': str(partition[i])}
                     for i in range(n))
    selected_fields = ['input_row_zero_based', 'cohort', 'evid', 'nc_sc_code', 'ev_bl_code',
                       'historical_ev_bl_text', 'axis_observable', 'historical_partition']
    write_csv(args.output_dir / 'SELECTED_MEMBERSHIP_ALL_61555.csv', selected_rows, selected_fields)
    write_csv(args.output_dir / 'CATEGORY_COUNTS_BY_COHORT_AND_PARTITION.csv', counts, list(counts[0]))
    exception_fields = list(next(iter(exceptions.values()))[0]) + ['evidence_group', 'cohort', 'axis_observable', 'historical_partition']
    write_csv(args.output_dir / 'SELECTED_KNOWN_CATALOG_EXCEPTIONS.csv', exception_rows, exception_fields)
    report = {
        'format': 'KCH_HELICAL_HISTORICAL_MEMBERSHIP_AUDIT_V0_1',
        'outcome': 'RETROSPECTIVE_MEMBERSHIP_RESERVATION_MATERIALLY_CONFIRMED',
        'record_scope': 'REAL_EXISTING_V0_8_1_SELECTION_AND_V0_8_2_PREFLIGHT',
        'selected_event_count': n, 'observable_event_count': int(observable.sum()),
        'selected_code_1_count': int((converted['ev_bl'] == 1).sum()),
        'observable_code_1_count': int(((converted['ev_bl'] == 1) & observable).sum()),
        'historical_test_code_1_count': int(((converted['ev_bl'] == 1) & (partition == 'test')).sum()),
        'identity_checks': {'same_original_catalog_sha256': SOURCE_HASH,
                            'all_61555_global_indices_valid_unique': True,
                            'all_selected_evid_nc_sc_ev_bl_agree_with_independent_blind_extract': True,
                            'selected_and_preflight_global_indices_and_cohorts_identical': True,
                            'historical_stage_counts_match_published_preflight': True,
                            'numeric_text_representations_compared_exactly_after_integrality_check': True},
        'original_sources': source_files,
        'source_receipt_ids': [selected_receipt['receipt_id'], extraction_receipt['receipt_id'],
                               preflight_receipt['preflight_result_id'], blind_receipt['receipt_id']],
        'npz_arrays_decoded': accesses,
        'category_counts': counts,
        'known_catalog_exceptions': exception_summary,
        'boundary': {
            'angular_values_decoded': False, 'sealed_directional_fields_opened': False,
            'historical_archive_contains_previously_opened_directional_values': True,
            'historical_archive_bytes_hashed_for_integrity_only': True,
            'axis_observable_is_an_existing_boolean_preflight_output': True,
            'pickle_executed': False, 'scientific_models_rerun': False,
            'new_dataset_selected': False, 'source_labels_replaced': False,
            'synthetic_records_created': False,
            'numeric_event_code_semantics_certified': False,
            'all_code_1_records_may_be_called_blasts': False,
            'old_scientific_metrics_changed': False,
            'post_2021_terminal_source_implicated_by_this_audit': False,
            'authority_ceiling': 'NONE',
        },
        'limitations': [
            'The 17 qb matches are row-level external-catalog labels under the earlier candidate network mapping and <=1 second origin agreement; they do not certify the entire numeric codebook.',
            'Counterpart CSVs and their immutable producer-path references were verified against the prior evidence archive; the 82 annual producer catalogs were not downloaded again during this audit.',
            'The 3513 numeric-code-1 rows are counted as codes, never automatically relabeled blasts.',
            'This audit quantifies membership; it does not estimate how corrected membership would change fitted metrics.',
            'Partition membership is reconstructed from the published Boolean observability mask and stable chronological split; no directions or scientific models are recomputed.',
        ],
        'next_requirement': 'Version-specific producer codebook plus an explicit event-membership disposition; retain old metrics as historical and qualify their cohort interpretation until then.',
        'audit_script_sha256': digest(Path(__file__).read_bytes()),
    }
    report['output_sha256'] = {p.name: digest(p.read_bytes()) for p in sorted(args.output_dir.glob('*.csv'))}
    report['receipt_id'] = 'hcontinuitymembership:' + digest(canonical(report))
    (args.output_dir / 'HISTORICAL_MEMBERSHIP_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('outcome', 'selected_event_count', 'observable_event_count',
                                            'selected_code_1_count', 'observable_code_1_count',
                                            'historical_test_code_1_count', 'known_catalog_exceptions', 'receipt_id')}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
