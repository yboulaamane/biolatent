"""
BioLatent Benchmark Harness: Standardized Frozen Embedding Probes
===================================================================

This module implements hyperparameter-free, standardized probes for evaluating
pre-computed frozen representation vectors (embeddings) on downstream property prediction tasks.

Design Principles:
1. Linear Probe Score (Ranked): L2-regularized LogisticRegression / Ridge on standardized features.
2. Diagnostic MLP Score (Secondary): Fixed 2-layer MLP (128 hidden units, max_iter=15, seed 42).
3. Dimensional Efficiency: Performance score normalized by log10(embedding_dimension).
"""

import numpy as np
import math
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.metrics import roc_auc_score, root_mean_squared_error, r2_score

def evaluate_linear_probe(X_train, y_train, X_test, y_test, task_type="classification"):
    """
    Fits a standardized L2-regularized linear probe (LogisticRegression or Ridge).
    Returns a dictionary of metrics.
    """
    train_mask = ~np.isnan(y_train)
    test_mask = ~np.isnan(y_test)

    X_tr, y_tr = X_train[train_mask], y_train[train_mask]
    X_te, y_te = X_test[test_mask], y_test[test_mask]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_tr)
    X_test_scaled = scaler.transform(X_te)
    dim = X_train.shape[1]

    if task_type == "classification":
        model = LogisticRegression(C=1.0, max_iter=200, random_state=42)
        model.fit(X_train_scaled, y_tr)
        
        y_prob = model.predict_proba(X_test_scaled)
        try:
            if y_prob.shape[1] == 2:
                auc = roc_auc_score(y_te, y_prob[:, 1])
            else:
                auc = roc_auc_score(y_te, y_prob, multi_class='ovr')
        except Exception:
            auc = 0.50
            
        dim_eff = auc / math.log10(max(dim, 2))
        return {
            "metric": "ROC-AUC",
            "score": round(float(auc), 4),
            "dim_efficiency": round(float(dim_eff), 4),
            "embedding_dim": dim,
            "probe_type": "Linear (LogisticRegression)"
        }
    
    elif task_type == "regression":
        model = Ridge(alpha=1.0, random_state=42)
        model.fit(X_train_scaled, y_tr)
        y_pred = model.predict(X_test_scaled)
        
        rmse = root_mean_squared_error(y_te, y_pred)
        r2 = r2_score(y_te, y_pred)
        
        dim_eff = 1.0 / (rmse * math.log10(max(dim, 2)))
        return {
            "metric": "RMSE",
            "score": round(float(rmse), 4),
            "r2_score": round(float(r2), 4),
            "dim_efficiency": round(float(dim_eff), 4),
            "embedding_dim": dim,
            "probe_type": "Linear (Ridge)"
        }
    else:
        raise ValueError(f"Unknown task_type: {task_type}")

def evaluate_mlp_probe(X_train, y_train, X_test, y_test, task_type="classification"):
    """
    Fits a fixed diagnostic 2-layer MLP probe (128 hidden units, max_iter=15, random_state=42).
    Reported as a diagnostic metric to measure non-linear decodability gap.
    """
    train_mask = ~np.isnan(y_train)
    test_mask = ~np.isnan(y_test)

    X_tr, y_tr = X_train[train_mask], y_train[train_mask]
    X_te, y_te = X_test[test_mask], y_test[test_mask]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_tr)
    X_test_scaled = scaler.transform(X_te)
    dim = X_train.shape[1]

    if task_type == "classification":
        model = MLPClassifier(hidden_layer_sizes=(128,), max_iter=15, random_state=42, early_stopping=True)
        model.fit(X_train_scaled, y_tr)
        
        y_prob = model.predict_proba(X_test_scaled)
        try:
            if y_prob.shape[1] == 2:
                auc = roc_auc_score(y_te, y_prob[:, 1])
            else:
                auc = roc_auc_score(y_te, y_prob, multi_class='ovr')
        except Exception:
            auc = 0.50
            
        return {
            "metric": "ROC-AUC",
            "score": round(float(auc), 4),
            "embedding_dim": dim,
            "probe_type": "Diagnostic MLP (128 hidden)"
        }
    
    elif task_type == "regression":
        model = MLPRegressor(hidden_layer_sizes=(128,), max_iter=15, random_state=42, early_stopping=True)
        model.fit(X_train_scaled, y_tr)
        y_pred = model.predict(X_test_scaled)
        
        rmse = root_mean_squared_error(y_te, y_pred)
        return {
            "metric": "RMSE",
            "score": round(float(rmse), 4),
            "embedding_dim": dim,
            "probe_type": "Diagnostic MLP (128 hidden)"
        }
    else:
        raise ValueError(f"Unknown task_type: {task_type}")
