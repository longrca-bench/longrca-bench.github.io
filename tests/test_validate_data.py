from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_data as validator  # noqa: E402


class ValidateDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(
            (REPO_ROOT / "data" / "leaderboard.json").read_text(encoding="utf-8")
        )

    def test_current_leaderboard_is_valid(self) -> None:
        validator.validate_leaderboard(self.payload)

    def test_checked_in_rows_match_the_paper_table(self) -> None:
        expected = [
            ("RCTA", 583, 275, 426, 38.6),
            ("ECHO", 314, 150, 282, 50.4),
            ("All-at-once", 299, 87, 227, 55.9),
            ("Step-by-step", 253, 60, 193, 52.3),
            ("Binary search", 262, 39, 152, 61.7),
            ("FALAT", 217, 32, 142, 66.6),
        ]
        actual = [
            (
                row["method"],
                row["role_correct"],
                row["root_exact_correct"],
                row["root_within_5_correct"],
                round(row["root_mae"], 1),
            )
            for row in self.payload["results"]
        ]
        self.assertEqual(expected, actual)

    def test_duplicate_id_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][1]["id"] = payload["results"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate result id"):
            validator.validate_leaderboard(payload)

    def test_out_of_range_count_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["role_correct"] = 1141
        with self.assertRaisesRegex(ValueError, "role_correct"):
            validator.validate_leaderboard(payload)

    def test_wrong_rank_order_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"] = list(reversed(payload["results"]))
        with self.assertRaisesRegex(ValueError, "Root Exact descending"):
            validator.validate_leaderboard(payload)

    def test_empty_model_provider_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["provider"] = "   "
        with self.assertRaisesRegex(ValueError, "provider must be non-empty"):
            validator.validate_leaderboard(payload)

    def test_missing_citation_metadata_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][0].pop("citation_label", None)
        with self.assertRaisesRegex(ValueError, "citation_label"):
            validator.validate_leaderboard(payload)

    def test_noncanonical_method_paper_link_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][1]["links"]["paper"] = payload["paper_url"]
        with self.assertRaisesRegex(ValueError, "paper citation"):
            validator.validate_leaderboard(payload)

    def test_benchmark_slice_total_mismatch_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["by_benchmark"]["swe_bench_pro"]["n"] = 127
        with self.assertRaisesRegex(ValueError, "swe_bench_pro"):
            validator.validate_leaderboard(payload)

    def test_forbidden_gold_or_prediction_fields_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["results"][0]["ground_truth_step"] = 12
        with self.assertRaisesRegex(ValueError, "forbidden field"):
            validator.validate_leaderboard(payload)

    def test_exporter_contract_forbids_step_derived_role_access(self) -> None:
        validator.validate_exporter_contract(REPO_ROOT / "scripts" / "export_paper_results.py")

        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad_exporter.py"
            bad.write_text(
                "def score(row):\n"
                "    return row['predicted_role_derived'] == row['ground_truth_agent']\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "predicted_role_derived"):
                validator.validate_exporter_contract(bad)

    def test_site_and_repository_safety_contracts_are_valid(self) -> None:
        validator.validate_site(REPO_ROOT)
        validator.validate_repository_safety(REPO_ROOT)

    def test_absolute_local_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "unsafe.md").write_text(
                "local artifact at " + "/".join(["", "Users", "alice", "secret.json"]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "absolute local path"):
                validator.validate_repository_safety(root)

    def test_secret_like_token_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            token = "ghp" + "_" + ("a" * 32)
            (root / "unsafe.txt").write_text(token, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "secret-like token"):
                validator.validate_repository_safety(root)


if __name__ == "__main__":
    unittest.main()
