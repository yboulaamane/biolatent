"""Quantify and map the chemical neighborhoods induced by frozen embeddings.

The analysis asks whether label efficiency and randomized-SMILES augmentation
can be explained by local representation geometry.  It deliberately treats
two-dimensional UMAP coordinates as a visual aid rather than evidence.  All
scientific comparisons use neighborhoods in the original representation
space and report projection preservation separately.

For each molecular task, the same deterministic sample of at most 1,000
molecules is used for every applicable representation.  ECFP4 uses Jaccard
(Tanimoto) similarity, standardized RDKit descriptors use Euclidean distance,
and dense learned representations use cosine similarity.  Results are
descriptive and exploratory; no claim of causal mechanism is made.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
import umap


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.datasets import MOLECULE_TASKS, load_benchmark_dataset
from benchmark.embed import MODEL_REGISTRY, cache_path, is_applicable
from benchmark.smiles_augmentation import output_path as augmentation_path


RESULT_DIR = ROOT / "results"
MAP_DIR = RESULT_DIR / "chemical_space_maps"
NEIGHBORHOOD_PATH = RESULT_DIR / "chemical_space_neighborhoods.csv"
MAP_SUMMARY_PATH = RESULT_DIR / "chemical_space_mapping_summary.csv"
CORRELATION_PATH = RESULT_DIR / "chemical_space_correlations.csv"
MAP_COORDINATE_PATH = RESULT_DIR / "chemical_space_map_coordinates.csv.gz"

MODEL_ORDER = (
    "ecfp4", "rdkit2d", "chemberta_77m", "chemberta_zinc",
    "molformer_xl", "unimol_v1", "molclr_gin", "grover_base",
    "grover_large",
)
SMILES_MODELS = ("chemberta_77m", "chemberta_zinc", "molformer_xl")
K_VALUES = (5, 10, 20)
ANALYSIS_SAMPLE_SIZE = 1000
MAP_SAMPLE_PER_TASK = 400
SEED = 42
PROTOCOL_VERSION = 1


def deterministic_sample(n_rows: int, maximum: int, seed: int) -> np.ndarray:
    """Return a sorted fixed random sample without inspecting labels."""
    if n_rows <= maximum:
        return np.arange(n_rows, dtype=int)
    rng = np.random.RandomState(seed)
    return np.sort(rng.choice(n_rows, size=maximum, replace=False))


def representation_kind(model_id: str) -> str:
    if model_id == "ecfp4":
        return "jaccard"
    if model_id == "rdkit2d":
        return "standardized_euclidean"
    return "cosine"


def prepare_matrix(matrix: np.ndarray, kind: str) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    if kind == "standardized_euclidean":
        values = StandardScaler().fit_transform(values).astype(np.float32)
    elif kind == "cosine":
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        values = values / np.maximum(norms, np.finfo(np.float32).eps)
    return values


def nearest_neighbors(matrix: np.ndarray, kind: str,
                      maximum_k: int) -> np.ndarray:
    """Exact neighbors for a moderate, common sample of molecules."""
    values = prepare_matrix(matrix, kind)
    if kind == "jaccard":
        binary = values > 0
        counts = binary.sum(axis=1, dtype=np.float32)
        intersection = binary.astype(np.float32) @ binary.T.astype(np.float32)
        union = counts[:, None] + counts[None, :] - intersection
        similarity = np.divide(
            intersection, union, out=np.zeros_like(intersection),
            where=union > 0)
        np.fill_diagonal(similarity, -np.inf)
        candidates = np.argpartition(
            -similarity, kth=maximum_k - 1, axis=1)[:, :maximum_k]
        candidate_values = np.take_along_axis(similarity, candidates, axis=1)
        order = np.argsort(-candidate_values, axis=1)
    elif kind == "cosine":
        similarity = values @ values.T
        np.fill_diagonal(similarity, -np.inf)
        candidates = np.argpartition(
            -similarity, kth=maximum_k - 1, axis=1)[:, :maximum_k]
        candidate_values = np.take_along_axis(similarity, candidates, axis=1)
        order = np.argsort(-candidate_values, axis=1)
    else:
        squared_norm = np.sum(values * values, axis=1)
        distance = (squared_norm[:, None] + squared_norm[None, :]
                    - 2.0 * (values @ values.T))
        np.maximum(distance, 0, out=distance)
        np.fill_diagonal(distance, np.inf)
        candidates = np.argpartition(
            distance, kth=maximum_k - 1, axis=1)[:, :maximum_k]
        candidate_values = np.take_along_axis(distance, candidates, axis=1)
        order = np.argsort(candidate_values, axis=1)
    return np.take_along_axis(candidates, order, axis=1)


def adjusted_agreement(labels: np.ndarray, neighbors: np.ndarray) -> float:
    """Agreement above the chance rate implied by marginal frequencies."""
    values = np.asarray(labels)
    if values.ndim == 2:
        return float(np.mean([
            adjusted_agreement(values[:, column], neighbors)
            for column in range(values.shape[1])
        ]))
    _, inverse, counts = np.unique(
        values.astype(str), return_inverse=True, return_counts=True)
    observed = np.mean(inverse[:, None] == inverse[neighbors])
    probabilities = counts / counts.sum()
    chance = float(np.sum(probabilities ** 2))
    if chance >= 1:
        return 0.0
    return float((observed - chance) / (1.0 - chance))


def regression_smoothness(targets: np.ndarray,
                          neighbors: np.ndarray) -> float:
    """Neighbor similarity relative to the mean difference of all pairs."""
    y = np.asarray(targets, dtype=float).reshape(-1)
    local_mae = float(np.mean(np.abs(y[:, None] - y[neighbors])))
    pairwise_mae = float(np.mean(np.abs(y[:, None] - y[None, :])))
    if pairwise_mae == 0:
        return 0.0
    return 1.0 - local_mae / pairwise_mae


def endpoint_coherence(targets: np.ndarray, task_type: str,
                       neighbors: np.ndarray) -> float:
    if task_type == "regression":
        return regression_smoothness(targets, neighbors)
    return adjusted_agreement(targets, neighbors)


def neighbor_prediction_score(targets: np.ndarray, task_type: str,
                              neighbors: np.ndarray) -> float:
    """Leave-one-out neighbor prediction, used only as a geometry diagnostic."""
    y = np.asarray(targets)
    if task_type == "regression":
        return float(r2_score(y, y[neighbors].mean(axis=1)))
    if task_type == "classification":
        prediction = y[neighbors].mean(axis=1)
        return float(roc_auc_score(y, prediction))
    scores = []
    for column in range(y.shape[1]):
        prediction = y[neighbors, column].mean(axis=1)
        scores.append(roc_auc_score(y[:, column], prediction))
    return float(np.mean(scores))


def neighbor_recall(neighbors: np.ndarray,
                    reference_neighbors: np.ndarray) -> float:
    """Fraction of reference neighbors recovered for each molecule."""
    recovered = []
    for observed, reference in zip(neighbors, reference_neighbors):
        recovered.append(len(set(observed).intersection(reference)) /
                         len(reference))
    return float(np.mean(recovered))


def analyze_task(task: str) -> list[dict]:
    data = load_benchmark_dataset(task)
    task_seed = SEED + 1009 * list(MOLECULE_TASKS).index(task)
    rows = deterministic_sample(len(data["inputs"]), ANALYSIS_SAMPLE_SIZE,
                                task_seed)
    targets = np.asarray(data["targets"])[rows]
    scaffolds = np.asarray(data["resampling_groups"], dtype=object)[rows]
    maximum_k = max(K_VALUES)
    ecfp = np.load(cache_path("ecfp4", task), mmap_mode="r")[rows]
    reference = nearest_neighbors(ecfp, "jaccard", maximum_k)
    records = []

    for model_id in MODEL_ORDER:
        if not is_applicable(model_id, task, data["modality"]):
            continue
        variants = [("canonical", Path(cache_path(model_id, task)))]
        if model_id in SMILES_MODELS:
            augmented = augmentation_path(model_id, task, 10)
            if augmented.exists():
                variants.append(("smiles_mean10", augmented))
        kind = representation_kind(model_id)
        for variant, matrix_path in variants:
            matrix = np.load(matrix_path, mmap_mode="r")[rows]
            neighbors = nearest_neighbors(matrix, kind, maximum_k)
            for k in K_VALUES:
                active = neighbors[:, :k]
                reference_active = reference[:, :k]
                records.append({
                    "protocol_version": PROTOCOL_VERSION,
                    "task": task,
                    "task_type": data["task_type"],
                    "model_id": model_id,
                    "model_label": MODEL_REGISTRY[model_id]["label"],
                    "variant": variant,
                    "distance_policy": kind,
                    "sample_seed": task_seed,
                    "sample_rows": len(rows),
                    "k": k,
                    "endpoint_coherence": endpoint_coherence(
                        targets, data["task_type"], active),
                    "neighbor_prediction_score": neighbor_prediction_score(
                        targets, data["task_type"], active),
                    "scaffold_coherence": adjusted_agreement(
                        scaffolds, active),
                    "ecfp_neighbor_recall": neighbor_recall(
                        active, reference_active),
                })
    return records


def common_map_rows() -> dict[str, np.ndarray]:
    """Identical molecules for the nine-panel representation atlas."""
    samples = {}
    # MolCLR is intentionally unavailable for ClinTox, so use the five-task
    # intersection to keep every atlas panel directly comparable.
    tasks = [task for task in MOLECULE_TASKS if task != "ClinTox"]
    for offset, task in enumerate(tasks):
        data = load_benchmark_dataset(task)
        samples[task] = deterministic_sample(
            len(data["inputs"]), MAP_SAMPLE_PER_TASK,
            SEED + 7919 * (offset + 1))
    return samples


def analyze_maps() -> tuple[pd.DataFrame, pd.DataFrame]:
    samples = common_map_rows()
    coordinate_records = []
    summary_records = []
    for model_id in MODEL_ORDER:
        matrices = []
        dataset_labels = []
        scaffold_labels = []
        source_rows = []
        for task, rows in samples.items():
            data = load_benchmark_dataset(task)
            matrix = np.load(cache_path(model_id, task), mmap_mode="r")[rows]
            matrices.append(np.asarray(matrix, dtype=np.float32))
            dataset_labels.extend([task] * len(rows))
            scaffold_labels.extend(
                np.asarray(data["resampling_groups"], dtype=object)[rows])
            source_rows.extend(rows.tolist())
        matrix = np.concatenate(matrices, axis=0)
        kind = representation_kind(model_id)
        prepared = prepare_matrix(matrix, kind)
        metric = {"jaccard": "jaccard",
                  "standardized_euclidean": "euclidean",
                  "cosine": "cosine"}[kind]
        reducer = umap.UMAP(
            n_neighbors=20, min_dist=0.15, n_components=2,
            metric=metric, random_state=SEED, transform_seed=SEED,
            n_jobs=1)
        coordinates = reducer.fit_transform(prepared)

        high_neighbors = nearest_neighbors(matrix, kind, 15)
        low_neighbors = nearest_neighbors(
            coordinates.astype(np.float32), "standardized_euclidean", 15)
        datasets = np.asarray(dataset_labels, dtype=object)
        scaffolds = np.asarray(scaffold_labels, dtype=object)
        summary_records.append({
            "protocol_version": PROTOCOL_VERSION,
            "model_id": model_id,
            "model_label": MODEL_REGISTRY[model_id]["label"],
            "distance_policy": kind,
            "map_rows": len(matrix),
            "map_tasks": ";".join(samples),
            "umap_neighbors": 20,
            "umap_min_dist": 0.15,
            "projection_neighbor_recall_at_15": neighbor_recall(
                low_neighbors, high_neighbors),
            "dataset_coherence_at_15": adjusted_agreement(
                datasets, high_neighbors),
            "scaffold_coherence_at_15": adjusted_agreement(
                scaffolds, high_neighbors),
        })
        task_offsets = np.cumsum([0, *[len(rows) for rows in samples.values()]])
        task_names = list(samples)
        for position, (x_coord, y_coord) in enumerate(coordinates):
            task_index = int(np.searchsorted(
                task_offsets[1:], position, side="right"))
            coordinate_records.append({
                "model_id": model_id,
                "model_label": MODEL_REGISTRY[model_id]["label"],
                "task": task_names[task_index],
                "source_row": source_rows[position],
                "umap_1": float(x_coord),
                "umap_2": float(y_coord),
            })
    return pd.DataFrame(summary_records), pd.DataFrame(coordinate_records)


def correlation_summary(neighborhoods: pd.DataFrame) -> pd.DataFrame:
    """Relate geometry to scarcity and augmentation without causal claims."""
    records = []
    canonical = neighborhoods[
        (neighborhoods["variant"] == "canonical") &
        (neighborhoods["k"] == 10)]
    scarcity = pd.read_csv(RESULT_DIR / "sample_efficiency_summary.csv")
    scarcity = scarcity[
        (scarcity["variant"] == "canonical") &
        (scarcity["fraction"] < 1.0)]
    merged = scarcity.merge(
        canonical,
        on=["task", "model_id"], validate="many_to_one")
    for fraction in (0.10, 0.25, 0.50):
        active = merged[merged["fraction"] == fraction]
        for task, group in active.groupby("task"):
            for geometry_metric in (
                    "endpoint_coherence", "ecfp_neighbor_recall",
                    "scaffold_coherence"):
                statistic, p_value = spearmanr(
                    group[geometry_metric], group["mean_score"])
                records.append({
                    "analysis": "label_efficiency",
                    "task": task,
                    "task_type": group["task_type_x"].iloc[0],
                    "fraction": fraction,
                    "geometry_metric": geometry_metric,
                    "performance_metric": "mean_score",
                    "n_cells": len(group),
                    "spearman_rho": statistic,
                    "unadjusted_p_value": p_value,
                })

    augmented = neighborhoods[
        (neighborhoods["variant"] == "smiles_mean10") &
        (neighborhoods["k"] == 10)]
    paired_geometry = canonical.merge(
        augmented, on=["task", "model_id"],
        suffixes=("_canonical", "_augmented"), validate="one_to_one")
    for metric in ("endpoint_coherence", "ecfp_neighbor_recall",
                   "scaffold_coherence"):
        paired_geometry[f"delta_{metric}"] = (
            paired_geometry[f"{metric}_augmented"] -
            paired_geometry[f"{metric}_canonical"])
    augmentation = pd.read_csv(
        RESULT_DIR / "smiles_augmentation_summary.csv")
    paired = augmentation.merge(
        paired_geometry, on=["task", "model_id"], validate="many_to_one")
    for fraction in (0.10, 0.25, 0.50, 1.0):
        active = paired[paired["fraction"] == fraction]
        for task_type, group in [
                ("all", active),
                ("classification", active[active["task_type_canonical"] !=
                                          "regression"]),
                ("regression", active[active["task_type_canonical"] ==
                                      "regression"])]:
            for metric in ("endpoint_coherence", "ecfp_neighbor_recall",
                           "scaffold_coherence"):
                statistic, p_value = spearmanr(
                    group[f"delta_{metric}"], group["mean_change"])
                records.append({
                    "analysis": "smiles_augmentation",
                    "task": task_type,
                    "task_type": task_type,
                    "fraction": fraction,
                    "geometry_metric": f"delta_{metric}",
                    "performance_metric": "score_change",
                    "n_cells": len(group),
                    "spearman_rho": statistic,
                    "unadjusted_p_value": p_value,
                })
    frame = pd.DataFrame(records)
    frame["holm_p_value"] = np.nan
    # Treat scarcity and augmentation as separate exploratory families.
    for _, indices in frame.groupby("analysis").groups.items():
        indices = np.asarray(list(indices), dtype=int)
        p_values = frame.loc[indices, "unadjusted_p_value"].to_numpy()
        order = np.argsort(p_values)
        adjusted_ordered = np.maximum.accumulate(
            p_values[order] * (len(p_values) - np.arange(len(p_values))))
        adjusted = np.empty_like(adjusted_ordered)
        adjusted[order] = np.minimum(adjusted_ordered, 1.0)
        frame.loc[indices, "holm_p_value"] = adjusted
    return frame


def run(skip_maps: bool = False) -> None:
    records = []
    for task in MOLECULE_TASKS:
        print(f"neighborhoods: {task}", flush=True)
        records.extend(analyze_task(task))
    neighborhoods = pd.DataFrame(records)
    neighborhoods.to_csv(NEIGHBORHOOD_PATH, index=False)
    print(f"wrote {NEIGHBORHOOD_PATH}", flush=True)

    correlations = correlation_summary(neighborhoods)
    correlations.to_csv(CORRELATION_PATH, index=False)
    print(f"wrote {CORRELATION_PATH}", flush=True)

    if not skip_maps:
        print("UMAP atlas", flush=True)
        summary, coordinates = analyze_maps()
        summary.to_csv(MAP_SUMMARY_PATH, index=False)
        coordinates.to_csv(MAP_COORDINATE_PATH, index=False,
                           compression="gzip")
        print(f"wrote {MAP_SUMMARY_PATH}", flush=True)
        print(f"wrote {MAP_COORDINATE_PATH}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-maps", action="store_true",
        help="Compute original-space neighborhoods without fitting UMAP")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    run(skip_maps=arguments.skip_maps)
