from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_paper_results as exporter  # noqa: E402


SOURCE_RECORDS = (
    REPO_ROOT.parent
    / "agent-bench"
    / "baseline_results"
    / "rcta_clean_prompt_deepseek_v4_flash_20260731"
    / "final_evaluation_results"
    / "records.tsv"
)


class ExportPaperResultsTest(unittest.TestCase):
    def test_normalize_role_only_removes_explicit_handoff_suffix(self) -> None:
        self.assertEqual(
            "diagnostagent",
            exporter.normalize_role("  DiagnostAgent (-> ActionAgent)  "),
        )
        self.assertEqual(
            "diagnostagent",
            exporter.normalize_role("DiagnostAgent (→ JudgeAgent)"),
        )
        self.assertEqual("planner (review)", exporter.normalize_role("Planner (Review)"))

    def test_explicit_predicted_agent_is_scored_independently(self) -> None:
        fields = [
            "method",
            "method_label",
            "benchmark",
            "qid",
            "predicted_agent",
            "predicted_role_derived",
            "ground_truth_agent",
            "step_exact",
            "step_within_5",
            "step_abs_err",
            "step_valid",
            "failed",
        ]
        row = {
            "method": "agent_error_trajectory_analysis",
            "method_label": "RCTA",
            "benchmark": "swe_bench_pro",
            "qid": "sample-1",
            "predicted_agent": "CorrectRole",
            "predicted_role_derived": "WrongRole",
            "ground_truth_agent": "CorrectRole",
            "step_exact": "True",
            "step_within_5": "True",
            "step_abs_err": "0",
            "step_valid": "True",
            "failed": "False",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.tsv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
                writer.writeheader()
                writer.writerow(row)

            result = exporter.build_leaderboard(path, expected_n=None)

        self.assertEqual(1, result["results"][0]["role_correct"])

    @unittest.skipUnless(
        SOURCE_RECORDS.is_file(),
        "canonical source records are available only in the local research workspace",
    )
    def test_canonical_records_reproduce_paper_table(self) -> None:
        payload = exporter.build_leaderboard(SOURCE_RECORDS)
        results = payload["results"]

        self.assertEqual(
            [
                "RCTA",
                "ECHO",
                "All-at-once",
                "Step-by-step",
                "Binary search",
                "FALAT",
            ],
            [row["method"] for row in results],
        )
        expected = {
            "RCTA": (583, 275, 426, 38.6),
            "ECHO": (314, 150, 282, 50.4),
            "All-at-once": (299, 87, 227, 55.9),
            "Step-by-step": (253, 60, 193, 52.3),
            "Binary search": (262, 39, 152, 61.7),
            "FALAT": (217, 32, 142, 66.6),
        }
        expected_display = {
            "RCTA": ("RCTA", "LongRCA", "https://arxiv.org/abs/2608.15242"),
            "ECHO": ("ECHO", "ECHO", "https://arxiv.org/abs/2510.04886"),
            "All-at-once": (
                "LLM-as-a-Judge / All-at-once",
                "Who&When",
                "https://proceedings.mlr.press/v267/zhang25cq.html",
            ),
            "Step-by-step": (
                "LLM-as-a-Judge / Step-by-step",
                "Who&When",
                "https://proceedings.mlr.press/v267/zhang25cq.html",
            ),
            "Binary search": (
                "Binary search",
                "Who&When",
                "https://proceedings.mlr.press/v267/zhang25cq.html",
            ),
            "FALAT": ("FALAT", "FALAT", "https://arxiv.org/abs/2606.00765"),
        }
        for row in results:
            role, exact, within_five, mae = expected[row["method"]]
            with self.subTest(method=row["method"]):
                self.assertEqual(1140, row["n"])
                self.assertEqual(role, row["role_correct"])
                self.assertEqual(exact, row["root_exact_correct"])
                self.assertEqual(within_five, row["root_within_5_correct"])
                self.assertEqual(mae, round(row["root_mae"], 1))
                self.assertEqual("DeepSeek-V4-Flash", row["model"])
                self.assertEqual("DeepSeek", row["provider"])
                self.assertEqual("Paper Result", row["status"])
                display_name, citation_label, paper_url = expected_display[row["method"]]
                self.assertEqual(display_name, row["display_name"])
                self.assertEqual(citation_label, row["citation_label"])
                self.assertEqual(paper_url, row["links"]["paper"])

        self.assertEqual(
            [
                ("swe_bench_pro", "SWE-bench Pro", 128),
                ("terminal_bench_2", "Terminal-Bench 2", 42),
                ("travelplanner", "TravelPlanner", 685),
                ("vitabench", "VitaBench", 108),
                ("webarena_verified", "WebArena", 177),
            ],
            [
                (item["id"], item["label"], item["n"])
                for item in payload["benchmark_slices"]
            ],
        )
        expected_exact = {
            "RCTA": [49, 11, 129, 27, 59],
            "ECHO": [10, 9, 61, 24, 46],
            "All-at-once": [2, 3, 31, 21, 30],
            "Step-by-step": [1, 2, 24, 13, 20],
            "Binary search": [1, 2, 14, 13, 9],
            "FALAT": [3, 1, 20, 4, 4],
        }
        slice_ids = [item["id"] for item in payload["benchmark_slices"]]
        for row in results:
            with self.subTest(method=row["method"], metric="per-benchmark exact"):
                self.assertEqual(
                    expected_exact[row["method"]],
                    [row["by_benchmark"][slice_id]["root_exact_correct"] for slice_id in slice_ids],
                )


if __name__ == "__main__":
    unittest.main()
