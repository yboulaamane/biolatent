# Proposal: BioLatent Active Benchmarking Suite (Frozen Embedding Probing)

## Executive Summary
This proposal outlines the strategic transition of **BioLatent** from a literature-indexed registry into an **active, community-driven benchmarking suite** for chemical and biological vector representations.

Instead of expensive end-to-end model fine-tuning, BioLatent adopts a **Frozen Embedding Probing** methodology. This decouples one-time representation generation from ultra-fast, zero-cost downstream evaluation, making it feasible to run a multi-modal leaderboard at **$0 infrastructure cost**.

---

## 1. Core Architecture & Methodology

### Phase A: Pre-Computed Embedding Tensors (One-Time Cost)
* Model authors or BioLatent maintainers run inference **once** per model over standardized dataset splits.
* The output is a frozen matrix of representation vectors ($N \times d$, e.g., $2050 \times 768$ for BBBP).
* Embeddings are hosted on open-access storage (e.g., Hugging Face Datasets or Zenodo).

### Phase B: Standardized Downstream Probing (Near-Zero Cost)
* Downstream evaluation uses standardized, hyperparameter-free probes (e.g., `scikit-learn` Ridge/Logistic Regression or a fixed 2-layer MLP).
* **Elimination of Downstream Tuning Bias**: All representations are evaluated with the exact same classifier architecture and random seeds on identical scaffold splits.
* Evaluation takes **seconds on a single CPU**, enabling automated leaderboard scoring via free GitHub Actions runners.

---

## 2. Curated Multi-Modal Task Suite (9 Tasks)

To ensure generalizability without benchmark bloat, the proposed suite spans 9 representative tasks across 3 modalities:

Sample counts below reflect the **actual downloaded datasets** (see §7, Dataset Provenance), not paper-reported figures.

### A. Small Molecule Modality (~22,700 compounds total)
1. **BBBP** (Classification, 2,039 compounds) — *Membrane permeability / Blood-brain barrier*
2. **ClinTox** (Classification, 1,480 compounds) — *Clinical toxicity & FDA approval*
3. **BACE** (Classification, 1,513 compounds) — *Target binding (Binding affinity)*
4. **ESOL** (Regression, 1,128 compounds) — *Aqueous solubility*
5. **Lipophilicity** (Regression, 4,200 compounds) — *Octanol-water partition coefficient*
6. **CYP3A4 Substrate** (Classification, 12,328 compounds) — *CYP3A4 inhibition, TDC `CYP3A4_Veith`*

### B. Protein Modality (~43,700 sequences total)
7. **DeepLoc** (Classification, 22,233 proteins) — *Global subcellular localization (argmax of 10 compartments)*
8. **Fluorescence** (Regression, 21,446 proteins) — *GFP fitness landscape (TAPE), log-fluorescence*

> **CB513 was dropped** per Design Decision D2. It was replaced with a **whole-protein regression** task (Fluorescence) so the protein modality mirrors the molecule side's classification + regression shape and preserves the per-object "one vector → one probe" harness. This also avoids enshrining a dataset ProtTrans itself calls "redundant and outdated."

### C. Genomic Modality (~31,400 sequences total)
9. **Human Promoters** (Classification, 31,443 sequences, 300 bp) — *Regulatory sequence detection; Nucleotide Transformer `promoter_all`, balanced*

---

## 3. Compute Feasibility & Math

| Modality / Task Set | Sample Count | Tensor Size ($d=768$ to $1024$) | CPU Evaluation Time |
| :--- | :--- | :--- | :--- |
| **6 Molecular Tasks** | ~22,700 compounds | ~68 MB | ~7 seconds |
| **DeepLoc (Protein)** | 22,233 proteins | ~68 MB | ~10 seconds |
| **Fluorescence (Protein)** | 21,446 proteins | ~66 MB | ~9 seconds |
| **Promoters (Genomics)** | 31,443 sequences | ~96 MB | ~12 seconds |
| **TOTAL SUITE** | **~98,000 vectors** | **~298 MB** | **< 60 seconds (Single CPU)** |

> Counts are the actual downloaded datasets. All are per-object (one vector per molecule/protein/sequence), so a single probing harness covers every task — no per-residue special case.

* **Total Hosting Cost**: $0 (Stored on Hugging Face Datasets)
* **Total Compute Cost per Submission**: $0 (Executed in GitHub Actions)

---

## 4. Key Metric Innovations

