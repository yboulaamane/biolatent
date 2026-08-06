"""
BioLatent: Paired Bootstrap Significance Test
=============================================

Answers "is the leading representation actually better than this one?" -- the
question a ranked table implies but a table of scores cannot settle.

Why paired, and not overlapping confidence intervals
----------------------------------------------------
The per-model intervals in ``benchmark_results.json`` describe each score in
isolation. Reading two of them and calling the models indistinguishable when
the intervals overlap is a real test, but a badly conservative one: both models
are scored on the *same* test molecules, so their errors are strongly
correlated. A test set that happens to contain hard items drags every model
down together, and that shared movement inflates both intervals while telling
us nothing about which model is better.

The paired bootstrap removes it. One resample of the test indices per
replicate, scored under every model, and the statistic is the *difference*.
Shared difficulty cancels; what remains is disagreement between the models on
the same items. A difference interval that excludes zero is a real separation.

The probes are fit once on the real training split -- exactly the fit that
produced the reported score -- and only the test set is resampled. The interval
therefore describes uncertainty from the finite test set, not from the split or
from probe initialisation.

Two things this does not fix
----------------------------
Each task runs one test per non-leading model, so p-values are Holm-corrected
within the task. That controls the family-wise error rate across the models
being compared, and without it twenty-four uncorrected tests at 5% would be
expected to manufacture roughly one separation from noise alone. Scale-ladder
steps (see LADDERS) form their own family and are corrected separately.

It does **not** correct for the leader being chosen as the maximum on the same
test set that then judges it. That is a winner's-curse selection, and it biases
every leader-versus-challenger gap upward. The consequence is directional and
worth stating plainly: a separation reported here may be optimistic, but a
*non*-separation is if anything conservative -- so "these two cannot be told
apart" is the safer of the two conclusions this test produces.

Memory
------
The protein embedding matrices are large (the 3-mer baseline on Fluorescence is
1.7 GB on its own) and a parallel grid search over one of them forks that
footprint. Each task therefore runs in its own subprocess, and the search is
serial for the non-molecular modalities. Results are merged into the report
file so a partial run keeps its finished tasks.

Usage:
    python benchmark/paired_test.py              # every task, one subprocess each
    python benchmark/paired_test.py DeepLoc      # a single task, in-process
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
from sklearn.model_selection import GridSearchCV

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import embed
from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.probe import ALPHA_GRID, C_GRID, SEED, _prepare, _search_subset

N_BOOT = 1000
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "results",
                           "paired_comparisons.json")

# Pre-specified secondary comparisons: each consecutive step of a model-scale
# ladder, tested against the step below it.
#
# These are a separate family from leader-versus-rest and are corrected
# separately, because they answer a different question. "Is anything reliably
# worse than the best model?" and "does making the model bigger reliably help?"
# are not the same claim, and pooling them into one correction would penalise
# both for the other's tests. The ladder is fixed here rather than derived from
# the results so that it cannot be chosen after seeing which steps look
# convincing.
LADDERS = {
    "esm2_scale": ["esm2_8m", "esm2_35m", "esm2_150m", "esm2_650m"],
}


def fit_predict(X, y, train_idx, test_idx, task_type, n_jobs):
    """Fit the standard linear probe and return its test-set predictions.

    Identical procedure to ``probe.linear_probe`` -- same grid, same folds, same
    seed -- so the comparison is between the scores that were actually reported.
    """
    X_tr, y_tr, X_te, y_te = _prepare(X[train_idx], y[train_idx],
                                      X[test_idx], y[test_idx])

    if task_type == "classification":
        y_tr, y_te = y_tr.astype(int), y_te.astype(int)
        n_classes = int(max(y_tr.max(), y_te.max())) + 1
        Xs, ys = _search_subset(X_tr, y_tr, stratify=True)
        search = GridSearchCV(
            LogisticRegression(max_iter=1000, random_state=SEED),
            {"C": C_GRID}, cv=3, n_jobs=n_jobs,
            scoring="roc_auc" if n_classes == 2 else "accuracy").fit(Xs, ys)
        model = LogisticRegression(C=search.best_params_["C"], max_iter=1000,
                                   random_state=SEED).fit(X_tr, y_tr)
        y_prob = model.predict_proba(X_te) if n_classes == 2 else None
        return y_te, model.predict(X_te), y_prob, n_classes

    Xs, ys = _search_subset(X_tr, y_tr, stratify=False)
    search = GridSearchCV(Ridge(random_state=SEED), {"alpha": ALPHA_GRID},
                          cv=3, n_jobs=n_jobs, scoring="r2").fit(Xs, ys)
    model = Ridge(alpha=search.best_params_["alpha"],
                  random_state=SEED).fit(X_tr, y_tr)
    return y_te, model.predict(X_te), None, None


def bootstrap_p(diff):
    """Two-sided percentile-bootstrap p-value for a paired difference.

    The proportion of replicates falling on the wrong side of zero, doubled.
    Floored at 1/n_boot: with 1,000 replicates the resolution runs out at
    p = 0.001, and reporting a smaller number would be inventing precision the
    resampling cannot supply.
    """
    n = len(diff)
    tail = min((diff <= 0).sum(), (diff >= 0).sum()) / n
    return float(min(1.0, max(2 * tail, 1.0 / n)))


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, order preserved.

    Every model on a task is compared against that task's leader, so a task
    with five models runs four tests and the suite runs twenty-four. At an
    uncorrected 5% that is more than one expected false separation across the
    molecular tasks alone -- enough to manufacture a ranking on its own. Holm
    is used rather than Bonferroni because it is uniformly more powerful and
    needs no independence assumption, which matters here: the comparisons share
    the leader and are strongly correlated.
    """
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def score(y_true, y_pred, y_prob, task_type, n_classes, idx):
    if task_type == "regression":
        rho = spearmanr(y_true[idx], y_pred[idx]).statistic
        return float(rho) if np.isfinite(rho) else np.nan
    if n_classes == 2:
        if len(np.unique(y_true[idx])) < 2:
            return np.nan          # resample lost a class; ROC-AUC undefined
        return float(roc_auc_score(y_true[idx], y_prob[idx, 1]))
    return float(accuracy_score(y_true[idx], y_pred[idx]))


