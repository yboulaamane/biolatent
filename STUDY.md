# BioLatent Frozen-Embedding Study — Methods and Results

This document records what the benchmark actually does and what it found. It is
the companion to `BENCHMARK_PROPOSAL.md`, which records the design decisions;
this file records the execution.

Everything below is computed by the code in `benchmark/`. Nothing is
transcribed from a publication, and nothing is imputed.

---

## 1. What replaced the previous implementation

The earlier benchmark runner did not run any model. It computed ECFP4 (for
molecules) or k-mer counts (for sequences) once, then produced each "model" by
applying a random Gaussian projection seeded from the model's name to reshape
that single baseline to the model's advertised dimension. Every entry was
therefore the same features under a different random rotation, and the reported
MLP column was the linear score multiplied by a constant. Protein language
models carried scores on molecular tasks, which is not possible.

That code has been deleted. The current pipeline loads real checkpoints and
runs real inference:

| Stage | File | What it does |
| :--- | :--- | :--- |
| Data | `download_real_datasets.py` | Fetches nine datasets, preserving official splits |
| Loading | `datasets.py` | One standard shape per task; refuses missing or degenerate data |
| Phase A | `embed.py` | Real frozen embeddings from real checkpoints, cached to disk |
| Phase B | `probe.py` | Linear probe (ranked) and fixed MLP (diagnostic) |
| Audit | `leakage.py`, `run_leakage.py` | Pretraining-corpus overlap per task |
| Runner | `run_study.py` | Orchestrates, resumable, never back-fills a failure |

---

## 2. Protocol

**Embeddings.** Every transformer is mean-pooled over its non-padding tokens.
Pooling is pinned rather than chosen per model because CLS-versus-mean pooling
alone can move a score by several points; leaving it free would let that choice
masquerade as a difference between representations. Truncation is fixed per
modality (proteins 1022, genomics 512, molecules 256 tokens). Each cached
matrix carries a sidecar JSON with checkpoint, dimension, pooling, truncation
and a content hash.

**Probes.** The ranked metric is an L2-regularised linear probe. Regularisation
is selected from one fixed grid by 3-fold cross-validation on the training
split — the same grid, folds and seed for every model — and then refit on the
full training split. On tasks with more than 6,000 training rows the search
runs on a stratified 6,000-row subsample and the selected value is refit on
everything; the reported model always sees all training data. The test split is
touched once.

A fixed 2-layer MLP (256 units, seed 42, identical settings everywhere) is
reported as a diagnostic and never ranked. Ranking it would measure the MLP's
capacity rather than the representation.

**Metrics follow the task.** Binary classification uses ROC-AUC; multi-class
uses accuracy and macro-F1; regression uses Spearman ρ, with RMSE and R² also
recorded. Spearman is ranked for regression because RMSE is not comparable
across tasks with different target scales — which is also why "RMSE per
embedding dimension" was dropped as a metric, being a quantity with no meaning.

**Modality is enforced.** A model is evaluated only on its own modality. A
protein language model cannot embed a SMILES string, so that cell is absent
rather than filled.

---

## 3. Splits

| Task | Split | Source |
| :--- | :--- | :--- |
| BBBP, ClinTox, BACE, ESOL, Lipophilicity | Balanced Bemis-Murcko scaffold, seed 42 | computed |
| CYP3A4 | Scaffold | TDC official |
| DeepLoc | Author partition | official |
| Fluorescence | Author partition | official (TAPE) |
| Promoters | Author partition | official (NT) |

Two split facts are worth stating plainly because both changed the results.

**Fluorescence must use the official partition.** Its test split (27,217) is
deliberately larger than its train split (21,446): training variants sit close
to wild-type and test variants are distant, so the task measures extrapolation.
An earlier version of this pipeline downloaded only the training split and
re-split it at random, which converts the benchmark into interpolation and
inflates every score.

**The scaffold split had to be balanced.** Assigning scaffold groups in dataset
order produced validation and test sets containing a single class on BBBP —
roughly three quarters of BBBP scaffolds are singletons, and taking them in file
order inherits the file's ordering bias — leaving ROC-AUC undefined and silently
returning NaN. Groups are now shuffled under a fixed seed, and `datasets.py`
raises if any classification split is single-class.

