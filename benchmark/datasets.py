"""
BioLatent Multi-Modal Dataset Manager (9 Tasks)
================================================

Provides standardized datasets across 3 biological modalities:
1. Molecules: BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4
2. Proteins: DeepLoc (subcellular localization), Fluorescence (GFP fitness regression)
3. Genomics: Promoters (regulatory sequence detection)
"""

import os
import pandas as pd
import numpy as np
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_datasets")

ALL_DATASETS = [
    "BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4",
    "DeepLoc", "Fluorescence", "Promoters"
]

def get_bemis_murcko_scaffold(smiles, include_chirality=False):
    """Computes Murcko Scaffold for a SMILES string."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return ""
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=include_chirality)
    except Exception:
        return ""

def generate_scaffold_split(smiles_list, frac_train=0.8, frac_val=0.1, frac_test=0.1, seed=42):
    """Generates Bemis-Murcko scaffold split indices matching DeepChem / MoleculeNet protocol."""
    np.random.seed(seed)
    scaffolds = defaultdict(list)
    for idx, sm in enumerate(smiles_list):
        scaffold = get_bemis_murcko_scaffold(sm)
        scaffolds[scaffold].append(idx)

    rng = np.random.RandomState(seed)
    scaffold_sets = list(scaffolds.values())
    rng.shuffle(scaffold_sets)

    total = len(smiles_list)
    train_cutoff = frac_train * total
    val_cutoff = (frac_train + frac_val) * total

    train_idx, val_idx, test_idx = [], [], []
    current_count = 0

    for scaf_set in scaffold_sets:
        if (current_count + len(scaf_set) <= train_cutoff) or len(train_idx) == 0:
            train_idx.extend(scaf_set)
        elif (current_count + len(scaf_set) <= val_cutoff) or len(val_idx) == 0:
            val_idx.extend(scaf_set)
        else:
            test_idx.extend(scaf_set)
        current_count += len(scaf_set)

    if len(test_idx) == 0 and len(val_idx) > 1:
        split_point = max(1, len(val_idx) // 2)
        test_idx = val_idx[split_point:]
        val_idx = val_idx[:split_point]

    return np.array(train_idx, dtype=int), np.array(val_idx, dtype=int), np.array(test_idx, dtype=int)

def generate_sequence_split(sequences, frac_train=0.8, frac_val=0.1, frac_test=0.1, seed=42):
    """Generates stratified/random split indices for protein and DNA sequence datasets."""
    rng = np.random.RandomState(seed)
    indices = np.arange(len(sequences))
    rng.shuffle(indices)

    total = len(sequences)
    n_train = int(frac_train * total)
    n_val = int(frac_val * total)

    train_idx = indices[:n_train]
    val_idx = indices[n_train:n_train + n_val]
    test_idx = indices[n_train + n_val:]

    return train_idx, val_idx, test_idx

def load_benchmark_dataset(dataset_name="BBBP"):
    """
    Loads and standardizes any of the 9 BioLatent benchmark datasets.
    
    Supported datasets:
    - Molecules: 'BBBP', 'ClinTox', 'BACE', 'ESOL', 'Lipophilicity', 'CYP3A4'
    - Proteins: 'DeepLoc', 'Fluorescence'
    - Genomics: 'Promoters'
    """
    csv_path = os.path.join(DATA_DIR, f"{dataset_name}.csv")

    # If dataset missing, generate standardized dataset representation
    if not os.path.exists(csv_path):
        _generate_missing_dataset(dataset_name, csv_path)

    df = pd.read_csv(csv_path)

    # 1. Molecular Datasets
    if dataset_name in ["BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4"]:
        modality = "molecule"
        
        # Prioritize exact 'smiles' column first
        smiles_candidates = [c for c in df.columns if c.lower() == "smiles"]
        if smiles_candidates:
            smiles_col = smiles_candidates[0]
        else:
            smiles_col = [c for c in df.columns if "smiles" in c.lower() or "mol" in c.lower() or "name" in c.lower()][0]
        
        if dataset_name == "BBBP":
            target_col = [c for c in df.columns if "p_np" in c or "target" in c][0]
            task_type = "classification"
        elif dataset_name == "ClinTox":
            target_col = "FDA_APPROVED"
            task_type = "classification"
        elif dataset_name == "BACE":
            target_col = [c for c in df.columns if "class" in c.lower() or "target" in c.lower()][0]
            task_type = "classification"
        elif dataset_name == "ESOL":
            target_col = [c for c in df.columns if "solubility" in c.lower() or "esol" in c.lower()][0]
            task_type = "regression"
        elif dataset_name == "Lipophilicity":
            target_col = "exp"
            task_type = "regression"
        elif dataset_name == "CYP3A4":
            target_col = [c for c in df.columns if "target" in c.lower() or "cyp" in c.lower() or "label" in c.lower()][0]
            task_type = "classification"

        # Validate SMILES
        clean_smiles = []
        valid_mask = []
        for s in df[smiles_col]:
            m = Chem.MolFromSmiles(str(s))
            if m is not None:
                valid_mask.append(True)
                clean_smiles.append(Chem.MolToSmiles(m))
            else:
                valid_mask.append(False)

        df = df[valid_mask].reset_index(drop=True)
        df["inputs"] = clean_smiles
        targets = pd.to_numeric(df[target_col], errors="coerce").values.astype(np.float32)
        
        train_idx, val_idx, test_idx = generate_scaffold_split(df["inputs"].tolist())

    # 2. Protein Datasets
    elif dataset_name in ["DeepLoc", "Fluorescence"]:
        modality = "protein"
        seq_col = [c for c in df.columns if "seq" in c.lower() or "sequence" in c.lower()][0]
        target_col = [c for c in df.columns if "target" in c.lower() or "label" in c.lower() or "loc" in c.lower() or "tm" in c.lower()][0]
        task_type = "classification" if dataset_name == "DeepLoc" else "regression"
        
        df["inputs"] = df[seq_col].str.upper().str.strip()
        targets = pd.to_numeric(df[target_col], errors="coerce").values.astype(np.float32)
        train_idx, val_idx, test_idx = generate_sequence_split(df["inputs"].tolist())

    # 3. Genomic / DNA Datasets
    elif dataset_name == "Promoters":
        modality = "genomics"
        seq_col = [c for c in df.columns if "seq" in c.lower() or "sequence" in c.lower()][0]
        target_col = [c for c in df.columns if "target" in c.lower() or "label" in c.lower()][0]
        task_type = "classification"
        
        df["inputs"] = df[seq_col].str.upper().str.strip()
        targets = pd.to_numeric(df[target_col], errors="coerce").values.astype(np.float32)
        train_idx, val_idx, test_idx = generate_sequence_split(df["inputs"].tolist())

    else:
        raise ValueError(f"Unsupported dataset: {dataset_name}")

    splits = np.array(["train"] * len(df))
    if len(val_idx) > 0: splits[val_idx] = "val"
    if len(test_idx) > 0: splits[test_idx] = "test"
    df["split"] = splits

    return {
        "df": df,
        "modality": modality,
        "inputs": df["inputs"].tolist(),
        "targets": targets,
        "splits": splits,
        "train_idx": train_idx,
        "val_idx": val_idx,
        "test_idx": test_idx,
        "task_type": task_type,
        "dataset_name": dataset_name
    }

def _generate_missing_dataset(dataset_name, csv_path):
    """Raises an error when a benchmark dataset CSV is missing.
    
    Previously this function silently generated fake random data, which
    produced meaningless benchmark scores. Now it fails loudly and directs
    the user to download real datasets.
    """
    raise FileNotFoundError(
        f"\n{'=' * 60}\n"
        f"MISSING DATASET: {dataset_name}\n"
        f"Expected file: {csv_path}\n\n"
        f"Run the download script to fetch real benchmark data:\n"
        f"  python benchmark/download_real_datasets.py\n"
        f"{'=' * 60}"
    )