def run_task(task):
    """Compare every model on one task against that task's leader."""
    data = load_benchmark_dataset(task)
    task_type, modality = data["task_type"], data["modality"]
    # Grid-search workers fork the parent's arrays; on the protein matrices
    # that multiplies several gigabytes by the worker count.
    n_jobs = 4 if modality == "molecule" else 1

    preds = {}
    for model_id, spec in embed.MODEL_REGISTRY.items():
        if spec["modality"] != modality:
            continue
        path = embed.cache_path(model_id, task)
        if not os.path.exists(path):
            continue
        X = np.load(path)
        preds[model_id] = fit_predict(X, data["targets"], data["train_idx"],
                                      data["test_idx"], task_type, n_jobs)
        del X
        gc.collect()

    if len(preds) < 2:
        print(f"{task}: fewer than two cached models, skipped", flush=True)
        return None

    def scored(model_id, idx):
        y_true, y_pred, y_prob, n_classes = preds[model_id]
        return score(y_true, y_pred, y_prob, task_type, n_classes, idx)

    names = list(preds)
    n = len(preds[names[0]][0])
    full = {m: scored(m, np.arange(n)) for m in names}
    leader = max(names, key=lambda m: full[m])

    rng = np.random.RandomState(SEED)
    boots = {m: np.empty(N_BOOT) for m in names}
    for b in range(N_BOOT):
        idx = rng.randint(0, n, n)
        for m in names:
            boots[m][b] = scored(m, idx)

    challengers = [m for m in sorted(names, key=lambda m: -full[m]) if m != leader]
    stats = {}
    for m in challengers:
        diff = boots[leader] - boots[m]
        diff = diff[np.isfinite(diff)]
        lo, hi = np.percentile(diff, [2.5, 97.5])
        stats[m] = (lo, hi, bootstrap_p(diff), len(diff))

    adjusted = holm([stats[m][2] for m in challengers])

    entry = {"leader": leader, "leader_score": round(float(full[leader]), 4),
             "n_test": int(n), "n_boot": N_BOOT,
             "correction": "Holm-Bonferroni within task", "comparisons": {}}
    print(f"\n{task} (n={n})  leader = {leader} {full[leader]:.4f}", flush=True)

    for m, p_adj in zip(challengers, adjusted):
        lo, hi, p_raw, n_valid = stats[m]
        entry["comparisons"][m] = {
            "score": round(float(full[m]), 4),
            "delta": round(float(full[leader] - full[m]), 4),
            "ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4),
            "p_raw": round(p_raw, 4), "p_holm": round(p_adj, 4),
            "significant": bool(p_adj < 0.05), "n_boot_valid": int(n_valid),
        }
        print(f"   vs {m:24s} d={full[leader] - full[m]:+.4f} "
              f"95% CI [{lo:+.4f}, {hi:+.4f}]  "
              f"p={p_raw:.3f} p_holm={p_adj:.3f}  "
              f"{'SIGNIFICANT' if p_adj < 0.05 else 'n.s.'}", flush=True)

    ladders = _ladder_steps(names, boots, full)
    if ladders:
        entry["ladders"] = ladders
    return entry


