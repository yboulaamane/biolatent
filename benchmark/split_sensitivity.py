"""Repeated balanced-scaffold split sensitivity for molecular tasks.

This is a sensitivity analysis, not a replacement leaderboard. It holds each
cached representation fixed and redraws the balanced Murcko-scaffold split at
five pre-specified seeds. Only the ranked linear probe is refit. The output
quantifies how much scores and within-task ordering depend on a single split.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import MOLECULE_TASKS, load_benchmark_dataset, scaffold_split
from benchmark.probe import linear_probe

SEEDS = [7, 21, 42, 73, 101]
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "results",
                      "split_seed_sensitivity.json")


def main():
    report = {
        "schema_version": 2,
        "seeds": SEEDS,
        "interpretation": ("Sensitivity to balanced Murcko-scaffold split seed. "
                           "These resplits are diagnostic and do not replace the "
                           "primary published or fixed benchmark partition."),
        "tasks": {},
    }
    for task in MOLECULE_TASKS:
        data = load_benchmark_dataset(task)
        by_model = {}
        rankings = []
        for seed in SEEDS:
            train, validation, test = scaffold_split(data["inputs"], seed=seed)
            # Match the primary score: validation participates in model
            # selection, then the reported probe is refit on every non-test
            # item. The sensitivity run has no separate reported validation
            # score, so its final fit likewise uses train + validation.
            final_train = np.concatenate([train, validation])
            scores = {}
            for model_id, spec in embed.MODEL_REGISTRY.items():
                if spec["modality"] != "molecule":
                    continue
                path = embed.cache_path(model_id, task)
                if not os.path.exists(path):
                    continue
                X = np.load(path, mmap_mode="r")
                result = linear_probe(
                    X[final_train], data["targets"][final_train], X[test],
                    data["targets"][test], data["task_type"], n_jobs=4,
                    groups=data["resampling_groups"][test], n_boot=0)
                scores[model_id] = result["score"]
                by_model.setdefault(model_id, []).append(result["score"])
            rankings.append({"seed": seed,
                             "order": sorted(scores, key=scores.get, reverse=True),
                             "scores": scores})
        summary = {}
        for model_id, values in by_model.items():
            summary[model_id] = {
                "mean": round(float(np.mean(values)), 4),
                "minimum": round(float(np.min(values)), 4),
                "maximum": round(float(np.max(values)), 4),
                "range": round(float(np.ptp(values)), 4),
            }
        report["tasks"][task] = {"models": summary, "runs": rankings}
        print(f"{task}: {len(rankings)} split seeds", flush=True)
    with open(OUTPUT, "w") as handle:
        json.dump(report, handle, indent=2)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
