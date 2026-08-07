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


def main(full_hash=False):
    results = read_result("benchmark_results.json")
    paired = read_result("paired_comparisons.json")
    exposure = read_result("exposure_report.json")
    manifest = read_result("run_manifest.json")
    sensitivity = read_result("split_seed_sensitivity.json")
    resolution = read_result("resolution_curves.json")
    assert set(results) == set(ALL_DATASETS)
    assert set(paired) == set(ALL_DATASETS)
    assert set(exposure["tasks"]) == set(ALL_DATASETS)
    assert set(sensitivity["tasks"]) == set(ALL_DATASETS[:6])
    assert set(resolution["tasks"]) == set(ALL_DATASETS)
    assert exposure["report_kind"] == "pretraining_input_exposure_proxy"

    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        result = results[task]
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

        expected_models = {model for model, spec in embed.MODEL_REGISTRY.items()
                           if spec["modality"] == data["modality"]}
        assert set(result["models"]) == expected_models
        for model, cell in result["models"].items():
            linear = cell["linear"]
            assert linear["protocol_version"] == PROBE_PROTOCOL_VERSION
            assert np.isfinite(linear["score"])
            sidecar_path = embed.cache_path(model, task).replace(".npy", ".json")
            with open(sidecar_path) as handle:
                sidecar = json.load(handle)
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
        assert comparison["reference"] in expected_models
        assert len(comparison["comparisons"]) == len(expected_models) - 1
        for value in comparison["comparisons"].values():
            assert "p_holm_global" in value and "significant_global" in value
            assert 0 <= value["p_raw"] <= 1
        prediction_path = os.path.join(ROOT, "results", "predictions", f"{task}.npz")
        assert os.path.exists(prediction_path)

    result_hash = file_hash(os.path.join(ROOT, "results", "benchmark_results.json"))
    assert manifest["benchmark_results_sha256"] == result_hash
    for filename in ("benchmark_results.json", "paired_comparisons.json",
                     "exposure_report.json", "split_seed_sensitivity.json",
                     "resolution_curves.json"):
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