def _ladder_steps(names, boots, full):
    """Test each consecutive step of every applicable scale ladder."""
    out = {}
    for ladder_name, rungs in LADDERS.items():
        present = [m for m in rungs if m in names]
        if len(present) < 2:
            continue
        steps = list(zip(present, present[1:]))
        stats = []
        for lower, upper in steps:
            diff = boots[upper] - boots[lower]
            diff = diff[np.isfinite(diff)]
            lo, hi = np.percentile(diff, [2.5, 97.5])
            stats.append((lo, hi, bootstrap_p(diff)))
        adjusted = holm([s[2] for s in stats])

        out[ladder_name] = {"rungs": present, "steps": {}}
        print(f"   -- {ladder_name} (Holm over {len(steps)} steps)", flush=True)
        for (lower, upper), (lo, hi, p_raw), p_adj in zip(steps, stats, adjusted):
            delta = full[upper] - full[lower]
            # Three outcomes, not two. A step that is reliably *worse* is a
            # different finding from a step that cannot be resolved, and
            # collapsing both into "no gain" would hide a scale regression --
            # which is exactly what ESM-2 35M -> 150M does on Fluorescence.
            if p_adj >= 0.05:
                direction = "no reliable difference"
            elif delta > 0:
                direction = "improves"
            else:
                direction = "REGRESSES"
            out[ladder_name]["steps"][f"{lower}->{upper}"] = {
                "delta": round(float(delta), 4),
                "ci_low": round(float(lo), 4), "ci_high": round(float(hi), 4),
                "p_raw": round(p_raw, 4), "p_holm": round(p_adj, 4),
                "direction": direction,
                "significant": bool(p_adj < 0.05),
            }
            print(f"      {lower} -> {upper:16s} d={delta:+.4f} "
                  f"95% CI [{lo:+.4f}, {hi:+.4f}] p_holm={p_adj:.3f}  "
                  f"{direction}", flush=True)
    return out


def merge_report(task, entry):
    """Read-modify-write, so a per-task subprocess keeps earlier tasks."""
    report = {}
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH) as fh:
            report = json.load(fh)
    report[task] = entry
    tmp = f"{REPORT_PATH}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        json.dump(report, fh, indent=2)
    os.replace(tmp, REPORT_PATH)


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
                            task_name], check=False)
        print(f"\nWrote {REPORT_PATH}", flush=True)
