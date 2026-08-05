"""
BioLatent Phase B: Standardised Frozen-Embedding Probes
=======================================================

Every representation is evaluated with the identical probing procedure, so that
differences in score reflect the embedding rather than differences in how hard
someone tuned a downstream head.

**Ranked metric -- linear probe.** L2-regularised logistic regression or ridge
on standardised features. A linear probe has almost no capacity of its own, so
what it decodes was already present in the embedding. The regularisation
strength is chosen from one fixed grid by cross-validation on the training
split, using the same grid and the same folds for every model; nothing else is
tuned, and the test split is touched exactly once.

**Diagnostic metric -- fixed MLP.** A pinned 2-layer MLP, identical
hyperparameters for all models. It is reported but never ranked: ranking on it
would measure the MLP's capacity rather than the representation. Its value is
the *gap* to the linear probe, which separates representations that encode
information linearly from those that need a non-linear head.

Metrics follow the task, not convenience:
  binary classification  ROC-AUC
  multi-class            accuracy and macro-F1
  regression             Spearman rho (ranked), with RMSE and R^2 reported

Spearman is ranked for regression because RMSE is not comparable across tasks
with different target scales, which also makes "RMSE per dimension" a quantity
with no meaning.
"""

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, f1_score, r2_score,
                             roc_auc_score, root_mean_squared_error)
from sklearn.model_selection import GridSearchCV
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler

SEED = 42
C_GRID = [0.001, 0.01, 0.1, 1.0, 10.0]
ALPHA_GRID = [0.1, 1.0, 10.0, 100.0, 1000.0]

# The regularisation search is run on at most this many training rows. The
# chosen value is then refit on the full training split. Searching on the whole
# of a large task means fitting the grid times the folds over tens of thousands
# of high-dimensional rows -- for the 8000-dimensional 3-mer baseline on
# DeepLoc that is hours for a hyperparameter that moves very little. Capping the
# search set keeps the procedure identical for every model while leaving the
# reported model fit on all available training data.
SEARCH_CAP = 6000

MLP_KWARGS = dict(hidden_layer_sizes=(256,), activation="relu", alpha=1e-4,
                  batch_size=256, learning_rate_init=1e-3, max_iter=200,
                  early_stopping=True, n_iter_no_change=10,
                  validation_fraction=0.1, random_state=SEED)


def _prepare(X_train, y_train, X_test, y_test):
    """Drop NaN targets, standardise features on train statistics only."""
    tr = ~np.isnan(y_train)
    te = ~np.isnan(y_test)
    X_tr, y_tr = X_train[tr], y_train[tr]
    X_te, y_te = X_test[te], y_test[te]

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_tr)
    X_te = scaler.transform(X_te)
    # Constant or degenerate columns can leave NaNs after scaling.
    X_tr = np.nan_to_num(X_tr, nan=0.0, posinf=0.0, neginf=0.0)
    X_te = np.nan_to_num(X_te, nan=0.0, posinf=0.0, neginf=0.0)
    return X_tr, y_tr, X_te, y_te


def _classification_metrics(y_true, y_pred, y_prob, n_classes):
    if n_classes == 2:
        return {"metric": "ROC-AUC",
                "score": round(float(roc_auc_score(y_true, y_prob[:, 1])), 4),
                "accuracy": round(float(accuracy_score(y_true, y_pred)), 4)}
    return {"metric": "Accuracy",
            "score": round(float(accuracy_score(y_true, y_pred)), 4),
            "macro_f1": round(float(f1_score(y_true, y_pred, average="macro")), 4)}


def _regression_metrics(y_true, y_pred):
    rho = spearmanr(y_true, y_pred).statistic
    return {"metric": "Spearman rho",
            "score": round(float(rho if np.isfinite(rho) else 0.0), 4),
            "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
            "r2": round(float(r2_score(y_true, y_pred)), 4)}


def _search_subset(X, y, stratify):
    """Deterministic subsample used only for the regularisation search."""
    if len(y) <= SEARCH_CAP:
        return X, y
    rng = np.random.RandomState(SEED)
    if stratify:
        idx = []
        per_class = max(1, SEARCH_CAP // len(np.unique(y)))
        for cls in np.unique(y):
            pool = np.where(y == cls)[0]
            idx.extend(rng.choice(pool, min(len(pool), per_class), replace=False))
        idx = np.array(idx)
    else:
        idx = rng.choice(len(y), SEARCH_CAP, replace=False)
    return X[idx], y[idx]


def linear_probe(X_train, y_train, X_test, y_test, task_type, n_jobs=4):
    """Ranked linear probe with CV-selected regularisation."""
    X_tr, y_tr, X_te, y_te = _prepare(X_train, y_train, X_test, y_test)

    if task_type == "classification":
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        n_classes = int(max(y_tr.max(), y_te.max())) + 1
        Xs, ys = _search_subset(X_tr, y_tr, stratify=True)
        search = GridSearchCV(
            LogisticRegression(max_iter=1000, random_state=SEED),
            {"C": C_GRID}, cv=3, n_jobs=n_jobs,
            scoring="roc_auc" if n_classes == 2 else "accuracy")
        search.fit(Xs, ys)
        model = LogisticRegression(C=search.best_params_["C"], max_iter=1000,
                                   random_state=SEED).fit(X_tr, y_tr)
        out = _classification_metrics(y_te, model.predict(X_te),
                                      model.predict_proba(X_te), n_classes)
        out["hyperparameter"] = {"C": search.best_params_["C"]}
    else:
        Xs, ys = _search_subset(X_tr, y_tr, stratify=False)
        search = GridSearchCV(Ridge(random_state=SEED), {"alpha": ALPHA_GRID},
                              cv=3, n_jobs=n_jobs, scoring="r2")
        search.fit(Xs, ys)
        model = Ridge(alpha=search.best_params_["alpha"],
                      random_state=SEED).fit(X_tr, y_tr)
        out = _regression_metrics(y_te, model.predict(X_te))
        out["hyperparameter"] = {"alpha": search.best_params_["alpha"]}

    out["probe"] = "linear"
    out["embedding_dim"] = int(X_train.shape[1])
    out["n_train"] = int(len(y_tr))
    out["n_test"] = int(len(y_te))
    return out


def mlp_probe(X_train, y_train, X_test, y_test, task_type):
    """Diagnostic MLP probe. Fixed hyperparameters, never ranked."""
    X_tr, y_tr, X_te, y_te = _prepare(X_train, y_train, X_test, y_test)

    if task_type == "classification":
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        n_classes = int(max(y_tr.max(), y_te.max())) + 1
        model = MLPClassifier(**MLP_KWARGS).fit(X_tr, y_tr)
        out = _classification_metrics(y_te, model.predict(X_te),
                                      model.predict_proba(X_te), n_classes)
    else:
        model = MLPRegressor(**MLP_KWARGS).fit(X_tr, y_tr)
        out = _regression_metrics(y_te, model.predict(X_te))

    out["probe"] = "mlp"
    out["embedding_dim"] = int(X_train.shape[1])
    return out
