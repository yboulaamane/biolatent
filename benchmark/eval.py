"""
BioLatent Multi-Modal Evaluation Runner (9 Datasets)
====================================================

Main entry point for evaluating representations across all 9 datasets:
- Molecules: BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4
- Proteins: DeepLoc, FLIP
- Genomics: Promoters
"""

import numpy as np
import pandas as pd
from benchmark.datasets import load_benchmark_dataset
from benchmark.probe import evaluate_linear_probe, evaluate_mlp_probe
from benchmark.models import get_representation

ALL_DATASETS = [
    "BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity", "CYP3A4",
    "DeepLoc", "FLIP", "Promoters"
]

def evaluate_embedding_matrix(embeddings_matrix, dataset_info):
    """
    Evaluates a single (N, d) embedding matrix against a dataset.
    """
    X = np.asarray(embeddings_matrix, dtype=np.float32)
    y = dataset_info["targets"]
    task_type = dataset_info["task_type"]
    dataset_name = dataset_info["dataset_name"]
    modality = dataset_info["modality"]
    
    train_idx = dataset_info["train_idx"]
    test_idx = dataset_info["test_idx"]

    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    # 1. Linear Probe Score (Ranked Metric)
    linear_res = evaluate_linear_probe(X_train, y_train, X_test, y_test, task_type=task_type)
    
    # 2. Diagnostic MLP Score (Secondary Metric)
    mlp_res = evaluate_mlp_probe(X_train, y_train, X_test, y_test, task_type=task_type)

    return {
        "dataset": dataset_name,
        "modality": modality,
        "task_type": task_type,
        "embedding_dim": X.shape[1],
        "linear_probe": linear_res,
        "diagnostic_mlp": mlp_res
    }

def run_suite_evaluation(model_or_func="ecfp4", dataset_names=ALL_DATASETS):
    """
    Evaluates a model or precomputed matrix across the requested benchmark datasets.
    
    model_or_func: String model name ('ecfp4', 'rdkit2d', 'kmer') or custom embedding generator function.
    """
    results = []

    print("=" * 80)
    print("      BIOLATENT ACTIVE BENCHMARK SUITE (9 MULTI-MODAL TASKS)")
    print("=" * 80)

    for name in dataset_names:
        print(f"\n[+] Loading Dataset [{name}]...")
        ds = load_benchmark_dataset(name)
        inputs = ds["inputs"]
        modality = ds["modality"]
        
        print(f"    Computing representations for {len(inputs)} {modality} inputs...")
        if callable(model_or_func):
            X_emb = model_or_func(inputs)
        else:
            X_emb = get_representation(model_or_func, inputs, modality=modality)
        
        print(f"    Running standardized probing harness (dim={X_emb.shape[1]})...")
        res = evaluate_embedding_matrix(X_emb, ds)
        results.append(res)

        lin_score = res["linear_probe"]["score"]
        lin_metric = res["linear_probe"]["metric"]
        dim_eff = res["linear_probe"]["dim_efficiency"]
        mlp_score = res["diagnostic_mlp"]["score"]

        print(f"    --> Linear Probe {lin_metric}: {lin_score} | Dim Eff: {dim_eff}")
        print(f"    --> Diagnostic MLP {lin_metric}: {mlp_score}")

    print("\n" + "=" * 80)
    print("                      SUMMARY BENCHMARK LEADERBOARD")
    print("=" * 80)
    summary_rows = []
    for r in results:
        summary_rows.append({
            "Dataset": r["dataset"],
            "Modality": r["modality"],
            "Task Type": r["task_type"],
            "Dim": r["embedding_dim"],
            "Linear Score": r["linear_probe"]["score"],
            "Dim Efficiency": r["linear_probe"]["dim_efficiency"],
            "Diagnostic MLP": r["diagnostic_mlp"]["score"]
        })
    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))
    print("=" * 80)

    return results
