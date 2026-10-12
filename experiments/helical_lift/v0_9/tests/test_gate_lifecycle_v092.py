"""Software-boundary fixtures only: no event observations or scientific eligibility."""
from __future__ import annotations

from argparse import Namespace
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parents[1] / "runtime"
SCRIPT = RUNTIME / "RUN_EXACT_BYTE_TO_BLIND_GATE_V0_9.py"
sys.path.insert(0, str(RUNTIME))
SPEC = importlib.util.spec_from_file_location("gate_lifecycle_under_test", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class GateLifecycleTests(unittest.TestCase):
    def dry_run(self, workspace: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(workspace), "--purge-raw-after-gate"],
            capture_output=True, text=True, check=False,
        )

    def test_rerun_continues_chain_and_preserves_previous_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.assertEqual(self.dry_run(workspace).returncode, 4)
            receipts = workspace / "receipts"
            previous_bytes = (receipts / "GATE_EXECUTION_RECEIPT_V0_9.json").read_bytes()
            previous = json.loads(previous_bytes)
            (receipts / "RUNTIME_ENVIRONMENT.json").write_text('{"fixture":"current preflight"}')
            self.assertEqual(self.dry_run(workspace).returncode, 4)
            count, _ = gate.validate_transition_chain(receipts / "STATE_TRANSITIONS_V0_9.jsonl")
            self.assertEqual(count, 4)
            archive = receipts / "history" / previous["execution_id"]
            self.assertEqual((archive / "GATE_EXECUTION_RECEIPT_V0_9.json").read_bytes(), previous_bytes)
            self.assertTrue((archive / "ACQUISITION_ATTEMPT_V0_9.json").is_file())
            self.assertTrue((archive / "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json").is_file())
            self.assertTrue((archive / "logs" / "01_acquisition.stdout.txt").is_file())
            self.assertTrue((receipts / "RUNTIME_ENVIRONMENT.json").is_file())
            cleanup = json.loads((receipts / "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json").read_text())
            self.assertEqual(cleanup["status"], "PASS")
            self.assertTrue(cleanup["complete_gate_receipt_available"])
            self.assertFalse((workspace / "cache").exists())

    def test_corrupt_chain_blocks_work_and_finally_purges_on_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            self.assertEqual(self.dry_run(workspace).returncode, 4)
            for name in ("cache", ".exact_sources_v09.software_fixture"):
                (workspace / name).mkdir()
                (workspace / name / "data").write_text("software boundary fixture")
            chain = workspace / "receipts" / "STATE_TRANSITIONS_V0_9.jsonl"
            rows = chain.read_text().splitlines()
            first = json.loads(rows[0])
            first["state"] = "CORRUPTED_SOFTWARE_FIXTURE"
            rows[0] = json.dumps(first)
            chain.write_text("\n".join(rows) + "\n")
            result = self.dry_run(workspace)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid transition chain", result.stderr)
            self.assertEqual(len(chain.read_text().splitlines()), 2)
            self.assertFalse((workspace / "cache").exists())
            self.assertFalse((workspace / ".exact_sources_v09.software_fixture").exists())
            cleanup = json.loads((workspace / "receipts" / "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json").read_text())
            self.assertEqual(cleanup["status"], "PASS")
            self.assertFalse(cleanup["complete_gate_receipt_available"])

    def test_stale_pass_cannot_override_failure_or_hold(self) -> None:
        # The mocked subprocess never runs extraction, eligibility, or unsealing.
        for returncode, corrupt_hold, expected in ((1, False, 21), (31, False, 31), (31, True, 21), (0, False, 21)):
            with self.subTest(returncode=returncode, corrupt_hold=corrupt_hold), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                for name in ("exact_sources", "blind", "eligibility", "receipts"):
                    (workspace / name).mkdir()
                acquisition = {
                    "outcome": "EXACT_BYTE_ACQUISITION_PASS", "receipt_id": "software-acquisition",
                    "source_receipts": {"mechanism": {"sha256": "a" * 64}, "fault": {"sha256": "c" * 64, "git_blob_sha1": "d" * 40}},
                }
                extraction = {"receipt_id": "software-extraction", "output_sha256": "b" * 64}
                verification = {"receipt_id": "software-verification"}
                (workspace / "exact_sources" / "ACQUISITION_RECEIPT_V0_9.json").write_text(json.dumps(acquisition))
                (workspace / "blind" / "EXTRACTION_RECEIPT_V0_9.json").write_text(json.dumps(extraction))
                (workspace / "blind" / "SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json").write_text(json.dumps(verification))
                stale = workspace / "eligibility" / "BLIND_ELIGIBILITY_RESULT_V0_9.json"
                stale.write_text('{"outcome":"ELIGIBILITY_PASS","fixture":"stale software output"}')

                def mocked_step(name, *unused, **kwargs):
                    if name == "01_acquisition":
                        attempt = {"outcome": "EXACT_BYTE_ACQUISITION_PASS", "receipt_id": "software-attempt"}
                        (workspace / "receipts" / "ACQUISITION_ATTEMPT_V0_9.json").write_text(json.dumps(attempt))
                        return {"name": name, "returncode": 0}
                    self.assertEqual(name, "03_blind_eligibility", "Must never prepare an unseal request for failure/HOLD")
                    self.assertFalse(stale.exists(), "Prior PASS must be quarantined before subprocess execution")
                    if returncode == 31:
                        hold = {
                            "format": "KCH_HELICAL_BLIND_INPUT_SEMANTIC_HOLD_V0_9_2",
                            "outcome": "BLOCKED_UNCERTIFIED_EVENT_TYPE_ENCODING", "protocol_id": gate.PROTOCOL_ID,
                            "source_sha256": "a" * 64, "safe_npz_sha256": "wrong" if corrupt_hold else "b" * 64,
                            "scientific_eligibility_executed": False, "directional_fields_unsealed": False,
                            "model_fitting_performed": False, "authority_ceiling": "NONE",
                        }
                        hold["receipt_id"] = gate.content_id("h9semantichold", hold)
                        (workspace / "eligibility" / "BLIND_INPUT_SEMANTIC_HOLD_V0_9_2.json").write_text(json.dumps(hold))
                    return {"name": name, "returncode": returncode}

                args = Namespace(workspace=workspace, execute_network=False, network_timeout_seconds=1,
                                 sandbox_timeout_seconds=1, sandbox_memory_mib=1, purge_raw_after_gate=True,
                                 execution_id="software-fixture-run")
                with patch.object(gate, "run_step", mocked_step), patch.object(gate, "blind_outputs_valid", lambda *args: True), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(gate._run_gate(args), expected)
                archives = list((workspace / "quarantine").glob("eligibility.*"))
                self.assertEqual(len(archives), 1)
                self.assertTrue((archives[0] / stale.name).is_file())
                receipt = json.loads((workspace / "receipts" / "GATE_EXECUTION_RECEIPT_V0_9.json").read_text())
                gate.verify_content_id(receipt, "gate_receipt_id", "h9gate")

    def test_transition_rejects_wrong_predecessor_and_reserved_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "chain.jsonl"
            tail = gate.append_transition(path, {"state": "SOFTWARE_FIXTURE"}, None)
            with self.assertRaises(ValueError):
                gate.append_transition(path, {"state": "INVALID"}, None)
            with self.assertRaises(ValueError):
                gate.append_transition(path, {"sequence": 2, "state": "INVALID"}, tail)
            self.assertEqual(gate.validate_transition_chain(path), (1, tail))


if __name__ == "__main__":
    unittest.main()
