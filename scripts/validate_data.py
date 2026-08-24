#!/usr/bin/env python3
"""Validate public leaderboard data and the paper-result export contract."""

from __future__ import annotations

import argparse
import ast
import json
import re
import struct
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "benchmark",
    "evaluation_split",
    "generated_at",
    "paper_url",
    "dataset_url",
    "sort",
    "benchmark_slices",
    "results",
}

REQUIRED_RESULT_FIELDS = {
    "id",
    "method",
    "display_name",
    "citation_label",
    "model",
    "provider",
    "n",
    "role_correct",
    "root_exact_correct",
    "root_within_5_correct",
    "root_mae",
    "valid_step_n",
    "failed_n",
    "by_benchmark",
    "date",
    "status",
    "links",
}

FORBIDDEN_FIELDS = {
    "question_ID",
    "predicted_role",
    "predicted_step",
    "predicted_role_derived",
    "ground_truth_agent",
    "ground_truth_step",
    "mistake_agent",
    "mistake_step",
    "mistake_reason",
    "history",
}

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CANONICAL_URL = "https://longrca-bench.github.io/"
REQUIRED_PUBLIC_LINKS = {
    "https://arxiv.org/abs/2608.15242",
    "https://huggingface.co/datasets/CLoud5-real/longrca-bench",
}
REQUIRED_ANCHORS = {"overview", "leaderboard", "contribute", "citation"}
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".py", ".txt", ".xml", ".yaml", ".yml"}

CANONICAL_BENCHMARK_SLICES = [
    {"id": "swe_bench_pro", "label": "SWE-bench Pro", "n": 128},
    {"id": "terminal_bench_2", "label": "Terminal-Bench 2", "n": 42},
    {"id": "travelplanner", "label": "TravelPlanner", "n": 685},
    {"id": "vitabench", "label": "VitaBench", "n": 108},
    {"id": "webarena_verified", "label": "WebArena", "n": 177},
]

