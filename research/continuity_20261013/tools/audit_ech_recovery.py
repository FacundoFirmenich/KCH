#!/usr/bin/env python3
"""Verify recovered original ECH inputs and explicitly bounded atlas checks."""
from pathlib import Path
import argparse, csv, hashlib, io, json, shutil, zipfile
from collections import Counter

def sha(data): return hashlib.sha256(data).hexdigest()
def rows(z, name): return list(csv.DictReader(io.StringIO(z.read(name).decode())))
def truth(value):
    assert value in ('True', 'False')
    return value == 'True'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
    a.output_dir.mkdir(parents=True,exist_ok=True)
    sources={
        'kernel_sha256':('cas_constitutional_kernel_v1.json','libfile_0c288d1c9bd08191832299344cf98ec6'),
        'codebooks_sha256':('compiled_distance_codebooks.json','libfile_551f0315b7588191b7b53ad0344cec2b'),
        'adjacent_migrations_sha256':('adjacent_contract_migrations.csv','libfile_49b4e1668c80819180a3e562679b959e'),
    }
    archive=a.source_dir/'ECH_HELICAL_EVIDENCE_MIGRATION_2026-10-12.zip'
    archive_sha=sha(archive.read_bytes())
    with zipfile.ZipFile(archive) as z:
        binding=json.loads(z.read('SOURCE_BINDING.json'))
        manifest=[]
        for line in z.read('SHA256SUMS.txt').decode().splitlines():
            expected,name=line.split('  ',1)
            actual=sha(z.read(name));assert actual==expected,name
            manifest.append({'member':name,'sha256':actual,'verified':True})
        loops=rows(z,'two_edge_loop_monodromy.csv')
        squares=rows(z,'migration_square_noncommutativity.csv')
    recovered=[]
    recovered_dir=a.output_dir/'recovered_inputs';recovered_dir.mkdir(exist_ok=True)
    for key,(name,libid) in sources.items():
        original=a.source_dir/name;digest=sha(original.read_bytes());assert digest==binding[key],name
        shutil.copy2(original,recovered_dir/name)
        recovered.append({'source_binding_key':key,'name':name,'library_file_id':libid,'bytes':original.stat().st_size,'sha256':digest,'exact_binding_match':True})
    books=json.loads((a.source_dir/'compiled_distance_codebooks.json').read_text())
    transitions=list(csv.DictReader((a.source_dir/'adjacent_contract_migrations.csv').open()))
    adjacency={(r['source_contract'],r['destination_contract']):r for r in transitions}
    assert len(books)==28 and len(transitions)==len(adjacency)==96
    loop_checks=[]
    for row in loops:
        start,other=row['start_contract'],row['other_contract']
        assert row['return_contract']==start
        edge=adjacency[(start,other)];assert (other,start) in adjacency
        book=books[start]
        initial={book['sensor']+':'+mask for mask in book['probes']}
        additions={edge['destination_sensor']+':'+mask for mask in json.loads(edge['selected_probe_masks'])}
        independently_derived_delta=additions-initial
        published_delta=json.loads(row['monodromy_coordinates'])
        assert sorted(independently_derived_delta)==published_delta
        assert len(independently_derived_delta)==int(row['evidence_monodromy_size'])==int(row['first_leg_new'])
        assert int(row['second_leg_new'])==0
        assert int(row['first_leg_new'])==int(edge['additional_queries'])
        assert truth(row['evidence_content_returns'])==(not independently_derived_delta)
        assert int(row['genealogical_receipts_added'])==2 and not truth(row['genealogical_state_returns'])
        loop_checks.append({'start_contract':start,'other_contract':other,'coordinate_difference_recomputed':True,
                            'published_delta_size':len(independently_derived_delta)})
    assert len(loops)==96
    for r in squares:
        for path in ('path1','path2'):
            assert int(r[path+'_first_cost'])+int(r[path+'_second_cost'])==int(r[path+'_total_cost'])
        left=json.loads(r['path1_only']);right=json.loads(r['path2_only'])
        assert len(set(left))==len(left) and len(set(right))==len(right) and not(set(left)&set(right))
        assert len(left)+len(right)==int(r['ledger_symmetric_difference'])
        assert int(r['path1_final_ledger_size'])-int(r['path2_final_ledger_size'])==len(left)-len(right)
        assert truth(r['cost_commutes'])==(int(r['path1_total_cost'])==int(r['path2_total_cost']))
        assert truth(r['evidence_commutes'])==(int(r['ledger_symmetric_difference'])==0)
        assert truth(r['evidence_commutes'])==(r['path1_ledger_hash']==r['path2_ledger_hash'])
    assert len(squares)==23
    result={
        'format':'ECH_ORIGINAL_INPUT_RECOVERY_AND_BOUNDED_REPLAY_V0_1',
        'status':'THREE_HASH_BOUND_INPUTS_RECOVERED_FULL_ATLAS_REPLAY_NOT_ESTABLISHED',
        'original_atlas_archive':{'name':archive.name,'library_file_id':'libfile_0e0c7a091c8c8191b8e03651fe4305bc','sha256':archive_sha,'bytes':archive.stat().st_size},
        'source_binding':binding,'recovered_exact_inputs':recovered,'archive_manifest_checks':manifest,
        'verification_levels':{
            'exact_input_byte_recovery':'3/3 source-binding digests matched',
            'finite_family':'28 codebooks and 96 distinct directed adjacent transitions recovered',
            'two_edge_coordinate_deltas':'96/96 recomputed from original codebooks and archived bridge probe choices',
            'loop_genealogy':'Published receipt-count and return flags checked; full per-step receipt chains are not supplied',
            'square_results':'23/23 arithmetic and set-difference identities checked on published rows',
            'bridge_optimality':'NOT_RECOMPUTED: solver choices inherited from the frozen adjacent table',
            'destination_claim_satisfaction':'NOT_RECOMPUTED: original kernel recovered but not evaluated by this audit',
            'full_state_ledger_hash_replay':'NOT_ESTABLISHED: original atlas serialization/generator absent',
            'complete_numerical_atlas_regeneration':'NOT_PERFORMED: original generator and 204-entry cache not recovered',
        },
        'observed_counts':{
            'loops':96,'positive_evidence_delta':sum(int(r['evidence_monodromy_size'])>0 for r in loops),
            'zero_evidence_delta':sum(int(r['evidence_monodromy_size'])==0 for r in loops),
            'squares':23,'cost_noncommuting':sum(not truth(r['cost_commutes']) for r in squares),
            'evidence_noncommuting':sum(not truth(r['evidence_commutes']) for r in squares),
        },
        'missing_for_original_replay':[
            {'item':'bridge solver cache','reported_entries':204,'filename_in_binding':None,'hash_in_binding':None,'recovered':False},
            {'item':'original atlas generator and serialization rules','filename_in_binding':None,'hash_in_binding':None,'recovered':False},
        ],
        'bounded_search':{
            'repo_base_commit':'60105a141c1790fcd2152fb0ba511835b4620793',
            'repo_exact_source_hash_or_named_input_matches':0,
            'library_named_search_terms':['codebooks','bridge_solver_cache','adjacent_migrations','bridge','migration','kernel','bridge_solver','helical_evidence','solver_cache'],
            'predecessor_archive_recovered':'ECH_EVIDENCE_CARRYING_CONTRACT_MIGRATIONS_2026-10-08.zip',
            'predecessor_archive_contains_generator_or_solver_cache':False,
            'evidence_migration_compiler_role':'CSV lookup; not a bridge solver or atlas generator',
            'helical_evidence_state_runtime_role':'apply a supplied transition delta; not a numerical atlas generator',
            'scope_limit':'Known Library names and this KCH checkout only; no claim of global nonexistence',
        },
        'safety':{'synthetic_input_created':False,'missing_inputs_reconstructed':False,'remote_mutations':False,'permission_granted':False},
        'audit_script_sha256':sha(Path(__file__).read_bytes()),
    }
    result['receipt_sha256']=sha(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    (a.output_dir/'ECH_INPUT_RECOVERY_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'observed_counts':result['observed_counts'],'receipt_sha256':result['receipt_sha256']},indent=2))

if __name__=='__main__':main()