1. **Linear Probe Score** (ranked): ROC-AUC (binary), accuracy and macro-F1 (multi-class), or Spearman ρ (regression), from a frozen L2-regularised linear probe. Named for what it measures — linear decodability under this probe — rather than "pure representation quality", which would overclaim.
2. **Linear-to-MLP gap** (diagnostic): the difference between a fixed 2-layer MLP and the linear probe, separating representations whose information is linearly accessible from those needing a non-linear head.
3. **Leakage-risk flag**: fraction of the test split recoverable from a model's declared pretraining corpora (§7 of `STUDY.md`).
4. **Embedding dimension and inference time**, recorded per model.

> *Dropped:* "RMSE per embedding dimension". RMSE is not comparable across tasks with different target scales, so dividing it by a dimension count produces a quantity with no meaning. Dimension is reported alongside the score instead.

---

## 5. Design Decisions

The three open questions below have been resolved. Each records the decision, the reasoning, and the trade-off accepted, so the choices can be defended in review rather than re-litigated.

### D1 — Probe selection: linear-ranked, MLP as diagnostic

**Decision:** The **ranked metric is a strict L2-regularized linear/logistic probe**. A **fixed 2-layer MLP is reported as a secondary diagnostic but is not ranked**.

- **Why linear ranks.** A linear probe has almost no capacity of its own, so whatever it decodes was already present in the embedding. This is the property that makes the fairness claim defensible: rank on the MLP and the metric starts measuring the MLP's capacity, not the representation.
- **Why keep the MLP.** The *gap* between linear and MLP performance is itself informative — it distinguishes representations that encode information linearly (cheap to use downstream) from those that need a non-linear head. Two models with equal linear scores but different MLP scores are genuinely different.
- **Guardrail.** The MLP must be pinned (fixed width 256, 2 layers, dropout 0.1, 100 epochs, seed 0, no per-model early stopping). Any per-model tuning reintroduces exactly the downstream-tuning bias the suite exists to eliminate.
- **Policy.** Ranking metric = L2-regularized linear/logistic probe (single fixed regularization value selected once by 5-fold CV, not per model). Secondary diagnostic = the fixed MLP above, reported but not ranked.
- **Trade-off accepted.** Two columns is more surface area to explain, but compute is negligible (MLP on frozen features is still seconds) and it preempts the "linear probing is too weak to be fair" objection. Metric #1 is renamed from "Pure Representation Score" to **"Linear Probe Score"** — the earlier name overclaimed, since linear probing measures *linear decodability under this probe*, not abstract representation quality.

### D2 — Task coverage: rebalance the 9 tasks, do not add PDBBind

**Decision:** **No 3D protein–ligand complex task in v1.** Keep the suite at 9 tasks but **rebalance** rather than grow it.

- **Why not PDBBind.** A complex-affinity task needs a joint pocket+ligand representation. Most registry models do not produce one — a 2D molecular encoder and a sequence protein LM have no native way to embed a complex. Any ad-hoc fusion (e.g. concatenating a ligand vector and a protein vector) becomes an uncontrolled variable that dwarfs the representation being measured, and the column would be N/A for most models — reintroducing the sparse-grid problem the audit removed.
- **The real imbalance is internal:** 6 molecule / 2 protein / 1 genomic, with 5 of 6 molecule tasks being classification. That skew invites the critique that the conclusions are really about molecular classification.
- **Rebalancing action.** **Drop CB513** (ProtTrans itself calls it "redundant and outdated"; it should not be enshrined in a best-practice benchmark) and either (a) replace it with a NetSurfP-2.0 / CASP-derived held-out secondary-structure set, or (b) drop per-residue probing from v1 entirely and add a **whole-protein regression** task (e.g. FLIP stability or fluorescence) so the protein side mirrors the molecule side's classification+regression shape. Option (b) also preserves the clean "one vector per object → one fixed probe" uniformity (see D-note below).
- **Trade-off accepted.** The suite loses a "covers 3D structure" breadth claim. This is the correct trade — breadth that cannot be evaluated fairly is a liability, not a feature. PDBBind-style complex tasks are deferred to an explicit **v2 / Future Work** scope so the omission reads as deliberate.

*D-note (probing uniformity):* per-residue CB513 is a different harness from the per-object tasks — different data shape and a protein-level (not scaffold) split. If a per-residue task is retained, it must be described as a separate harness rather than folded into the "same classifier, same seed, same everything" uniformity claim.

### D3 — Pretraining leakage: computed, first-class, per-model audit

**Decision:** **Leakage is measured by BioLatent, not self-reported.** It becomes a computed, per-(model, task) flag — the scientific centerpiece of the suite, not a footnote.