CANONICAL_METHOD_PRESENTATION = {
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


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.links: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("href"):
            self.hrefs.append(values["href"])
        if values.get("src"):
            self.srcs.append(values["src"])
        if tag == "link":
            self.links.append(values)
        elif tag == "meta":
            self.meta.append(values)


def require_https_url(value: Any, *, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{label} must be an absolute HTTPS URL")
    if parsed.hostname in {"localhost", "127.0.0.1"}:
        raise ValueError(f"{label} must not point to a local host")


def require_iso_date(value: Any, *, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use YYYY-MM-DD")


def _find_forbidden_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_FIELDS:
                raise ValueError(f"forbidden field {key!r} at {path}")
            _find_forbidden_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _find_forbidden_fields(child, path=f"{path}[{index}]")


def _validate_count(row: dict[str, Any], field: str, n: int) -> None:
    value = row.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= n:
        raise ValueError(f"{row.get('id', '<unknown>')}: {field} must be in [0, n]")


def validate_leaderboard(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("leaderboard root must be a JSON object")
    missing = REQUIRED_TOP_LEVEL - set(payload)
    if missing:
        raise ValueError(f"leaderboard is missing fields: {sorted(missing)}")
    _find_forbidden_fields(payload)

    if payload["schema_version"] != "1.3.0":
        raise ValueError("schema_version must be 1.3.0")
    if payload["benchmark"] != "LongRCA Bench":
        raise ValueError("benchmark must be LongRCA Bench")
    if payload["evaluation_split"] != "public":
        raise ValueError("evaluation_split must be public")
    require_iso_date(payload["generated_at"], label="generated_at")
    require_https_url(payload["paper_url"], label="paper_url")
    require_https_url(payload["dataset_url"], label="dataset_url")
    if payload["sort"] != {"metric": "root_exact", "direction": "descending"}:
        raise ValueError("sort contract must be Root Exact descending")

    benchmark_slices = payload["benchmark_slices"]
    if benchmark_slices != CANONICAL_BENCHMARK_SLICES:
        raise ValueError("benchmark_slices must match the five canonical public slices")
    benchmark_ids = [item["id"] for item in benchmark_slices]
    benchmark_n = {item["id"]: item["n"] for item in benchmark_slices}
    if sum(benchmark_n.values()) != 1140:
        raise ValueError("benchmark_slices must sum to n=1140")

    results = payload["results"]
    if not isinstance(results, list) or not results:
        raise ValueError("results must be a non-empty array")

    ids: set[str] = set()
    methods: set[str] = set()
    scores: list[float] = []
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            raise ValueError(f"results[{index}] must be an object")
        missing_fields = REQUIRED_RESULT_FIELDS - set(row)
        if missing_fields:
            raise ValueError(f"results[{index}] missing fields: {sorted(missing_fields)}")
        extra_fields = set(row) - REQUIRED_RESULT_FIELDS
        if extra_fields:
            raise ValueError(f"results[{index}] has unknown fields: {sorted(extra_fields)}")

        result_id = row["id"]
        if not isinstance(result_id, str) or not ID_PATTERN.fullmatch(result_id):
            raise ValueError(f"results[{index}].id must be a lowercase kebab-case id")
        if result_id in ids:
            raise ValueError(f"duplicate result id: {result_id}")
        ids.add(result_id)

        method = row["method"]
        if not isinstance(method, str) or not method.strip():
            raise ValueError(f"{result_id}: method must be non-empty")
        if method in methods:
            raise ValueError(f"duplicate method: {method}")
        methods.add(method)
        if method not in CANONICAL_METHOD_PRESENTATION:
            raise ValueError(f"{result_id}: unknown canonical method")
        display_name, citation_label, paper_url = CANONICAL_METHOD_PRESENTATION[method]
        if row["display_name"] != display_name:
            raise ValueError(f"{result_id}: display_name does not match method")
        if row["citation_label"] != citation_label:
            raise ValueError(f"{result_id}: citation_label does not match method")
        if row["model"] != "DeepSeek-V4-Flash":
            raise ValueError(f"{result_id}: model must be DeepSeek-V4-Flash")
        if not isinstance(row["provider"], str) or not row["provider"].strip():
            raise ValueError(f"{result_id}: provider must be non-empty")
        if row["status"] != "Paper Result":
            raise ValueError(f"{result_id}: status must be Paper Result")

        n = row["n"]
        if not isinstance(n, int) or isinstance(n, bool) or n != 1140:
            raise ValueError(f"{result_id}: n must equal 1140")
        for field in (
            "role_correct",
            "root_exact_correct",
            "root_within_5_correct",
            "valid_step_n",
            "failed_n",
        ):
            _validate_count(row, field, n)
        if row["root_within_5_correct"] < row["root_exact_correct"]:
            raise ValueError(f"{result_id}: Root ±5 cannot be below Root Exact")
        if row["valid_step_n"] + row["failed_n"] != n:
            raise ValueError(f"{result_id}: valid_step_n + failed_n must equal n")
        if not isinstance(row["root_mae"], (int, float)) or isinstance(
            row["root_mae"], bool
        ) or row["root_mae"] < 0:
            raise ValueError(f"{result_id}: root_mae must be non-negative")

        by_benchmark = row["by_benchmark"]
        if not isinstance(by_benchmark, dict) or list(by_benchmark) != benchmark_ids:
            raise ValueError(
                f"{result_id}: by_benchmark must contain the canonical slices in order"
            )
        slice_exact_total = 0
        for benchmark_id in benchmark_ids:
            slice_result = by_benchmark[benchmark_id]
            if not isinstance(slice_result, dict) or set(slice_result) != {
                "n",
                "root_exact_correct",
            }:
                raise ValueError(
                    f"{result_id}.{benchmark_id}: expected n and root_exact_correct"
                )
            if slice_result["n"] != benchmark_n[benchmark_id]:
                raise ValueError(
                    f"{result_id}.{benchmark_id}: n must equal {benchmark_n[benchmark_id]}"
                )
            _validate_count(slice_result, "root_exact_correct", slice_result["n"])
            slice_exact_total += slice_result["root_exact_correct"]
        if slice_exact_total != row["root_exact_correct"]:
            raise ValueError(
                f"{result_id}: per-benchmark Root Exact counts must sum to overall"
            )
        require_iso_date(row["date"], label=f"{result_id}.date")

        links = row["links"]
        if not isinstance(links, dict) or not links:
            raise ValueError(f"{result_id}: links must be a non-empty object")
        for link_name, link_url in links.items():
            require_https_url(link_url, label=f"{result_id}.links.{link_name}")
        if links.get("paper") != paper_url:
            raise ValueError(f"{result_id}: paper citation does not match method")

        scores.append(row["root_exact_correct"] / n)

    if scores != sorted(scores, reverse=True):
        raise ValueError("results must be sorted by Root Exact descending")


def validate_exporter_contract(exporter_path: Path) -> None:
    tree = ast.parse(exporter_path.read_text(encoding="utf-8"), filename=str(exporter_path))
    accessed_keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            slice_node = node.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                accessed_keys.add(slice_node.value)

    if "predicted_role_derived" in accessed_keys:
        raise ValueError("exporter must not access predicted_role_derived")
    for required_key in ("predicted_agent", "ground_truth_agent"):
        if required_key not in accessed_keys:
            raise ValueError(f"exporter must explicitly score {required_key}")


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name} must be a valid PNG")
    return struct.unpack(">II", header[16:24])


def validate_site(root: Path) -> None:
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(html)

    missing_anchors = REQUIRED_ANCHORS - parser.ids
    if missing_anchors:
        raise ValueError(f"index.html is missing anchors: {sorted(missing_anchors)}")
    if "metrics" in parser.ids or "#metrics" in parser.hrefs:
        raise ValueError("the removed metrics section must not be linked or rendered")
    for href in parser.hrefs:
        if href.startswith("#") and href[1:] not in parser.ids:
            raise ValueError(f"navigation target does not exist: {href}")
    missing_links = REQUIRED_PUBLIC_LINKS - set(parser.hrefs)
    if missing_links:
        raise ValueError(f"index.html is missing public links: {sorted(missing_links)}")

    canonicals = [
        link.get("href")
        for link in parser.links
        if "canonical" in link.get("rel", "").split()
    ]
    if canonicals != [CANONICAL_URL]:
        raise ValueError(f"canonical URL must be exactly {CANONICAL_URL}")

    meta_pairs = {
        (entry.get("name") or entry.get("property"), entry.get("content"))
        for entry in parser.meta
    }
    required_meta_names = {
        "description",
        "og:title",
        "og:description",
        "og:image",
        "twitter:card",
        "twitter:title",
        "twitter:description",
        "twitter:image",
    }
    present_meta_names = {name for name, content in meta_pairs if name and content}
    missing_meta = required_meta_names - present_meta_names
    if missing_meta:
        raise ValueError(f"index.html is missing metadata: {sorted(missing_meta)}")

    for asset in parser.srcs + [
        link.get("href", "")
        for link in parser.links
        if link.get("rel") in {"stylesheet", "icon"}
    ]:
        if asset.startswith(("http://", "https://", "/")):
            raise ValueError(f"runtime asset must be repository-relative: {asset}")
        if not (root / asset).is_file():
            raise ValueError(f"referenced runtime asset does not exist: {asset}")

    required_files = [
        "assets/styles.css",
        "assets/app.js",
        "assets/favicon.png",
        "assets/og-card.png",
        "data/site.json",
        "data/leaderboard.json",
        "robots.txt",
        "sitemap.xml",
    ]
    for relative_path in required_files:
        if not (root / relative_path).is_file():
            raise ValueError(f"required site file is missing: {relative_path}")
    if _png_dimensions(root / "assets" / "og-card.png") != (1200, 630):
        raise ValueError("og-card.png must be exactly 1200 x 630")

    site = json.loads((root / "data" / "site.json").read_text(encoding="utf-8"))
    expected_stats = [
        ("Trajectories", "1,140"),
        ("Benchmarks", "5"),
        ("Median steps", "145"),
        ("Median root-to-end", "48"),
    ]
    actual_stats = [(item.get("label"), item.get("value")) for item in site.get("stats", [])]
    if actual_stats != expected_stats:
        raise ValueError("site.json benchmark statistics do not match the paper contract")
    if set(site.get("links", {}).values()) != REQUIRED_PUBLIC_LINKS:
        raise ValueError("site.json resource links do not match the approved URLs")


def validate_repository_safety(root: Path) -> None:
    local_path_patterns = [
        re.compile("/" + "Users/"),
        re.compile("/" + "home/"),
        re.compile(r"[A-Za-z]:\\Users\\"),
        re.compile("file" + "://", re.IGNORECASE),
    ]
    secret_patterns = [
        re.compile("ghp" + r"_[A-Za-z0-9]{20,}"),
        re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
        re.compile("sk" + r"-[A-Za-z0-9]{20,}"),
        re.compile("AKIA" + r"[A-Z0-9]{16}"),
    ]

    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root)
        if any(pattern.search(text) for pattern in local_path_patterns):
            raise ValueError(f"absolute local path found in {relative}")
        if any(pattern.search(text) for pattern in secret_patterns):
            raise ValueError(f"secret-like token found in {relative}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root.resolve()

    payload = json.loads((root / "data" / "leaderboard.json").read_text(encoding="utf-8"))
    validate_leaderboard(payload)
    validate_exporter_contract(root / "scripts" / "export_paper_results.py")
    validate_site(root)
    validate_repository_safety(root)
    print(f"Validated {len(payload['results'])} leaderboard results and static site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
