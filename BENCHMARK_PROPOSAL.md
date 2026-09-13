# Proposal: BioLatent Active Benchmarking Suite (Frozen Embedding Probing)

## Executive Summary
This proposal outlines the strategic transition of **BioLatent** from a literature-indexed registry into an **active, community-driven benchmarking suite** for chemical and biological vector representations.

Instead of end-to-end model fine-tuning, BioLatent adopts a **Frozen Embedding Probing** methodology. This decouples one-time representation generation from downstream evaluation. Repeated probing is CPU-only, but neither embedding generation nor evaluation is described as universally free or sub-90-second.

## Representation inclusion rule

The literature registry is broader than the measured benchmark. A registry
entry enters the frozen benchmark only when all of the following are true
before its task scores are examined:

1. An official, publicly released checkpoint and inference implementation can
   be pinned by revision and file hash.
2. The checkpoint produces one deterministic, task-independent vector from the
   benchmark's native object input without fitting on benchmark labels.
3. Its native featuriser can represent every object in a task. An unsupported
   chemistry or input type makes that model-task cell N/A; rows are not dropped,
   imputed, or chemically rewritten to make a model run.
4. The extracted layer, pooling, precision, truncation, software environment,
   and any native conformer fallback are recorded with the matrix.
5. Model choice and extraction policy are fixed before inspecting downstream
   test performance. Failed or inconvenient cells remain absent rather than
   being replaced by a related model.

Consequently, supervised task-trained systems such as the standard Chemprop
D-MPNN and ChemXTree are not frozen-representation comparators. They may be
reported later in a separately labelled end-to-end track, with their own
nested model-selection protocol, but their scores must not enter the frozen
embedding ranking or its multiple-testing family. The registry's
"Supervised + ContextPred" checkpoint is also excluded because its supervised
pretraining task family overlaps the downstream MoleculeNet endpoints.

The graph-encoder expansion is pre-specified as Uni-Mol v1, MolCLR GIN, and
GROVER Base/Large. Uni-Mol uses the pinned official molecular checkpoint and a
fixed mean atom readout. MolCLR uses the 512-dimensional encoder feature before
its contrastive projection head; its ClinTox cell is N/A because the official
featuriser cannot encode all real ClinTox structures, including dative bonds.
GROVER uses the official `both` fingerprint, concatenating its atom- and
bond-view mean readouts. Graphormer is deferred until its legacy Fairseq stack
and checkpoint can be reproduced without an implementation substitution.

---

## 1. Core Architecture & Methodology

### Phase A: Pre-Computed Embedding Tensors (One-Time Cost)
* Model authors or BioLatent maintainers run inference **once** per model over standardized dataset splits.
* The output is a frozen matrix of representation vectors ($N \times d$, e.g., $2050 \times 768$ for BBBP).
* Embeddings are hosted on open-access storage (e.g., Hugging Face Datasets or Zenodo).

### Phase B: Standardized Downstream Probing
* Downstream evaluation uses a standardised L2 linear probe with one fixed regularisation grid and training-only cross-validation. A one-hidden-layer MLP is diagnostic and never ranked.
* **Reduction of Downstream Tuning Bias**: Representations within a task use the same probe family, grid, metric and seed on identical object splits.
* Evaluation is CPU-only after embeddings are cached. Runtime depends on sample count, dimension and cache state and is recorded as operational context rather than a scientific score.

---

## 2. Curated Multi-Modal Task Suite (9 Tasks)

To ensure generalizability without benchmark bloat, the proposed suite spans 9 representative tasks across 3 modalities:

Sample counts below reflect the **actual downloaded datasets** (see §7, Dataset Provenance), not paper-reported figures.

### A. Small Molecule Modality (~11,000 compounds total)
1. **BBBP** (Classification, 2,039 compounds) — *Membrane permeability / Blood-brain barrier*
2. **ClinTox** (Classification, 1,480 compounds) — *Clinical toxicity & FDA approval*
3. **BACE** (Classification, 1,513 compounds) — *Target binding (Binding affinity)*
4. **ESOL** (Regression, 1,128 compounds) — *Aqueous solubility*
5. **Lipophilicity** (Regression, 4,200 compounds) — *Octanol-water partition coefficient*
6. **CYP3A4 Substrate** (Classification, 667 unique compounds) — *TDC `CYP3A4_Substrate_CarbonMangels`, canonicalised and deduplicated before scaffold splitting at seed 42. TDC `CYP3A4_Veith` measures inhibition and is not interchangeable.*

### B. Protein Modality (~82,300 sequences total)
7. **DeepLoc 2.0** (Multi-label classification, 28,303 proteins) — *Ten localisation labels; published homology partitions retained with a fixed train/validation/test fold assignment*
8. **Fluorescence** (Regression, 54,025 proteins; 21,446 train) — *GFP fitness landscape (TAPE), log-fluorescence*

