"""Label-scarcity analysis for the BioLatent frozen-representation study.

The primary benchmark asks what can be decoded from each complete frozen
representation.  This secondary analysis repeats the same linear-probe
protocol after reducing only the labelled training partition.  The original
test partition is never resampled or used for model selection.

Molecular training subsets retain complete Bemis--Murcko scaffold groups.
Other modalities are sampled at the sequence level because the published
training files do not expose within-training homology/chromosome group IDs.
Classification subsets are rejected unless every outcome supports three-fold
cross-validation.  Results are written incrementally so Slurm jobs can resume.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.embed import MODEL_REGISTRY, cache_path, is_applicable
from benchmark.probe import linear_probe


DEFAULT_OUTPUT = ROOT / "results" / "sample_efficiency.json"
DEFAULT_FRACTIONS = (0.10, 0.25, 0.50, 1.00)
DEFAULT_SEEDS = (7, 11, 19, 21, 29, 31, 37, 42, 53, 61)
PROTOCOL_VERSION = 1


def _valid_for_cv(y: np.ndarray, task_type: str, folds: int = 3) -> bool:
    """Whether every fitted outcome has enough observations for CV."""
    values = np.asarray(y)
    if task_type == "regression":
        return len(values) >= folds
    if task_type == "classification":
        _, counts = np.unique(values.astype(int), return_counts=True)
        return len(counts) >= 2 and bool(np.all(counts >= folds))
    if task_type == "multilabel":
        if values.ndim != 2 or len(values) < 2 * folds:
            return False
        for column in range(values.shape[1]):
            _, counts = np.unique(values[:, column].astype(int),
                                  return_counts=True)
            if len(counts) < 2 or np.any(counts < folds):
                return False
        return True
    raise ValueError(f"Unknown task type {task_type}")


def _sample_complete_groups(pool: np.ndarray, groups: np.ndarray,
                            target_n: int, rng: np.random.RandomState) -> np.ndarray:
    """Sample whole dependence groups, stopping close to ``target_n``."""
    group_to_rows = {}
    for row in pool:
        group_to_rows.setdefault(str(groups[row]), []).append(int(row))
    keys = np.array(list(group_to_rows), dtype=object)
    rng.shuffle(keys)
    chosen = []
    for key in keys:
        rows = group_to_rows[str(key)]
        before = abs(len(chosen) - target_n)
        after = abs(len(chosen) + len(rows) - target_n)
        if len(chosen) < target_n or after < before:
            chosen.extend(rows)
        if len(chosen) >= target_n:
            break
    return np.asarray(sorted(chosen), dtype=int)


def select_training_subset(data: dict, fraction: float, seed: int,
                           max_attempts: int = 500) -> np.ndarray:
    """Return a deterministic, CV-valid subset of the non-test partition."""
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0, 1]")
    pool = np.asarray(data["final_train_idx"], dtype=int)
    if fraction == 1:
        return pool.copy()

    target_n = max(3, int(round(len(pool) * fraction)))
    targets = np.asarray(data["targets"])
    for attempt in range(max_attempts):
        rng = np.random.RandomState(seed + 1009 * attempt)
        if data["modality"] == "molecule":
            chosen = _sample_complete_groups(
                pool, np.asarray(data["resampling_groups"], dtype=object),
                target_n, rng)
        else:
            chosen = np.sort(rng.choice(pool, size=target_n, replace=False))
        if _valid_for_cv(targets[chosen], data["task_type"]):
            return chosen
    raise RuntimeError(
        f"{data['dataset_name']}: could not draw a CV-valid {fraction:.0%} "
        f"training subset after {max_attempts} attempts")


def _empty_output() -> dict:
    return {
        "schema_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "estimand": "fixed-test performance versus labelled training fraction",
        "fractions": list(DEFAULT_FRACTIONS),
        "seeds": list(DEFAULT_SEEDS),
        "records": [],
    }


def _record_directory(path: Path) -> Path:
    return path.parent / f"{path.stem}_records"


def _load_base_output(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return _empty_output()


def _load_output(path: Path) -> dict:
    output = _load_base_output(path)
    keyed = {_record_key(item): item for item in output["records"]}
    for shard in sorted(_record_directory(path).glob("*.json")):
        item = json.loads(shard.read_text())
        keyed[_record_key(item)] = item
    output["records"] = sorted(
        keyed.values(), key=lambda item: (
            item["task"], item["model_id"], item["variant"],
            item["fraction"], item["seed"]))
    return output


def _record_key(record: dict) -> tuple:
    return (record["task"], record["model_id"], record["variant"],
            float(record["fraction"]), int(record["seed"]))


def _write_record_shard(path: Path, record: dict) -> None:
    """Persist a result independently before rebuilding the combined JSON.

    Independent shards are robust to advisory-lock behavior on a shared
    cluster filesystem: concurrent jobs may race while materializing the
    combined file, but they cannot erase another completed fit.
    """
    directory = _record_directory(path)
    directory.mkdir(parents=True, exist_ok=True)
    encoded_key = json.dumps(_record_key(record), separators=(",", ":"))
    digest = hashlib.sha256(encoded_key.encode("utf-8")).hexdigest()
    destination = directory / f"{digest}.json"
    temporary = directory / (
        f".{digest}.{socket.gethostname()}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, indent=2))
    os.replace(temporary, destination)


def _save_record(path: Path, record: dict) -> None:
    """Merge one record under a lock and replace the JSON atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_record_shard(path, record)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Shards are the durable source of truth, but scanning thousands of
        # files after every fit would make the analysis quadratic. Update the
        # convenience combined file from its current contents here; a resume
        # or final consolidation reads all shards exactly once.
        output = _load_base_output(path)
        keyed = {_record_key(item): item for item in output["records"]}
        keyed[_record_key(record)] = record
        output["records"] = sorted(
            keyed.values(), key=lambda item: (
                item["task"], item["model_id"], item["variant"],
                item["fraction"], item["seed"]))
        temporary = path.with_name(
            f"{path.name}.{socket.gethostname()}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(output, indent=2))
        os.replace(temporary, path)
        fcntl.flock(lock, fcntl.LOCK_UN)


def consolidate_output(path: Path = DEFAULT_OUTPUT) -> dict:
    """Materialize all durable record shards as one release JSON file."""
    import rdkit
    import scipy
    import sklearn

    path = Path(path)
    output = _load_output(path)
    output["software"] = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "rdkit": rdkit.__version__,
    }
    temporary = path.with_name(
        f"{path.name}.{socket.gethostname()}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(output, indent=2))
    os.replace(temporary, path)
    return output


def run(tasks, models=None, fractions=DEFAULT_FRACTIONS,
        seeds=DEFAULT_SEEDS, output=DEFAULT_OUTPUT, variant="canonical",
        matrix_template=None, n_jobs=4):
    """Run or resume learning curves for selected task/model cells."""
    output = Path(output)
    existing = _load_output(output)
    # Backfill legacy combined-only records so future concurrent runs cannot
    # lose them if advisory locks are not honored across compute nodes.
    for record in existing["records"]:
        shard = _record_directory(output) / (
            hashlib.sha256(json.dumps(
                _record_key(record), separators=(",", ":")
            ).encode("utf-8")).hexdigest() + ".json")
        if not shard.exists():
            _write_record_shard(output, record)
    completed = {_record_key(record) for record in existing["records"]}
    for task in tasks:
        data = load_benchmark_dataset(task)
        task_models = [
            model_id for model_id in MODEL_REGISTRY
            if is_applicable(model_id, task, data["modality"])
            and (models is None or model_id in models)
        ]
        for model_id in task_models:
            matrix_path = (Path(matrix_template.format(
                task=task, model=model_id, variant=variant))
                if matrix_template else Path(cache_path(model_id, task)))
            if not matrix_path.exists():
                raise FileNotFoundError(
                    f"Missing frozen matrix for {model_id}/{task}: "
                    f"{matrix_path}")
            matrix = np.load(matrix_path, mmap_mode="r")
            if len(matrix) != len(data["inputs"]):
                raise RuntimeError(
                    f"{model_id}/{task}: matrix has {len(matrix)} rows, "
                    f"dataset has {len(data['inputs'])}")
            test_idx = np.asarray(data["test_idx"], dtype=int)
            for fraction in fractions:
                active_seeds = seeds if fraction < 1 else seeds[:1]
                for seed in active_seeds:
                    key = (task, model_id, variant, float(fraction), int(seed))
                    if key in completed:
                        continue
                    train_idx = select_training_subset(data, fraction, seed)
                    result = linear_probe(
                        np.asarray(matrix[train_idx]),
                        np.asarray(data["targets"])[train_idx],
                        np.asarray(matrix[test_idx]),
                        np.asarray(data["targets"])[test_idx],
                        data["task_type"], n_jobs=n_jobs, n_boot=0)
                    record = {
                        "task": task,
                        "modality": data["modality"],
                        "task_type": data["task_type"],
                        "model_id": model_id,
                        "model_label": MODEL_REGISTRY[model_id]["label"],
                        "variant": variant,
                        "fraction": float(fraction),
                        "seed": int(seed),
                        "target_training_rows": int(round(
                            len(data["final_train_idx"]) * fraction)),
                        "actual_training_rows": int(len(train_idx)),
                        "test_rows": int(len(test_idx)),
                        "subset_unit": ("Bemis-Murcko scaffold"
                                        if data["modality"] == "molecule"
                                        else "sequence"),
                        **result,
                    }
                    _save_record(output, record)
                    completed.add(key)
                    print(
                        f"{task:15s} {model_id:24s} {fraction:>5.0%} "
                        f"seed={seed:3d} n={len(train_idx):6d} "
                        f"score={result['score']:.4f}", flush=True)
    consolidate_output(output)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", nargs="*", default=ALL_DATASETS,
                        choices=ALL_DATASETS)
    parser.add_argument("--models", nargs="*")
    parser.add_argument("--fractions", nargs="+", type=float,
                        default=DEFAULT_FRACTIONS)
    parser.add_argument("--repeats", type=int, default=len(DEFAULT_SEEDS))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variant", default="canonical")
    parser.add_argument(
        "--matrix-template",
        help=("Optional format string with {task}, {model}, and {variant}; "
              "defaults to data/embeddings/<model>__<task>.npy"))
    parser.add_argument("--n-jobs", type=int, default=4)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    if not 1 <= arguments.repeats <= len(DEFAULT_SEEDS):
        raise SystemExit(f"--repeats must be 1..{len(DEFAULT_SEEDS)}")
    run(arguments.tasks, models=arguments.models,
        fractions=tuple(arguments.fractions),
        seeds=DEFAULT_SEEDS[:arguments.repeats], output=arguments.output,
        variant=arguments.variant, matrix_template=arguments.matrix_template,
        n_jobs=arguments.n_jobs)
