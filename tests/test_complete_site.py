from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.meta: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("href"):
            self.hrefs.append(values["href"])
        if values.get("src"):
            self.srcs.append(values["src"])
        if tag == "meta":
            self.meta.append(values)


class CompleteSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        cls.parser = StructureParser()
        cls.parser.feed(cls.html)

    def test_all_sections_and_navigation_anchors_exist(self) -> None:
        expected = {"overview", "leaderboard", "example", "contribute", "citation"}
        self.assertTrue(expected.issubset(self.parser.ids))
        for anchor in expected - {"overview"}:
            self.assertIn(f"#{anchor}", self.parser.hrefs)
        self.assertNotIn("metrics", self.parser.ids)
        self.assertNotIn("#metrics", self.parser.hrefs)

    def test_failed_trajectory_example_is_between_leaderboard_and_contribute(self) -> None:
        self.assertIn('id="example"', self.html)
        leaderboard = self.html.index('id="leaderboard"')
        example = self.html.index('id="example"')
        contribute = self.html.index('id="contribute"')
        self.assertLess(leaderboard, example)
        self.assertLess(example, contribute)
        self.assertIn("An Example of a Failed Task Trajectory", self.html)
        self.assertIn("Agent status", self.html)
        self.assertIn("Benchmark outcome", self.html)
        self.assertIn('id="trajectory-example"', self.html)
        self.assertIn('src="assets/trajectory.js"', self.html)
        self.assertNotIn("<iframe", self.html)

    def test_example_exposes_three_accessible_views(self) -> None:
        for view in ("map", "failure", "result"):
            self.assertIn(f'data-trace-tab="{view}"', self.html)
            self.assertIn(f'data-trace-view="{view}"', self.html)
        self.assertIn('aria-label="Play trajectory"', self.html)
        self.assertIn('aria-label="Trajectory step"', self.html)

    def test_leaderboard_copy_is_concise(self) -> None:
        self.assertIn("LongRCA Bench Leaderboard", self.html)
        self.assertNotIn("Exact-step leaderboard", self.html)
        self.assertNotIn(
            "One shared public evaluation set and one DeepSeek-V4-Flash backbone.",
            self.html,
        )
        self.assertNotIn('class="notice"', self.html)

    def test_contribution_contract_is_visible(self) -> None:
        for token in (
            "metadata.json",
            "predictions.jsonl",
            "1,140",
            "question_ID",
            "predicted_role",
            "predicted_step",
            "external storage",
        ):
            self.assertIn(token, self.html)

    def test_citation_and_copy_affordance_exist(self) -> None:
        self.assertIn("arXiv:2608.15242", self.html)
        self.assertIn('id="citation-code"', self.html)
        self.assertIn('id="copy-citation"', self.html)

    def test_social_metadata_and_local_assets_exist(self) -> None:
        self.assertIn('property="og:title"', self.html)
        self.assertIn('property="og:description"', self.html)
        self.assertIn('property="og:image"', self.html)
        self.assertIn('name="twitter:card" content="summary_large_image"', self.html)
        self.assertIn('rel="icon" href="assets/favicon.png"', self.html)
        self.assertTrue((REPO_ROOT / "assets" / "og-card.png").is_file())
        self.assertTrue((REPO_ROOT / "assets" / "favicon.png").is_file())

    def test_no_external_runtime_asset_dependencies(self) -> None:
        runtime_assets = self.parser.srcs + [
            href
            for href in self.parser.hrefs
            if href.endswith((".css", ".js", ".woff", ".woff2", ".png"))
        ]
        self.assertFalse(
            [asset for asset in runtime_assets if re.match(r"^https?://", asset)],
            runtime_assets,
        )

    def test_robots_and_sitemap_target_the_pages_url(self) -> None:
        robots = (REPO_ROOT / "robots.txt").read_text(encoding="utf-8")
        sitemap = (REPO_ROOT / "sitemap.xml").read_text(encoding="utf-8")
        canonical = "https://longrca-bench.github.io/"
        self.assertIn(f"Sitemap: {canonical}sitemap.xml", robots)
        self.assertIn(f"<loc>{canonical}</loc>", sitemap)


if __name__ == "__main__":
    unittest.main()
