"""Create tidy, descriptive summaries of the secondary scarcity analyses."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.sample_efficiency import consolidate_output

RESULT_PATH = ROOT / "results" / "sample_efficiency.json"
SUMMARY_PATH = ROOT / "results" / "sample_efficiency_summary.csv"
AUGMENTATION_PATH = ROOT / "results" / "smiles_augmentation_summary.csv"
INVARIANCE_PATH = ROOT / "results" / "smiles_view_invariance.csv"
PRIMARY_PATH = ROOT / "results" / "benchmark_results.json"
REPRODUCTION_PATH = ROOT / "results" / "sample_efficiency_reproduction.csv"
AUGMENTED_MODELS = {"chemberta_77m", "chemberta_zinc", "molformer_xl"}
FRACTION_REPEATS = {0.10: 10, 0.25: 10, 0.50: 10, 1.00: 1}
FULL_REPRODUCTION_TOLERANCE = 0.001


def validate_complete(frame: pd.DataFrame, primary_path=PRIMARY_PATH):
    """Reject partial, duplicated, or non-reproducing secondary results."""
    key = ["task", "model_id", "variant", "fraction", "seed"]
    duplicated = frame.duplicated(key, keep=False)
    if duplicated.any():
        raise RuntimeError(
            f"Found {int(duplicated.sum())} duplicated result records")
    if not np.isfinite(frame["score"].to_numpy(dtype=float)).all():
        raise RuntimeError("At least one secondary score is non-finite")

    primary = json.loads(Path(primary_path).read_text())
    expected_canonical = {
        (task, model_id)
        for task, task_payload in primary.items()
        for model_id in task_payload["models"]
    }
    molecular_tasks = {
        task for task, task_payload in primary.items()
        if task_payload["modality"] == "molecule"
    }
    expected_augmented = {
        (task, model_id)
        for task in molecular_tasks for model_id in AUGMENTED_MODELS
        if model_id in primary[task]["models"]
    }
    expected_cells = {
        "canonical": expected_canonical,
        "smiles_mean10": expected_augmented,
    }
    for variant, cells in expected_cells.items():
        observed = frame.loc[frame["variant"] == variant]
        observed_cells = set(zip(observed["task"], observed["model_id"]))
        if observed_cells != cells:
            missing = sorted(cells - observed_cells)
            extra = sorted(observed_cells - cells)
            raise RuntimeError(
                f"{variant}: cell mismatch; missing={missing}, extra={extra}")
        counts = observed.groupby(
            ["task", "model_id", "fraction"]).size()
        for task, model_id in cells:
            for fraction, expected_n in FRACTION_REPEATS.items():
                actual_n = int(counts.get((task, model_id, fraction), 0))
                if actual_n != expected_n:
                    raise RuntimeError(
                        f"{variant}/{task}/{model_id}/{fraction}: expected "
                        f"{expected_n} repeats, found {actual_n}")

    canonical_full = frame[
        (frame["variant"] == "canonical") & (frame["fraction"] == 1.0)]
    reproduction = []
    for row in canonical_full.itertuples():
        reference = primary[row.task]["models"][row.model_id]["linear"]
        difference = row.score - reference["score"]
        reproduction.append({
            "task": row.task,
            "model_id": row.model_id,
            "model_label": row.model_label,
            "primary_score": reference["score"],
            "secondary_full_score": row.score,
            "difference": difference,
            "absolute_difference": abs(difference),
        })
        if not np.isclose(
                row.score, reference["score"],
                atol=FULL_REPRODUCTION_TOLERANCE, rtol=0):
            raise RuntimeError(
                f"Full-data score mismatch for {row.task}/{row.model_id}: "
                f"secondary={row.score}, primary={reference['score']}")
        if row.test_rows != reference["n_test"]:
            raise RuntimeError(
                f"Test-row mismatch for {row.task}/{row.model_id}")

    subset_columns = ["task", "fraction", "seed"]
    canonical_subsets = (frame[frame["variant"] == "canonical"]
                         .groupby(subset_columns)["actual_training_rows"]
                         .nunique())
    if (canonical_subsets != 1).any():
        raise RuntimeError(
            "Canonical models did not use identical subset sizes")
    paired_subsets = frame.pivot_table(
        index=["task", "model_id", "fraction", "seed"],
        columns="variant", values="actual_training_rows", aggfunc="first")
    paired_subsets = paired_subsets.dropna(
        subset=["canonical", "smiles_mean10"])
    if not (paired_subsets["canonical"] ==
            paired_subsets["smiles_mean10"]).all():
        raise RuntimeError(
            "Canonical and augmented variants used different subset sizes")

    expected_total = sum(
        len(cells) * sum(FRACTION_REPEATS.values())
        for cells in expected_cells.values())
    if len(frame) != expected_total:
        raise RuntimeError(
            f"Expected {expected_total} records, found {len(frame)}")
    reproduction = pd.DataFrame(reproduction).sort_values(
        ["task", "model_id"])
    print(
        f"validated {len(frame)} complete records; maximum full-data "
        f"reproduction delta={reproduction['absolute_difference'].max():.4g}")
    return reproduction


def summarize(result_path=RESULT_PATH):
    payload = consolidate_output(Path(result_path))
    frame = pd.DataFrame(payload["records"])
    if frame.empty:
        raise RuntimeError("No sample-efficiency records are available")
    reproduction = validate_complete(frame)
    reproduction.to_csv(REPRODUCTION_PATH, index=False)
    keys = ["task", "modality", "task_type", "model_id", "model_label",
            "variant", "fraction"]
    summary = (frame.groupby(keys, as_index=False)["score"]
               .agg(n_repeats="count", mean_score="mean", sd_score="std",
                    median_score="median", minimum_score="min",
                    maximum_score="max",
                    empirical_q025=lambda x: np.quantile(x, 0.025),
                    empirical_q975=lambda x: np.quantile(x, 0.975)))
    full = (summary[summary["fraction"] == 1.0]
            .set_index(["task", "model_id", "variant"])["mean_score"])
    summary["change_from_full"] = [
        row.mean_score - full.loc[(row.task, row.model_id, row.variant)]
        for row in summary.itertuples()
    ]
    summary.to_csv(SUMMARY_PATH, index=False)

    canonical = frame[frame["variant"] == "canonical"]
    augmented = frame[frame["variant"] == "smiles_mean10"]
    paired = canonical.merge(
        augmented,
        on=["task", "model_id", "fraction", "seed"],
        suffixes=("_canonical", "_augmented"), validate="one_to_one")
    paired["score_change"] = (
        paired["score_augmented"] - paired["score_canonical"])
    aug_keys = ["task", "model_id", "model_label_canonical", "fraction"]
    aug_summary = (paired.groupby(aug_keys, as_index=False)["score_change"]
                   .agg(n_pairs="count", mean_change="mean",
                        sd_change="std", median_change="median",
                        minimum_change="min", maximum_change="max",
                        empirical_q025=lambda x: np.quantile(x, 0.025),
                        empirical_q975=lambda x: np.quantile(x, 0.975),
                        fraction_improved=lambda x: np.mean(x > 0)))
    aug_summary = aug_summary.rename(
        columns={"model_label_canonical": "model_label"})
    aug_summary.to_csv(AUGMENTATION_PATH, index=False)

    invariance = []
    for sidecar in sorted((ROOT / "data" / "augmentation_embeddings")
                          .glob("*.json")):
        metadata = json.loads(sidecar.read_text())
        invariance.append({
            "task": metadata["task"],
            "model_id": metadata["model_id"],
            "model_label": metadata["model_label"],
            "views_per_molecule": metadata["views_per_molecule"],
            "mean_unique_views": metadata["mean_unique_views"],
            "minimum_unique_views": metadata["minimum_unique_views"],
            "maximum_unique_views": metadata["maximum_unique_views"],
            "mean_randomized_to_source_cosine": metadata[
                "mean_randomized_to_source_cosine"],
            "median_randomized_to_source_cosine": metadata[
                "median_randomized_to_source_cosine"],
            "fifth_percentile_randomized_to_source_cosine": metadata[
                "fifth_percentile_randomized_to_source_cosine"],
        })
    pd.DataFrame(invariance).to_csv(INVARIANCE_PATH, index=False)
    print(f"wrote {SUMMARY_PATH}")
    print(f"wrote {AUGMENTATION_PATH}")
    print(f"wrote {INVARIANCE_PATH}")
    print(f"wrote {REPRODUCTION_PATH}")


if __name__ == "__main__":
    summarize()