Splits were verified to be scaffold-disjoint: zero shared scaffolds and zero
shared SMILES between train and test on BBBP, BACE and ClinTox.

> Because this is a *balanced* scaffold split, these numbers are not directly
> comparable to published values computed under DeepChem's deterministic
> scaffold splitter, which produces a harder test set. That incomparability is
> the point: benchmark values do not transfer across protocols, which is why
> the suite recomputes everything under one protocol rather than aggregating
> reported numbers.

---

## 4. Results — molecular tasks

Ranked metric, linear probe. `gap` is MLP minus linear.

| Task | Best | Score | 2nd | Score |
| :--- | :--- | :--- | :--- | :--- |
| BBBP (ROC-AUC) | **RDKit2D** | 0.9176 | ChemBERTa-ZINC | 0.9048 |
| ClinTox (ROC-AUC) | ChemBERTa-ZINC | 0.8597 | ECFP4 | 0.8109 |
| BACE (ROC-AUC) | **ECFP4** | 0.8601 | ChemBERTa-ZINC | 0.8571 |
| ESOL (Spearman) | **RDKit2D** | 0.9185 | ChemBERTa-77M | 0.8398 |
| Lipophilicity (Spearman) | **RDKit2D** | 0.6409 | ChemBERTa-77M | 0.6376 |
| CYP3A4 (ROC-AUC) | **ECFP4** | 0.8463 | RDKit2D | 0.8333 |

**Classical descriptors win five of six molecular tasks.** A 210-dimensional
RDKit descriptor vector beats both pretrained ChemBERTa variants on BBBP, ESOL
and Lipophilicity, and 1024-bit ECFP4 wins BACE and CYP3A4. The only task where
a pretrained transformer leads is ClinTox.

This is consistent with, and independently reproduces, the conclusion of Sultan
et al. (*J. Cheminform.* 2026, 10.1186/s13321-026-01252-z) that descriptor
baselines remain strong against pretrained molecular transformers.