- **Why not self-report.** Deduplication self-reports are unreliable: authors won't apply them uniformly, many cannot reconstruct their exact training set, and there is an incentive not to look. A benchmark whose integrity depends on the honesty of the ranked parties is not a benchmark. With frozen embeddings the stakes are maximal — a test item seen in pretraining has its label already encoded in its vector, so a leaked model gets an unearned linear-probe boost and the leaderboard rewards leakage.
- **Audit pipeline (computed by us):**
  1. **Structural overlap.** For each benchmark test set, compute Bemis–Murcko **scaffold** overlap (molecules) or **sequence-identity** overlap via MMseqs2 at 30–50% identity (proteins) against the *public* pretraining corpora that can be obtained (PubChem, ZINC, ChEMBL, UniRef, etc.). Private data can't be checked, but the largest models train on public data. Output a **leakage-risk score per (model, task)** = fraction of test items with a near-duplicate in that model's declared corpus.
  2. **Structured self-declaration (auditable, not trusted).** Each submission names its pretraining corpora from a **controlled list**; these map onto the precomputed overlap tables. The self-report is used to *select which overlap table applies*, not taken on faith.
  3. **Flag, don't exclude.** Display a leakage-risk badge beside each score. Silent exclusion invites "you disqualified my model" disputes; transparent flagging is more defensible and lets readers discount appropriately.
  4. **Leakage-controlled sub-leaderboard (optional).** Additionally rank on the subset of test items with zero detected overlap across *all* models — the cleanest apples-to-apples number the suite can offer.
- **Trade-off accepted.** This is the most expensive part of the plan (it requires obtaining the pretraining corpora and building an overlap pipeline), but it is also what makes the work novel and citable: a **leakage-audited** frozen-embedding benchmark is a materially stronger claim than "another leaderboard," and the overlap statistics are a publishable result in their own right.

---

## 6. Build Items Carrying Real Cost

1. **CB513 replacement (D2).** ✅ **Done** — replaced with the whole-protein **Fluorescence** regression task (TAPE GFP landscape). Uses the same per-object probing harness as every other task; no separate per-residue code path.
2. **Leakage-audit pipeline (D3).** ✅ **Built and run** — `benchmark/leakage.py` and `benchmark/run_leakage.py`. Molecular overlap is measured empirically against a ZINC sample (Murcko scaffold identity plus ECFP4 Tanimoto ≥ 0.9); protein and genomic contamination is recorded as a structural claim because it is near-total by construction. Results in `STUDY.md` §5. Remaining extension: sampling PubChem so the molecular bound tightens, and MMseqs2 identity search against a UniRef50 sample.

> **The study itself is now built and partly run.** `STUDY.md` records the protocol, the split decisions, the molecular results and the leakage audit. The fabricated runner that produced the previous `benchmark_results.json` — random Gaussian projections of a single baseline, standing in for 38 models — has been deleted.

---

## 7. Dataset Provenance

All nine datasets are **real, sourced data** — downloaded via `benchmark/download_real_datasets.py` and loaded through `benchmark/datasets.py`. An earlier version of the loader silently fabricated random SMILES/sequences for any missing dataset; that fallback has been **removed** and now raises a loud `FileNotFoundError` directing the user to the download script. No synthetic data is admissible.

| Dataset | Modality | Type | N | Source |
| :--- | :--- | :--- | :--- | :--- |
| BBBP | molecule | classification | 2,039 | MoleculeNet |
| ClinTox | molecule | classification | 1,480 | MoleculeNet |
| BACE | molecule | classification | 1,513 | MoleculeNet |
| ESOL | molecule | regression | 1,128 | MoleculeNet |
| Lipophilicity | molecule | regression | 4,200 | MoleculeNet |
| CYP3A4 | molecule | classification | 12,328 | TDC `CYP3A4_Veith` |
| DeepLoc | protein | classification | 22,233 | HF `bloyal/deeploc` (argmax of 10 compartments) |
| Fluorescence | protein | regression | 21,446 | HF `proteinglm/fluorescence_prediction` (TAPE GFP) |
| Promoters | genomics | classification | 31,443 | HF `InstaDeepAI/nucleotide_transformer_downstream_tasks_revised`, task `promoter_all` |

**Two corrections applied during this pass:**
- **"FLIP" → "Fluorescence"**: the file named `FLIP.csv` actually contained the TAPE GFP fluorescence landscape (Strategy 1 of the downloader succeeded, so the FLIP fallbacks never ran). Renamed to reflect true provenance rather than mislabel it as FLIP (stability/Meltome).
- **Promoters re-download**: the previous file held only 106 sequences — the tiny UCI *E. coli* fallback, because the NT config name `promoter_all` no longer exists (the dataset restructured to a single `default` config with a `task` column). Fixed to filter `task == "promoter_all"`, yielding 31,443 balanced 300 bp human sequences.
