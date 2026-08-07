"""
BioLatent D3: Pretraining Input-Exposure Audit
==============================================

Self-supervised pretraining can expose a model to benchmark inputs without
exposing their downstream labels. This is not label leakage, but it can make a
nominally held-out test item familiar and is therefore important context for a
frozen-embedding comparison.

This module measures that overlap directly instead of trusting a self-report.
Authors declare *which corpora* they pretrained on -- a controlled, checkable
claim -- and the overlap against those corpora is computed here.

Two similarity notions, one per modality:

* **Molecules** -- Bemis-Murcko scaffold identity, plus ECFP4 Tanimoto >= 0.9
  for near-duplicate detection. Scaffold identity is the stricter test of
  whether a benchmark's *chemotype* was seen; Tanimoto catches the same
  compound in a different salt or tautomer form.
* **Proteins / DNA** -- MMseqs2 search at a configurable identity threshold
  (default 30% for proteins, the conventional homology floor).

Output per (corpus, task) is the fraction of *test-split* items with a hit,
and the per-item hit mask so that an exposure-controlled sensitivity subset can
be formed by intersecting masks across models.
"""

import json
import os
import subprocess
import tempfile

import numpy as np
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.Scaffolds import MurckoScaffold

RDLogger.DisableLog("rdApp.*")

AUDIT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "leakage")
os.makedirs(AUDIT_DIR, exist_ok=True)

MMSEQS = os.path.expanduser("~/miniforge3/envs/cdd/bin/mmseqs")

# Declared pretraining corpora per model. These are the *claims* made by each
# model's publication; the audit checks them, it does not take them on trust.
# A corpus of None means the model does no pretraining (classical featurisers).
DECLARED_CORPORA = {
    "ecfp4": [], "rdkit2d": [], "kmer3_protein": [], "kmer5_dna": [],
    "chemberta_77m": ["pubchem10m"],
    "chemberta_zinc": ["zinc250k"],
    "molformer_xl": ["pubchem10m", "zinc250k"],
    "esm2_8m": ["uniref50"], "esm2_35m": ["uniref50"],
    "esm2_150m": ["uniref50"], "esm2_650m": ["uniref50"],
    "protbert": ["uniref100"],
    "nucleotide_transformer": ["human_ref_genome"],
    "hyenadna": ["human_ref_genome"],
}


# ------------------------------------------------------------- molecules

def scaffold_set(smiles_list):
    out = set()
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        try:
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(
                mol=mol, includeChirality=False)
            # Acyclic compounds all have the empty Murcko scaffold. Treating
            # that empty string as a shared chemotype would flag any acyclic
            # benchmark molecule whenever the corpus contains one unrelated
            # acyclic molecule.
            if scaffold:
                out.add(scaffold)
        except Exception:
            continue
    return out


def _fps(smiles_list):
    fps, keep = [], []
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        fps.append(AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024))
        keep.append(i)
    return fps, keep


def prepare_molecule_corpus(smiles_list):
    """Parse a molecular exposure corpus once for reuse across tasks."""
    canonical, scaffolds, fingerprints = set(), set(), []
    for value in smiles_list:
        molecule = Chem.MolFromSmiles(str(value))
        if molecule is None:
            continue
        canonical.add(Chem.MolToSmiles(molecule))
        try:
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(
                mol=molecule, includeChirality=False)
            if scaffold:
                scaffolds.add(scaffold)
        except Exception:
            pass
        fingerprints.append(AllChem.GetMorganFingerprintAsBitVect(
            molecule, 2, nBits=1024))
    return {"canonical": canonical, "scaffolds": scaffolds,
            "fingerprints": fingerprints}


