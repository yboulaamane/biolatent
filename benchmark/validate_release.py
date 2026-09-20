"""Fail-fast integrity checks for a public BioLatent study release."""

import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.inference_policy import inference_policy
from benchmark.paired_test import INFERENCE_PROTOCOL_VERSION, score as paired_score
from benchmark.probe import PROBE_PROTOCOL_VERSION

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_result(name):
    path = os.path.join(ROOT, "results", name)
    if not os.path.exists(path):
        raise AssertionError(f"missing public artefact: {path}")
    with open(path) as handle:
        return json.load(handle)


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_target_rows(values):
    """Return the finite-label rows used by both probe implementations."""
    values = np.asarray(values)
    return (np.isfinite(values).all(axis=1) if values.ndim == 2
            else np.isfinite(values))


def validate_prediction_bundle(path, task, data, result, comparison,
                               expected_models):
    """Bind paired statistics to the saved labels and model predictions."""
    expected_keys = {"y_true", "groups"}
    for model in expected_models:
        expected_keys.add(f"{model}__pred")
        if data["task_type"] in ("classification", "multilabel"):
            expected_keys.add(f"{model}__prob")

    target = np.asarray(data["targets"])[data["test_idx"]]
    valid = valid_target_rows(target)
    expected_y = target[valid]
    expected_groups = np.asarray(inference_policy(task, data)["groups"])[valid].astype(str)

    with np.load(path) as predictions:
        assert set(predictions.files) == expected_keys, \
            f"{task}: unexpected or missing arrays in prediction bundle"
        assert np.array_equal(predictions["y_true"], expected_y), \
            f"{task}: saved prediction labels differ from the dataset test labels"
        assert np.array_equal(predictions["groups"].astype(str), expected_groups), \
            f"{task}: saved resampling groups differ from the dataset"

        computed_scores = {}
        for model in expected_models:
            y_pred = predictions[f"{model}__pred"]
            y_prob = (predictions[f"{model}__prob"]
                      if f"{model}__prob" in predictions.files else None)
            assert len(y_pred) == len(expected_y) and np.isfinite(y_pred).all(), \
                f"{task}/{model}: invalid saved predictions"
            if y_prob is not None:
                assert len(y_prob) == len(expected_y) and np.isfinite(y_prob).all(), \
                    f"{task}/{model}: invalid saved probabilities"
            n_classes = (int(np.max(expected_y)) + 1
                         if data["task_type"] == "classification" else None)
            bundle = {
                "y_true": predictions["y_true"], "y_pred": y_pred,
                "y_prob": y_prob, "task_type": data["task_type"],
                "n_classes": n_classes,
            }
            computed_scores[model] = round(float(paired_score(bundle)), 4)

        reference = comparison["reference"]
        assert computed_scores[reference] == comparison["reference_test_score"], \
            f"{task}: reference score differs from saved predictions"
        for model, reported in comparison["comparisons"].items():
            assert computed_scores[model] == reported["score"], \
                f"{task}/{model}: comparison score differs from saved predictions"
        observed_best = max(computed_scores, key=computed_scores.get)
        assert observed_best == comparison["observed_test_best"]
        assert computed_scores[observed_best] == comparison["observed_test_best_score"]
        for model, computed in computed_scores.items():
            assert computed == result["models"][model]["linear"]["score"], \
                f"{task}/{model}: headline score differs from saved predictions"


