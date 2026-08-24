from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTest(unittest.TestCase):
    def test_contributing_guide_defines_reviewed_pr_submission(self) -> None:
        guide = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for token in (
            "metadata.json",
            "predictions.jsonl",
            "REPRODUCE.md",
            "question_ID",
            "predicted_role",
            "predicted_step",
            "1,140",
            "pull request",
            "maintainer",
            "external",
        ):
            self.assertIn(token, guide)

    def test_pages_workflow_uses_official_actions_and_permissions(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        for token in (
            "actions/configure-pages@v5",
            "actions/upload-pages-artifact@v4",
            "actions/deploy-pages@v4",
            "contents: read",
            "pages: write",
            "id-token: write",
            "environment:",
            "github-pages",
        ):
            self.assertIn(token, workflow)
        self.assertIn("node --check assets/trajectory.js", workflow)

    def test_ci_runs_data_tests_and_javascript_check(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pull_request:", workflow)
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("python scripts/validate_data.py", workflow)
        self.assertIn("node --check assets/app.js", workflow)
        self.assertIn("node --check assets/trajectory.js", workflow)

    def test_public_json_schema_documents_count_based_rows(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "data" / "leaderboard.schema.json").read_text(
                encoding="utf-8"
            )
        )
        result_fields = schema["$defs"]["result"]["properties"]
        self.assertIn("benchmark_slices", schema["properties"])
        self.assertIn("by_benchmark", result_fields)
        self.assertIn("provider", result_fields)
        for field in (
            "role_correct",
            "root_exact_correct",
            "root_within_5_correct",
            "root_mae",
            "valid_step_n",
            "failed_n",
        ):
            self.assertIn(field, result_fields)
        for forbidden_duplicate in ("role_accuracy", "root_exact", "root_within_5"):
            self.assertNotIn(forbidden_duplicate, result_fields)

    def test_readme_has_live_resource_links(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for url in (
            "https://longrca-bench.github.io/",
            "https://arxiv.org/abs/2608.15242",
            "https://huggingface.co/datasets/CLoud5-real/longrca-bench",
            "https://github.com/longrca-bench/longrca-bench.github.io",
        ):
            self.assertIn(url, readme)


if __name__ == "__main__":
    unittest.main()
