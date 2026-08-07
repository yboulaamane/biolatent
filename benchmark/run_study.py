"""
BioLatent Benchmark Runner
==========================

Executes the full frozen-embedding study:

    for each task -> for each applicable model -> embed (cached) -> probe

Results are written incrementally to ``results/benchmark_results.json`` so an
interrupted run resumes without recomputing finished cells.

Two invariants are enforced here rather than left to convention:

* A model is evaluated **only on its own modality**. A protein language model
  has no way to embed a SMILES string, so the cell is omitted entirely. It is
  never filled by projecting, imputing, or substituting another featuriser.
* Nothing is written for a cell that failed. A missing result stays missing.

Usage:
    python benchmark/run_study.py                # everything
    python benchmark/run_study.py BBBP ClinTox   # named tasks only
"""

import json
import hashlib
import importlib.metadata
import os
import platform
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.probe import (PROBE_PROTOCOL_VERSION, SEARCH_CAP, SEED,
                             linear_probe, mlp_probe)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
RESULTS_PATH = os.path.join(RESULTS_DIR, "benchmark_results.json")
MANIFEST_PATH = os.path.join(RESULTS_DIR, "run_manifest.json")
PUBLIC_RESULT_FILES = [
    "benchmark_results.json", "paired_comparisons.json",
    "exposure_report.json", "split_seed_sensitivity.json",
    "resolution_curves.json",
]


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as fh:
            return json.load(fh)
    return {}


def save_results(results):
    """Merge this runner's cells into the file, then write atomically.

    Writing the in-memory dict wholesale loses work when two runners are active:
    each holds a snapshot taken at start-up, so whichever saves last erases
    every cell the other computed in the meantime. Re-reading and merging keeps
    concurrent runs on disjoint tasks safe, which matters because the natural
    way to use this harness is one runner per modality.
    """
    merged = load_results()
    for task, info in results.items():
        if task not in merged:
            merged[task] = info
            continue
        incoming_hash = info.get("dataset_sha256")
        stored_hash = merged[task].get("dataset_sha256")
        identity_changed = (
            (incoming_hash and incoming_hash != stored_hash)
            or info.get("input_sha256") != merged[task].get("input_sha256")
            or info.get("protocol_version") != merged[task].get("protocol_version")
        )
        if identity_changed:
            merged[task] = info
            continue
        merged[task].update({k: v for k, v in info.items() if k != "models"})
        merged[task].setdefault("models", {}).update(info.get("models", {}))

    tmp = f"{RESULTS_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(merged, fh, indent=2)
    os.replace(tmp, RESULTS_PATH)
    return merged


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name):
    """Version from installed package metadata rather than a module attribute.

    Running this file as a script puts benchmark/ first on sys.path, so a bare
    ``import datasets`` resolves to this package's own datasets.py instead of the
    Hugging Face library and raises AttributeError on ``__version__``. Reading
    the distribution metadata sidesteps shadowing entirely and also covers
    packages that simply do not export ``__version__``.
    """
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def write_manifest(results):
    """Write public provenance for every dataset, embedding and result cell."""
    import torch

    manifest = {
        "schema_version": 1,
        "execution_context": "local",
        "benchmark_protocol": {
            "embedding_protocol_version": embed.EMBED_PROTOCOL_VERSION,
            "probe_protocol_version": PROBE_PROTOCOL_VERSION,
            "seed": SEED,
            "regularisation_search_cap": SEARCH_CAP,
            "ranked_probe": "standardised L2 linear probe",
            "cross_validation_preprocessing": (
                "feature scaling fitted independently inside each CV fold"),
            "final_fit": "all non-test labels after validation selection",
            "diagnostic_probe": "one-hidden-layer MLP (256 ReLU units)",
        },
        "software": {
            "python": platform.python_version(),
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
            "scipy": _package_version("scipy"),
            "scikit_learn": _package_version("scikit-learn"),
            "rdkit": _package_version("rdkit"),
            "torch": _package_version("torch"),
            # Distribution metadata drops the local build suffix, so the CUDA
            # build that actually produced the embeddings is recorded separately.
            "torch_build": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "transformers": _package_version("transformers"),
            "datasets": _package_version("datasets"),
        },
        "tasks": {},
        "public_artifacts": {},
        "prediction_artifacts": {},
    }
    for task, task_result in results.items():
        task_entry = {
            key: task_result.get(key) for key in (
                "dataset_label", "dataset_source", "dataset_variant",
                "dataset_sha256", "input_sha256", "split_source", "task_type", "n_total",
                "n_train", "n_test")
        }
        task_entry["embeddings"] = {}
        for model_id in task_result.get("models", {}):
            sidecar = embed.cache_path(model_id, task).replace(".npy", ".json")
            if os.path.exists(sidecar):
                with open(sidecar) as handle:
                    metadata = json.load(handle)
                spec = embed.MODEL_REGISTRY[model_id]
                metadata.setdefault("matrix_dtype", "float32")
                metadata.setdefault(
                    "inference_precision_policy",
                    ("float32 on all devices" if spec.get("force_float32")
                     else "float16 on CUDA; float32 when CUDA is unavailable")
                    if spec["kind"] == "hf" else "not applicable")
                task_entry["embeddings"][model_id] = metadata
        manifest["tasks"][task] = task_entry
        prediction_path = os.path.join(RESULTS_DIR, "predictions", f"{task}.npz")
        if os.path.exists(prediction_path):
            manifest["prediction_artifacts"][f"predictions/{task}.npz"] = \
                _file_sha256(prediction_path)
    if os.path.exists(RESULTS_PATH):
        manifest["benchmark_results_sha256"] = _file_sha256(RESULTS_PATH)
    for filename in PUBLIC_RESULT_FILES:
        path = os.path.join(RESULTS_DIR, filename)
        if os.path.exists(path):
            manifest["public_artifacts"][filename] = _file_sha256(path)
    with open(MANIFEST_PATH, "w") as handle:
        json.dump(manifest, handle, indent=2)


