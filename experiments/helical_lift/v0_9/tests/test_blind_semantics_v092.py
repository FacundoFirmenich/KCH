"""Software-only boundary fixtures; never scientific observations or eligibility."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runtime"))
from blind_semantics_v092 import inspect_blind_inputs
from RUN_BLIND_ELIGIBILITY_SAFE_NPZ_V0_9 import verify_receipt_id
from common_v09 import content_id


def columns(label="earthquake"):
    values = dict(year=2000, month=1, day=1, hour=0, minute=0, second=0,
                  lat_reloc=0, lon_reloc=0, dep_reloc=0, mag=0, uncer=0,
                  npol=0, prob=0, evid="software-test", nc_sc=1, time_utc=0, ev_bl=label)
    return {name: np.asarray([value]) for name, value in values.items()}


class BlindInputBoundaryTests(unittest.TestCase):
    def test_explicit_labels_match_frozen_operator_domain(self):
        for label in ("earthquake", "Earthquake", "blast", "BLAST", "b", "B"):
            with self.subTest(label=label):
                self.assertEqual(inspect_blind_inputs(columns(label), 1)["status"], "PASS")

    def test_unknown_labels_fail_closed_including_numeric_strings(self):
        for label in ("0", "1", "0.0", "1.0", "unknown", "", " blast ", "e", "eq", 0, 1, True):
            with self.subTest(label=label):
                result = inspect_blind_inputs(columns(label), 1)
                self.assertIn("UNCERTIFIED_EVENT_TYPE_ENCODING", result["issues"])
                self.assertEqual(result["status"], "HOLD")

    def test_vector_length_mismatch_blocks_before_selection(self):
        data = columns()
        data["evid"] = np.array([], dtype=str)
        self.assertEqual(inspect_blind_inputs(data, 1)["issues"], ["EVENT_VECTOR_LENGTH_MISMATCH"])

    def test_nonfinite_and_fractional_calendar_values_are_not_imputed(self):
        for name, value, expected in (("year", 2000.5, "NONINTEGRAL_FIELD:year"),
                                      ("prob", np.nan, "INVALID_NUMERIC_FIELD:prob"),
                                      ("second", 60, "UNCERTIFIED_SECOND_RANGE")):
            data = columns()
            data[name] = np.array([value])
            result = inspect_blind_inputs(data, 1)
            self.assertIn(expected, result["issues"])
            self.assertEqual(result["values_imputed"], 0)

    def test_impossible_calendar_date_blocks(self):
        data = columns()
        data["month"] = np.array([2])
        data["day"] = np.array([30])
        self.assertIn("INVALID_CALENDAR_COMPONENTS", inspect_blind_inputs(data, 1)["issues"])

    def test_tampered_receipt_rejected(self):
        data = {"status": "PASS"}
        data["receipt_id"] = content_id("h9npz", data)
        verify_receipt_id(data, "h9npz")
        data["status"] = "HOLD"
        with self.assertRaises(SystemExit):
            verify_receipt_id(data, "h9npz")


if __name__ == "__main__":
    unittest.main()
