"""Paired inference for the BioLatent frozen-embedding study.

The representation used as comparator is selected on validation data, never on
the test scores it is compared against. Test-set uncertainty is estimated by a
paired cluster bootstrap (Murcko scaffold clusters for molecules; individual
items otherwise). P-values come from a paired randomisation test that swaps the
two models' predictions within the same resampling units under the null.

Primary significance uses a Holm correction across every reference comparison
in the study. Within-task and within-modality adjusted values are retained as
sensitivity analyses. ESM-2 scale steps are pre-specified and corrected as a
separate family.
"""

import gc
import json
import os
import subprocess
import sys

import numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.probe import (ALPHA_GRID, C_GRID, PROBE_PROTOCOL_VERSION,
                             SEED, _multilabel_auc_scorer, _search_subset,
                             _valid_rows)

N_BOOT = 2000
N_PERM = 2000
INFERENCE_PROTOCOL_VERSION = 4
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "results",
                           "paired_comparisons.json")
PREDICTION_DIR = os.path.join(os.path.dirname(__file__), "..", "results",
                              "predictions")

LADDERS = {
    "esm2_scale": ["esm2_8m", "esm2_35m", "esm2_150m", "esm2_650m"],
}


def _spearman_scorer(estimator, X, y_true):
    value = spearmanr(y_true, estimator.predict(X)).statistic
    return float(value) if np.isfinite(value) else 0.0


def fit_model(X, y, train_idx, task_type, n_jobs):
    """Fit the exact standard linear-probe protocol on ``train_idx``."""
    valid = _valid_rows(y[train_idx])
    X_raw = X[train_idx][valid]
    y_train = y[train_idx][valid]
    scaler = StandardScaler().fit(X_raw)
    X_train = np.nan_to_num(scaler.transform(X_raw), nan=0.0,
                            posinf=0.0, neginf=0.0)

    if task_type == "classification":
        y_train = y_train.astype(int)
        n_classes = int(y_train.max()) + 1
        Xs, ys = _search_subset(X_raw, y_train, stratify=True)
        scoring = "roc_auc" if n_classes == 2 else "accuracy"
        search = GridSearchCV(
            Pipeline([
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000,
                                               random_state=SEED)),
            ]),
            {"model__C": C_GRID}, cv=3, n_jobs=n_jobs,
            scoring=scoring).fit(Xs, ys)
        model = LogisticRegression(C=search.best_params_["model__C"], max_iter=1000,
                                   random_state=SEED).fit(X_train, y_train)
    elif task_type == "multilabel":
        y_train = y_train.astype(int)
        n_classes = y_train.shape[1]
        Xs, ys = _search_subset(X_raw, y_train, stratify=False)
        search = GridSearchCV(
            Pipeline([
                ("scale", StandardScaler()),
                ("model", OneVsRestClassifier(
                    LogisticRegression(max_iter=1000, random_state=SEED))),
            ]),
            {"model__estimator__C": C_GRID}, cv=3, n_jobs=n_jobs,
            scoring=_multilabel_auc_scorer).fit(Xs, ys)
        model = OneVsRestClassifier(LogisticRegression(
            C=search.best_params_["model__estimator__C"], max_iter=1000,
            random_state=SEED)).fit(X_train, y_train)
    else:
        n_classes = None
        Xs, ys = _search_subset(X_raw, y_train, stratify=False)
        search = GridSearchCV(
            Pipeline([
                ("scale", StandardScaler()),
                ("model", Ridge(random_state=SEED)),
            ]),
            {"model__alpha": ALPHA_GRID}, cv=3, n_jobs=n_jobs,
            scoring=_spearman_scorer).fit(Xs, ys)
        model = Ridge(alpha=search.best_params_["model__alpha"],
                      random_state=SEED).fit(X_train, y_train)
    return scaler, model, n_classes


