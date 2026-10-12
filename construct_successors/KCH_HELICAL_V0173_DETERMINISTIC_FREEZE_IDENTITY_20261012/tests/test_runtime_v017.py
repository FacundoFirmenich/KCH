from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kch_helical_null_v017.runtime import (  # noqa: E402
    COHORTS,
    EXPECTED_JOB_COUNT,
    HISTORICAL_LEDGER_ID,
    HISTORICAL_LEDGER_SHA256,
    HISTORICAL_RUNTIME_CONTRACT_ID,
    NULL_FAMILIES,
    OPERATOR_BINDINGS,
    PROTOCOL_ID,
    QUALIFICATION_FAIL_CLOSED,
    QUALIFICATION_NOT_EXECUTED,
    QUALIFICATION_PASS,
    STAGE_COUNTS,
    STATUS_FAIL_CLOSED,
    STATUS_PASS,
    build_job_ledger,
    canonical_json_bytes,
    content_id,
    not_run_records,
    qualification_status,
    runtime_contract,
    stable_seed,
    validate_job_ledger,
)

PARENT = "h8parent:f61e9b60c455e75e53f16b9579cd085b68de20d810f05165504f91ab09d400cb"
LOCATION = "h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5"


def jobs():
    return build_job_ledger(
        protocol_id=PROTOCOL_ID,
        parent_graph_lock_id=PARENT,
        location_operator_id=LOCATION,
    )


