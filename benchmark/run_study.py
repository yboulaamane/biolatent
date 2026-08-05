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
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.probe import linear_probe, mlp_probe

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
RESULTS_PATH = os.path.join(RESULTS_DIR, "benchmark_results.json")


def load_results():
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH) as fh:
            return json.load(fh)
    return {}


def save_results(results):
    tmp = RESULTS_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(results, fh, indent=2)
    os.replace(tmp, RESULTS_PATH)


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

        results.setdefault(task, {
            "modality": modality,
            "task_type": data["task_type"],
            "split_source": data["split_source"],
            "n_total": len(data["inputs"]),
            "n_train": int(len(data["train_idx"])),
            "n_test": int(len(data["test_idx"])),
            "models": {},
        })

        for model_id in applicable:
            if model_id in results[task]["models"]:
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
                tr, te = data["train_idx"], data["test_idx"]
                lin = linear_probe(X[tr], y[tr], X[te], y[te], data["task_type"])
                entry = {"label": spec["label"], "linear": lin,
                         "embed_seconds": round(embed_time, 1)}

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

            except Exception:
                # A failed cell is left absent. It is never back-filled.
                print(f"     FAILED: {traceback.format_exc().splitlines()[-1]}",
                      flush=True)

    save_results(results)
    print(f"\nWrote {RESULTS_PATH}", flush=True)
    return results


if __name__ == "__main__":
    run(sys.argv[1:] or None)