def molecule_overlap_components(test_smiles, corpus_smiles,
                                tanimoto_cutoff=0.9, corpus_index=None):
    """Exact, near-duplicate and scaffold exposure masks.

    These dimensions are reported separately because a shared chemotype is a
    much weaker form of familiarity than an exact canonical molecule.
    """
    n = len(test_smiles)
    exact = np.zeros(n, dtype=bool)
    near = np.zeros(n, dtype=bool)
    scaffold = np.zeros(n, dtype=bool)

    prepared = (corpus_index if corpus_index is not None
                else prepare_molecule_corpus(corpus_smiles))
    canonical_corpus = prepared["canonical"]
    corpus_scaffolds = prepared["scaffolds"]
    for i, smi in enumerate(test_smiles):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        exact[i] = Chem.MolToSmiles(mol) in canonical_corpus
        try:
            test_scaffold = MurckoScaffold.MurckoScaffoldSmiles(
                mol=mol, includeChirality=False)
            if test_scaffold and test_scaffold in corpus_scaffolds:
                scaffold[i] = True
        except Exception:
            pass

    corpus_fps = prepared["fingerprints"]
    if corpus_fps:
        test_fps, keep = _fps(test_smiles)
        for fp, idx in zip(test_fps, keep):
            sims = DataStructs.BulkTanimotoSimilarity(fp, corpus_fps)
            if sims and max(sims) >= tanimoto_cutoff:
                near[idx] = True
    return {"exact_identity": exact, "near_duplicate": near,
            "shared_scaffold": scaffold,
            "any_proxy_hit": exact | near | scaffold}


def molecule_overlap(test_smiles, corpus_smiles, tanimoto_cutoff=0.9):
    """Compatibility wrapper returning the union exposure mask."""
    return molecule_overlap_components(test_smiles, corpus_smiles,
                                       tanimoto_cutoff)["any_proxy_hit"]


# ------------------------------------------------------- sequences (mmseqs)

def _write_fasta(path, seqs, prefix):
    with open(path, "w") as fh:
        for i, s in enumerate(seqs):
            fh.write(f">{prefix}{i}\n{str(s)}\n")


def sequence_overlap(test_seqs, corpus_seqs, min_identity=0.3, coverage=0.5):
    """Per-test-item homology-exposure mask via MMseqs2 search.

    A test sequence is flagged if any corpus sequence aligns to it at or above
    ``min_identity`` sequence identity with at least ``coverage`` coverage.
    """
    mask = np.zeros(len(test_seqs), dtype=bool)
    if not corpus_seqs:
        return mask

    with tempfile.TemporaryDirectory() as tmp:
        q = os.path.join(tmp, "query.fasta")
        t = os.path.join(tmp, "target.fasta")
        res = os.path.join(tmp, "hits.m8")
        _write_fasta(q, test_seqs, "q")
        _write_fasta(t, corpus_seqs, "t")
        cmd = [MMSEQS, "easy-search", q, t, res, os.path.join(tmp, "tmp"),
               "--min-seq-id", str(min_identity), "-c", str(coverage),
               "--threads", "8", "-v", "1"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"mmseqs failed: {proc.stderr[-400:]}")
        if os.path.exists(res):
            with open(res) as fh:
                for line in fh:
                    parts = line.split("\t")
                    if parts:
                        mask[int(parts[0][1:])] = True
    return mask


# ------------------------------------------------------------------ driver

def audit_task(task_name, test_inputs, modality, corpora):
    """Compute input-exposure masks for one task against supplied corpus proxies.

    ``corpora`` maps corpus name -> list of items (SMILES or sequences).
    """
    report = {}
    for corpus_name, items in corpora.items():
        if not items:
            continue
        if modality == "molecule":
            mask = molecule_overlap(test_inputs, items)
        else:
            ident = 0.3 if modality == "protein" else 0.8
            mask = sequence_overlap(test_inputs, items, min_identity=ident)
        report[corpus_name] = {
            "n_test": int(len(test_inputs)),
            "n_flagged": int(mask.sum()),
            "fraction": round(float(mask.mean()), 4),
            "mask": mask.tolist(),
        }
        print(f"      {task_name} vs {corpus_name}: "
              f"{mask.sum()}/{len(mask)} ({mask.mean():.1%}) flagged", flush=True)
    return report


def save_audit(report, name):
    path = os.path.join(AUDIT_DIR, f"{name}.json")
    with open(path, "w") as fh:
        json.dump(report, fh, indent=2)
    return path
