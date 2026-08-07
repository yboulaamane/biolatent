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
    "BBBP": "classification", "ClinTox": "multilabel", "BACE": "classification",
    "ESOL": "regression", "Lipophilicity": "regression", "CYP3A4": "classification",
    "DeepLoc": "multilabel", "Fluorescence": "regression",
    "Promoters": "classification",
}

MODALITY = ({t: "molecule" for t in MOLECULE_TASKS}
            | {t: "protein" for t in PROTEIN_TASKS}
            | {t: "genomics" for t in GENOMIC_TASKS})

DATASET_LABEL = {
    "ClinTox": "ClinTox (FDA approval and clinical toxicity)",
    "CYP3A4": "CYP3A4 Substrate",
    "DeepLoc": "DeepLoc 2.0 (10-label localisation)",
}
DATASET_SOURCE = {
    "BBBP": "DeepChem MoleculeNet BBBP.csv",
    "ClinTox": "DeepChem MoleculeNet clintox.csv.gz",
    "BACE": "DeepChem MoleculeNet bace.csv",
    "ESOL": "DeepChem MoleculeNet delaney-processed.csv",
    "Lipophilicity": "DeepChem MoleculeNet Lipophilicity.csv",
    "CYP3A4": "TDC CYP3A4_Substrate_CarbonMangels",
    "DeepLoc": "DeepLoc 2.0 SwissProt localisation dataset",
    "Fluorescence": ("proteinglm/fluorescence_prediction revision "
                     "d2a150fc808dbb02330c5fff6c4cb4807efe1979"),
    "Promoters": ("InstaDeepAI/nucleotide_transformer_downstream_tasks_revised "
                  "revision 851f9946252e90c665cdb3cc3eedb78f1f26197c"),
}
DATASET_VARIANT = {
    "BBBP": "source SMILES retained; 11 RDKit-invalid rows excluded",
    "ClinTox": ("two-endpoint task; macro-average over FDA_APPROVED and CT_TOX; "
                "4 RDKit-invalid rows excluded"),
    "BACE": "source SMILES retained; binary Class endpoint",
    "ESOL": "source SMILES retained; measured log-solubility endpoint",
    "Lipophilicity": "source SMILES retained; experimental logD endpoint",
    "CYP3A4": "canonical-SMILES deduplicated before TDC scaffold splitting",
    "DeepLoc": ("original multi-label task; published homology partitions "
                "assigned as folds 0 test, 1 validation, and 2-4 train"),
    "Fluorescence": ("TAPE GFP log-fluorescence task; published train, "
                     "validation and extrapolation-test partitions retained"),
    "Promoters": "within-split exact-sequence deduplicated official partition",
}

TARGET_COLUMNS = {
    "ClinTox": ["target_FDA_APPROVED", "target_CT_TOX"],
    "DeepLoc": [
        "target_Cytoplasm", "target_Nucleus", "target_Extracellular",
        "target_Cell_membrane", "target_Mitochondrion", "target_Plastid",
        "target_Endoplasmic_reticulum", "target_Lysosome_Vacuole",
        "target_Golgi_apparatus", "target_Peroxisome",
    ],
}

PUBLISHED_SPLIT_LABEL = {
    "CYP3A4": "TDC scaffold split (seed 42)",
    "DeepLoc": "published homology partitions (fixed fold assignment)",
    "Fluorescence": "published extrapolation partition",
    "Promoters": "published chromosome partition (within-split deduplicated)",
}


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