def structural_pass_records(ledger):
    records = []
    for job in ledger:
        input_hash = hashlib.sha256(("input:" + job["job_id"]).encode()).hexdigest()
        output_hash = hashlib.sha256(("output:" + job["job_id"]).encode()).hexdigest()
        records.append(
            {
                "job_id": job["job_id"],
                "seed": job["seed"],
                "runtime_contract_id": job["runtime_contract_id"],
                "protocol_id": job["protocol_id"],
                "stage": job["stage"],
                "cohort": job["cohort"],
                "family": job["family"],
                "replicate": job["replicate"],
                "status": STATUS_PASS,
                "input_hashes": {"structural_fixture": input_hash},
                "output_sha256": output_hash,
                "operator_diagnostics": {
                    "structural_fixture_only": True,
                    "scientific_execution": False,
                },
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        )
    return records


class RuntimeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = runtime_contract(
            protocol_id=PROTOCOL_ID,
            parent_graph_lock_id=PARENT,
            location_operator_id=LOCATION,
        )
        cls.jobs = jobs()

    def test_001_contract_identity_is_new(self):
        self.assertTrue(self.contract["contract_id"].startswith("h17nullspec:"))
        self.assertNotEqual(self.contract["contract_id"], HISTORICAL_RUNTIME_CONTRACT_ID)

    def test_002_historical_identity_transfer_forbidden(self):
        self.assertEqual(
            self.contract["derivation_basis"]["historical_identity_transfer"],
            "FORBIDDEN",
        )

    def test_003_protocol_reference_exact(self):
        self.assertEqual(self.contract["derivation_basis"]["protocol_id"], PROTOCOL_ID)

    def test_004_historical_ledger_reference_exact(self):
        self.assertEqual(self.contract["derivation_basis"]["historical_ledger_id"], HISTORICAL_LEDGER_ID)
        self.assertEqual(
            self.contract["derivation_basis"]["historical_ledger_sha256"],
            HISTORICAL_LEDGER_SHA256,
        )

    def test_005_job_census_exact(self):
        self.assertEqual(self.contract["job_count"], 6376)
        self.assertEqual(self.contract["job_census"], dict(STAGE_COUNTS))

    def test_006_five_null_families_exact(self):
        self.assertEqual(tuple(self.contract["null_families"]), NULL_FAMILIES)

    def test_007_all_null_families_bound(self):
        self.assertTrue(set(NULL_FAMILIES).issubset(OPERATOR_BINDINGS))
        for family in NULL_FAMILIES:
            self.assertTrue(OPERATOR_BINDINGS[family])

    def test_008_test_access_forbidden(self):
        self.assertEqual(self.contract["sealed_test_access"], "FORBIDDEN")

    def test_009_promotion_blocked(self):
        self.assertEqual(self.contract["promotion"], "BLOCKED")
        self.assertEqual(self.contract["canonicalization"], "BLOCKED")

    def test_010_no_scientific_result(self):
        self.assertIsNone(self.contract["scientific_result"])
        self.assertEqual(self.contract["physical_helicity"], "NOT_EVALUATED")

    def test_011_canonical_json_is_order_invariant(self):
        self.assertEqual(canonical_json_bytes({"b": 2, "a": 1}), canonical_json_bytes({"a": 1, "b": 2}))

    def test_012_content_id_changes_with_content(self):
        self.assertNotEqual(content_id("test", {"a": 1}), content_id("test", {"a": 2}))

    def test_013_seed_is_deterministic(self):
        self.assertEqual(stable_seed({"a": 1}), stable_seed({"a": 1}))

    def test_014_seed_is_positive_63_bit(self):
        seed = stable_seed({"a": 1})
        self.assertGreater(seed, 0)
        self.assertLess(seed, 1 << 63)

    def test_015_wrong_cohorts_fail_closed(self):
        with self.assertRaises(ValueError):
            runtime_contract(
                protocol_id=PROTOCOL_ID,
                parent_graph_lock_id=PARENT,
                location_operator_id=LOCATION,
                cohorts=(COHORTS[0],),
            )


class LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = jobs()
        cls.contract_id = cls.jobs[0]["runtime_contract_id"]

    def test_016_total_job_count(self):
        self.assertEqual(len(self.jobs), EXPECTED_JOB_COUNT)

    def test_017_unique_job_ids(self):
        self.assertEqual(len({job["job_id"] for job in self.jobs}), EXPECTED_JOB_COUNT)

    def test_018_unique_seeds(self):
        self.assertEqual(len({job["seed"] for job in self.jobs}), EXPECTED_JOB_COUNT)

    def test_019_repeatability(self):
        self.assertEqual(self.jobs, jobs())

    def test_020_stage_counts(self):
        report = validate_job_ledger(self.jobs, expected_contract_id=self.contract_id)
        self.assertEqual(report["stage_counts"], dict(STAGE_COUNTS))

    def test_021_null_family_counts(self):
        report = validate_job_ledger(self.jobs, expected_contract_id=self.contract_id)
        self.assertEqual(report["null_family_counts"], {family: 398 for family in NULL_FAMILIES})

    def test_022_all_jobs_use_train_calibration_only(self):
        self.assertTrue(all(job["allowed_partitions"] == ["TRAIN", "CALIBRATION"] for job in self.jobs))

    def test_023_no_job_allows_test(self):
        self.assertTrue(all(job["sealed_test_access"] == "FORBIDDEN" for job in self.jobs))

    def test_024_no_job_has_scientific_result(self):
        self.assertTrue(all(job["scientific_result"] is None for job in self.jobs))

    def test_025_job_ids_are_v017(self):
        self.assertTrue(all(job["job_id"].startswith("h17job:") for job in self.jobs))

    def test_026_contract_id_is_consistent(self):
        self.assertEqual({job["runtime_contract_id"] for job in self.jobs}, {self.contract_id})

    def test_027_null_jobs_have_operator_bindings(self):
        selected = [job for job in self.jobs if job["stage"] == "NULL_CALIBRATION_REPLICATE"]
        self.assertTrue(selected)
        self.assertTrue(all(job["operator_binding"] for job in selected))

    def test_028_holm_depends_on_observed_and_null(self):
        job = next(job for job in self.jobs if job["stage"] == "HOLM_MULTIPLICITY_AGGREGATION")
        self.assertEqual(
            job["dependency_selector"],
            [
                {"stage": "OBSERVED_CALIBRATION_SCORE", "cohort": "*"},
                {"stage": "NULL_CALIBRATION_REPLICATE", "cohort": "*"},
            ],
        )

    def test_029_adjudication_is_last(self):
        self.assertEqual(self.jobs[-1]["stage"], "RUNTIME_QUALIFICATION_ADJUDICATION")

    def test_030_tampered_contract_fails_validation(self):
        broken = copy.deepcopy(self.jobs)
        broken[0]["runtime_contract_id"] = "tampered"
        with self.assertRaises(ValueError):
            validate_job_ledger(broken, expected_contract_id=self.contract_id)

    def test_031_duplicate_seed_fails_validation(self):
        broken = copy.deepcopy(self.jobs)
        broken[1]["seed"] = broken[0]["seed"]
        with self.assertRaises(ValueError):
            validate_job_ledger(broken, expected_contract_id=self.contract_id)

    def test_032_missing_job_fails_validation(self):
        with self.assertRaises(ValueError):
            validate_job_ledger(self.jobs[:-1], expected_contract_id=self.contract_id)


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = jobs()
        cls.not_run = not_run_records(cls.jobs)
        cls.passing = structural_pass_records(cls.jobs)

    def test_033_all_not_run_is_not_executed(self):
        result = qualification_status(self.jobs, self.not_run)
        self.assertEqual(result["outcome"], QUALIFICATION_NOT_EXECUTED)

    def test_034_all_structural_pass_is_pass(self):
        result = qualification_status(self.jobs, self.passing)
        self.assertEqual(result["outcome"], QUALIFICATION_PASS)

    def test_035_missing_record_fails_closed(self):
        result = qualification_status(self.jobs, self.not_run[:-1])
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)

    def test_036_duplicate_record_fails_closed(self):
        broken = copy.deepcopy(self.not_run)
        broken[-1] = copy.deepcopy(broken[0])
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)

    def test_037_seed_tamper_fails_closed(self):
        broken = copy.deepcopy(self.not_run)
        broken[0]["seed"] += 1
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)
        self.assertEqual(result["reason"], "RESULT_IDENTITY_MISMATCH")

    def test_038_test_access_fails_closed(self):
        broken = copy.deepcopy(self.not_run)
        broken[0]["sealed_test_accessed"] = True
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)
        self.assertEqual(result["reason"], "SEALED_TEST_FIREWALL_VIOLATION")

    def test_039_scientific_result_fails_closed(self):
        broken = copy.deepcopy(self.not_run)
        broken[0]["scientific_result"] = {"forbidden": True}
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)

    def test_040_explicit_fail_closed_propagates(self):
        broken = copy.deepcopy(self.not_run)
        broken[0]["status"] = STATUS_FAIL_CLOSED
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)
        self.assertEqual(result["reason"], "ONE_OR_MORE_JOBS_FAIL_CLOSED")

    def test_041_pass_without_hashes_fails_closed(self):
        broken = copy.deepcopy(self.passing)
        broken[0]["input_hashes"] = {}
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)

    def test_042_pass_with_bad_output_hash_fails_closed(self):
        broken = copy.deepcopy(self.passing)
        broken[0]["output_sha256"] = "bad"
        result = qualification_status(self.jobs, broken)
        self.assertEqual(result["outcome"], QUALIFICATION_FAIL_CLOSED)

    def test_043_mixed_pass_not_run_is_not_executed(self):
        mixed = copy.deepcopy(self.passing)
        mixed[0] = copy.deepcopy(self.not_run[0])
        result = qualification_status(self.jobs, mixed)
        self.assertEqual(result["outcome"], QUALIFICATION_NOT_EXECUTED)

    def test_044_structural_fixture_never_claims_science(self):
        self.assertTrue(all(record["scientific_result"] is None for record in self.passing))
        self.assertTrue(all(record["operator_diagnostics"]["scientific_execution"] is False for record in self.passing))


if __name__ == "__main__":
    unittest.main(verbosity=2)
