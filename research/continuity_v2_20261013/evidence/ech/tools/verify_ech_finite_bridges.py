#!/usr/bin/env python3
"""Independent finite ECH bridge audit from hash-bound, archived inputs.

No observational data are generated. The script enumerates the declared finite
decision kernel and verifies archived witnesses with newly computed rational
LP-dual certificates. It does not claim to recover the original atlas generator.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, platform, sys, zipfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import linprog

EXPECTED = {
    "cas_constitutional_kernel_v1.json": "82a9d8b10b90ea1debfeb480ac10e5bcc183e034d0d33a6dbf23b55931053138",
    "compiled_distance_codebooks.json": "9d5ffe66c18b6c764963a484f91eed09ebb064a59be205fc3f7a0681adb81a5b",
    "adjacent_contract_migrations.csv": "818beed9111f102a863ad619a6209b27f44026b5adb335ea715814c8d1e3d91d",
}
ATLAS_SHA = "a201aafbeda966e5d600e803cd19ea9ff16e6a21bbf9ad21b7f51f27e272504e"

def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
def ledger_hash(E): return sha("\n".join(sorted(E)).encode())
def rows(raw): return list(csv.DictReader(io.StringIO(raw.decode())))
def mode(s): return "OUTSIDE" if s == "OUTSIDE_DECLARED_DOMAIN" else s.split(":", 1)[0]
def actionable(s):
    mo = mode(s)
    return "OUTSIDE" if mo == "OUTSIDE" else ("ACTIONABLE" if mo in {"APPLY", "TOP_2"} else "NONACTIONABLE")

class Family:
    def __init__(self, kernel, books):
        self.k, self.books = kernel, books
        assert kernel["permission_granted"] is False
        self.nodes = kernel["nodes"]
        self.n = len(kernel["ordered_blocks"])
        self.roots = {}
        for r in kernel["roots"]:
            c = int(r["class_id"])
            if c in self.roots: assert self.roots[c] == r["root"]
            self.roots[c] = int(r["root"])
        self.classes = sorted(self.roots)
        self.masks = [m for m in range(1 << self.n) if m.bit_count() >= kernel["domain_floor"]]
        self.qindex = {f"{m:03x}": i for i, m in enumerate(self.masks)}
        self.structural_hash_checks = self.check_structure()
        raw = [[self.evaluate(self.roots[c], m) for m in self.masks] for c in self.classes]
        self.matrices = {
            "EXACT": np.asarray(raw),
            "MODE": np.asarray([[mode(s) for s in row] for row in raw]),
            "ACTIONABLE": np.asarray([[actionable(s) for s in row] for row in raw]),
        }
        assert not any("OUTSIDE" in s for row in raw for s in row)
        self.i, self.j = np.triu_indices(len(self.classes), 1)
        self.diff = {s: mat[self.i] != mat[self.j] for s, mat in self.matrices.items()}
        self.relevant = {s: d.any(axis=1) for s, d in self.diff.items()}
        self.cache = {}

    def evaluate(self, root, m):
        seen = set()
        while "label" not in self.nodes[root]:
            assert root not in seen
            seen.add(root)
            node = self.nodes[root]
            root = int(node["if_included"] if m & (1 << node["query_index"]) else node["if_excluded"])
        return self.nodes[root]["label"]

    def check_structure(self):
        memo = {}
        def digest(idx):
            if idx in memo: return memo[idx]
            n = self.nodes[idx]
            if "label" in n: raw = ("L\0" + n["label"]).encode()
            else:
                assert 0 <= int(n["query_index"]) < self.n
                # The archived DAG uses child-before-parent indices.
                assert 0 <= n["if_excluded"] < idx and 0 <= n["if_included"] < idx
                raw = b"Q\0" + str(n["query_index"]).encode() + b"\0" + bytes.fromhex(digest(n["if_excluded"])) + bytes.fromhex(digest(n["if_included"]))
            memo[idx] = sha(raw)
            return memo[idx]
        checks = []
        for r in self.k["roots"]:
            actual = digest(r["root"])
            assert actual == r["structural_sha256"]
            checks.append({"class_id": r["class_id"], "structural_sha256": actual, "matched": True})
        return checks

    def ledger(self, c):
        b = self.books[c]
        assert b["permission_granted"] is False
        assert len(b["probes"]) == b["probe_count"] == len(set(b["probes"]))
        assert all(q in self.qindex for q in b["probes"])
        return {b["sensor"] + ":" + q for q in b["probes"]}

    def distances(self, E):
        out = np.zeros(len(self.i), dtype=np.int64)
        for coordinate in E:
            s, m = coordinate.split(":")
            out += self.diff[s][:, self.qindex[m]]
        return out

    def minimum(self, E, target): return int(self.distances(E)[self.relevant[target]].min())

    def prove_bridge(self, E, destination, additions):
        """Check witness feasibility and certify a matching integer lower bound.

        The relaxation permits nonnegative unbounded multiplicity x_q. This is
        a superset of legal 0/1 query selections, hence its dual is a valid lower
        bound without assuming historical candidate deduplication behavior.
        """
        b = self.books[destination]
        s, target, d = b["sensor"], b["target"], b["distance"]
        additions = set(additions)
        assert not E.intersection(additions)
        assert all(q.startswith(s + ":") for q in additions)
        final_minimum = self.minimum(E | additions, target)
        assert final_minimum >= d
        key = sha(canonical({"E": sorted(E), "destination": destination}))
        cost = len(additions)
        dist = self.distances(E)
        active = np.flatnonzero(self.relevant[target] & (dist < d))
        if key in self.cache:
            cert = self.cache[key]
            assert cost == cert["certified_minimum_queries"]
            return {"problem_id": key, "witness": sorted(additions), "cost": cost, "final_minimum_distance": final_minimum}
        cert = {
            "problem_id": key, "inherited_coordinates": sorted(E), "destination": destination,
            "inherited_minimum_distance": int(dist[self.relevant[target]].min()),
            "required_distance": d, "active_pair_constraints": int(len(active)),
            "witness": sorted(additions), "witness_verified_with_integer_arithmetic": True,
            "final_minimum_distance": final_minimum, "permission_granted": False,
        }
        if not len(active):
            assert cost == 0
            cert.update(certified_minimum_queries=0, exact_dual_lower_bound="0", certificate_type="NONNEGATIVE_COST_AND_ZERO_FEASIBLE_WITNESS", rational_dual=[])
        else:
            # Retain every distinct allowed coordinate. No equivalence-class
            # column deletion or cap of one query per response pattern occurs.
            candidates = [j for q, j in self.qindex.items() if s + ":" + q not in E]
            A = self.diff[s][active][:, candidates].astype(np.int8)
            needs = (d - dist[active]).astype(np.int64)
            sol = linprog(np.ones(len(candidates)), A_ub=-A, b_ub=-needs, bounds=(0, None), method="highs")
            assert sol.success, sol.message
            y = [max(Fraction(0), Fraction(float(-v)).limit_denominator(1000000)) for v in sol.ineqlin.marginals]
            # Exact arithmetic, not LP tolerance, establishes dual feasibility.
            denom = math.lcm(*(f.denominator for f in y))
            numerators = np.asarray([f.numerator * (denom // f.denominator) for f in y], dtype=object)
            loads = numerators @ A.astype(object)
            maxload = max([int(v) for v in loads] + [denom])
            if maxload > denom:
                y = [f * Fraction(denom, maxload) for f in y]
                denom = math.lcm(*(f.denominator for f in y))
                numerators = np.asarray([f.numerator * (denom // f.denominator) for f in y], dtype=object)
                loads = numerators @ A.astype(object)
            assert all(int(v) <= denom for v in loads)
            lower = sum((f * int(v) for f, v in zip(y, needs)), Fraction(0))
            integer_lower = (lower.numerator + lower.denominator - 1) // lower.denominator
            assert integer_lower == cost, (destination, cost, str(lower), sol.fun)
            cert.update(
                certified_minimum_queries=cost, exact_dual_lower_bound=str(lower),
                certificate_type="EXACT_RATIONAL_DUAL_CEILING_EQUALS_INTEGER_WITNESS",
                allowed_distinct_new_coordinates=len(candidates),
                all_candidate_dual_inequalities_verified=True,
                rational_dual=[{"classes": [self.classes[int(self.i[p])], self.classes[int(self.j[p])]], "residual_distance": int(n), "weight": str(f)} for p, n, f in zip(active, needs, y) if f],
                diagnostic_float_lp_objective=float(sol.fun),
            )
        self.cache[key] = cert
        print(json.dumps({"certified": len(self.cache), "destination": destination, "minimum_queries": cost}), flush=True)
        return {"problem_id": key, "witness": sorted(additions), "cost": cost, "final_minimum_distance": final_minimum}

def main():
    if not __debug__:
        raise RuntimeError("Verification must not run with Python assertion checks disabled.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--atlas", type=Path, required=True)
    ap.add_argument("--predecessor", type=Path, required=True)
    ap.add_argument("--semantics-archive", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    provenance = []
    for name, expected in EXPECTED.items():
        raw = (args.inputs / name).read_bytes()
        assert sha(raw) == expected
        provenance.append({"name": name, "sha256": expected, "bytes": len(raw)})
    assert sha(args.atlas.read_bytes()) == ATLAS_SHA
    with zipfile.ZipFile(args.semantics_archive) as z:
        source = z.read("successive_refinement_decoder.py")
        # Source is archived as evidence; the evaluator above is independent.
        assert b'if mo in {"APPLY", "TOP_2"}' in source
        semantics = {"archive": args.semantics_archive.name, "archive_sha256": sha(args.semantics_archive.read_bytes()), "member": "successive_refinement_decoder.py", "member_sha256": sha(source)}
        (args.output / "original_sensor_semantics.py").write_bytes(source)
    k = json.loads((args.inputs / "cas_constitutional_kernel_v1.json").read_text())
    books = json.loads((args.inputs / "compiled_distance_codebooks.json").read_text())
    F = Family(k, books)
    adjacency = rows((args.inputs / "adjacent_contract_migrations.csv").read_bytes())
    byedge = {(r["source_contract"], r["destination_contract"]): r for r in adjacency}
    assert len(byedge) == len(adjacency) == 96
    def additions(r): return {r["destination_sensor"] + ":" + m for m in json.loads(r["selected_probe_masks"])}
    codebook_checks = []
    for c in books:
        md = F.minimum(F.ledger(c), books[c]["target"])
        assert md >= books[c]["distance"]
        codebook_checks.append({"contract": c, "minimum_distance": md, "satisfies": True})
    direct = []
    for c in books:
        E = F.ledger(c)
        for dst in books:
            md = F.minimum(E, books[dst]["target"])
            direct.append({"source": c, "destination": dst, "minimum_distance": md, "satisfies": md >= books[dst]["distance"]})
    with zipfile.ZipFile(args.predecessor) as z:
        archived_direct = rows(z.read("direct_claim_satisfaction_matrix.csv"))
        counter = json.loads(z.read("label_only_composition_counterexample.json"))
    # Comparison is by contract identity, not file row order.
    published = {(r['source_contract'],r['destination_contract']):r for r in archived_direct}
    assert len(published) == len(direct) == 784
    for r in direct:
        original = published[(r['source'],r['destination'])]
        assert r['minimum_distance'] == int(original['source_min_distance_for_dst_target'])
        assert r['satisfies'] == (original['zero_cost_claim_satisfaction'] == 'True')
    assert sum(x["satisfies"] for x in direct) == 353
    profiles = {tuple(x["satisfies"] for x in direct if x["source"] == c) for c in books}
    assert len(profiles) == 21
    E = F.ledger(counter["initial_actual_evidence_contract"])
    missing_pairs = [[F.classes[int(F.i[p])], F.classes[int(F.j[p])]] for p in np.flatnonzero(F.relevant["EXACT"] & (F.distances(E) == 0))]
    assert missing_pairs == counter["exact_target_pairs_unseparated_by_actual_evidence"]
    adjacent_checks = []
    for r in adjacency:
        proof = F.prove_bridge(F.ledger(r["source_contract"]), r["destination_contract"], additions(r))
        assert proof["cost"] == int(r["additional_queries"])
        adjacent_checks.append({"source": r["source_contract"], "destination": r["destination_contract"], **proof})
    with zipfile.ZipFile(args.atlas) as z:
        archived_loops = rows(z.read("two_edge_loop_monodromy.csv"))
        archived_squares = rows(z.read("migration_square_noncommutativity.csv"))
    loop_checks = []
    for r in archived_loops:
        start, other = r["start_contract"], r["other_contract"]
        E = F.ledger(start)
        a = additions(byedge[(start, other)])
        first = F.prove_bridge(E, other, a)
        # Return inherits the first bridge. The archived loops require zero
        # second-leg evidence; confirm independently against the kernel.
        second = F.prove_bridge(E | a, start, set())
        delta = (E | a) - E
        assert sorted(delta) == json.loads(r["monodromy_coordinates"])
        assert first["cost"] == int(r["first_leg_new"])
        assert second["cost"] == int(r["second_leg_new"])
        assert len(delta) == int(r["evidence_monodromy_size"])
        assert ledger_hash(E) == r["initial_ledger_hash"]
        assert ledger_hash(E | a) == r["final_ledger_hash"]
        loop_checks.append({"start": start, "other": other, "first": first, "return": second, "evidence_delta": sorted(delta), "both_archived_ledger_hashes_match": True})
    square_checks = []
    for r in archived_squares:
        start, mid1, mid2, dst = (r[k] for k in ["source_contract", "intermediate_1", "intermediate_2", "destination_contract"])
        E = F.ledger(start)
        a, b = additions(byedge[(start, mid1)]), additions(byedge[(start, mid2)])
        inherited1, inherited2 = E | a, E | b
        only1, only2 = set(json.loads(r["path1_only"])), set(json.loads(r["path2_only"]))
        assert not only1 & only2
        common = (inherited1 | inherited2) - (only1 | only2)
        missing = int(r["path1_final_ledger_size"]) - len(only1) - len(common)
        assert missing == int(r["path2_final_ledger_size"]) - len(only2) - len(common)
        recovered = []
        if missing:
            assert missing == 1, "Archived differences underdetermine more than one common coordinate."
            sensor = books[dst]["sensor"]
            matches = []
            for mask in F.qindex:
                q = sensor + ":" + mask
                if q in common | only1 | only2: continue
                candidate_common = common | {q}
                if ledger_hash(candidate_common | only1) == r["path1_ledger_hash"] and ledger_hash(candidate_common | only2) == r["path2_ledger_hash"]:
                    matches.append(q)
            assert len(matches) == 1, (start, dst, len(matches))
            recovered = matches
            common |= set(matches)
        final1, final2 = common | only1, common | only2
        assert inherited1 <= final1 and inherited2 <= final2
        assert ledger_hash(final1) == r["path1_ledger_hash"]
        assert ledger_hash(final2) == r["path2_ledger_hash"]
        p11 = F.prove_bridge(E, mid1, a)
        p12 = F.prove_bridge(inherited1, dst, final1 - inherited1)
        p21 = F.prove_bridge(E, mid2, b)
        p22 = F.prove_bridge(inherited2, dst, final2 - inherited2)
        for key, actual in [("path1_first_cost",p11["cost"]),("path1_second_cost",p12["cost"]),("path2_first_cost",p21["cost"]),("path2_second_cost",p22["cost"])]: assert actual == int(r[key])
        cost1, cost2 = p11["cost"] + p12["cost"], p21["cost"] + p22["cost"]
        assert cost1 == int(r["path1_total_cost"]) and cost2 == int(r["path2_total_cost"])
        assert (cost1 == cost2) == (r["cost_commutes"] == "True")
        assert (final1 == final2) == (r["evidence_commutes"] == "True")
        assert len(final1 ^ final2) == int(r["ledger_symmetric_difference"])
        square_checks.append({"source": start, "destination": dst, "intermediate_1":mid1,"intermediate_2":mid2,"path1":[p11,p12],"path2":[p21,p22],"path1_cost":cost1,"path2_cost":cost2,"path1_final_coordinates":sorted(final1),"path2_final_coordinates":sorted(final2),"both_archived_ledger_hashes_match":True,"common_coordinates_recovered_by_exhaustive_hash_match":recovered,"cost_commutes":cost1==cost2,"evidence_commutes":final1==final2})
    certificates = list(F.cache.values())
    cert_raw = json.dumps(certificates, indent=2, sort_keys=True).encode() + b"\n"
    (args.output / "EXACT_BRIDGE_CERTIFICATES.json").write_bytes(cert_raw)
    detailed = {"codebooks":codebook_checks,"direct_satisfaction":direct,"adjacent":adjacent_checks,"loops":loop_checks,"squares":square_checks}
    detail_raw = json.dumps(detailed, indent=2, sort_keys=True).encode() + b"\n"
    (args.output / "FINITE_ATLAS_REPLAY_DETAIL.json").write_bytes(detail_raw)
    result = {
        "schema":"ECH_INDEPENDENT_FINITE_BRIDGE_VERIFICATION_V1",
        "status":"ALL_ARCHIVED_BRIDGE_COSTS_AND_EVIDENCE_SETS_VERIFIED_WITH_EXACT_CERTIFICATES",
        "inputs":provenance,"atlas_sha256":ATLAS_SHA,"predecessor_archive_sha256":sha(args.predecessor.read_bytes()),"sensor_semantics_primary_source":semantics,
        "environment":{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__},
        "script_sha256":sha(Path(__file__).read_bytes()),
        "kernel":{"nodes":len(F.nodes),"jurisdictions":len(k['roots']),"structural_hashes_matched":len(F.structural_hash_checks),"functional_classes":len(F.classes),"admissible_masks":len(F.masks),"projected_classes":{s:len(np.unique(mat,axis=0)) for s,mat in F.matrices.items()}},
        "verified":{"codebooks":len(codebook_checks),"direct_claim_combinations":len(direct),"direct_satisfied":sum(x['satisfies'] for x in direct),"distinct_claim_profiles":len(profiles),"adjacent_transitions":len(adjacent_checks),"two_edge_loops":len(loop_checks),"positive_evidence_loops":sum(bool(x['evidence_delta']) for x in loop_checks),"squares":len(square_checks),"cost_noncommuting_squares":sum(not x['cost_commutes'] for x in square_checks),"evidence_noncommuting_squares":sum(not x['evidence_commutes'] for x in square_checks),"maximum_square_cost_difference":max(abs(x['path1_cost']-x['path2_cost']) for x in square_checks),"maximum_square_symmetric_difference":max(len(set(x['path1_final_coordinates'])^set(x['path2_final_coordinates'])) for x in square_checks),"archive_ledger_hashes_matched":2*len(loop_checks)+2*len(square_checks),"unique_bridge_problems_certified":len(certificates),"positive_cost_rational_certificates":sum(c['certified_minimum_queries']>0 for c in certificates),"zero_cost_integer_certificates":sum(c['certified_minimum_queries']==0 for c in certificates)},
        "recovered_common_coordinates":[{"source":x['source'],"destination":x['destination'],"coordinates":x['common_coordinates_recovered_by_exhaustive_hash_match']} for x in square_checks if x['common_coordinates_recovered_by_exhaustive_hash_match']],
        "exactness":{"arithmetic":"Integer feasibility and Fraction rational dual inequality checks; float LP proposes dual weights only","lower_bound":"ceil(b dot y); all remaining admissible destination-sensor coordinates checked","upper_bound":"Archived distinct-coordinate witness, evaluated independently on every relevant class pair","optimal_probe_identity":"NOT_CLAIMED_UNIQUE; optimal costs do not determine a unique bridge","ledger_serialization":"UTF-8 of sorted sensor:mask coordinates joined with LF, with no trailing LF; independently identified and matched against 238 archived digests","original_generator_recovered":False,"original_solver_cache_recovered":False,"historic_receipt_chains_reconstructed":False,"historic_full_state_hashes_verified":False},
        "scientific_boundaries":["Exact computational audit conditional on frozen finite kernel; no new physical or observational validation.","The 23 squares reproduce archived optimal local witnesses; noncommutativity counts are not proved invariant under alternative optimal tie selections.","Append-only genealogy implies nonreturn of the full state, not a geometrical helix.","No observational readings, synthetic samples, missing receipt values, authority or permissions are manufactured."],
        "permission_granted":False,
        "output_hashes":{"EXACT_BRIDGE_CERTIFICATES.json":sha(cert_raw),"FINITE_ATLAS_REPLAY_DETAIL.json":sha(detail_raw)},
    }
    result["result_sha256"] = sha(canonical(result))
    (args.output / "ECH_EXACT_SUCCESSOR_RESULT.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