def _resampling_groups(inputs, modality):
    """Return dependence groups used by bootstrap and randomisation tests."""
    if modality != "molecule":
        return np.arange(len(inputs)).astype(str)
    groups = []
    for i, value in enumerate(inputs):
        scaffold = get_scaffold(value)
        # Acyclic molecules have an empty Murcko scaffold. Treating every such
        # molecule as one giant cluster is too conservative and scientifically
        # unrelated, so each empty scaffold receives its own identity group.
        groups.append(scaffold if scaffold else f"__acyclic_{i}")
    return np.asarray(groups, dtype=object)


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
        # Validate with RDKit but retain source SMILES as the model input.
        # Canonicalising MoleculeNet collapses distinct source rows (including
        # salts or stereoisomers) and can create identical inputs with
        # conflicting labels. CYP3A4 is already explicitly canonicalised and
        # deduplicated by its downloader.
        keep = []
        for smi in df["smiles"]:
            mol = Chem.MolFromSmiles(str(smi))
            keep.append(mol is not None)
        df = df[keep].reset_index(drop=True)
        df["inputs"] = df["smiles"].astype(str).str.strip()
    else:
        df["inputs"] = df["sequence"].astype(str).str.upper().str.strip()

    target_columns = TARGET_COLUMNS.get(name, ["target"])
    missing = [column for column in target_columns if column not in df.columns]
    if missing:
        raise RuntimeError(
            f"{name}: missing required target columns {missing}. Refresh the "
            "dataset with benchmark/download_real_datasets.py."
        )
    target_frame = df[target_columns].apply(pd.to_numeric, errors="coerce")
    valid_targets = ~target_frame.isna().any(axis=1)
    if not bool(valid_targets.all()):
        df = df.loc[valid_targets].reset_index(drop=True)
        target_frame = target_frame.loc[valid_targets].reset_index(drop=True)
    targets = target_frame.to_numpy(dtype=np.float32)
    if task_type != "multilabel":
        targets = targets[:, 0]

    if "split" in df.columns:
        split_source = PUBLISHED_SPLIT_LABEL.get(name, "published partition")
        splits = df["split"].values
        train_idx = np.where(splits == "train")[0]
        val_idx = np.where(splits == "val")[0]
        test_idx = np.where(splits == "test")[0]
    else:
        split_source = "balanced Murcko scaffold split (seed 42)"
        train_idx, val_idx, test_idx = scaffold_split(df["inputs"].tolist())
        splits = np.array(["train"] * len(df), dtype=object)
        splits[val_idx] = "val"
        splits[test_idx] = "test"

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError(f"{name}: empty train or test split")
    final_train_idx = (np.concatenate([train_idx, val_idx])
                       if len(val_idx) else train_idx.copy())

    if task_type == "classification":
        # A single-class split makes ROC-AUC undefined and silently yields NaN
        # scores rather than an error, so it is caught at load time.
        for label, idx in (("train", train_idx), ("test", test_idx)):
            if len(np.unique(targets[idx])) < 2:
                raise RuntimeError(
                    f"{name}: {label} split contains a single class -- "
                    f"the split is degenerate and metrics would be undefined")
    elif task_type == "multilabel":
        for label, idx in (("train", train_idx), ("test", test_idx)):
            degenerate = [target_columns[j] for j in range(targets.shape[1])
                          if len(np.unique(targets[idx, j])) < 2]
            if degenerate:
                raise RuntimeError(
                    f"{name}: {label} split has single-class labels "
                    f"{degenerate}; macro ROC-AUC would be undefined")

    with open(path, "rb") as dataset_file:
        dataset_sha256 = hashlib.sha256(dataset_file.read()).hexdigest()
    input_sha256 = hashlib.sha256(
        "\0".join(df["inputs"].tolist()).encode("utf-8")).hexdigest()

    return {
        "dataset_name": name,
        "dataset_label": DATASET_LABEL.get(name, name),
        "dataset_source": DATASET_SOURCE.get(name),
        "dataset_variant": DATASET_VARIANT.get(name),
        "dataset_sha256": dataset_sha256,
        "input_sha256": input_sha256,
        "modality": modality,
        "task_type": task_type,
        "inputs": df["inputs"].tolist(),
        "targets": targets,
        "target_labels": target_columns,
        "splits": splits,
        "train_idx": train_idx,
        "val_idx": val_idx,
        "final_train_idx": final_train_idx,
        "test_idx": test_idx,
        "split_source": split_source,
        "n_classes": int(np.nanmax(targets)) + 1 if task_type == "classification" else None,
        "resampling_groups": _resampling_groups(df["inputs"].tolist(), modality),
    }