def main(full_hash=False):
    results = read_result("benchmark_results.json")
    paired = read_result("paired_comparisons.json")
    exposure = read_result("exposure_report.json")
    manifest = read_result("run_manifest.json")
    sensitivity = read_result("split_seed_sensitivity.json")
    resolution = read_result("resolution_curves.json")
    sequence_clusters = read_result("sequence_clusters.json")
    split_diagnostics = read_result("split_diagnostics.json")
    assert set(results) == set(ALL_DATASETS)
    assert set(paired) == set(ALL_DATASETS)
    assert set(exposure["tasks"]) == set(ALL_DATASETS)
    assert set(sensitivity["tasks"]) == set(ALL_DATASETS[:6])
    assert set(resolution["tasks"]) == set(ALL_DATASETS)
    assert exposure["report_kind"] == "pretraining_input_exposure_proxy"
    assert sensitivity["schema_version"] == 2
    assert len(sensitivity["seeds"]) == 20
    assert resolution["schema_version"] == 1
    assert sequence_clusters["schema_version"] == 1
    assert split_diagnostics["schema_version"] == 1
    assert set(sequence_clusters["tasks"]) == {"DeepLoc", "Fluorescence"}
    assert set(split_diagnostics["tasks"]) == set(ALL_DATASETS)
    for task in ALL_DATASETS[:6]:
        runs = sensitivity["tasks"][task]["runs"]
        assert [run["seed"] for run in runs] == sensitivity["seeds"]
        assert len(runs) == 20

    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        result = results[task]
        diagnostic = split_diagnostics["tasks"][task]
        assert diagnostic["dataset_input_sha256"] == data["input_sha256"]
        for split, indices in (("train", data["train_idx"]),
                               ("validation", data["val_idx"]),
                               ("non_test_fit", data["final_train_idx"]),
                               ("test", data["test_idx"])):
            assert diagnostic["splits"][split]["n"] == len(indices)
        assert diagnostic["fit_test_overlap"]["exact_input_count"] == 0
        if data["modality"] == "molecule":
            assert diagnostic["fit_test_overlap"]["scaffold_count"] == 0

        if task in sequence_clusters["tasks"]:
            clustered = sequence_clusters["tasks"][task]
            assignments = clustered["assignments"]
            assert clustered["dataset_input_sha256"] == data["input_sha256"]
            assert clustered["n_test"] == len(data["test_idx"])
            assert len(assignments) == clustered["n_test"]
            assert len(set(assignments)) == clustered["n_clusters"]
            if task == "DeepLoc":
                assert clustered["n_clusters"] > 1
            else:
                assert clustered["n_clusters"] == 1
        assert result["dataset_sha256"] == data["dataset_sha256"]
        assert result["input_sha256"] == data["input_sha256"]
        assert result["protocol_version"] == PROBE_PROTOCOL_VERSION
        assert result["n_total"] == len(data["inputs"])
        assert result["n_train"] == len(data["final_train_idx"])
        assert result["n_test"] == len(data["test_idx"])

        train_values = {data["inputs"][index] for index in data["final_train_idx"]}
        test_values = {data["inputs"][index] for index in data["test_idx"]}
        assert not train_values.intersection(test_values), f"{task}: exact split overlap"
        train_groups = set(data["resampling_groups"][data["final_train_idx"]])
        test_groups = set(data["resampling_groups"][data["test_idx"]])
        if data["modality"] == "molecule":
            assert not train_groups.intersection(test_groups), \
                f"{task}: molecular scaffold overlap"

        expected_models = {model for model in embed.MODEL_REGISTRY
                           if embed.is_applicable(
                               model, task, data["modality"])}
        assert set(result["models"]) == expected_models
        for model, cell in result["models"].items():
            linear = cell["linear"]
            assert linear["protocol_version"] == PROBE_PROTOCOL_VERSION
            assert np.isfinite(linear["score"])
            sidecar_path = embed.cache_path(model, task).replace(".npy", ".json")
            with open(sidecar_path) as handle:
                sidecar = json.load(handle)
            assert cell.get("embedding_sha256") == sidecar["sha256"], \
                f"{task}/{model}: score is not bound to its embedding matrix"
            assert sidecar["input_sha256"] == data["input_sha256"]
            assert sidecar["protocol_version"] == embed.EMBED_PROTOCOL_VERSION
            assert sidecar.get("revision") == embed.MODEL_REGISTRY[model].get("revision")
            if full_hash:
                matrix_path = embed.cache_path(model, task)
                matrix = np.load(matrix_path, mmap_mode="r")
                digest = hashlib.sha256()
                for start in range(0, matrix.shape[0], 1024):
                    digest.update(np.ascontiguousarray(matrix[start:start + 1024]).tobytes())
                assert digest.hexdigest() == sidecar["sha256"]

        comparison = paired[task]
        assert comparison["protocol_version"] == INFERENCE_PROTOCOL_VERSION
        assert comparison["reference"] in expected_models
        assert len(comparison["comparisons"]) == len(expected_models) - 1
        policy = inference_policy(task, data)
        assert comparison["inference_status"] == \
            ("primary" if policy["enabled"] else "descriptive_only")
        assert comparison["n_resampling_groups"] == \
            len(np.unique(policy["groups"]))
        for value in comparison["comparisons"].values():
            assert "p_holm_global" in value and "significant_global" in value
            if policy["enabled"]:
                assert value["inferential"] is True
                assert 0 <= value["p_raw"] <= 1
                assert value["p_holm"] == value["p_holm_global"]
                assert value["significant"] == value["significant_global"]
            else:
                assert value["inferential"] is False
                assert value["p_raw"] is None and value["p_holm"] is None
                assert value["significant"] is False
        prediction_path = os.path.join(ROOT, "results", "predictions", f"{task}.npz")
        assert os.path.exists(prediction_path)
        validate_prediction_bundle(prediction_path, task, data, result,
                                   comparison, expected_models)

        curve_task = resolution["tasks"][task]
        assert curve_task["n_test"] == result["n_test"]
        assert curve_task["reference"] == comparison["reference"]
        assert set(curve_task["comparisons"]) == set(comparison["comparisons"])
        for model, curve_report in curve_task["comparisons"].items():
            assert curve_report["full_test_delta"] == \
                comparison["comparisons"][model]["delta"]
            for point in curve_report["curve"]:
                assert 20 <= point["requested_n"] < curve_task["n_test"]
                assert 0 <= point["sign_consistency"] <= 1
                assert 0 < point["valid_repeats"] <= resolution["repeats"]
                for key in ("median_delta", "central_95_low",
                            "central_95_high", "central_95_width"):
                    assert np.isfinite(point[key])

    result_hash = file_hash(os.path.join(ROOT, "results", "benchmark_results.json"))
    assert manifest["benchmark_results_sha256"] == result_hash
    for filename in ("benchmark_results.json", "paired_comparisons.json",
                     "exposure_report.json", "split_seed_sensitivity.json",
                     "resolution_curves.json", "sequence_clusters.json",
                     "split_diagnostics.json"):
        path = os.path.join(ROOT, "results", filename)
        assert manifest["public_artifacts"][filename] == file_hash(path)
    for task in ALL_DATASETS:
        relative = f"predictions/{task}.npz"
        path = os.path.join(ROOT, "results", relative)
        assert manifest["prediction_artifacts"][relative] == file_hash(path)
    print(f"Validated {len(ALL_DATASETS)} tasks and "
          f"{sum(len(task['models']) for task in results.values())} cells.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-hash", action="store_true",
                        help="also hash every local embedding matrix")
    arguments = parser.parse_args()
    main(arguments.full_hash)
