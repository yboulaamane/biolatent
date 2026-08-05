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

Ranked metric, linear probe. Best score per task in bold.

| Model | BBBP | ClinTox | BACE | ESOL | Lipo | CYP3A4 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| ECFP4 (1024d) | 0.8826 | 0.8109 | 0.8601 | 0.5924 | 0.5883 | **0.8463** |
| RDKit2D (210d) | **0.9176** | 0.8003 | 0.8170 | **0.9185** | 0.6409 | 0.8333 |
| ChemBERTa-77M (384d) | 0.8927 | 0.7837 | 0.8402 | 0.8398 | 0.6376 | 0.8194 |
| ChemBERTa-ZINC (768d) | 0.9048 | 0.8597 | 0.8571 | 0.7930 | 0.5100 | 0.8160 |
| MoLFormer-XL (768d) | 0.9013 | **0.8968** | **0.8635** | 0.9063 | **0.6410** | 0.8462 |

Metrics: ROC-AUC for BBBP/ClinTox/BACE/CYP3A4, Spearman ρ for ESOL/Lipophilicity.

**Scale separates the pretrained models; the ChemBERTa-class models do not beat
descriptors, and MoLFormer-XL does.** The picture splits cleanly in two:

- **Descriptor baselines win where physicochemistry is the target.** RDKit2D
  takes BBBP (0.9176) and ESOL (0.9185) outright, and its ESOL margin over
  ECFP4 is enormous (0.918 vs 0.592) — a binary fingerprint is a poor substrate
  for a continuous solubility regression.
- **MoLFormer-XL wins ClinTox (0.8968) and BACE (0.8635)**, and ties the best
  classical score on Lipophilicity (0.6410 vs 0.6409) and CYP3A4 (0.8462 vs
  0.8463). Those last two differences, one ten-thousandth of a point, are ties
  in everything but sort order.

So across six tasks: two clear wins for classical descriptors, two for
MoLFormer-XL, and two ties. The two ChemBERTa variants, pretrained on far less
data, lead nothing.

> **This corrects an earlier reading of these results.** Before MoLFormer-XL was
> evaluated, the same table supported "classical descriptors win five of six
> tasks". That conclusion was an artefact of which models had been run: the only
> pretrained molecular models in the roster were two small SMILES BERTs. Adding
> the one large-scale molecular foundation model overturned it. The episode is
> the clearest argument in this study for auditing a benchmark's *roster* as
> carefully as its numbers — an absent model is not a neutral omission, it
> silently shapes the conclusion.

The relationship to Sultan et al. (*J. Cheminform.* 2026,
10.1186/s13321-026-01252-z) is therefore narrower than it first appeared. Their
finding that descriptor baselines remain strong is reproduced here — descriptors
are never far behind and win outright twice — but these results do not support a
blanket claim that pretrained molecular transformers underperform them.

**The linear-to-MLP gap is small and usually negative** (range −0.157 to +0.040).
Adding non-linear capacity on top of these frozen embeddings rarely helps, so
what the representations encode is largely linearly accessible.

---

## 4b. Results — protein tasks

| Model | Dim | DeepLoc (accuracy) | Fluorescence (Spearman ρ) |
| :--- | ---: | ---: | ---: |
| 3-mer frequency | 8000 | 0.5288 | **0.6755** |
| ESM-2 8M | 320 | 0.6639 | 0.5724 |
| ESM-2 35M | 480 | 0.7045 | 0.5924 |
| ESM-2 150M | 640 | 0.7308 | 0.5835 |
| ESM-2 650M | 1280 | **0.7473** | 0.6138 |
| ProtBERT | 1024 | 0.7052 | 0.6615 |

The two protein tasks point in **opposite directions**, and the reason is
informative rather than noise.

**On DeepLoc, pretrained representations win decisively and scale helps.** ESM-2
8M is 13.5 points above 3-mer frequency while using 25× fewer dimensions, and
the ladder is monotonic across all four ESM-2 sizes (0.664 → 0.705 → 0.731 →
0.747). Returns flatten sharply: 8M → 35M buys 4.1 points, 35M → 150M buys 2.6,
150M → 650M buys 1.7 for 4.3× the parameters. ProtBERT (0.7052) lands between
ESM-2 35M and 150M despite being larger than either.