> **CB513 was dropped** per Design Decision D2. It was replaced with a **whole-protein regression** task (Fluorescence) so the protein modality mirrors the molecule side's classification + regression shape and preserves the per-object "one vector → one probe" harness. This also avoids enshrining a dataset ProtTrans itself calls "redundant and outdated."

### C. Genomic Modality (~31,400 sequences total)
9. **Human Promoters** (Classification, 31,443 sequences, 300 bp) — *Regulatory sequence detection; Nucleotide Transformer `promoter_all`, balanced*

---

## 3. Compute Feasibility & Math

| Modality / Task Set | Sample Count | Tensor Size ($d=768$ to $1024$) | CPU Evaluation Time |
| :--- | :--- | :--- | :--- |
| **6 Molecular Tasks** | ~11,000 compounds | ~34 MB | ~7 seconds |
| **DeepLoc 2.0 (Protein)** | 28,303 proteins | model-dependent | CPU-only after embedding |
| **Fluorescence (Protein)** | 54,025 proteins | ~166 MB | ~9 seconds |
| **Promoters (Genomics)** | 31,443 sequences | ~96 MB | ~12 seconds |
| **TOTAL SUITE** | **~124,800 vectors** | **model-dependent** | **no universal timing claim** |

> Counts are the actual downloaded datasets. All are per-object (one vector per molecule/protein/sequence), so a single probing harness covers every task — no per-residue special case.

Embedding generation is paid once per model-task cell and can require substantial accelerator time. Hosted storage and CI may be covered by free service allowances, but that is an operational funding detail, not zero resource use.

---

## 4. Key Metric Innovations

1. **Linear Probe Score** (ranked): ROC-AUC (binary), macro ROC-AUC (multi-label), or Spearman ρ (regression), from a frozen L2-regularised linear probe. It measures linear decodability under the stated pooling and truncation protocol.
2. **Linear-to-MLP gap** (diagnostic): the difference between a fixed one-hidden-layer MLP and the linear probe.
3. **Validation-selected paired inference**: cluster-bootstrap difference intervals, paired-randomisation p-values and study-wide Holm correction.
4. **Pretraining input-exposure proxies**: exact identity, near-duplicate and scaffold overlap reported separately for molecules; Swiss-Prot homology for proteins. These are not labelled as contamination or label leakage.
5. **Embedding provenance**: checkpoint revision, input and matrix hashes, special-token handling, truncation and software versions.

> *Dropped:* "RMSE per embedding dimension". RMSE is not comparable across tasks with different target scales, so dividing it by a dimension count produces a quantity with no meaning. Dimension is reported alongside the score instead.

---

## 5. Design Decisions

The three open questions below have been resolved. Each records the decision, the reasoning, and the trade-off accepted, so the choices can be defended in review rather than re-litigated.

### D1 — Probe selection: linear-ranked, MLP as diagnostic

**Decision:** The **ranked metric is a strict L2-regularized linear/logistic probe**. A **fixed one-hidden-layer MLP is reported as a secondary diagnostic but is not ranked**.

- **Why linear ranks.** A linear probe has almost no capacity of its own, so whatever it decodes was already present in the embedding. This is the property that makes the fairness claim defensible: rank on the MLP and the metric starts measuring the MLP's capacity, not the representation.
- **Why keep the MLP.** The *gap* between linear and MLP performance is itself informative — it distinguishes representations that encode information linearly (cheap to use downstream) from those that need a non-linear head. Two models with equal linear scores but different MLP scores are genuinely different.
- **Guardrail.** The MLP is pinned to one 256-unit ReLU hidden layer, alpha 10^-4, batch size 256, learning rate 10^-3, early stopping and seed 42. Any per-model tuning is prohibited.
- **Policy.** Ranking metric = L2-regularized linear/logistic probe, with C or alpha selected from one fixed grid by three-fold training-only CV and a disclosed 6,000-row search cap. Secondary diagnostic = the fixed MLP above, reported but not ranked.
- **Trade-off accepted.** Two columns is more surface area to explain, but compute is negligible (MLP on frozen features is still seconds) and it preempts the "linear probing is too weak to be fair" objection. Metric #1 is renamed from "Pure Representation Score" to **"Linear Probe Score"** — the earlier name overclaimed, since linear probing measures *linear decodability under this probe*, not abstract representation quality.

### D2 — Task coverage: rebalance the 9 tasks, do not add PDBBind

**Decision:** **No 3D protein–ligand complex task in v1.** Keep the suite at 9 tasks but **rebalance** rather than grow it.

