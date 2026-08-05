"""
BioLatent D3: Leakage Audit Runner
==================================

Measures, per task, how much of the *test split* is recoverable from the
pretraining corpora that models declare. The result is a per-model leakage-risk
flag that sits beside the score rather than a silent correction to it.

Scope and honesty about it
--------------------------
Corpus coverage is uneven and the report says so per row:

* **ZINC** is audited directly against a random sample of the real corpus. The
  reported fraction is therefore a *lower bound* -- sampling can only miss
  overlap, never invent it.
* **UniRef50 and the human reference genome** are not sampled here. For those
  the overlap is structural rather than empirical: DeepLoc entries are UniProt
  proteins and UniRef50 clusters essentially all of UniProt, and the promoter
  sequences are excerpts of the same human reference assembly the genomic
  models were pretrained on. Sampling would produce a number that understates a
  contamination which is near-total by construction, so the audit records the
  structural claim instead of a misleading percentage.

Usage:
    python benchmark/run_leakage.py [--sample 200000]
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.leakage import AUDIT_DIR, DECLARED_CORPORA, molecule_overlap

CORPORA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "corpora")
REPORT_PATH = os.path.join(AUDIT_DIR, "leakage_report.json")

# Corpora that cover a benchmark's items by construction rather than by
# sampling. Recorded as a structural claim with its justification.
STRUCTURAL = {
    "uniref50": ("DeepLoc entries are UniProt proteins and UniRef50 clusters "
                 "essentially all of UniProt at 50% identity, so test proteins "
                 "are represented in pretraining by construction."),
    "human_ref_genome": ("Promoter sequences are excerpts of the human reference "
                         "assembly used for pretraining, so test sequences are "
                         "contained in the pretraining corpus by construction."),
    "pubchem10m": ("PubChem is the union source for most public medicinal-chemistry "
                   "sets; overlap is expected but was not sampled here."),
}


def load_zinc(sample_n, seed=42):
    path = os.path.join(CORPORA_DIR, "zinc_full.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, usecols=["smiles"])
    if len(df) > sample_n:
        df = df.sample(sample_n, random_state=seed)
    return df["smiles"].astype(str).tolist()


def main(sample_n):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    print(f"Loading ZINC sample (n={sample_n:,})...", flush=True)
    zinc = load_zinc(sample_n)
    if zinc is None:
        print("  ZINC corpus absent; molecular audit will be skipped.", flush=True)

    report = {"sample_size": sample_n, "tasks": {}}

    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        test_inputs = [data["inputs"][i] for i in data["test_idx"]]
        entry = {"modality": data["modality"], "n_test": len(test_inputs),
                 "empirical": {}, "structural": {}}

        if data["modality"] == "molecule" and zinc:
            print(f"  {task}: ECFP4/scaffold overlap vs ZINC sample...", flush=True)
            mask = molecule_overlap(test_inputs, zinc)
            entry["empirical"]["zinc"] = {
                "n_flagged": int(mask.sum()),
                "fraction": round(float(mask.mean()), 4),
                "basis": "Murcko scaffold identity or ECFP4 Tanimoto >= 0.9 "
                         "against a random sample of ZINC (lower bound)",
            }
            np.save(os.path.join(AUDIT_DIR, f"{task}__zinc_mask.npy"), mask)
            print(f"     {mask.sum()}/{len(mask)} ({mask.mean():.1%})", flush=True)

        for corpus, justification in STRUCTURAL.items():
            models = [m for m, c in DECLARED_CORPORA.items() if corpus in c]
            relevant = (
                (corpus == "uniref50" and data["modality"] == "protein")
                or (corpus == "human_ref_genome" and data["modality"] == "genomics")
                or (corpus == "pubchem10m" and data["modality"] == "molecule")
            )
            if relevant:
                entry["structural"][corpus] = {
                    "affected_models": models,
                    "claim": justification,
                }

        report["tasks"][task] = entry

    with open(REPORT_PATH, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {REPORT_PATH}", flush=True)
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200000)
    main(ap.parse_args().sample)