def refresh_metadata(task_names=None):
    """Refresh dataset/protocol provenance without recomputing finished cells."""
    results = load_results()
    for task in (task_names or ALL_DATASETS):
        if task not in results:
            continue
        data = load_benchmark_dataset(task)
        results[task].update({
            "dataset_label": data["dataset_label"],
            "dataset_source": data["dataset_source"],
            "dataset_variant": data["dataset_variant"],
            "dataset_sha256": data["dataset_sha256"],
            "input_sha256": data["input_sha256"],
            "protocol_version": PROBE_PROTOCOL_VERSION,
            "modality": data["modality"], "task_type": data["task_type"],
            "split_source": data["split_source"],
            "n_total": len(data["inputs"]),
            "n_train": int(len(data["final_train_idx"])),
            "n_test": int(len(data["test_idx"])),
            "target_labels": data["target_labels"],
        })
        for cell in results[task].get("models", {}).values():
            # Wall time depends on whether a local embedding cache was warm and
            # is therefore not a scientifically comparable result field.
            cell.pop("embed_seconds", None)
    temporary = f"{RESULTS_PATH}.{os.getpid()}.tmp"
    with open(temporary, "w") as handle:
        json.dump(results, handle, indent=2)
    os.replace(temporary, RESULTS_PATH)
    write_manifest(results)


def precompute_embeddings(task_names=None):
    """Populate valid embedding caches without fitting downstream probes."""
    for task in (task_names or ALL_DATASETS):
        data = load_benchmark_dataset(task)
        applicable = [model for model, spec in embed.MODEL_REGISTRY.items()
                      if spec["modality"] == data["modality"]]
        print(f"\n{task}: precomputing {len(applicable)} representations", flush=True)
        for model_id in applicable:
            print(f"  -> {model_id}", flush=True)
            embed.generate(model_id, task, data["inputs"], data["modality"])
    print("\nEmbedding caches are complete.", flush=True)


