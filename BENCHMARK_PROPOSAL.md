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

### A. Small Molecule Modality (~15,000 compounds total)
1. **BBBP** (Classification, 2,050 compounds) — *Membrane permeability / Blood-brain barrier*
2. **ClinTox** (Classification, 1,478 compounds) — *Clinical toxicity & FDA approval*
3. **BACE** (Classification, 1,513 compounds) — *Target binding (Binding affinity)*
4. **ESOL** (Regression, 1,128 compounds) — *Aqueous solubility*
5. **Lipophilicity** (Regression, 4,200 compounds) — *Octanol-water partition coefficient*
6. **CYP3A4 Substrate** (Classification, 6,676 compounds) — *Metabolism stability (TDC)*

### B. Protein Modality (~94,000 sequences/residues total)
7. **DeepLoc** (Classification, 14,000 proteins) — *Global subcellular localization*
8. **CB513** (Per-residue Q3 Classification, 80,000 residues) — *Secondary structure prediction*

### C. Genomic Modality (~15,000 sequences total)
9. **GenomicBenchmarks / Human Promoters** (Classification, 15,000 sequences) — *Regulatory sequence detection*

---

## 3. Compute Feasibility & Math

| Modality / Task Set | Sample Count | Tensor Size ($d=768$ to $1024$) | CPU Evaluation Time |
| :--- | :--- | :--- | :--- |
| **6 Molecular Tasks** | ~15,000 compounds | ~45 MB | ~5 seconds |
| **DeepLoc (Protein)** | 14,000 proteins | ~57 MB | ~8 seconds |
| **CB513 (Residues)** | 80,000 residues | ~320 MB | ~45 seconds |
| **Genomics Task** | 15,000 sequences | ~45 MB | ~5 seconds |
| **TOTAL SUITE** | **~124,000 vectors** | **~467 MB** | **< 90 seconds (Single CPU)** |

* **Total Hosting Cost**: $0 (Stored on Hugging Face Datasets)
* **Total Compute Cost per Submission**: $0 (Executed in GitHub Actions)

---

## 4. Key Metric Innovations

1. **Pure Representation Score**: ROC-AUC / RMSE evaluated strictly via frozen linear probes.
2. **Dimensional Efficiency (AUC/dim or RMSE/dim)**: Evaluates performance per embedding dimension to inform high-throughput virtual screening (billion-scale compound libraries).
3. **Latency / Inference Time**: Time required to generate 1,000 embeddings.

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

Two decisions above are not free and should be scoped explicitly before committing:

1. **CB513 replacement (D2).** Sourcing and splitting a NetSurfP-2.0 / CASP-derived secondary-structure set, *or* standing up a whole-protein FLIP regression task, plus its probing harness.
2. **Leakage-audit pipeline (D3).** Obtaining public pretraining corpora and building the scaffold/sequence-identity overlap computation — the highest-effort, highest-value item in the proposal.