**On Fluorescence, the 3-mer baseline beats every protein language model.** It
leads ProtBERT by 1.4 points and ESM-2 650M by 6.2. The scale ladder still rises
(0.572 → 0.584 → 0.614) but never reaches a plain k-mer count.

This is a pooling artefact, and it is *this study's* artefact. Fluorescence is a
mutational scan: all 54,025 sequences are 237-residue GFP variants differing at
a handful of positions. Mean-pooling a transformer over 237 residues averages
away exactly the one-to-fifteen substitutions that carry the entire label, while
3-mer frequencies register each substitution directly as a change in counts.

Design decision D1 pinned mean pooling for every model so that pooling could not
masquerade as a difference between representations. The cost of that choice is
visible here: on tasks whose signal is local, a fixed global pooling discards
it. The honest reading is not "protein language models are bad at fitness
prediction" — published work using per-residue readouts does far better — but
"a frozen mean-pooled embedding is the wrong probe for a mutational scan."

That distinction matters for how a leaderboard should be read. A single number
per (model, task) silently encodes a readout choice, and for one of these nine
tasks that choice dominates the result.

---

## 4c. Results — genomics

| Model | Dim | Promoters (ROC-AUC) |
| :--- | ---: | ---: |
| 5-mer frequency | 1024 | 0.9304 |
| Nucleotide Transformer 500M | 1280 | 0.9363 |
| HyenaDNA tiny | 128 | **0.9381** |

**All three are within 0.008 of each other.** A 500M-parameter genomic foundation
model buys 0.6 points over counting 5-mers, and is edged out by HyenaDNA-tiny
using ten times fewer dimensions than either.

Read alongside §5, this is the least reassuring result in the suite: the
promoter sequences are excerpts of the very assembly both pretrained models were
trained on, so even that 0.6-point margin is measured under total corpus
contamination. Whatever these models offer over k-mer counting on this task, it
is not visible through a frozen linear probe.

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

**Molecules** — ECFP4, RDKit2D, ChemBERTa-77M-MLM, ChemBERTa-ZINC-base,
MoLFormer-XL.
**Proteins** — 3-mer frequency, ESM-2 (8M / 35M / 150M / 650M), ProtBERT.
**Genomics** — 5-mer frequency, Nucleotide Transformer 500M, HyenaDNA-tiny.

MoLFormer-XL needs a newer `transformers` than the main environment's 4.50.3,
because its remote modelling code imports `transformers.masking_utils`. Since
embedding already runs in a subprocess per (model, dataset), that model declares
its own interpreter and runs in a second environment; the main environment, and
every result already computed in it, are untouched. A model that cannot be run
is reported as not evaluated — never substituted with another featuriser.

**This roster is a subset of the BioLatent registry, not the whole of it.**
`src/app/data/embeddings.ts` catalogues 38 entries; 14 are evaluated here. Most
of the remainder — AlphaFold 2, DiffDock, ProteinMPNN, RXNMapper — do not emit a
single per-object embedding vector for these tasks, so they are out of scope for
this harness rather than missing from it. The distinction belongs in any write-up:
the suite evaluates representative representations, it does not benchmark the
registry.

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
   recommend a different readout. This is deliberate for comparability, but §4b
   shows it is not free: on Fluorescence it costs the protein language models
   the task outright, because averaging over 237 residues erases the point
   mutations that carry the label. Any per-residue or mutation-aware readout
   would change that row substantially.
6. **No confidence intervals.** Scores are single-seed point estimates; the
   probe is deterministic but the split seed is not varied. Several margins
   reported here — MoLFormer-XL versus RDKit2D on Lipophilicity (0.0001), versus
   ECFP4 on CYP3A4 (0.0001), and all three genomic models (within 0.008) — are
   almost certainly inside the noise, and are reported as ties rather than
   rankings.
7. **Concurrent runners previously lost results.** Each runner held a snapshot
   of the results file taken at start-up, so the last writer erased cells
   computed by the other; six MoLFormer-XL results were destroyed this way and
   had to be recomputed. Saving now merges against the file on disk. Any results
   produced before this fix should be regenerated rather than trusted.