def run(task_names=None, run_mlp=True):
    tasks = task_names or ALL_DATASETS
    results = load_results()

    for task in tasks:
        data = load_benchmark_dataset(task)
        modality = data["modality"]
        applicable = [m for m, s in embed.MODEL_REGISTRY.items()
                      if s["modality"] == modality]

        print(f"\n{'=' * 72}\n{task}  ({modality}, {data['task_type']}, "
              f"{data['split_source']} split, n={len(data['inputs'])})\n{'=' * 72}",
              flush=True)

        task_info = {
            "dataset_label": data["dataset_label"],
            "dataset_source": data["dataset_source"],
            "dataset_variant": data["dataset_variant"],
            "dataset_sha256": data["dataset_sha256"],
            "input_sha256": data["input_sha256"],
            "protocol_version": PROBE_PROTOCOL_VERSION,
            "modality": modality,
            "task_type": data["task_type"],
            "split_source": data["split_source"],
            "n_total": len(data["inputs"]),
            "n_train": int(len(data["final_train_idx"])),
            "n_test": int(len(data["test_idx"])),
            "target_labels": data["target_labels"],
            "models": {},
        }
        if (results.get(task, {}).get("dataset_sha256") != data["dataset_sha256"]
                or results.get(task, {}).get("input_sha256") != data["input_sha256"]
                or results.get(task, {}).get("protocol_version") !=
                PROBE_PROTOCOL_VERSION):
            results[task] = task_info
        else:
            existing_models = results[task].get("models", {})
            results[task].update({key: value for key, value in task_info.items()
                                  if key != "models"})
            results[task]["models"] = existing_models

        for model_id in applicable:
            if (model_id in results[task]["models"]
                    and results[task]["models"][model_id].get("linear", {}).get(
                        "protocol_version") == PROBE_PROTOCOL_VERSION):
                print(f"  .. {model_id} cached, skipping", flush=True)
                continue

            spec = embed.MODEL_REGISTRY[model_id]
            print(f"  -> {model_id} ({spec['label']})", flush=True)
            t0 = time.time()
            try:
                X = embed.generate(model_id, task, data["inputs"], modality)
                if X is None:
                    continue
                embed_time = time.time() - t0

                y = data["targets"]
                tr, te = data["final_train_idx"], data["test_idx"]
                lin = linear_probe(
                    X[tr], y[tr], X[te], y[te], data["task_type"],
                    groups=data["resampling_groups"][te])
                entry = {"label": spec["label"], "linear": lin}

                if run_mlp:
                    entry["mlp"] = mlp_probe(X[tr], y[tr], X[te], y[te],
                                             data["task_type"])
                    entry["linear_mlp_gap"] = round(
                        entry["mlp"]["score"] - lin["score"], 4)

                results[task]["models"][model_id] = entry
                save_results(results)

                gap = (f", MLP {entry['mlp']['score']:.4f} "
                       f"(gap {entry['linear_mlp_gap']:+.4f})") if run_mlp else ""
                print(f"     {lin['metric']} = {lin['score']:.4f} "
                      f"(dim {lin['embedding_dim']}, {embed_time:.0f}s){gap}",
                      flush=True)

            except Exception as exc:
                # A failed cell is left absent. It is never back-filled.
                print(f"     FAILED: {type(exc).__name__}: {exc}", flush=True)
                traceback.print_exc()

    save_results(results)
    write_manifest(load_results())
    print(f"\nWrote {RESULTS_PATH}", flush=True)
    return results


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--embeddings-only" in arguments:
        requested = [argument for argument in arguments
                     if argument != "--embeddings-only"]
        precompute_embeddings(requested or None)
    elif "--refresh-metadata" in arguments:
        # Run this last in a release. write_manifest hashes every public
        # artefact, so running it before paired_test.py, run_leakage.py,
        # resolution_analysis.py and split_sensitivity.py have written their
        # outputs records hashes of files that no longer exist in that form.
        requested = [argument for argument in arguments
                     if argument != "--refresh-metadata"]
        refresh_metadata(requested or None)
        print(f"Refreshed {RESULTS_PATH} and {MANIFEST_PATH}", flush=True)
    else:
        run(arguments or None)
