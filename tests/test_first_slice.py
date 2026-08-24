from __future__ import annotations

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_URL = "https://arxiv.org/abs/2608.15242"
DATASET_URL = "https://huggingface.co/datasets/CLoud5-real/longrca-bench"
GITHUB_URL = "https://github.com/longrca-bench/longrca-bench.github.io"


class FirstSliceTest(unittest.TestCase):
    def test_hero_stats_and_leaderboard_surface_exist(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            "Pinpointing Error Steps in Long-Horizon Agent Failures.",
            html,
        )
        self.assertIn(
            "1,140 trajectories · 5 benchmarks · exact failure-step attribution.",
            html,
        )
        self.assertNotIn("Long-Horizon Root-Cause Localization.", html)
        self.assertNotIn("Diagnosing <em>who</em>", html)
        self.assertNotIn(">Who?<", html)
        self.assertNotIn(">When?<", html)
        for url in (PAPER_URL, DATASET_URL):
            self.assertIn(url, html)
        for anchor in ("overview", "leaderboard"):
            self.assertIn(f'id="{anchor}"', html)
        self.assertIn('id="benchmark-stats"', html)
        self.assertIn('id="leaderboard-body"', html)
        self.assertIn('href="assets/styles.css"', html)
        self.assertIn('src="assets/app.js"', html)

    def test_hero_dataset_action_uses_download_label(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            f'href="{PAPER_URL}"><img class="resource-icon" '
            'src="assets/icons/arxiv.svg" alt="">Read the Paper</a>',
            html,
        )
        self.assertIn(
            f'href="{DATASET_URL}"><img class="resource-icon" '
            'src="assets/icons/huggingface.svg" alt="">Download the Dataset</a>',
            html,
        )

    def test_hero_resource_links_have_local_icons(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        for icon in ("arxiv.svg", "huggingface.svg"):
            relative_path = f"assets/icons/{icon}"
            self.assertIn(f'src="{relative_path}"', html)
            self.assertTrue((REPO_ROOT / relative_path).is_file())

    def test_resource_icons_preserve_brand_colors(self) -> None:
        expected_colors = {
            "arxiv.svg": "#B31B1B",
            "huggingface.svg": "#FFD21E",
            "github.svg": "#181717",
        }
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        for icon, expected_color in expected_colors.items():
            with self.subTest(icon=icon):
                root = ET.parse(REPO_ROOT / "assets" / "icons" / icon).getroot()
                paths = root.findall(".//svg:path", namespace)
                self.assertTrue(paths)
                self.assertEqual(
                    {expected_color},
                    {path.get("fill") for path in paths},
                )

    def test_code_repository_is_not_advertised_as_a_project_resource(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        hero_start = html.index('<div class="hero-actions"')
        hero_end = html.index("</div>", hero_start)
        footer_start = html.index('<footer class="footer">')
        hero_actions = html[hero_start:hero_end]
        footer = html[footer_start:]

        self.assertNotIn(GITHUB_URL, hero_actions)
        self.assertNotIn(f'href="{GITHUB_URL}"', footer)
        self.assertNotIn("github.svg", hero_actions)

    def test_submission_guide_remains_available_for_leaderboard_prs(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(
            f'href="{GITHUB_URL}/blob/main/CONTRIBUTING.md"',
            html,
        )

    def test_leaderboard_is_method_first_and_step_exact_focused(self) -> None:
        html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        headers = [
            "Method",
            "Overall",
            "SWE-bench Pro",
            "Terminal-Bench 2",
            "TravelPlanner",
            "VitaBench",
            "WebArena",
        ]
        positions = [html.index(f">{header}<") for header in headers]
        self.assertEqual(sorted(positions), positions)
        table_head = html[html.index("<thead>") : html.index("</thead>")]
        self.assertNotIn(">Model<", table_head)
        self.assertNotIn(">Role Acc.<", table_head)
        self.assertNotIn(">Root ±5<", table_head)
        self.assertNotIn(">Root MAE ↓<", table_head)

    def test_leaderboard_uses_method_citations_and_equipped_model_subline(self) -> None:
        payload = json.loads(
            (REPO_ROOT / "data" / "leaderboard.json").read_text(encoding="utf-8")
        )
        expected = {
            "RCTA": (
                "RCTA",
                "LongRCA",
                "https://arxiv.org/abs/2608.15242",
            ),
            "ECHO": (
                "ECHO",
                "ECHO",
                "https://arxiv.org/abs/2510.04886",
            ),
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
            "FALAT": (
                "FALAT",
                "FALAT",
                "https://arxiv.org/abs/2606.00765",
            ),
        }
        self.assertEqual(set(expected), {row["method"] for row in payload["results"]})
        for row in payload["results"]:
            with self.subTest(method=row["method"]):
                display_name, citation_label, paper_url = expected[row["method"]]
                self.assertEqual(display_name, row["display_name"])
                self.assertEqual(citation_label, row["citation_label"])
                self.assertEqual(paper_url, row["links"]["paper"])

        script = (REPO_ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn("row.display_name", script)
        self.assertIn("row.citation_label", script)
        self.assertIn("Equipped with", script)
        self.assertNotIn('class="model-cell"', script)

    def test_site_metadata_contains_approved_statistics(self) -> None:
        site = json.loads((REPO_ROOT / "data" / "site.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [
                ("Trajectories", "1,140"),
                ("Benchmarks", "5"),
                ("Median steps", "145"),
                ("Median root-to-end", "48"),
            ],
            [(stat["label"], stat["value"]) for stat in site["stats"]],
        )
        self.assertEqual(
            {"paper": PAPER_URL, "dataset": DATASET_URL},
            site["links"],
        )

    def test_javascript_fetches_the_unique_leaderboard_source(self) -> None:
        script = (REPO_ROOT / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('fetch("data/leaderboard.json")', script)
        self.assertIn("root_exact_correct", script)
        self.assertIn("benchmark_slices", script)
        self.assertIn("by_benchmark", script)
        for method in ("RCTA", "ECHO", "All-at-once", "Step-by-step"):
            self.assertNotIn(f'"{method}"', script)


if __name__ == "__main__":
    unittest.main()
