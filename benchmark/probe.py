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

**Diagnostic metric -- fixed MLP.** A pinned one-hidden-layer MLP, identical
hyperparameters for all models. It is reported but never ranked: ranking on it
would measure the MLP's capacity rather than the representation. Its value is
the *gap* to the linear probe, which separates representations that encode
information linearly from those that need a non-linear head.

Metrics follow the task, not convenience:
  binary classification  ROC-AUC
  multi-label            macro ROC-AUC, subset accuracy and macro-F1
  regression             Spearman rho (ranked), with RMSE and R^2 reported

Spearman is ranked for regression because RMSE is not comparable across tasks
with different target scales, which also makes "RMSE per dimension" a quantity
with no meaning.
"""

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, f1_score, r2_score,
                             roc_auc_score, root_mean_squared_error,
                             make_scorer)
from sklearn.model_selection import GridSearchCV
from sklearn.multiclass import OneVsRestClassifier
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
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

PROBE_PROTOCOL_VERSION = 4


def _valid_rows(y):
    values = np.asarray(y)
    return ~np.isnan(values).any(axis=1) if values.ndim == 2 else ~np.isnan(values)


def _prepare(X_train, y_train, X_test, y_test):
    """Drop NaN targets, standardise features on train statistics only."""
    tr = _valid_rows(y_train)
    te = _valid_rows(y_test)
    X_tr, y_tr = X_train[tr], y_train[tr]
    X_te, y_te = X_test[te], y_test[te]

    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_tr)
    X_te = scaler.transform(X_te)
    # Constant or degenerate columns can leave NaNs after scaling.
    X_tr = np.nan_to_num(X_tr, nan=0.0, posinf=0.0, neginf=0.0)
    X_te = np.nan_to_num(X_te, nan=0.0, posinf=0.0, neginf=0.0)
    return X_tr, y_tr, X_te, y_te


def _valid_unscaled(X, y):
    """Return finite-target rows without fitting any feature transform.

    Hyperparameter selection uses these raw features in a scikit-learn
    Pipeline so each cross-validation fold learns its own scaling statistics.
    The final estimator is still refit after scaling the complete training
    partition in ``_prepare``.
    """
    valid = _valid_rows(y)
    return X[valid], y[valid]


def _classification_metrics(y_true, y_pred, y_prob, n_classes,
                            task_type="classification"):
    if task_type == "multilabel":
        return {
            "metric": "Macro ROC-AUC",
            "score": round(float(roc_auc_score(y_true, y_prob,
                                                average="macro")), 4),
            "subset_accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "macro_f1": round(float(f1_score(y_true, y_pred,
                                              average="macro")), 4),
        }
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


def _multilabel_auc_scorer(estimator, X, y_true):
    """Grid-search scorer that preserves OneVsRest's 2-D probabilities."""
    probabilities = estimator.predict_proba(X)
    return float(roc_auc_score(y_true, probabilities, average="macro"))


def _score_only(y_true, y_pred, y_prob, task_type, n_classes):
    """Recompute just the ranked metric, for bootstrap resampling."""
    if task_type == "regression":
        rho = spearmanr(y_true, y_pred).statistic
        return float(rho) if np.isfinite(rho) else np.nan
    if task_type == "multilabel":
        if any(len(np.unique(y_true[:, j])) < 2
               for j in range(y_true.shape[1])):
            return np.nan
        return float(roc_auc_score(y_true, y_prob, average="macro"))
    if n_classes == 2:
        if len(np.unique(y_true)) < 2:
            return np.nan          # resample lost a class; ROC-AUC undefined
        return float(roc_auc_score(y_true, y_prob[:, 1]))
    return float(accuracy_score(y_true, y_pred))


def bootstrap_ci(y_true, y_pred, y_prob, task_type, n_classes,
                 n_boot=1000, alpha=0.05, seed=SEED, groups=None):
    """Percentile bootstrap interval for the ranked metric.

    Resamples the test set rather than refitting, so the interval describes
    uncertainty from the finite test set -- which is the relevant question when
    two models differ by a ten-thousandth of a point on 420 test molecules. It
    does not capture variance from the split itself; see split_seed_spread.
    """
    rng = np.random.RandomState(seed)
    n = len(y_true)
    group_values = None if groups is None else np.asarray(groups)
    unique_groups = None
    membership = None
    if group_values is not None:
        unique_groups, membership = np.unique(group_values, return_inverse=True)
    scores = np.empty(n_boot)
    for b in range(n_boot):
        if unique_groups is None:
            idx = rng.randint(0, n, n)
        else:
            # A cluster bootstrap samples clusters with replacement. Metrics
            # are invariant to row order, so expand each item by the number of
            # times its cluster was sampled. This is exactly the former
            # concatenate-of-where implementation without millions of Python
            # scans over the group vector.
            sampled = rng.randint(0, len(unique_groups), len(unique_groups))
            counts = np.bincount(sampled, minlength=len(unique_groups))
            idx = np.repeat(np.arange(n), counts[membership])
        scores[b] = _score_only(
            y_true[idx], y_pred[idx],
            y_prob[idx] if y_prob is not None else None,
            task_type, n_classes)
    scores = scores[np.isfinite(scores)]
    if len(scores) == 0:
        return None
    lo, hi = np.percentile(scores, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4),
            "ci_width": round(float(hi - lo), 4), "n_boot": int(len(scores))}


