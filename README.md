# LongRCA Bench Leaderboard

The official static leaderboard for **LongRCA Bench: Diagnosing Responsible Roles and Root Causes in Long-Horizon Agent Failures**.

- [Leaderboard](https://longrca-bench.github.io/)
- [Paper](https://arxiv.org/abs/2608.15242)
- [Dataset](https://huggingface.co/datasets/CLoud5-real/longrca-bench)
- [Repository](https://github.com/longrca-bench/longrca-bench.github.io)

The first release presents the six paper results on 1,140 public trajectories across five domains. Because the gold labels are public, this site is a reproducibility leaderboard rather than a hidden-test competition.

## Data model

`data/leaderboard.json` is the only source used to render leaderboard rows. The primary table ranks by overall exact error-step accuracy and shows the corresponding exact-step result for SWE-bench Pro, Terminal-Bench 2, TravelPlanner, VitaBench, and WebArena. It stores exact counts and denominators—including each `by_benchmark` slice—instead of duplicated percentages, so the browser computes every displayed value directly from versioned counts.

Each row keeps a canonical `method`, a presentation-oriented `display_name`, a short `citation_label`, and an independently linked method paper. The equipped LLM remains versioned in `model` and `provider`, but is rendered as supporting metadata beneath the method rather than as the primary leaderboard identity.

Responsible-role accuracy, root ±5 accuracy, MAE, coverage, and failure counts remain in the same JSON record as complementary diagnostics even though they are not shown in the primary table.

`data/example_trajectory.json` is the source for the illustrative TravelPlanner case below the leaderboard. It stores the complete 77-step trace, actors, phases, event kinds, and cumulative blackboard state rendered by `assets/trajectory.js`. The four views preserve the source visualization's execution map, full event table, blackboard-growth analysis, stage-level payload ledger, and final itinerary output.

The paper-result exporter scores responsible-role accuracy from the explicit `predicted_agent` column in the evaluation records. It never derives the role from `history[predicted_step].name`. Paper-reported Root MAE values are pinned in the exporter because failed predictions do not serialize a `step_abs_err` in the records table.

## Local preview

No build step or package installation is required.

```bash
python3 -m http.server 8000
```

Then open `http://127.0.0.1:8000/`.

## Reproduce the paper rows

```bash
python3 scripts/export_paper_results.py \
  --records <path-to-records.tsv>
python3 scripts/validate_data.py
python3 -m unittest discover -s tests -v
node --check assets/app.js
node --check assets/trajectory.js
```

## Contributing

Community results are submitted through reviewed pull requests. See [CONTRIBUTING.md](CONTRIBUTING.md) for the required `metadata.json`, 1,140-line `predictions.jsonl`, and reproduction notes.

## Deployment

Merges to `main` are deployed with the official GitHub Pages Actions workflow. All HTML, CSS, JavaScript, JSON, fonts, and images are served from this repository without CDN dependencies.
