"""Empirical test-size resolution curves from saved paired predictions.

For every validation-reference comparison, repeatedly subsample the fixed test
set without replacement and recompute the paired metric difference. Molecular
subsamples select whole Murcko-scaffold groups and DeepLoc subsets select whole
MMseqs2 homology clusters until the requested size is met.
The resulting central range and sign consistency show how estimate stability
changes with sample size without asserting that sample size is the only source
of cross-task differences.
"""

import json
import os
import sys

import numpy as np
from scipy.stats import rankdata, spearmanr
from sklearn.metrics import accuracy_score, roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets import load_benchmark_dataset

PAIRED_PATH = os.path.join(os.path.dirname(__file__), "..", "results",
                           "paired_comparisons.json")
PREDICTION_DIR = os.path.join(os.path.dirname(__file__), "..", "results",
                              "predictions")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "results",
                      "resolution_curves.json")
REPEATS = 400
SEED = 42


def metric(y, pred, prob, task_type):
    if task_type == "regression":
        value = spearmanr(y, pred).statistic
        return float(value) if np.isfinite(value) else np.nan
    if task_type == "multilabel":
        if any(len(np.unique(y[:, column])) < 2
               for column in range(y.shape[1])):
            return np.nan
        aucs = []
        for column in range(y.shape[1]):
            labels = y[:, column].astype(bool)
            n_positive = int(labels.sum())
            n_negative = len(labels) - n_positive
            ranks = rankdata(prob[:, column], method="average")
            numerator = (ranks[labels].sum()
                         - n_positive * (n_positive + 1) / 2)
            aucs.append(numerator / (n_positive * n_negative))
        return float(np.mean(aucs))
    if len(np.unique(y)) < 2:
        return np.nan
    return float(roc_auc_score(y, prob[:, 1]))


def sample_indices(rng, n_items, members, target_n, clustered):
    if not clustered:
        return rng.choice(n_items, target_n, replace=False)
    chosen = rng.permutation(len(members))
    parts, count = [], 0
    for group in chosen:
        group_members = members[group]
        parts.append(group_members)
        count += len(group_members)
        if count >= target_n:
            break
    return np.concatenate(parts)


def main():
    with open(PAIRED_PATH) as handle:
        paired = json.load(handle)
    requested = set(sys.argv[1:])
    previous_tasks = {}
    if requested and os.path.exists(OUTPUT):
        with open(OUTPUT) as handle:
            previous_tasks = json.load(handle).get("tasks", {})
    report = {
        "schema_version": 1, "repeats": REPEATS,
        "sampling": ("without replacement; whole Murcko-scaffold groups for "
                     "molecules, whole MMseqs2 homology clusters for DeepLoc, "
                     "and individual items otherwise"),
        "interpretation": ("Empirical subsampling stability conditional on the "
                           "fixed test set; not a causal decomposition of modality."),
        "tasks": previous_tasks,
    }
    rng = np.random.RandomState(SEED)
    for task, paired_task in paired.items():
        if requested and task not in requested:
            continue
        path = os.path.join(PREDICTION_DIR, f"{task}.npz")
        if not os.path.exists(path):
            continue
        data = np.load(path)
        definition = load_benchmark_dataset(task)
        y, groups = data["y_true"], data["groups"].astype(str)
        _, membership = np.unique(groups, return_inverse=True)
        members = [np.flatnonzero(membership == group)
                   for group in range(int(membership.max()) + 1)]
        clustered = len(members) < len(groups)
        reference = paired_task["reference"]
        ref_pred = data[f"{reference}__pred"]
        ref_prob = data[f"{reference}__prob"] if f"{reference}__prob" in data else None
        # Sampling the complete fixed test set without replacement has zero
        # variation by construction, so it is not a meaningful curve point.
        # Include pre-specified sizes plus fractional points below the full n.
        candidates = [50, 100, 150, 250, 500, 1000, 2000, 5000,
                      10000, 20000, int(0.25 * len(y)), int(0.5 * len(y)),
                      int(0.75 * len(y))]
        sizes = sorted({size for size in candidates if 20 <= size < len(y)})
        task_out = {"n_test": int(len(y)), "reference": reference,
                    "comparisons": {}}
        for model, comparison in paired_task["comparisons"].items():
            pred = data[f"{model}__pred"]
            prob = data[f"{model}__prob"] if f"{model}__prob" in data else None
            full_delta = comparison["delta"]
            curve = []
            for size in sizes:
                values, effective = [], []
                for _ in range(REPEATS):
                    idx = sample_indices(
                        rng, len(groups), members, size,
                        clustered,
                    )
                    left = metric(y[idx], ref_pred[idx],
                                  ref_prob[idx] if ref_prob is not None else None,
                                  definition["task_type"])
                    right = metric(y[idx], pred[idx],
                                   prob[idx] if prob is not None else None,
                                   definition["task_type"])
                    if np.isfinite(left) and np.isfinite(right):
                        values.append(left - right)
                        effective.append(len(idx))
                if not values:
                    continue
                values = np.asarray(values)
                lo, hi = np.percentile(values, [2.5, 97.5])
                sign = np.mean(np.sign(values) == np.sign(full_delta))
                curve.append({
                    "requested_n": size,
                    "median_effective_n": int(np.median(effective)),
                    "median_delta": round(float(np.median(values)), 4),
                    "central_95_low": round(float(lo), 4),
                    "central_95_high": round(float(hi), 4),
                    "central_95_width": round(float(hi - lo), 4),
                    "sign_consistency": round(float(sign), 4),
                    "valid_repeats": int(len(values)),
                })
            task_out["comparisons"][model] = {
                "full_test_delta": full_delta, "curve": curve}
        report["tasks"][task] = task_out
        print(f"{task}: {len(task_out['comparisons'])} curves", flush=True)
    with open(OUTPUT, "w") as handle:
        json.dump(report, handle, indent=2)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