- **Why not PDBBind.** A complex-affinity task needs a joint pocket+ligand representation. Most registry models do not produce one — a 2D molecular encoder and a sequence protein LM have no native way to embed a complex. Any ad-hoc fusion (e.g. concatenating a ligand vector and a protein vector) becomes an uncontrolled variable that dwarfs the representation being measured, and the column would be N/A for most models — reintroducing the sparse-grid problem the audit removed.
- **The real imbalance is internal:** 6 molecule / 2 protein / 1 genomic, with 5 of 6 molecule tasks being classification. That skew invites the critique that the conclusions are really about molecular classification.
- **Rebalancing action.** **Drop CB513** (ProtTrans itself calls it "redundant and outdated"; it should not be enshrined in a best-practice benchmark) and either (a) replace it with a NetSurfP-2.0 / CASP-derived held-out secondary-structure set, or (b) drop per-residue probing from v1 entirely and add a **whole-protein regression** task (e.g. FLIP stability or fluorescence) so the protein side mirrors the molecule side's classification+regression shape. Option (b) also preserves the clean "one vector per object → one fixed probe" uniformity (see D-note below).
- **Trade-off accepted.** The suite loses a "covers 3D structure" breadth claim. This is the correct trade — breadth that cannot be evaluated fairly is a liability, not a feature. PDBBind-style complex tasks are deferred to an explicit **v2 / Future Work** scope so the omission reads as deliberate.

*D-note (probing uniformity):* per-residue CB513 is a different harness from the per-object tasks — different data shape and a protein-level (not scaffold) split. If a per-residue task is retained, it must be described as a separate harness rather than folded into the "same classifier, same seed, same everything" uniformity claim.

### D3 — Pretraining input exposure: computed, first-class context

**Decision:** BioLatent reports **input-exposure proxies**, not confirmed contamination or label leakage.

- **Why the terminology matters.** Self-supervised pretraining can contain a benchmark input without containing its downstream label. Familiarity may affect an embedding, but it does not prove memorised labels or an unearned score.
- **Audit pipeline (computed by us):**
  1. **Separate measures.** For molecules report exact canonical identity, ECFP4 Tanimoto ≥0.9 and Murcko-scaffold identity separately. For proteins report MMseqs2 homology at a stated identity and coverage threshold.
  2. **Structured self-declaration (auditable, not trusted).** Each submission names its pretraining corpora from a **controlled list**; these map onto the precomputed overlap tables. The self-report is used to *select which overlap table applies*, not taken on faith.
  3. **Flag, don't silently exclude.** Display the proxy beside each score and retain masks for sensitivity subsets.
  4. **Bound the claim.** Random ZINC/PubChem samples are not exact checkpoint subsets, and Swiss-Prot homology is not exact UniRef50 membership.
- **Trade-off accepted.** This audit adds context and reproducibility, but it cannot infer whether familiarity helped any prediction.

---

## 6. Build Items Carrying Real Cost

1. **CB513 replacement (D2).** ✅ **Done** — replaced with the whole-protein **Fluorescence** regression task (TAPE GFP landscape). Uses the same per-object probing harness as every other task; no separate per-residue code path.
2. **Input-exposure pipeline (D3).** ✅ **Built and run** — `benchmark/leakage.py` and `benchmark/run_leakage.py`. Molecular proxy dimensions are separated, Swiss-Prot is searched in full, and human-reference input exposure is stated structurally without implying label exposure.

> **The study is executable end to end.** `STUDY.md` is a local audit report; the public website and manuscript read the generated artefacts in `results/`. The earlier fabricated Gaussian-projection runner has been deleted and no failed or missing cell is back-filled.

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
| CYP3A4 Substrate | molecule | classification | 667 | TDC `CYP3A4_Substrate_CarbonMangels` |
| DeepLoc 2.0 | protein | multi-label | 28,303 | Published SwissProt localisation data and homology partitions |
| Fluorescence | protein | regression | 54,025 (21,446 train) | HF `proteinglm/fluorescence_prediction` (TAPE GFP) |
| Promoters | genomics | classification | 31,443 | HF `InstaDeepAI/nucleotide_transformer_downstream_tasks_revised`, task `promoter_all` |

**Two corrections applied during this pass:**
- **"FLIP" → "Fluorescence"**: the file named `FLIP.csv` actually contained the TAPE GFP fluorescence landscape (Strategy 1 of the downloader succeeded, so the FLIP fallbacks never ran). Renamed to reflect true provenance rather than mislabel it as FLIP (stability/Meltome).
- **Promoters re-download**: the previous file held only 106 sequences — the tiny UCI *E. coli* fallback, because the NT config name `promoter_all` no longer exists (the dataset restructured to a single `default` config with a `task` column). Fixed to filter `task == "promoter_all"`, yielding 31,443 balanced 300 bp human sequences.
