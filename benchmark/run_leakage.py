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
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.datasets import ALL_DATASETS, load_benchmark_dataset
from benchmark.leakage import (AUDIT_DIR, DECLARED_CORPORA, molecule_overlap,
                               sequence_overlap)

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


def load_pubchem(sample_n, seed=42):
    """Reservoir-sample SMILES from the PubChem CID-SMILES dump.

    The file holds >100M rows, so it is streamed rather than loaded. PubChem is
    the corpus behind ChemBERTa and one of MoLFormer-XL's two sources, which
    makes it the corpus that matters most for the molecular results.
    """
    path = os.path.join(CORPORA_DIR, "cid-smiles.gz")
    if not os.path.exists(path):
        return None

    rng = np.random.RandomState(seed)
    reservoir, seen = [], 0
    with gzip.open(path, "rt") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            smi = parts[1]
            seen += 1
            if len(reservoir) < sample_n:
                reservoir.append(smi)
            else:
                j = rng.randint(0, seen)
                if j < sample_n:
                    reservoir[j] = smi
    print(f"  PubChem: sampled {len(reservoir):,} of {seen:,} rows", flush=True)
    return reservoir


def load_swissprot(sample_n=None):
    """Load Swiss-Prot sequences.

    Swiss-Prot rather than a random UniRef50 sample, deliberately. UniRef50
    clusters essentially all of UniProt, so a random sample of it would report a
    near-zero hit rate against a few thousand test proteins while true coverage
    is near-total -- a number that would be technically correct and completely
    misleading. Swiss-Prot is the reviewed subset DeepLoc is actually built
    from, so overlap against it is a real, tight lower bound.
    """
    path = os.path.join(CORPORA_DIR, "sprot.fasta")
    if not os.path.exists(path):
        return None
    seqs, current = [], []
    with open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                if current:
                    seqs.append("".join(current))
                    current = []
            else:
                current.append(line.strip())
    if current:
        seqs.append("".join(current))
    if sample_n and len(seqs) > sample_n:
        rng = np.random.RandomState(42)
        seqs = [seqs[i] for i in rng.choice(len(seqs), sample_n, replace=False)]
    return seqs


def main(sample_n):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    print(f"Loading molecular corpora (sample n={sample_n:,})...", flush=True)
    mol_corpora = {}
    zinc = load_zinc(sample_n)
    if zinc:
        mol_corpora["zinc"] = zinc
    pubchem = load_pubchem(sample_n)
    if pubchem:
        mol_corpora["pubchem"] = pubchem
    if not mol_corpora:
        print("  No molecular corpus present; molecular audit skipped.", flush=True)

    print("Loading Swiss-Prot...", flush=True)
    swissprot = load_swissprot()
    print(f"  Swiss-Prot: {len(swissprot):,} sequences"
          if swissprot else "  Swiss-Prot absent; protein audit skipped.", flush=True)

    report = {"sample_size": sample_n, "tasks": {}}

    for task in ALL_DATASETS:
        data = load_benchmark_dataset(task)
        test_inputs = [data["inputs"][i] for i in data["test_idx"]]
        entry = {"modality": data["modality"], "n_test": len(test_inputs),
                 "empirical": {}, "structural": {}}

        if data["modality"] == "molecule":
            for corpus_name, corpus in mol_corpora.items():
                print(f"  {task}: scaffold/ECFP4 overlap vs {corpus_name}...",
                      flush=True)
                mask = molecule_overlap(test_inputs, corpus)
                entry["empirical"][corpus_name] = {
                    "n_flagged": int(mask.sum()),
                    "fraction": round(float(mask.mean()), 4),
                    "basis": f"Murcko scaffold identity or ECFP4 Tanimoto >= 0.9 "
                             f"against a random {sample_n:,}-molecule sample of "
                             f"{corpus_name} (lower bound)",
                }
                np.save(os.path.join(AUDIT_DIR, f"{task}__{corpus_name}_mask.npy"),
                        mask)
                print(f"     {mask.sum()}/{len(mask)} ({mask.mean():.1%})", flush=True)

        elif data["modality"] == "protein" and swissprot:
            print(f"  {task}: MMseqs2 search vs Swiss-Prot at 50% identity...",
                  flush=True)
            mask = sequence_overlap(test_inputs, swissprot,
                                    min_identity=0.5, coverage=0.5)
            entry["empirical"]["swissprot"] = {
                "n_flagged": int(mask.sum()),
                "fraction": round(float(mask.mean()), 4),
                "basis": "MMseqs2 alignment at >=50% sequence identity and >=50% "
                         "coverage against all of Swiss-Prot. Swiss-Prot is a "
                         "subset of the UniProt that UniRef50 clusters, so this "
                         "is a lower bound on UniRef50 coverage.",
            }
            np.save(os.path.join(AUDIT_DIR, f"{task}__swissprot_mask.npy"), mask)
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