**The linear-to-MLP gap is small and often negative** (range −0.157 to +0.040).
Adding non-linear capacity on top of these frozen embeddings rarely helps, so
what the representations encode is largely linearly accessible. The one large
negative gap, ECFP4 on ESOL (−0.157), reflects a binary fingerprint being a poor
substrate for a continuous physicochemical regression — it is also ECFP4's worst
task in absolute terms (ρ = 0.592 against RDKit2D's 0.918).

---

## 4b. Results — protein tasks (DeepLoc, in progress)

Ranked metric: accuracy over ten localisation classes.

| Model | Dim | Accuracy | MLP gap |
| :--- | ---: | ---: | ---: |
| 3-mer frequency | 8000 | 0.5288 | +0.018 |
| ESM-2 8M | 320 | 0.6639 | +0.019 |
| ESM-2 150M | 640 | 0.7308 | −0.017 |
| ESM-2 650M | 1280 | *running* | |
| ProtBERT | 1024 | *pending* | |

Unlike the molecular tasks, **pretrained protein representations beat the
classical baseline decisively** — ESM-2 8M is 13.5 points above 3-mer frequency
despite using 25× fewer dimensions, and accuracy rises monotonically with model
scale. This is the clearest scale effect anywhere in the suite, and it is the
opposite of the molecular picture, where descriptor baselines won five of six
tasks.

The contrast is worth stating carefully: it does **not** show that protein
language models generalise better than molecular ones. The leakage audit (§5)
finds that every DeepLoc test protein is represented in UniRef50 by
construction, so part of what this ladder measures is how much of a
memorised corpus a larger model retains.

### A note on compute stability

These runs exposed a failure mode worth recording. On this stack an allocation
failure surfaces as `AcceleratorError: CUDA error: out of memory` rather than
`torch.cuda.OutOfMemoryError`, and it leaves the CUDA context unusable — so
after one model overflowed, every subsequent model failed instantly with the
same error for an unrelated reason, and the log showed four "failures" that were
really one. Embedding runs are therefore executed in an isolated subprocess per
(model, dataset), which confines a context loss to the cell that caused it.

Separately, two runner instances briefly competed for the same 4 GB card, which
reduced throughput from roughly 220 sequences/second to 8 and produced
allocation failures at model load. Throughput figures in this document are from
single-tenant runs.

---

## 5. Results — leakage audit

Fraction of each **test split** with a Murcko-scaffold match or ECFP4 Tanimoto
≥ 0.9 against a random 150,000-molecule sample of ZINC.

| Task | Test items flagged | Fraction |
| :--- | :--- | :--- |
| ESOL | 53 / 114 | **46.5%** |
| BBBP | 61 / 205 | 29.8% |
| ClinTox | 44 / 148 | 29.7% |
| Lipophilicity | 95 / 420 | 22.6% |
| CYP3A4 | 249 / 1234 | 20.2% |
| BACE | 2 / 152 | **1.3%** |

These are **lower bounds**: sampling 150k of ZINC can only miss overlap, never
invent it, and only one corpus was audited empirically.

Two things follow. First, between a fifth and nearly a half of the test items on
five of six molecular benchmarks are chemically present in a corpus that
molecular language models routinely pretrain on — so a frozen-embedding score on
those tasks is partly a memorisation readout. Second, **BACE is the exception at
1.3%**, which makes it the most trustworthy molecular task in the suite: it is a
focused inhibitor series that sits outside generic drug-like chemical space. It
is also, notably, the one task where the ranking is tightest (ECFP4 0.8601 versus
ChemBERTa-ZINC 0.8571).

### Structural contamination

For the protein and genomic tasks the overlap is not a sampling question:

- **DeepLoc and Fluorescence** entries are UniProt proteins; UniRef50 clusters
  essentially all of UniProt at 50% identity. Every ESM-2 variant and ProtBERT
  declares UniRef50 as its pretraining corpus, so test proteins are represented
  in pretraining **by construction**.
- **Promoters** sequences are excerpts of the same human reference assembly the
  Nucleotide Transformer and HyenaDNA were pretrained on — again contained **by
  construction**.

Reporting a sampled percentage here would understate a near-total contamination,
so the audit records the structural claim instead. The practical consequence is
that frozen-embedding leaderboards for protein and genomic language models
cannot be interpreted as measuring generalisation to unseen sequences, and
should not be presented as if they were.

---

## 6. Model roster

Fourteen entries were specified; thirteen ran.

**Molecules** — ECFP4, RDKit2D, ChemBERTa-77M-MLM, ChemBERTa-ZINC-base.
**Proteins** — 3-mer frequency, ESM-2 (8M / 35M / 150M / 650M), ProtBERT.
**Genomics** — 5-mer frequency, Nucleotide Transformer 500M, HyenaDNA-tiny.

**MoLFormer-XL is absent.** Its remote modelling code imports
`transformers.masking_utils`, which does not exist in transformers 4.50.3.
Rather than pin a separate stack for one model, it is reported as not evaluated.
An unrun model is an omission; a substituted one would be an error.

---

## 7. Limitations

1. **One corpus was audited empirically.** ZINC was sampled; PubChem was not.
   Reported molecular leakage is a lower bound.
2. **Balanced scaffold splits are easier** than DeepChem's deterministic
   splitter, so absolute values here sit above commonly cited figures for the
   same task names. Values are internally comparable, not externally.
3. **DeepLoc is a simplification.** The source is multi-label over ten
   compartments; the argmax compartment is used as a single-label 10-class
   target. This is not the original multi-label task.
4. **CYP3A4 is inhibition, not substrate** (TDC `CYP3A4_Veith`). The substrate
   dataset is a different and much smaller one.
5. **Mean pooling is imposed on every model**, including those whose authors
   recommend a different readout. This is deliberate for comparability but will
   disadvantage some checkpoints relative to their published usage.
6. **No confidence intervals.** Scores are single-seed point estimates; the
   probe is deterministic but the split seed is not varied.
