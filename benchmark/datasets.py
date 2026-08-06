"""
BioLatent Benchmark Dataset Loader (9 tasks, 3 modalities)
==========================================================

Loads the nine benchmark tasks into a single standardised shape so that one
probing harness covers every task:

    molecules  BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4
    proteins   DeepLoc, Fluorescence
    genomics   Promoters

Splitting policy
----------------
If the source CSV carries a ``split`` column, that split is used verbatim. This
matters: several of these datasets define their split as part of the task. The
TAPE Fluorescence partition trains on variants near wild-type and tests on
distant ones, so re-splitting it randomly measures interpolation instead of
extrapolation and inflates every score.

Datasets without a published split (the five MoleculeNet tasks) get a
Bemis-Murcko scaffold split, the DeepChem convention for those benchmarks.

Every input file must exist. Nothing is generated.
"""

import hashlib
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold

RDLogger.DisableLog("rdApp.*")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_datasets")

MOLECULE_TASKS = ["BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4"]
PROTEIN_TASKS = ["DeepLoc", "Fluorescence"]
GENOMIC_TASKS = ["Promoters"]
ALL_DATASETS = MOLECULE_TASKS + PROTEIN_TASKS + GENOMIC_TASKS

TASK_TYPE = {
    "BBBP": "classification", "ClinTox": "classification", "BACE": "classification",
    "ESOL": "regression", "Lipophilicity": "regression", "CYP3A4": "classification",
    "DeepLoc": "classification", "Fluorescence": "regression",
    "Promoters": "classification",
}

MODALITY = ({t: "molecule" for t in MOLECULE_TASKS}
            | {t: "protein" for t in PROTEIN_TASKS}
            | {t: "genomics" for t in GENOMIC_TASKS})

DATASET_LABEL = {"CYP3A4": "CYP3A4 Substrate"}
DATASET_SOURCE = {"CYP3A4": "TDC CYP3A4_Substrate_CarbonMangels"}


def get_scaffold(smiles):
    """Bemis-Murcko scaffold of a SMILES string, '' if unparseable."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    except Exception:
        return ""


def scaffold_split(smiles_list, frac_train=0.8, frac_val=0.1, seed=42):
    """Balanced Bemis-Murcko scaffold split (Chemprop / MoleculeNet convention).

    Scaffold groups larger than half a split are placed in train first so that
    common chemotypes are learned rather than tested on; the remaining groups
    are shuffled under a fixed seed before greedy assignment.

    The shuffle is what makes the split usable. Assigning the remaining groups
    in dataset order instead lets the file's own ordering leak into the split:
    on BBBP, roughly three quarters of scaffolds are singletons, and taking
    them in file order yields validation and test sets containing a single
    class, for which ROC-AUC is undefined.
    """
    scaffolds = defaultdict(list)
    for idx, smi in enumerate(smiles_list):
        scaffolds[get_scaffold(smi)].append(idx)

    n = len(smiles_list)
    n_train, n_val = frac_train * n, frac_val * n

    big, small = [], []
    for group in scaffolds.values():
        if len(group) > n_val / 2:
            big.append(group)
        else:
            small.append(group)

    rng = np.random.RandomState(seed)
    rng.shuffle(small)
    groups = big + small

    train, val, test = [], [], []
    for group in groups:
        if len(train) + len(group) <= n_train:
            train += group
        elif len(val) + len(group) <= n_val:
            val += group
        else:
            test += group

    return (np.array(train, dtype=int), np.array(val, dtype=int),
            np.array(test, dtype=int))


def load_benchmark_dataset(name):
    """Load one benchmark task.

    Returns a dict with inputs, targets, split indices, modality and task type.
    """
    if name not in ALL_DATASETS:
        raise ValueError(f"Unknown dataset '{name}'. Expected one of {ALL_DATASETS}")

    path = os.path.join(DATA_DIR, f"{name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n{'=' * 60}\nMISSING DATASET: {name}\nExpected: {path}\n\n"
            f"Fetch the real data with:\n"
            f"  python benchmark/download_real_datasets.py\n{'=' * 60}"
        )

    df = pd.read_csv(path)
    modality = MODALITY[name]
    task_type = TASK_TYPE[name]

    if modality == "molecule":
        # Canonicalise and drop molecules RDKit cannot parse.
        keep, canonical = [], []
        for smi in df["smiles"]:
            mol = Chem.MolFromSmiles(str(smi))
            keep.append(mol is not None)
            if mol is not None:
                canonical.append(Chem.MolToSmiles(mol))
        df = df[keep].reset_index(drop=True)
        df["inputs"] = canonical
    else:
        df["inputs"] = df["sequence"].astype(str).str.upper().str.strip()

    targets = pd.to_numeric(df["target"], errors="coerce").values.astype(np.float32)

    if "split" in df.columns:
        split_source = "official"
        splits = df["split"].values
        train_idx = np.where(splits == "train")[0]
        val_idx = np.where(splits == "val")[0]
        test_idx = np.where(splits == "test")[0]
    else:
        split_source = "scaffold"
        train_idx, val_idx, test_idx = scaffold_split(df["inputs"].tolist())
        splits = np.array(["train"] * len(df), dtype=object)
        splits[val_idx] = "val"
        splits[test_idx] = "test"

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError(f"{name}: empty train or test split")

    if task_type == "classification":
        # A single-class split makes ROC-AUC undefined and silently yields NaN
        # scores rather than an error, so it is caught at load time.
        for label, idx in (("train", train_idx), ("test", test_idx)):
            if len(np.unique(targets[idx])) < 2:
                raise RuntimeError(
                    f"{name}: {label} split contains a single class -- "
                    f"the split is degenerate and metrics would be undefined")

    with open(path, "rb") as dataset_file:
        dataset_sha256 = hashlib.sha256(dataset_file.read()).hexdigest()

    return {
        "dataset_name": name,
        "dataset_label": DATASET_LABEL.get(name, name),
        "dataset_source": DATASET_SOURCE.get(name),
        "dataset_sha256": dataset_sha256,
        "modality": modality,
        "task_type": task_type,
        "inputs": df["inputs"].tolist(),
        "targets": targets,
        "splits": splits,
        "train_idx": train_idx,
        "val_idx": val_idx,
        "test_idx": test_idx,
        "split_source": split_source,
        "n_classes": int(np.nanmax(targets)) + 1 if task_type == "classification" else None,
    }