def _search_subset(X, y, stratify):
    """Deterministic subsample used only for the regularisation search."""
    if len(y) <= SEARCH_CAP:
        return X, y
    rng = np.random.RandomState(SEED)
    if stratify and np.asarray(y).ndim == 1:
        idx = []
        per_class = max(1, SEARCH_CAP // len(np.unique(y)))
        for cls in np.unique(y):
            pool = np.where(y == cls)[0]
            idx.extend(rng.choice(pool, min(len(pool), per_class), replace=False))
        idx = np.array(idx)
    else:
        idx = rng.choice(len(y), SEARCH_CAP, replace=False)
    return X[idx], y[idx]


def linear_probe(X_train, y_train, X_test, y_test, task_type, n_jobs=4,
                 groups=None, n_boot=1000):
    """Ranked linear probe with CV-selected regularisation."""
    test_groups = (None if groups is None else
                   np.asarray(groups)[_valid_rows(y_test)])
    X_search_raw, y_search_raw = _valid_unscaled(X_train, y_train)
    X_tr, y_tr, X_te, y_te = _prepare(X_train, y_train, X_test, y_test)

    if task_type in ("classification", "multilabel"):
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        n_classes = (y_tr.shape[1] if task_type == "multilabel"
                     else int(max(y_tr.max(), y_te.max())) + 1)
        Xs, ys = _search_subset(
            X_search_raw, y_search_raw.astype(int),
            stratify=task_type == "classification")
        if task_type == "multilabel":
            estimator = Pipeline([
                ("scale", StandardScaler()),
                ("model", OneVsRestClassifier(
                    LogisticRegression(max_iter=1000, random_state=SEED))),
            ])
            parameters = {"model__estimator__C": C_GRID}
            scoring = _multilabel_auc_scorer
            parameter_name = "model__estimator__C"
        else:
            estimator = Pipeline([
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000,
                                               random_state=SEED)),
            ])
            parameters = {"model__C": C_GRID}
            scoring = "roc_auc" if n_classes == 2 else "accuracy"
            parameter_name = "model__C"
        search = GridSearchCV(estimator, parameters, cv=3, n_jobs=n_jobs,
                              scoring=scoring)
        search.fit(Xs, ys)
        best_c = search.best_params_[parameter_name]
        if task_type == "multilabel":
            model = OneVsRestClassifier(LogisticRegression(
                C=best_c, max_iter=1000, random_state=SEED)).fit(X_tr, y_tr)
        else:
            model = LogisticRegression(C=best_c, max_iter=1000,
                                       random_state=SEED).fit(X_tr, y_tr)
        y_pred, y_prob = model.predict(X_te), model.predict_proba(X_te)
        out = _classification_metrics(y_te, y_pred, y_prob, n_classes,
                                      task_type)
        out["hyperparameter"] = {"C": best_c}
        if n_boot:
            ci = bootstrap_ci(y_te, y_pred, y_prob, task_type, n_classes,
                              groups=test_groups, n_boot=n_boot)
            if ci:
                out.update(ci)
    else:
        Xs, ys = _search_subset(X_search_raw, y_search_raw, stratify=False)
        spearman_scorer = make_scorer(
            lambda truth, prediction: float(
                np.nan_to_num(spearmanr(truth, prediction).statistic)))
        estimator = Pipeline([
            ("scale", StandardScaler()),
            ("model", Ridge(random_state=SEED)),
        ])
        search = GridSearchCV(
            estimator, {"model__alpha": ALPHA_GRID}, cv=3, n_jobs=n_jobs,
            scoring=spearman_scorer)
        search.fit(Xs, ys)
        model = Ridge(alpha=search.best_params_["model__alpha"],
                      random_state=SEED).fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        out = _regression_metrics(y_te, y_pred)
        out["hyperparameter"] = {"alpha": search.best_params_["model__alpha"]}
        if n_boot:
            ci = bootstrap_ci(y_te, y_pred, None, task_type, None,
                              groups=test_groups, n_boot=n_boot)
            if ci:
                out.update(ci)

    out["probe"] = "linear"
    out["protocol_version"] = PROBE_PROTOCOL_VERSION
    out["regularisation_search_rows"] = int(min(len(y_tr), SEARCH_CAP))
    out["embedding_dim"] = int(X_train.shape[1])
    out["n_train"] = int(len(y_tr))
    out["n_test"] = int(len(y_te))
    return out


def mlp_probe(X_train, y_train, X_test, y_test, task_type):
    """Diagnostic MLP probe. Fixed hyperparameters, never ranked."""
    X_tr, y_tr, X_te, y_te = _prepare(X_train, y_train, X_test, y_test)

    if task_type in ("classification", "multilabel"):
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        n_classes = (y_tr.shape[1] if task_type == "multilabel"
                     else int(max(y_tr.max(), y_te.max())) + 1)
        model = MLPClassifier(**MLP_KWARGS).fit(X_tr, y_tr)
        out = _classification_metrics(y_te, model.predict(X_te),
                                      model.predict_proba(X_te), n_classes,
                                      task_type)
    else:
        model = MLPRegressor(**MLP_KWARGS).fit(X_tr, y_tr)
        out = _regression_metrics(y_te, model.predict(X_te))

    out["probe"] = "mlp"
    out["architecture"] = "one hidden layer with 256 ReLU units"
    out["embedding_dim"] = int(X_train.shape[1])
    return out
