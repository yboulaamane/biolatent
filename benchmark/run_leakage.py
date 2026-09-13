"""
BioLatent D3: Pretraining Input-Exposure Audit Runner
=====================================================

Measures, per task, how much of the *test split* is similar to available
proxies for corpora that models declare. The result is input-exposure context
that sits beside the score rather than a silent correction to it.

Scope and honesty about it
--------------------------
Corpus coverage is uneven and the report says so per row:

* **ZINC and PubChem** are audited against random samples of the broader
  databases, not the checkpoints' exact dated training subsets. The resulting
  fractions are exposure proxies, not confirmed membership or contamination.
  **Swiss-Prot** is searched in full as a homology proxy for the UniRef50 and
  UniRef100 corpora used by the evaluated protein checkpoints.
* **The human reference genome** is not sampled. There the overlap is
  structural rather than empirical: the promoter sequences are excerpts of the
  same assembly the genomic models were pretrained on, so coverage is total by
  definition and there is no independent corpus to search against. Sampling
  would produce a number that understates input exposure which is total by
  construction, so the audit records the structural claim instead of a
  misleading percentage. This is input exposure, not evidence that downstream
  labels were seen during pretraining.
* **ChEMBL** is declared for GROVER but no local ChEMBL snapshot is available.
  It is listed as unmeasured rather than silently represented by another
  chemical database.

A corpus is never reported both ways. Once it has an empirical measurement the
structural claim is dropped, so a reader is not offered a percentage and a
hand-wave for the same row.

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

from benchmark.datasets import (ALL_DATASETS, MOLECULE_TASKS, PROTEIN_TASKS,
                                load_benchmark_dataset)
from benchmark.leakage import (AUDIT_DIR, DECLARED_CORPORA,
                               molecule_overlap_components,
                               prepare_molecule_corpus, sequence_overlap)

CORPORA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "corpora")

# The report is committed; the per-item boolean masks it summarises stay in
# AUDIT_DIR under the ignored data/ tree. Keeping the summary beside the other
# study outputs means the numbers STUDY.md quotes are inspectable from a fresh
# clone, without committing anything that can be regenerated.
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "results",
                           "exposure_report.json")

# Corpora that cover a benchmark's items by construction rather than by
# sampling. Recorded as a structural claim with its justification.
#
# Only construction-level input exposure is stored here. Swiss-Prot homology is
# empirical and remains explicitly a proxy for UniRef50/UniRef100, not a
# structural claim.
STRUCTURAL = {
    "human_ref_genome": ("Promoter sequences are excerpts of the human reference "
                         "assembly used for pretraining, so the benchmark inputs "
                         "are exposed by construction. This does not imply label "
                         "exposure."),
}

UNMEASURED = {
    "chembl": ("No pinned local ChEMBL snapshot is available; the ZINC proxy "
               "covers only the other declared GROVER pretraining source."),
}

# Declared-corpus name -> the corpus actually sampled in the empirical audit.
MEASURED_BY = {"pubchem10m": "pubchem", "zinc250k": "zinc", "zinc": "zinc"}


def affected_models(corpus_name):
    """Models whose declared pretraining corpus is represented by a proxy."""
    aliases = ({"uniref50", "uniref100"} if corpus_name == "swissprot"
               else {declared for declared, measured in MEASURED_BY.items()
                     if measured == corpus_name})
    return [model for model, corpora in DECLARED_CORPORA.items()
            if aliases.intersection(corpora)]


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

    Swiss-Prot rather than a random UniRef sample, deliberately. UniRef50 and
    UniRef100 cluster essentially all of UniProt, so a random sample would report a
    near-zero hit rate against a few thousand test proteins and would not be a
    useful proxy. Swiss-Prot is the reviewed source from which DeepLoc 2.0 was
    curated, so homology against it is measured directly. It is used as a
    proxy for both UniRef50 (ESM-2) and UniRef100 (ProtBERT). It still does not
    prove exact membership in a checkpoint's dated training snapshot.
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


def _structural_for(modality, empirical):
    """Structural claims that apply to a modality and were not measured.

    A corpus whose overlap was actually sampled is omitted: reporting a measured
    percentage and an unquantified "overlap is expected" claim for the same
    corpus would let a reader take the weaker statement as the finding.
    """
    applies = {"protein": [], "genomics": ["human_ref_genome"],
               "molecule": []}
    out = {}
    for corpus in applies.get(modality, []):
        if MEASURED_BY.get(corpus) in empirical:
            continue
        out[corpus] = {
            "affected_models": [m for m, c in DECLARED_CORPORA.items()
                                if corpus in c],
            "claim": STRUCTURAL[corpus],
        }
    return out


def _unmeasured_for(modality):
    if modality != "molecule":
        return {}
    return {
        corpus: {
            "affected_models": [model for model, corpora in DECLARED_CORPORA.items()
                                if corpus in corpora],
            "reason": reason,
        }
        for corpus, reason in UNMEASURED.items()
        if any(corpus in corpora for corpora in DECLARED_CORPORA.values())
    }


def refresh_model_mapping():
    """Refresh model names without recomputing model-independent overlaps."""
    with open(REPORT_PATH) as handle:
        report = json.load(handle)
    for entry in report["tasks"].values():
        for corpus, empirical in entry.get("empirical", {}).items():
            empirical["affected_models"] = affected_models(corpus)
        entry["unmeasured"] = _unmeasured_for(entry["modality"])
    temporary = f"{REPORT_PATH}.{os.getpid()}.tmp"
    with open(temporary, "w") as handle:
        json.dump(report, handle, indent=2)
    os.replace(temporary, REPORT_PATH)
    print(f"Refreshed model-to-corpus mapping in {REPORT_PATH}", flush=True)


def main(sample_n, task_names=None):
    tasks = task_names or ALL_DATASETS
    unknown = sorted(set(tasks) - set(ALL_DATASETS))
    if unknown:
        raise ValueError(f"Unknown tasks: {unknown}")

    os.makedirs(AUDIT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    mol_corpora = {}
    needs_molecules = any(t in MOLECULE_TASKS for t in tasks)
    if needs_molecules:
        print(f"Loading molecular corpora (sample n={sample_n:,})...", flush=True)
        zinc = load_zinc(sample_n)
        if zinc:
            mol_corpora["zinc"] = zinc
        pubchem = load_pubchem(sample_n)
        if pubchem:
            mol_corpora["pubchem"] = pubchem
        if not mol_corpora:
            print("  No molecular corpus present; molecular audit skipped.", flush=True)
    mol_indexes = {}
    for corpus_name, corpus in mol_corpora.items():
        print(f"  Indexing {corpus_name} molecular proxy once...", flush=True)
        mol_indexes[corpus_name] = prepare_molecule_corpus(corpus)

    swissprot = None
    if any(t in PROTEIN_TASKS for t in tasks):
        print("Loading Swiss-Prot...", flush=True)
        swissprot = load_swissprot()
        print(f"  Swiss-Prot: {len(swissprot):,} sequences"
              if swissprot else "  Swiss-Prot absent; protein audit skipped.", flush=True)

    report = {
        "report_kind": "pretraining_input_exposure_proxy",
        "interpretation": ("Input familiarity audit; not evidence of downstream "
                           "label leakage or exact checkpoint-corpus membership."),
        "sample_size": sample_n, "tasks": {}}
    if task_names and os.path.exists(REPORT_PATH):
        with open(REPORT_PATH) as fh:
            report = json.load(fh)
        report["sample_size"] = sample_n

    for task in tasks:
        data = load_benchmark_dataset(task)
        test_inputs = [data["inputs"][i] for i in data["test_idx"]]
        entry = {"modality": data["modality"], "n_test": len(test_inputs),
                 "empirical": {}, "structural": {},
                 "unmeasured": _unmeasured_for(data["modality"])}

        if data["modality"] == "molecule":
            for corpus_name, corpus in mol_corpora.items():
                print(f"  {task}: exposure proxies vs {corpus_name}...",
                      flush=True)
                masks = molecule_overlap_components(
                    test_inputs, corpus, corpus_index=mol_indexes[corpus_name])
                entry["empirical"][corpus_name] = {
                    "affected_models": affected_models(corpus_name),
                    "sample_role": (f"random {sample_n:,}-molecule database "
                                    "sample used as an exposure proxy; not the "
                                    "checkpoint's exact training subset"),
                    "measures": {
                        "exact_identity": _measure(
                            masks["exact_identity"], "canonical SMILES identity"),
                        "near_duplicate": _measure(
                            masks["near_duplicate"], "ECFP4 Tanimoto >= 0.9"),
                        "shared_scaffold": _measure(
                            masks["shared_scaffold"], "Murcko scaffold identity"),
                        "any_proxy_hit": _measure(
                            masks["any_proxy_hit"], "union of the three proxies"),
                    },
                }
                for measure, mask in masks.items():
                    np.save(os.path.join(
                        AUDIT_DIR, f"{task}__{corpus_name}__{measure}.npy"), mask)
                union = masks["any_proxy_hit"]
                print(f"     union {union.sum()}/{len(union)} "
                      f"({union.mean():.1%})", flush=True)

        elif data["modality"] == "protein" and swissprot:
            print(f"  {task}: MMseqs2 search vs Swiss-Prot at 50% identity...",
                  flush=True)
            mask = sequence_overlap(test_inputs, swissprot,
                                    min_identity=0.5, coverage=0.5)
            entry["empirical"]["swissprot"] = {
                "affected_models": affected_models("swissprot"),
                "n_flagged": int(mask.sum()),
                "fraction": round(float(mask.mean()), 4),
                "basis": "MMseqs2 alignment at >=50% sequence identity and >=50% "
                         "coverage against all of Swiss-Prot. This is a homology "
                         "exposure proxy for UniRef50/UniRef100, not confirmation of exact "
                         "checkpoint training membership.",
            }
            np.save(os.path.join(AUDIT_DIR, f"{task}__swissprot_mask.npy"), mask)
            print(f"     {mask.sum()}/{len(mask)} ({mask.mean():.1%})", flush=True)

        entry["structural"] = _structural_for(data["modality"], entry["empirical"])

        report["tasks"][task] = entry

    with open(REPORT_PATH, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nWrote {REPORT_PATH}", flush=True)
    return report


def _measure(mask, basis):
    return {"n_flagged": int(mask.sum()),
            "fraction": round(float(mask.mean()), 4), "basis": basis}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200000)
    ap.add_argument("--refresh-model-mapping", action="store_true",
                    help="update declared model names without recomputing overlaps")
    ap.add_argument("tasks", nargs="*", help="optional task names to refresh")
    args = ap.parse_args()
    if args.refresh_model_mapping:
        if args.tasks:
            ap.error("--refresh-model-mapping does not accept task names")
        refresh_model_mapping()
    else:
        main(args.sample, args.tasks or None)
