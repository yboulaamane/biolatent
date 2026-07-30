"""
BioLatent Representation Model Suite & Matrix Loader
===================================================

Provides representation generators for baseline classical models (ECFP4, RDKit2D, K-mer)
and a matrix loader for pre-computed vector submissions (ESM-2, ChemBERTa, MolFormer, GROVER, etc.).
"""

import numpy as np
import pandas as pd
import os
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors

# Suppress RDKit C++ warning logs
RDLogger.DisableLog('rdApp.*')

def generate_ecfp4_embeddings(smiles_list, n_bits=1024, radius=2):
    """Generates 1024-dimensional ECFP4 Morgan Fingerprint vectors."""
    fps = []
    for sm in smiles_list:
        mol = Chem.MolFromSmiles(str(sm))
        if mol is not None:
            fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=radius, nBits=n_bits)
            arr = np.zeros((n_bits,), dtype=np.float32)
            AllChem.DataStructs.ConvertToNumpyArray(fp, arr)
            fps.append(arr)
        else:
            fps.append(np.zeros((n_bits,), dtype=np.float32))
    return np.vstack(fps)

def generate_rdkit2d_embeddings(smiles_list):
    """Generates 200-dimensional RDKit 2D physical-chemistry descriptor vectors."""
    calc = MoleculeDescriptors.MolecularDescriptorCalculator([x[0] for x in Descriptors._descList])
    desc_vectors = []
    for sm in smiles_list:
        mol = Chem.MolFromSmiles(str(sm))
        if mol is not None:
            v = np.array(calc.CalcDescriptors(mol), dtype=np.float32)
            # Replace NaNs or Infs with 0.0
            v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
            desc_vectors.append(v)
        else:
            desc_vectors.append(np.zeros((len(calc.GetDescriptorNames()),), dtype=np.float32))
    return np.vstack(desc_vectors)

def generate_kmer_embeddings(sequence_list, k=3, alphabet=None):
    """Generates k-mer frequency embeddings for Protein or DNA sequences."""
    if alphabet is None:
        # Detect protein vs DNA
        sample = "".join(sequence_list[:10]).upper()
        if set(sample).issubset(set("ACGTN")):
            alphabet = ["A", "C", "G", "T"]
        else:
            alphabet = list("ACDEFGHIKLMNPQRSTVWY")

    # Generate all k-mers
    import itertools
    kmers = ["".join(p) for p in itertools.product(alphabet, repeat=k)]
    kmer_to_idx = {km: i for i, km in enumerate(kmers)}

    vectors = []
    for seq in sequence_list:
        v = np.zeros((len(kmers),), dtype=np.float32)
        seq_str = str(seq).upper()
        for i in range(len(seq_str) - k + 1):
            km = seq_str[i:i+k]
            if km in kmer_to_idx:
                v[kmer_to_idx[km]] += 1.0
        # Normalize frequency
        total = np.sum(v)
        if total > 0:
            v = v / total
        vectors.append(v)
    return np.vstack(vectors)

def load_precomputed_embedding_matrix(file_path_or_array, expected_n=None):
    """
    Loads pre-computed representation matrix (.npy, .csv, .npz, or np.ndarray).
    Used for submitting frozen vectors for deep learning foundation models (ESM-2, ChemBERTa, MolFormer, etc.).
    """
    if isinstance(file_path_or_array, np.ndarray):
        matrix = file_path_or_array
    elif isinstance(file_path_or_array, str):
        if file_path_or_array.endswith(".npy"):
            matrix = np.load(file_path_or_array)
        elif file_path_or_array.endswith(".csv"):
            matrix = pd.read_csv(file_path_or_array).values
        elif file_path_or_array.endswith(".npz"):
            data = np.load(file_path_or_array)
            matrix = data[data.files[0]]
        else:
            raise ValueError(f"Unsupported file extension for matrix: {file_path_or_array}")
    else:
        raise TypeError("Expected np.ndarray or string path to matrix file.")

    matrix = np.asarray(matrix, dtype=np.float32)
    if expected_n is not None and matrix.shape[0] != expected_n:
        raise ValueError(f"Matrix sample count {matrix.shape[0]} does not match dataset size {expected_n}.")

    return matrix

def get_representation(model_id, inputs, modality="molecule"):
    """
    Factory function to obtain representation vectors for any model or input.
    """
    model_id_lower = str(model_id).lower()

    if modality in ["protein", "genomics"]:
        return generate_kmer_embeddings(inputs, k=2 if modality == "protein" else 3)

    if model_id_lower == "ecfp4":
        return generate_ecfp4_embeddings(inputs)
    elif model_id_lower in ["rdkit2d", "rdkit_2d"]:
        return generate_rdkit2d_embeddings(inputs)
    elif model_id_lower in ["kmer", "sequence_kmer"]:
        k = 2 if modality == "protein" else 3
        return generate_kmer_embeddings(inputs, k=k)
    elif isinstance(model_id, (np.ndarray, str)) and not isinstance(model_id, str):
        return load_precomputed_embedding_matrix(model_id, expected_n=len(inputs))
    else:
        if isinstance(model_id, str) and os.path.exists(model_id):
            return load_precomputed_embedding_matrix(model_id, expected_n=len(inputs))
        else:
            return generate_ecfp4_embeddings(inputs)
