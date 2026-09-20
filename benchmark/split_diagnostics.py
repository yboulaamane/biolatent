"""Generate release-level split balance and disjointness diagnostics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.datasets import ALL_DATASETS, get_scaffold, load_benchmark_dataset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "split_diagnostics.json"


def target_summary(values: np.ndarray, labels: list[str], task_type: str):
    values = np.asarray(values)
    if task_type == "regression":
        return {
            "mean": round(float(np.mean(values)), 6),
            "standard_deviation": round(float(np.std(values)), 6),
            "minimum": round(float(np.min(values)), 6),
            "maximum": round(float(np.max(values)), 6),
        }
    if task_type == "multilabel":
        return {
            label: {
                "positive": int(np.sum(values[:, index] == 1)),
                "negative": int(np.sum(values[:, index] == 0)),
                "positive_fraction": round(float(np.mean(values[:, index] == 1)), 6),
            }
            for index, label in enumerate(labels)
        }
    return {
        "positive": int(np.sum(values == 1)),
        "negative": int(np.sum(values == 0)),
        "positive_fraction": round(float(np.mean(values == 1)), 6),
    }


def molecular_groups(inputs: list[str], indices: np.ndarray) -> list[str]:
    groups = []
    for index in indices:
        scaffold = get_scaffold(inputs[index])
        groups.append(scaffold if scaffold else f"__acyclic_{index}")
    return groups


def main() -> None:
    report = {
        "schema_version": 1,
        "interpretation": (
            "Split sizes, target balance and identity/scaffold disjointness. "
            "Zero overlap is checked between the complete non-test fit set and test set."
        ),
        "tasks": {},
    }
    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        split_indices = {
            "train": data["train_idx"],
            "validation": data["val_idx"],
            "non_test_fit": data["final_train_idx"],
            "test": data["test_idx"],
        }
        splits = {}
        for split, indices in split_indices.items():
            entry = {
                "n": int(len(indices)),
                "target": target_summary(
                    data["targets"][indices], data["target_labels"], data["task_type"]
                ) if len(indices) else None,
            }
            if data["modality"] == "molecule" and len(indices):
                groups = molecular_groups(data["inputs"], indices)
                counts = {group: groups.count(group) for group in set(groups)}
                entry.update({
                    "n_scaffold_groups": len(counts),
                    "n_singleton_scaffold_groups": sum(value == 1 for value in counts.values()),
                })
            splits[split] = entry

        fit_inputs = {data["inputs"][index] for index in data["final_train_idx"]}
        test_inputs = {data["inputs"][index] for index in data["test_idx"]}
        overlap = {
            "exact_input_count": len(fit_inputs.intersection(test_inputs)),
            "scaffold_count": None,
        }
        if data["modality"] == "molecule":
            fit_groups = set(molecular_groups(data["inputs"], data["final_train_idx"]))
            test_groups = set(molecular_groups(data["inputs"], data["test_idx"]))
            overlap["scaffold_count"] = len(fit_groups.intersection(test_groups))
        report["tasks"][task] = {
            "modality": data["modality"],
            "task_type": data["task_type"],
            "split_source": data["split_source"],
            "dataset_input_sha256": data["input_sha256"],
            "splits": splits,
            "fit_test_overlap": overlap,
        }
        print(f"{task}: fit/test exact overlap={overlap['exact_input_count']}")
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
