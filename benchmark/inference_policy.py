"""Task-specific dependence and inferential-scope policy."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CLUSTER_REPORT = ROOT / "results" / "sequence_clusters.json"


def _cluster_entry(task: str, data: dict[str, object]) -> dict[str, object]:
    if not CLUSTER_REPORT.exists():
        raise FileNotFoundError(
            f"Missing {CLUSTER_REPORT}; run benchmark/sequence_clusters.py first"
        )
    report = json.loads(CLUSTER_REPORT.read_text())
    entry = report.get("tasks", {}).get(task)
    if not entry:
        raise RuntimeError(f"{task}: no sequence-cluster entry")
    if entry["dataset_input_sha256"] != data["input_sha256"]:
        raise RuntimeError(f"{task}: sequence clusters were built for different inputs")
    if entry["n_test"] != len(data["test_idx"]):
        raise RuntimeError(f"{task}: sequence-cluster length differs from test split")
    return entry


def inference_policy(task: str, data: dict[str, object]) -> dict[str, object]:
    if data["modality"] == "molecule":
        groups = np.asarray(data["resampling_groups"])[data["test_idx"]]
        return {
            "enabled": True,
            "groups": groups.astype(str),
            "resampling_unit": "Murcko scaffold cluster",
            "note": "Molecular dependence is represented by complete Murcko scaffolds.",
        }
    if task == "DeepLoc":
        entry = _cluster_entry(task, data)
        return {
            "enabled": True,
            "groups": np.asarray(entry["assignments"], dtype=str),
            "resampling_unit": "MMseqs2 30%-identity homology cluster",
            "note": (
                f"{entry['n_test']} test proteins form {entry['n_clusters']} "
                "MMseqs2 clusters at 30% identity and 80% bidirectional coverage."
            ),
        }
    if task == "Fluorescence":
        entry = _cluster_entry(task, data)
        return {
            "enabled": False,
            "groups": np.arange(len(data["test_idx"])).astype(str),
            "resampling_unit": "test variant (descriptive only)",
            "note": (
                f"Formal inference is withheld because all {entry['n_test']} "
                "GFP test variants form one MMseqs2 component at 90% identity "
                "and 90% bidirectional coverage. Intervals describe only the "
                "fixed test variants."
            ),
        }
    return {
        "enabled": True,
        "groups": np.arange(len(data["test_idx"])).astype(str),
        "resampling_unit": "test item",
        "note": "Inference is conditional on the fixed published test partition.",
    }