def predict_bundle(X, y, eval_idx, fitted, task_type):
    scaler, model, n_classes = fitted
    valid = _valid_rows(y[eval_idx])
    X_eval = np.nan_to_num(scaler.transform(X[eval_idx][valid]), nan=0.0,
                           posinf=0.0, neginf=0.0)
    y_true = y[eval_idx][valid]
    y_pred = model.predict(X_eval)
    y_prob = (model.predict_proba(X_eval)
              if task_type in ("classification", "multilabel") else None)
    return {"y_true": y_true, "y_pred": y_pred, "y_prob": y_prob,
            "n_classes": n_classes, "valid": valid}


def score(bundle, idx=None):
    y_true, y_pred, y_prob = (bundle["y_true"], bundle["y_pred"],
                              bundle["y_prob"])
    if idx is not None:
        y_true, y_pred = y_true[idx], y_pred[idx]
        y_prob = y_prob[idx] if y_prob is not None else None
    task_type, n_classes = bundle["task_type"], bundle["n_classes"]
    if task_type == "regression":
        value = spearmanr(y_true, y_pred).statistic
        return float(value) if np.isfinite(value) else np.nan
    if task_type == "multilabel":
        if any(len(np.unique(y_true[:, column])) < 2
               for column in range(y_true.shape[1])):
            return np.nan
        return float(roc_auc_score(y_true, y_prob, average="macro"))
    if n_classes == 2:
        if len(np.unique(y_true)) < 2:
            return np.nan
        return float(roc_auc_score(y_true, y_prob[:, 1]))
    return float(accuracy_score(y_true, y_pred))


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, preserving input order."""
    m = len(pvalues)
    if not m:
        return []
    order = sorted(range(m), key=lambda index: pvalues[index])
    adjusted, running = [0.0] * m, 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[index]))
        adjusted[index] = running
    return adjusted


def _sample_indices(rng, groups):
    unique = np.unique(groups)
    sampled = rng.choice(unique, len(unique), replace=True)
    return np.concatenate([np.where(groups == group)[0] for group in sampled])


def _swapped_bundle(left, right, swap_items):
    """Return predictions formed by swapping paired outcomes under the null."""
    mask = np.asarray(swap_items)
    shape = (len(mask),) + (1,) * (left["y_pred"].ndim - 1)
    pred_mask = mask.reshape(shape)
    left_pred = np.where(pred_mask, right["y_pred"], left["y_pred"])
    right_pred = np.where(pred_mask, left["y_pred"], right["y_pred"])
    if left["y_prob"] is None:
        left_prob = right_prob = None
    else:
        probability_mask = mask.reshape(
            (len(mask),) + (1,) * (left["y_prob"].ndim - 1))
        left_prob = np.where(probability_mask, right["y_prob"], left["y_prob"])
        right_prob = np.where(probability_mask, left["y_prob"], right["y_prob"])
    common = {key: left[key] for key in ("y_true", "n_classes", "task_type")}
    return ({**common, "y_pred": left_pred, "y_prob": left_prob},
            {**common, "y_pred": right_pred, "y_prob": right_prob})


def paired_inference(left, right, groups, seed=SEED):
    """Cluster-bootstrap CI and paired randomisation p-value for a difference."""
    observed = score(left) - score(right)
    rng = np.random.RandomState(seed)
    boot = np.empty(N_BOOT)
    for index in range(N_BOOT):
        sampled = _sample_indices(rng, groups)
        boot[index] = score(left, sampled) - score(right, sampled)
    boot = boot[np.isfinite(boot)]
    lo, hi = np.percentile(boot, [2.5, 97.5])

    unique_groups = np.unique(groups)
    group_membership = {group: np.where(groups == group)[0]
                        for group in unique_groups}
    extreme, valid = 0, 0
    for _ in range(N_PERM):
        selected = rng.randint(0, 2, len(unique_groups)).astype(bool)
        swap = np.zeros(len(groups), dtype=bool)
        for group, enabled in zip(unique_groups, selected):
            if enabled:
                swap[group_membership[group]] = True
        perm_left, perm_right = _swapped_bundle(left, right, swap)
        value = score(perm_left) - score(perm_right)
        if np.isfinite(value):
            valid += 1
            extreme += abs(value) >= abs(observed) - 1e-15
    p_value = (extreme + 1) / (valid + 1)
    return {"delta": round(float(observed), 4),
            "ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4),
            "p_raw": round(float(p_value), 6),
            "n_boot_valid": int(len(boot)), "n_perm_valid": int(valid)}


def _selection_indices(data):
    if len(data["val_idx"]):
        return data["train_idx"], data["val_idx"], "published validation split"
    train = data["train_idx"]
    labels = data["targets"][train]
    stratify = labels if data["task_type"] == "classification" else None
    fit, select = train_test_split(train, test_size=0.1, random_state=SEED,
                                   stratify=stratify)
    return np.asarray(fit), np.asarray(select), \
        "deterministic 10% holdout from training split"


def _save_predictions(task, data, predictions):
    os.makedirs(PREDICTION_DIR, exist_ok=True)
    first = next(iter(predictions.values()))
    valid = first["valid"]
    payload = {
        "y_true": first["y_true"],
        "groups": np.asarray(data["resampling_groups"]
                             [data["test_idx"]][valid], dtype=str),
    }
    for model_id, bundle in predictions.items():
        payload[f"{model_id}__pred"] = bundle["y_pred"]
        if bundle["y_prob"] is not None:
            payload[f"{model_id}__prob"] = bundle["y_prob"]
    np.savez_compressed(os.path.join(PREDICTION_DIR, f"{task}.npz"), **payload)


def run_task(task):
    data = load_benchmark_dataset(task)
    task_type, modality = data["task_type"], data["modality"]
    n_jobs = 4 if modality == "molecule" else 1
    selection_train, selection_idx, selection_source = _selection_indices(data)

    test_predictions, selection_scores = {}, {}
    for model_id, spec in embed.MODEL_REGISTRY.items():
        if spec["modality"] != modality:
            continue
        path = embed.cache_path(model_id, task)
        if not os.path.exists(path):
            continue
        X = np.load(path)
        selection_fit = fit_model(X, data["targets"], selection_train,
                                  task_type, n_jobs)
        selection = predict_bundle(X, data["targets"], selection_idx,
                                   selection_fit, task_type)
        selection["task_type"] = task_type
        selection_scores[model_id] = score(selection)

        # After the representation is selected on held-out validation data,
        # every final probe is refit on all non-test labels. Promoters has no
        # published validation split, so this is its complete training set.
        test_fit = fit_model(X, data["targets"], data["final_train_idx"],
                             task_type, n_jobs)
        test = predict_bundle(X, data["targets"], data["test_idx"],
                              test_fit, task_type)
        test["task_type"] = task_type
        test_predictions[model_id] = test
        del X
        gc.collect()

    if len(test_predictions) < 2:
        print(f"{task}: fewer than two cached models, skipped", flush=True)
        return None

    names = list(test_predictions)
    reference = max(names, key=lambda model: selection_scores[model])
    test_scores = {model: score(bundle)
                   for model, bundle in test_predictions.items()}
    observed_best = max(names, key=lambda model: test_scores[model])
    valid = test_predictions[reference]["valid"]
    groups = np.asarray(data["resampling_groups"]
                        [data["test_idx"]][valid], dtype=str)

    comparisons = {}
    challengers = [model for model in sorted(names,
                                             key=lambda item: -test_scores[item])
                   if model != reference]
    print(f"\n{task}: validation reference={reference}; "
          f"test best={observed_best}", flush=True)
    for offset, model in enumerate(challengers):
        result = paired_inference(test_predictions[reference],
                                  test_predictions[model], groups,
                                  seed=SEED + offset)
        result["score"] = round(float(test_scores[model]), 4)
        comparisons[model] = result
        print(f"  vs {model:24s} d={result['delta']:+.4f} "
              f"CI [{result['ci_low']:+.4f}, {result['ci_high']:+.4f}] "
              f"p={result['p_raw']:.4g}", flush=True)

    adjusted = holm([comparisons[model]["p_raw"] for model in challengers])
    for model, p_value in zip(challengers, adjusted):
        comparisons[model]["p_holm_task"] = round(float(p_value), 6)
        comparisons[model]["significant_task"] = bool(p_value < 0.05)

    entry = {
        "protocol_version": INFERENCE_PROTOCOL_VERSION,
        "reference": reference,
        "reference_selection": selection_source,
        "reference_selection_score": round(float(selection_scores[reference]), 4),
        "reference_test_score": round(float(test_scores[reference]), 4),
        "observed_test_best": observed_best,
        "observed_test_best_score": round(float(test_scores[observed_best]), 4),
        "n_test": int(len(groups)), "n_resampling_groups": int(len(np.unique(groups))),
        "n_boot": N_BOOT, "n_permutations": N_PERM,
        "resampling_unit": "Murcko scaffold cluster" if modality == "molecule"
                           else "test item",
        "primary_correction": "Holm-Bonferroni across all reference comparisons",
        "comparisons": comparisons,
    }
    entry["ladders"] = _ladder_steps(names, test_predictions, test_scores, groups)
    _save_predictions(task, data, test_predictions)
    return entry


def _ladder_steps(names, predictions, test_scores, groups):
    out = {}
    for ladder_name, rungs in LADDERS.items():
        present = [model for model in rungs if model in names]
        if len(present) < 2:
            continue
        steps, raw = {}, []
        for offset, (lower, upper) in enumerate(zip(present, present[1:])):
            result = paired_inference(predictions[upper], predictions[lower],
                                      groups, seed=SEED + 100 + offset)
            steps[f"{lower}->{upper}"] = result
            raw.append(result["p_raw"])
        for key, p_value in zip(steps, holm(raw)):
            result = steps[key]
            result["p_holm"] = round(float(p_value), 6)
            result["significant"] = bool(p_value < 0.05)
            if p_value >= 0.05:
                result["direction"] = "no reliable difference"
            elif result["delta"] > 0:
                result["direction"] = "improves"
            else:
                result["direction"] = "REGRESSES"
        out[ladder_name] = {"rungs": present, "steps": steps,
                            "correction": "Holm within pre-specified ladder"}
    return out


def merge_report(task, entry):
    report = {}
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH) as handle:
            report = json.load(handle)
    report[task] = entry
    temporary = f"{REPORT_PATH}.{os.getpid()}.tmp"
    with open(temporary, "w") as handle:
        json.dump(report, handle, indent=2)
    os.replace(temporary, REPORT_PATH)


def apply_familywise_corrections():
    with open(REPORT_PATH) as handle:
        report = json.load(handle)
    records = []
    for task, entry in report.items():
        modality = load_benchmark_dataset(task)["modality"]
        for model, comparison in entry["comparisons"].items():
            records.append((task, modality, model, comparison))

    for modality in sorted({record[1] for record in records}):
        family = [record for record in records if record[1] == modality]
        adjusted = holm([record[3]["p_raw"] for record in family])
        for record, p_value in zip(family, adjusted):
            record[3]["p_holm_modality"] = round(float(p_value), 6)
            record[3]["significant_modality"] = bool(p_value < 0.05)

    adjusted = holm([record[3]["p_raw"] for record in records])
    for record, p_value in zip(records, adjusted):
        record[3]["p_holm_global"] = round(float(p_value), 6)
        record[3]["significant_global"] = bool(p_value < 0.05)
        # Backwards-compatible aliases used by older website builds. They now
        # point to the primary, study-wide correction rather than task-only Holm.
        record[3]["p_holm"] = record[3]["p_holm_global"]
        record[3]["significant"] = record[3]["significant_global"]

    with open(REPORT_PATH, "w") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":
    requested = sys.argv[1:]
    if len(requested) == 1:
        result = run_task(requested[0])
        if result:
            merge_report(requested[0], result)
    else:
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        for task_name in (requested or ALL_DATASETS):
            subprocess.run([sys.executable, "-u", os.path.abspath(__file__),
                            task_name], check=True)
        apply_familywise_corrections()
        print(f"\nWrote {REPORT_PATH}", flush=True)
