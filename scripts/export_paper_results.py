#!/usr/bin/env python3
"""Export the LongRCA paper leaderboard from the canonical evaluation records.

Role accuracy is recomputed from the explicit ``predicted_agent`` column. The
step-emitter role in ``predicted_role_derived`` is intentionally never scored.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


PAPER_URL = "https://arxiv.org/abs/2608.15242"
DATASET_URL = "https://huggingface.co/datasets/CLoud5-real/longrca-bench"
MODEL_NAME = "DeepSeek-V4-Flash"
PROVIDER_NAME = "DeepSeek"
PAPER_DATE = "2026-08-20"

METHOD_LABELS = {
    "full_all_at_once": "All-at-once",
    "full_step_by_step": "Step-by-step",
    "full_binary_search": "Binary search",
    "full_echo": "ECHO",
    "falat": "FALAT",
    "agent_error_trajectory_analysis": "RCTA",
}

METHOD_DISPLAY_NAMES = {
    "full_all_at_once": "LLM-as-a-Judge / All-at-once",
    "full_step_by_step": "LLM-as-a-Judge / Step-by-step",
    "full_binary_search": "Binary search",
    "full_echo": "ECHO",
    "falat": "FALAT",
    "agent_error_trajectory_analysis": "RCTA",
}

METHOD_CITATIONS = {
    "full_all_at_once": (
        "Who&When",
        "https://proceedings.mlr.press/v267/zhang25cq.html",
    ),
    "full_step_by_step": (
        "Who&When",
        "https://proceedings.mlr.press/v267/zhang25cq.html",
    ),
    "full_binary_search": (
        "Who&When",
        "https://proceedings.mlr.press/v267/zhang25cq.html",
    ),
    "full_echo": ("ECHO", "https://arxiv.org/abs/2510.04886"),
    "falat": ("FALAT", "https://arxiv.org/abs/2606.00765"),
    "agent_error_trajectory_analysis": ("LongRCA", PAPER_URL),
}

# The paper-reported MAE values are pinned because failed predictions have no
# serialized ``step_abs_err`` in records.tsv. Counts and all percentage metrics
# are recomputed from records; these six MAEs preserve the published contract.
PAPER_ROOT_MAE = {
    "full_all_at_once": 55.937183450550016,
    "full_step_by_step": 52.26005565815123,
    "full_binary_search": 61.708771929824564,
    "full_echo": 50.396491228070175,
    "falat": 66.6061403508772,
    "agent_error_trajectory_analysis": 38.6140350877193,
}

REQUIRED_COLUMNS = {
    "method",
    "method_label",
    "benchmark",
    "qid",
    "predicted_agent",
    "ground_truth_agent",
    "step_exact",
    "step_within_5",
    "step_abs_err",
    "step_valid",
    "failed",
}

BENCHMARK_LABELS = {
    "swe_bench_pro": "SWE-bench Pro",
    "terminal_bench_2": "Terminal-Bench 2",
    "travelplanner": "TravelPlanner",
    "vitabench": "VitaBench",
    "webarena_verified": "WebArena",
}

BENCHMARK_EXPECTED_N = {
    "swe_bench_pro": 128,
    "terminal_bench_2": 42,
    "travelplanner": 685,
    "vitabench": 108,
    "webarena_verified": 177,
}


def normalize_role(value: Any) -> str:
    """Normalize a role while preserving meaningful parenthetical text."""

    text = str(value or "").strip()
    text = re.sub(r"\s*\((?:->|→)\s*[^()]+\)\s*$", "", text)
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(text.strip().split())


def parse_bool(value: Any, *, field: str, qid: str) -> bool:
    text = str(value).strip().casefold()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"{qid}: {field} must be True or False, got {value!r}")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _read_rows(records_path: Path) -> list[dict[str, str]]:
    with records_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"records.tsv is missing columns: {sorted(missing)}")
        return list(reader)


def _mean_step_error(rows: Iterable[dict[str, str]]) -> float:
    values = [float(row["step_abs_err"]) for row in rows if row["step_abs_err"].strip()]
    if not values:
        raise ValueError("cannot compute root_mae without a valid step_abs_err")
    return mean(values)


def build_leaderboard(
    records_path: Path,
    *,
    expected_n: int | None = 1140,
    paper_date: str = PAPER_DATE,
) -> dict[str, Any]:
    rows = _read_rows(records_path)
    if not rows:
        raise ValueError("records.tsv contains no evaluation rows")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["method"]].append(row)

    if expected_n is not None and set(grouped) != set(METHOD_LABELS):
        raise ValueError(
            "canonical export requires exactly these methods: "
            f"{sorted(METHOD_LABELS)}"
        )

    benchmark_ids = [
        benchmark_id
        for benchmark_id in BENCHMARK_LABELS
        if any(row["benchmark"] == benchmark_id for row in rows)
    ]
    unknown_benchmarks = {row["benchmark"] for row in rows} - set(BENCHMARK_LABELS)
    if unknown_benchmarks:
        raise ValueError(f"unknown benchmark ids: {sorted(unknown_benchmarks)}")
    if expected_n == 1140 and benchmark_ids != list(BENCHMARK_LABELS):
        raise ValueError("canonical export requires all five benchmark slices")

    benchmark_slices: list[dict[str, Any]] = []
    for benchmark_id in benchmark_ids:
        counts = {
            method_id: sum(row["benchmark"] == benchmark_id for row in method_rows)
            for method_id, method_rows in grouped.items()
        }
        if len(set(counts.values())) != 1:
            raise ValueError(
                f"{benchmark_id}: inconsistent sample counts across methods: {counts}"
            )
        benchmark_n = next(iter(counts.values()))
        if expected_n == 1140 and benchmark_n != BENCHMARK_EXPECTED_N[benchmark_id]:
            raise ValueError(
                f"{benchmark_id}: expected {BENCHMARK_EXPECTED_N[benchmark_id]} rows "
                f"per method, found {benchmark_n}"
            )
        benchmark_slices.append(
            {
                "id": benchmark_id,
                "label": BENCHMARK_LABELS[benchmark_id],
                "n": benchmark_n,
            }
        )

    results: list[dict[str, Any]] = []
    for method_id, method_rows in grouped.items():
        n = len(method_rows)
        if expected_n is not None and n != expected_n:
            raise ValueError(f"{method_id}: expected {expected_n} rows, found {n}")

        qids = [row["qid"] for row in method_rows]
        if len(qids) != len(set(qids)):
            raise ValueError(f"{method_id}: duplicate qid values found")

        role_correct = sum(
            bool(normalize_role(row["predicted_agent"]))
            and normalize_role(row["predicted_agent"])
            == normalize_role(row["ground_truth_agent"])
            for row in method_rows
        )
        root_exact_correct = sum(
            parse_bool(row["step_exact"], field="step_exact", qid=row["qid"])
            for row in method_rows
        )
        root_within_5_correct = sum(
            parse_bool(
                row["step_within_5"], field="step_within_5", qid=row["qid"]
            )
            for row in method_rows
        )
        valid_step_n = sum(
            parse_bool(row["step_valid"], field="step_valid", qid=row["qid"])
            for row in method_rows
        )
        failed_n = sum(
            parse_bool(row["failed"], field="failed", qid=row["qid"])
            for row in method_rows
        )
        method_label = METHOD_LABELS.get(
            method_id, method_rows[0].get("method_label") or method_id
        )
        display_name = METHOD_DISPLAY_NAMES.get(method_id, method_label)
        citation_label, citation_url = METHOD_CITATIONS.get(
            method_id, ("Paper", PAPER_URL)
        )
        root_mae = (
            PAPER_ROOT_MAE[method_id]
            if expected_n == 1140 and method_id in PAPER_ROOT_MAE
            else _mean_step_error(method_rows)
        )
        by_benchmark: dict[str, dict[str, int]] = {}
        for benchmark in benchmark_slices:
            benchmark_rows = [
                row for row in method_rows if row["benchmark"] == benchmark["id"]
            ]
            by_benchmark[benchmark["id"]] = {
                "n": len(benchmark_rows),
                "root_exact_correct": sum(
                    parse_bool(row["step_exact"], field="step_exact", qid=row["qid"])
                    for row in benchmark_rows
                ),
            }

        results.append(
            {
                "id": f"{slugify(method_label)}-deepseek-v4-flash-paper",
                "method": method_label,
                "display_name": display_name,
                "citation_label": citation_label,
                "model": MODEL_NAME,
                "provider": PROVIDER_NAME,
                "n": n,
                "role_correct": role_correct,
                "root_exact_correct": root_exact_correct,
                "root_within_5_correct": root_within_5_correct,
                "root_mae": root_mae,
                "valid_step_n": valid_step_n,
                "failed_n": failed_n,
                "by_benchmark": by_benchmark,
                "date": paper_date,
                "status": "Paper Result",
                "links": {"paper": citation_url},
            }
        )

    results.sort(
        key=lambda row: (
            -row["root_exact_correct"] / row["n"],
            row["root_mae"],
            row["method"].casefold(),
        )
    )
    return {
        "schema_version": "1.3.0",
        "benchmark": "LongRCA Bench",
        "evaluation_split": "public",
        "generated_at": paper_date,
        "paper_url": PAPER_URL,
        "dataset_url": DATASET_URL,
        "sort": {"metric": "root_exact", "direction": "descending"},
        "benchmark_slices": benchmark_slices,
        "results": results,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "leaderboard.json",
    )
    parser.add_argument("--date", default=PAPER_DATE)
    args = parser.parse_args()

    payload = build_leaderboard(args.records, paper_date=args.date)
    write_json(args.output, payload)
    print(f"Wrote {len(payload['results'])} paper results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
