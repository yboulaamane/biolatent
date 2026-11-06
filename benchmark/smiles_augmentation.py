"""Deterministic randomized-SMILES view aggregation for frozen encoders.

Randomized SMILES preserve the molecular graph and therefore the endpoint
label.  This analysis asks whether averaging several serialization views makes
SMILES-language-model representations more useful when labelled molecules are
scarce.  It is deliberately restricted to frozen SMILES encoders; artificial
protein mutations, DNA edits, SMOTE, and embedding-space noise are not assumed
to be biologically label preserving.

One source SMILES and ``views - 1`` randomized SMILES are embedded separately,
then averaged to one vector per molecule.  Keeping one row per molecule avoids
pseudo-replication and validation leakage between alternative serializations
of the same structure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np
from rdkit import Chem

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.datasets import MOLECULE_TASKS, load_benchmark_dataset
from benchmark.embed import MODEL_REGISTRY, embed_hf


OUTPUT_DIR = ROOT / "data" / "augmentation_embeddings"
SUPPORTED_MODELS = ("chemberta_77m", "chemberta_zinc", "molformer_xl")
PROTOCOL_VERSION = 1


def randomized_views(smiles_values, views=10, seed=42):
    """Return flattened deterministic views and per-molecule uniqueness."""
    if views < 2:
        raise ValueError("At least two views are required for augmentation")
    flattened = []
    unique_counts = []
    for index, source in enumerate(smiles_values):
        molecule = Chem.MolFromSmiles(str(source))
        if molecule is None:
            raise ValueError(f"Invalid SMILES at row {index}: {source}")
        canonical = Chem.MolToSmiles(molecule, canonical=True)
        # RDKit can very occasionally emit a non-equivalent stereochemical
        # serialization for large macrocycles. Generate candidates one at a
        # time and retain only those that round-trip to the exact isomeric
        # canonical SMILES. This makes the augmentation conservative: a view
        # is never used merely because it parses successfully.
        randomized = []
        candidates = list(Chem.MolToRandomSmilesVect(
            molecule, views - 1, randomSeed=seed + index))
        attempt = 0
        max_attempts = 100 * (views - 1)
        while candidates and len(randomized) < views - 1:
            candidate = candidates.pop(0)
            parsed = Chem.MolFromSmiles(candidate)
            if parsed is None:
                continue
            candidate_canonical = Chem.MolToSmiles(
                parsed, canonical=True, isomericSmiles=True)
            if candidate_canonical == canonical:
                randomized.append(candidate)
        # Refill only the rare candidates that failed the identity check.
        while len(randomized) < views - 1 and attempt < max_attempts:
            candidate = Chem.MolToRandomSmilesVect(
                molecule, 1,
                randomSeed=seed + (index + 1) * max_attempts + attempt)[0]
            attempt += 1
            parsed = Chem.MolFromSmiles(candidate)
            if parsed is not None and Chem.MolToSmiles(
                    parsed, canonical=True,
                    isomericSmiles=True) == canonical:
                randomized.append(candidate)
        if len(randomized) != views - 1:
            raise RuntimeError(
                f"Row {index}: obtained only {len(randomized)} identity-"
                f"preserving randomized views after {attempt} attempts")
        molecule_views = [str(source), *randomized]
        if len(molecule_views) != views:
            raise RuntimeError(
                f"Row {index}: requested {views} views, obtained "
                f"{len(molecule_views)}")
        flattened.extend(molecule_views)
        unique_counts.append(len(set(molecule_views)))
    return flattened, np.asarray(unique_counts, dtype=int)


def output_path(model_id, task, views):
    return OUTPUT_DIR / f"{model_id}__{task}__mean{views}.npy"


def generate(model_id, task, views=10, seed=42, force=False):
    if model_id not in SUPPORTED_MODELS:
        raise ValueError(
            f"Augmentation is defined only for {SUPPORTED_MODELS}; got "
            f"{model_id}")
    if task not in MOLECULE_TASKS:
        raise ValueError("Randomized SMILES apply only to molecular tasks")
    spec = MODEL_REGISTRY[model_id]
    if spec["kind"] != "hf" or spec["modality"] != "molecule":
        raise ValueError(f"{model_id} is not a supported SMILES encoder")

    data = load_benchmark_dataset(task)
    views_flat, unique_counts = randomized_views(
        data["inputs"], views=views, seed=seed)
    view_sha256 = hashlib.sha256(
        "\0".join(views_flat).encode("utf-8")).hexdigest()
    destination = output_path(model_id, task, views)
    sidecar = destination.with_suffix(".json")
    if destination.exists() and sidecar.exists() and not force:
        metadata = json.loads(sidecar.read_text())
        if (metadata.get("protocol_version") == PROTOCOL_VERSION
                and metadata.get("view_sha256") == view_sha256
                and metadata.get("revision") == spec.get("revision")):
            print(f"cached {destination}", flush=True)
            return np.load(destination, mmap_mode="r")

    view_matrix, inference = embed_hf(
        views_flat, spec, "molecule", token_budget=2048)
    view_matrix = view_matrix.reshape(len(data["inputs"]), views, -1)
    norms = np.linalg.norm(view_matrix, axis=2, keepdims=True)
    normalized = view_matrix / np.maximum(norms, np.finfo(np.float32).eps)
    source_cosine = np.sum(
        normalized[:, :1, :] * normalized[:, 1:, :], axis=2).ravel()
    matrix = view_matrix.mean(axis=1)
    matrix = matrix.astype(np.float32)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f"{destination.stem}.{os.getpid()}.tmp.npy")
    np.save(temporary, matrix)
    os.replace(temporary, destination)
    metadata = {
        "protocol_version": PROTOCOL_VERSION,
        "model_id": model_id,
        "model_label": spec["label"],
        "checkpoint": spec["checkpoint"],
        "revision": spec.get("revision"),
        "task": task,
        "dataset_sha256": data["dataset_sha256"],
        "input_sha256": data["input_sha256"],
        "view_sha256": view_sha256,
        "views_per_molecule": int(views),
        "view_policy": "source SMILES plus deterministic randomized SMILES",
        "aggregation": "arithmetic mean of frozen view embeddings",
        "seed": int(seed),
        "n_molecules": int(len(matrix)),
        "embedding_dim": int(matrix.shape[1]),
        "mean_unique_views": float(unique_counts.mean()),
        "minimum_unique_views": int(unique_counts.min()),
        "maximum_unique_views": int(unique_counts.max()),
        "mean_randomized_to_source_cosine": float(source_cosine.mean()),
        "median_randomized_to_source_cosine": float(
            np.median(source_cosine)),
        "fifth_percentile_randomized_to_source_cosine": float(
            np.percentile(source_cosine, 5)),
        "matrix_sha256": hashlib.sha256(matrix.tobytes()).hexdigest(),
        **inference,
    }
    temporary_sidecar = sidecar.with_name(
        f"{sidecar.name}.{os.getpid()}.tmp")
    temporary_sidecar.write_text(json.dumps(metadata, indent=2))
    os.replace(temporary_sidecar, sidecar)
    print(f"wrote {destination} {matrix.shape}", flush=True)
    return matrix


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", choices=SUPPORTED_MODELS)
    parser.add_argument("task", choices=MOLECULE_TASKS)
    parser.add_argument("--views", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    generate(arguments.model, arguments.task, views=arguments.views,
             seed=arguments.seed, force=arguments.force)
