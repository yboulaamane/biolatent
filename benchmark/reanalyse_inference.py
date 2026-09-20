"""Upgrade saved prediction-level inference without refitting any probe."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from joblib import Parallel, delayed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.inference_policy import inference_policy
from benchmark.paired_test import (
    INFERENCE_PROTOCOL_VERSION,
    N_BOOT,
    N_PERM,
    PREDICTION_DIR,
    REPORT_PATH,
    SEED,
    _ladder_steps,
    apply_familywise_corrections,
    holm,
    paired_inference,
    score,
)
from benchmark.probe import bootstrap_ci


ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = ROOT / "results" / "benchmark_results.json"


def load_prediction_bundles(task: str, task_type: str):
    path = Path(PREDICTION_DIR) / f"{task}.npz"
    with np.load(path) as saved:
        payload = {key: saved[key] for key in saved.files}
    models = sorted(
        key.removesuffix("__pred") for key in payload if key.endswith("__pred")
    )
    if task_type == "classification":
        n_classes = int(np.max(payload["y_true"])) + 1
    else:
        n_classes = None
    bundles = {}
    for model in models:
        bundles[model] = {
            "y_true": payload["y_true"],
            "y_pred": payload[f"{model}__pred"],
            "y_prob": payload.get(f"{model}__prob"),
            "task_type": task_type,
            "n_classes": n_classes,
        }
    return path, payload, bundles


def save_groups(path: Path, payload: dict[str, np.ndarray], groups: np.ndarray) -> None:
    payload["groups"] = np.asarray(groups, dtype=str)
    np.savez_compressed(path, **payload)


def recompute_deeploc(entry, results_entry, data, policy, bundles):
    groups = np.asarray(policy["groups"], dtype=str)
    reference = entry["reference"]
    scores = {model: score(bundle) for model, bundle in bundles.items()}
    challengers = [
        model for model in sorted(scores, key=scores.get, reverse=True)
        if model != reference
    ]
    def compare(offset, model):
        return model, paired_inference(
            bundles[reference], bundles[model], groups, seed=SEED + offset)

    comparisons = {}
    comparison_results = Parallel(n_jobs=min(8, len(challengers)))(
        delayed(compare)(offset, model)
        for offset, model in enumerate(challengers)
    )
    for model, result in comparison_results:
        result["inferential"] = True
        result["score"] = round(float(scores[model]), 4)
        comparisons[model] = result
        print(
            f"DeepLoc vs {model}: delta={result['delta']:+.4f}, "
            f"p={result['p_raw']:.4g}",
            flush=True,
        )
    for model, adjusted in zip(
        challengers, holm([comparisons[model]["p_raw"] for model in challengers])
    ):
        comparisons[model]["p_holm_task"] = round(float(adjusted), 6)
        comparisons[model]["significant_task"] = bool(adjusted < 0.05)

    entry.update({
        "protocol_version": INFERENCE_PROTOCOL_VERSION,
        "reference_test_score": round(float(scores[reference]), 4),
        "observed_test_best": max(scores, key=scores.get),
        "observed_test_best_score": round(float(max(scores.values())), 4),
        "n_test": len(groups),
        "n_resampling_groups": len(np.unique(groups)),
        "n_boot": N_BOOT,
        "n_permutations": N_PERM,
        "resampling_unit": policy["resampling_unit"],
        "inference_status": "primary",
        "inference_note": policy["note"],
        "primary_correction": "Holm-Bonferroni across all eligible reference comparisons",
        "comparisons": comparisons,
        "ladders": _ladder_steps(
            list(bundles), bundles, scores, groups, inference_enabled=True
        ),
    })

    def model_interval(offset, model, bundle):
        return model, bootstrap_ci(
            bundle["y_true"], bundle["y_pred"], bundle["y_prob"],
            data["task_type"], bundle["n_classes"], n_boot=N_BOOT,
            seed=SEED + 500 + offset, groups=groups,
        )

    intervals = Parallel(n_jobs=min(8, len(bundles)))(
        delayed(model_interval)(offset, model, bundle)
        for offset, (model, bundle) in enumerate(sorted(bundles.items()))
    )
    for model, interval in intervals:
        if interval:
            results_entry["models"][model]["linear"].update(interval)


def mark_primary(entry, policy):
    entry["protocol_version"] = INFERENCE_PROTOCOL_VERSION
    entry["inference_status"] = "primary"
    entry["inference_note"] = policy["note"]
    entry["resampling_unit"] = policy["resampling_unit"]
    entry["primary_correction"] = (
        "Holm-Bonferroni across all eligible reference comparisons"
    )
    for comparison in entry["comparisons"].values():
        comparison["inferential"] = True


def mark_descriptive(entry, policy):
    entry["protocol_version"] = INFERENCE_PROTOCOL_VERSION
    entry["inference_status"] = "descriptive_only"
    entry["inference_note"] = policy["note"]
    entry["resampling_unit"] = policy["resampling_unit"]
    entry["n_resampling_groups"] = len(policy["groups"])
    entry["primary_correction"] = "Not included in inferential multiplicity family"
    for comparison in entry["comparisons"].values():
        comparison.update({
            "p_raw": None,
            "n_perm_valid": 0,
            "inferential": False,
            "p_holm_task": None,
            "significant_task": False,
            "p_holm_modality": None,
            "significant_modality": False,
            "p_holm_global": None,
            "significant_global": False,
            "p_holm": None,
            "significant": False,
        })
    for ladder in entry.get("ladders", {}).values():
        ladder["correction"] = "Descriptive differences; no formal test"
        for step in ladder["steps"].values():
            step.update({
                "p_raw": None,
                "n_perm_valid": 0,
                "inferential": False,
                "p_holm": None,
                "significant": False,
                "direction": "descriptive only",
            })


def main() -> None:
    groups_only = "--groups-only" in sys.argv[1:]
    report = json.loads(Path(REPORT_PATH).read_text())
    results = json.loads(RESULTS_PATH.read_text())
    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        policy = inference_policy(task, data)
        path, payload, bundles = load_prediction_bundles(task, data["task_type"])
        if groups_only:
            save_groups(path, payload, np.asarray(policy["groups"], dtype=str))
            print(f"{task}: synchronized prediction groups", flush=True)
            continue
        if task == "DeepLoc":
            recompute_deeploc(report[task], results[task], data, policy, bundles)
            save_groups(path, payload, np.asarray(policy["groups"], dtype=str))
        elif policy["enabled"]:
            mark_primary(report[task], policy)
        else:
            mark_descriptive(report[task], policy)

    if groups_only:
        return
    Path(REPORT_PATH).write_text(json.dumps(report, indent=2) + "\n")
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")
    apply_familywise_corrections()
    print(f"Updated {REPORT_PATH} and DeepLoc score intervals")


if __name__ == "__main__":
    main()
