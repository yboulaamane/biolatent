"""Repeated balanced-scaffold split sensitivity for molecular tasks.

This is a sensitivity analysis, not a replacement leaderboard. It holds each
cached representation fixed and redraws the balanced Murcko-scaffold split at
20 pre-specified seeds. Only the ranked linear probe is refit. The output
quantifies how much scores and within-task ordering depend on a single split.
"""

import json
import os
import sys

import numpy as np
from joblib import Parallel, delayed, parallel_config

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import MOLECULE_TASKS, load_benchmark_dataset, scaffold_split
from benchmark.probe import linear_probe

SEEDS = [7, 11, 19, 21, 29, 31, 37, 42, 53, 61,
         67, 73, 79, 89, 97, 101, 109, 127, 137, 149]
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "results",
                      "split_seed_sensitivity.json")


def evaluate_seed(task, data, seed):
    """Fit every available representation on one deterministic resplit."""
    train, validation, test = scaffold_split(data["inputs"], seed=seed)
    final_train = np.concatenate([train, validation])
    scores = {}
    for model_id in embed.MODEL_REGISTRY:
        if not embed.is_applicable(model_id, task, "molecule"):
            continue
        path = embed.cache_path(model_id, task)
        if not os.path.exists(path):
            continue
        X = np.load(path, mmap_mode="r")
        result = linear_probe(
            X[final_train], data["targets"][final_train], X[test],
            data["targets"][test], data["task_type"], n_jobs=1,
            groups=data["resampling_groups"][test], n_boot=0)
        scores[model_id] = result["score"]
    return {"seed": seed,
            "order": sorted(scores, key=scores.get, reverse=True),
            "scores": scores}


def main():
    previous = {}
    if os.path.exists(OUTPUT):
        with open(OUTPUT) as handle:
            previous = json.load(handle).get("tasks", {})
    report = {
        "schema_version": 2,
        "seeds": SEEDS,
        "interpretation": ("Sensitivity to balanced Murcko-scaffold split seed. "
                           "These resplits are diagnostic and do not replace the "
                           "primary published or fixed benchmark partition."),
        # Keep completed task blocks across a pre-emption. Each task is
        # replaced atomically below after all missing seeds have finished.
        "tasks": previous.copy(),
    }
    for task in MOLECULE_TASKS:
        data = load_benchmark_dataset(task)
        by_model = {}
        saved_runs = {
            run["seed"]: run
            for run in previous.get(task, {}).get("runs", [])
        }
        missing = [seed for seed in SEEDS if seed not in saved_runs]
        if missing:
            # Split seeds are independent. Limit numerical libraries to one
            # thread inside each worker to avoid the severe oversubscription
            # caused by nested BLAS and cross-validation parallelism.
            with parallel_config(backend="loky", inner_max_num_threads=1):
                computed = Parallel(n_jobs=min(12, len(missing)))(
                    delayed(evaluate_seed)(task, data, seed) for seed in missing
                )
            saved_runs.update({run["seed"]: run for run in computed})
        rankings = [saved_runs[seed] for seed in SEEDS]
        for run in rankings:
            for model_id, value in run["scores"].items():
                by_model.setdefault(model_id, []).append(value)
        summary = {}
        for model_id, values in by_model.items():
            summary[model_id] = {
                "mean": round(float(np.mean(values)), 4),
                "minimum": round(float(np.min(values)), 4),
                "maximum": round(float(np.max(values)), 4),
                "range": round(float(np.ptp(values)), 4),
            }
        report["tasks"][task] = {"models": summary, "runs": rankings}
        temporary = f"{OUTPUT}.tmp"
        with open(temporary, "w") as handle:
            json.dump(report, handle, indent=2)
        os.replace(temporary, OUTPUT)
        print(f"{task}: {len(rankings)} split seeds", flush=True)
    with open(OUTPUT, "w") as handle:
        json.dump(report, handle, indent=2)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
