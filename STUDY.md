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
| Significance | `paired_test.py` | Paired bootstrap of each model against the task leader |
| Runner | `run_study.py` | Orchestrates, resumable, never back-fills a failure |

Environment is pinned in `benchmark/requirements.txt`; MoLFormer-XL's separate
interpreter is built by `benchmark/setup_molformer_env.sh` (see §6).

---

## 2. Protocol

**Embeddings.** Every transformer is mean-pooled over its non-padding tokens.
Pooling is pinned rather than chosen per model because CLS-versus-mean pooling
alone can move a score by several points; leaving it free would let that choice
masquerade as a difference between representations. Truncation is fixed per
modality (proteins 512, genomics 512, molecules 256 tokens) and recorded in
every cached sidecar JSON alongside checkpoint, dimension, pooling and a
content hash.

> Protein truncation at 512 is a real constraint on the DeepLoc results, not a
> neutral setting. ESM-2 accepts 1022 residues, and **38.6% of DeepLoc
> sequences are longer than 512** (median 426, maximum 2000), so for well over a
> third of that task every transformer sees a truncated protein and any
> localisation signal past residue 512 is invisible to it. The limit was imposed
> by 4.3 GB of VRAM and applies identically to all models, so the comparison
> between them is fair — but absolute DeepLoc numbers would likely move if it
> were lifted, and the 3-mer baseline, computed over the full sequence, is not
> subject to it at all. Fluorescence is unaffected: every sequence is 237
> residues.

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
| CYP3A4 Substrate | Scaffold, seed 42 | TDC `CYP3A4_Substrate_CarbonMangels` |
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

| Model | BBBP | ClinTox | BACE | ESOL | Lipo | CYP3A4 Substrate |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| ECFP4 (1024d) | 0.8826 | 0.8109 | 0.8601 | 0.5924 | 0.5883 | 0.6946 |
| RDKit2D (210d) | **0.9176** | 0.8003 | 0.8170 | **0.9185** | 0.6409 | 0.6946 |
| ChemBERTa-77M (384d) | 0.8927 | 0.7837 | 0.8402 | 0.8398 | 0.6376 | **0.7614** |
| ChemBERTa-ZINC (768d) | 0.9048 | 0.8597 | 0.8571 | 0.7930 | 0.5100 | 0.6337 |
| MoLFormer-XL (768d) | 0.9013 | **0.8968** | **0.8635** | 0.9063 | **0.6410** | 0.6429 |

Metrics: ROC-AUC for BBBP/ClinTox/BACE/CYP3A4 Substrate, Spearman ρ for ESOL/Lipophilicity.

### Which of these differences are real

Every model is compared against its task's leader by **paired bootstrap**
(`benchmark/paired_test.py`, 1,000 resamples). Both models are scored on the
same test molecules, so the test set is resampled once per replicate and the
statistic is the *difference*: shared difficulty cancels and what remains is
genuine disagreement between the two models on the same items. Because each
task runs one test per non-leading model, p-values are **Holm-corrected within
the task**.

| Task | Test n | Leader | Reliably below the leader | Tied with the leader |
| :--- | ---: | :--- | :--- | :--- |
| BBBP | 205 | RDKit2D 0.9176 | — | all 4 |
| ClinTox | 148 | MoLFormer-XL 0.8968 | — | all 4 |
| BACE | 152 | MoLFormer-XL 0.8635 | — | all 4 |
| ESOL | 114 | RDKit2D 0.9185 | ECFP4, ChemBERTa-ZINC, ChemBERTa-77M | MoLFormer-XL |
| Lipophilicity | 420 | MoLFormer-XL 0.6410 | ChemBERTa-ZINC | RDKit2D, ChemBERTa-77M, ECFP4 |
| CYP3A4 Substrate | 67 | ChemBERTa-77M 0.7614 | — | all 4 |

Per-comparison deltas, intervals and Holm-adjusted p-values are in
`results/paired_comparisons.json`.

Four of twenty-four comparisons survive. **No task separates its leader from the
whole field** — every task's top is a statistical tie of two or more
representations — but on two tasks the *bottom* of the table is real.

Counting how often each representation sits in the statistically tied top group
is the most that these six tasks support, and it is deliberately not a ranking:

| Representation | In the top group on |
| :--- | ---: |
| RDKit2D (210d) | 6 of 6 |
| MoLFormer-XL (768d) | 6 of 6 |
| ECFP4 (1024d) | 5 of 6 |
| ChemBERTa-77M (384d) | 5 of 6 |
| ChemBERTa-ZINC (768d) | 4 of 6 |

> **A note on the test itself, because an earlier version of this document got
> it wrong.** The first analysis compared each model's independent 95% interval
> against the leader's and called any overlap a tie. That is a real test but a
> badly conservative one, since it discards the fact that both models saw the
> same test items; it found only 2 separations. The paired test finds 10 before
> correction and 4 after. The conclusion below is similar to the one that wrong
> test produced, but it is now reached by a test that could have contradicted it.

What holds up:

- **No representation is demonstrably best on any molecular task.** Six tasks,
  five representations, and not one leader is separated from its runner-up.
- **ECFP4 is genuinely poor for solubility regression** (ESOL ρ = 0.592 against
  RDKit2D's 0.918, Δ = 0.326, Holm p = 0.004). A binary fingerprint is a poor
  substrate for a continuous physicochemical target — this is the largest
  effect anywhere in the molecular suite.
- **ChemBERTa-ZINC is the weakest entry.** It falls reliably below the leader
  on two of six tasks. ChemBERTa-77M is below the leader only on ESOL and is
  the numerical leader on CYP3A4 Substrate, although that lead is unresolved.
  Small SMILES BERTs are therefore not interchangeable, even with each other.
- **Pretraining is not distinguishable from descriptors.** MoLFormer-XL
  (~1.1B molecules) and a 210-dimensional RDKit descriptor vector are in the
  tied top group on all six tasks and are never separated from each other in
  either direction.

Where separations survive, the effect is large enough to clear a limited test
set: ESOL reaches Δ = 0.33 and the one Lipophilicity separation reaches 0.13.
BBBP, ClinTox and BACE have smaller gaps on 148–205 test molecules. CYP3A4
Substrate is smaller still: 67 test compounds give its leader an interval 0.24
wide, so even an apparent 0.128 ROC-AUC gap does not survive correction. At
that resolution the differences these benchmarks appear to show — and that the
wider literature routinely reports on these same task names — are smaller than
the measurement.

> **This is the fifth time these results changed a conclusion, and the pattern
> is the finding.** With only two small SMILES BERTs standing in for pretrained
> models, the data said "classical descriptors win five of six". Adding
> MoLFormer-XL turned that into "two wins each, two ties". Adding confidence
> intervals turned *that* into "almost nothing is distinguishable". Replacing
> the interval-overlap test with the correct paired one brought six separations
> back. Finally, replacing the mismatched CYP3A4 inhibition task with the
> audited substrate task reduced that to four — still none at the top of a
> table. Each intermediate claim was a
> faithful reading of the numbers then in hand, and each was wrong. A
> single-number leaderboard over small test sets will produce a ranking whatever
> the data does, and it will look convincing.

This connects to Sultan et al. (*J. Cheminform.* 2026,
10.1186/s13321-026-01252-z). Their conclusion that descriptor baselines remain
competitive is consistent with what is found here — RDKit2D is never beaten by
a pretrained model on any of these six tasks. But the stronger reading is that
**these benchmarks lack the resolution to support either claim**, theirs or its
opposite.

**The linear-to-MLP gap is small and usually negative** (range −0.157 to +0.081).
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

**Unlike the molecular tasks, these separations are real.** DeepLoc's test set
holds 2,782 proteins and Fluorescence's 27,217. Under the same paired bootstrap
and the same Holm correction that erased almost everything in §4, **every single
comparison on both protein tasks survives** — ten of ten, against four of
twenty-four on the molecular side.

| Task | Leader | Reliably below the leader (Holm-corrected) |
| :--- | :--- | :--- |
| DeepLoc | ESM-2 650M 0.7473 | ESM-2 150M, ProtBERT, ESM-2 35M, ESM-2 8M, 3-mer — **all 5** |
| Fluorescence | 3-mer 0.6755 | ProtBERT, ESM-2 650M/35M/150M/8M — **all 5** |

Even the narrowest gaps resolve: ESM-2 150M sits 0.0165 below ESM-2 650M on
DeepLoc (p = 0.018), and ProtBERT 0.0140 below the 3-mer baseline on
Fluorescence (p = 0.005).

Test-set size, not modality, is what decides whether a benchmark can rank
anything. ClinTox cannot establish a **0.113** ROC-AUC gap on 148 molecules;
Fluorescence establishes a **0.014** Spearman gap — eight times smaller — on
27,217 sequences.

The two protein tasks point in **opposite directions**, and the reason is
informative rather than noise.

**On DeepLoc, pretrained representations win decisively.** ESM-2 650M is
separated from all five other entries, and the 3-mer baseline trails it by 21.9
points while using 6× more dimensions. Even the smallest ESM-2 (8M, 320
dimensions) scores 13.5 points above 3-mer frequency at 25× fewer dimensions —
a gap larger than several that were tested and confirmed, though that specific
pair was not itself tested (limitation 10).

ProtBERT (0.7052) and ESM-2 35M (0.7045) differ by 0.0007 and sit 0.0421 and
0.0428 below the leader respectively — the same distance to within a
thousandth. An earlier version of this document said ProtBERT "lands between
ESM-2 35M and 150M"; that was a ranking read off a gap far inside the noise,
and it is withdrawn. What can be said is that ProtBERT, at 1024 dimensions and
more parameters than either, is not distinguishable from ESM-2 35M.

**Here scale does help, at every step, with diminishing returns.** Each
consecutive ESM-2 step tested against the one below it:

| Step | Δ accuracy | 95% CI | Holm p | |
| :--- | ---: | :--- | ---: | :--- |
| 8M → 35M | +0.0406 | [+0.026, +0.055] | 0.003 | improves |
| 35M → 150M | +0.0262 | [+0.013, +0.039] | 0.003 | improves |
| 150M → 650M | +0.0165 | [+0.003, +0.031] | 0.018 | improves |

Every step is a reliable gain and each buys less than the one before — 4.1, then
2.6, then 1.7 points, the last for 4.3× the parameters. This is the one place in
the suite where a scale ladder behaves the way the scaling literature would
predict, and it is now tested rather than asserted.

**On Fluorescence, the 3-mer baseline beats every protein language model** —
reliably, all five of them. It leads ProtBERT by 1.4 points and ESM-2 650M by
6.2, and both gaps clear Holm correction.

Here the scale ladder does **not** simply rise. Testing each consecutive ESM-2
step against the one below it (a pre-specified family, Holm-corrected within it):

| Step | Δ Spearman ρ | 95% CI | Holm p | |
| :--- | ---: | :--- | ---: | :--- |
| 8M → 35M | +0.0200 | [+0.014, +0.026] | 0.003 | improves |
| 35M → 150M | **−0.0089** | [−0.015, −0.003] | 0.008 | **reliably worse** |
| 150M → 650M | +0.0303 | [+0.024, +0.036] | 0.003 | improves |

The middle step is not noise around a flat trend: the interval lies entirely
below zero, so on this task a 4.3× larger model is **reliably worse** than the
one it replaces. Scale is not monotonic here, and a table of six scores read
top-to-bottom would not reveal that.

The same four checkpoints, the same probe and the same test therefore give
**opposite verdicts on whether scale helps**, depending only on which task they
are pointed at: three reliable gains on DeepLoc, a reliable loss in the middle
of the ladder on Fluorescence. "Does a bigger protein language model produce a
better frozen embedding?" has no task-independent answer here.

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

**All three are within 0.008 of each other and none is separated from the
leader** (paired bootstrap, Holm-corrected, n = 1,571). Nucleotide Transformer
sits 0.0018 below HyenaDNA (p = 0.57) and the 5-mer baseline 0.0077 below
(raw p = 0.030, Holm p = 0.060 — the one comparison in the suite that changes
verdict under correction, and it lands on the wrong side). A 500M-parameter
genomic foundation model is not distinguishable from counting 5-mers on this
task, and neither is distinguishable from a 128-dimensional HyenaDNA.

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

Fraction of each **test split** found in a pretraining corpus. Molecules: Murcko
scaffold identity or ECFP4 Tanimoto ≥ 0.9 against a random 150,000-molecule
sample. Proteins: MMseqs2 alignment at ≥50% identity and ≥50% coverage against
**all** of Swiss-Prot (575,503 sequences).

| Task | ZINC | PubChem | Swiss-Prot |
| :--- | ---: | ---: | ---: |
| ESOL | 46.5% | **82.5%** | — |
| BBBP | 29.8% | 46.3% | — |
| Lipophilicity | 22.6% | 42.4% | — |
| ClinTox | 29.7% | 38.5% | — |
| CYP3A4 Substrate | 43.3% | 70.1% | — |
| BACE | 1.3% | **0.7%** | — |
| DeepLoc | — | — | **99.5%** |
| Fluorescence | — | — | **100.0%** |

Every molecular figure is a **lower bound**: the PubChem sample is 150,000 of
124,466,629 rows, roughly one molecule in 830. Sampling can only miss overlap,
never invent it.

**The molecular picture.** PubChem overlap exceeds ZINC overlap on five of six
tasks, which is what one would expect given that PubChem is the union source for
public medicinal chemistry and the declared corpus behind ChemBERTa and one of
MoLFormer-XL's two sources. ESOL is the extreme: **82.5% of its test molecules
have a near-duplicate or shared scaffold in one-tenth of one percent of
PubChem.** ESOL is also where RDKit2D posts its highest score in the suite
(ρ = 0.919). A solubility benchmark of 114 small, common molecules is close to a
lookup task.

**BACE is the exception, and it is the informative one.** At 1.3% and 0.7% it is
effectively uncontaminated — a focused inhibitor series outside generic drug-like
space. It is also the task with the tightest spread between representations
(MoLFormer-XL 0.8635, ECFP4 0.8601, ChemBERTa-ZINC 0.8571). The suite's cleanest
task is the one where the models are hardest to tell apart, which is the
relationship one would predict if part of the separation seen elsewhere is
memorisation rather than representation quality.

**The protein figures replace an argument with a measurement.** An earlier
version of this document asserted that DeepLoc and Fluorescence were contaminated
"by construction" because UniRef50 clusters essentially all of UniProt. That
claim is now measured: **99.5% of DeepLoc test proteins and 100.0% of
Fluorescence test proteins** align at ≥50% identity to a Swiss-Prot entry. Since
Swiss-Prot is the reviewed subset of the UniProt that UniRef50 clusters — and
every ESM-2 variant and ProtBERT declares UniRef50 — these are themselves lower
bounds on pretraining coverage.

Swiss-Prot was chosen over a random UniRef50 sample deliberately. Sampling
UniRef50 would report a near-zero hit rate against a few thousand test proteins
while true coverage is near-total: technically correct, and completely
misleading. Swiss-Prot is the corpus DeepLoc is actually built from, so the
overlap is real and tight.

**Promoters** remains a structural claim rather than a measurement: the sequences
are excerpts of the same human reference assembly the Nucleotide Transformer and
HyenaDNA were pretrained on, so coverage is total by definition and there is no
independent corpus to search against.

### What this means for the leaderboard

The protein and genomic tasks cannot be read as measuring generalisation to
unseen sequences — at 99.5% and 100% coverage, they measure how much of a
memorised corpus a model retains and how linearly that content is exposed. The
ESM-2 scale ladder on DeepLoc is best read that way: a larger model recovering
more of what it has already seen, reliably, at every step.

But coverage does not explain the ladders on its own. DeepLoc and Fluorescence
are contaminated at 99.5% and 100% respectively — effectively equally — and the
same four checkpoints climb monotonically on the first while reversing in the
middle of the second. Leakage sets a ceiling on what a score can be claimed to
demonstrate; it does not determine which model reaches it. The readout does, and
here that readout is the mean pooling of decision D1.

That is not a reason to discard the tasks, but it is a reason to stop presenting
a single number per model as evidence of generalisation. The suite reports the
leakage fraction beside every score for exactly this reason.

---

## 6. Model roster

Fourteen entries were specified and all fourteen ran, producing 45 filled
(model, task) cells.

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

1. **Molecular leakage is sampled, not exhaustive.** ZINC and PubChem were each
   sampled at 150,000 molecules — for PubChem that is one row in 830 — so every
   molecular figure is a lower bound. Swiss-Prot was searched in full.
   Promoters has no independent corpus to search and remains a structural claim.
2. **Balanced scaffold splits are easier** than DeepChem's deterministic
   splitter, so absolute values here sit above commonly cited figures for the
   same task names. Values are internally comparable, not externally.
3. **DeepLoc is a simplification.** The source is multi-label over ten
   compartments; the argmax compartment is used as a single-label 10-class
   target. This is not the original multi-label task.
4. **CYP3A4 is substrate prediction**, using the 670-compound TDC
   `CYP3A4_Substrate_CarbonMangels` dataset so the measured and literature
   surfaces refer to the same biological task. They remain numerically
   incomparable because the literature rows use different downstream heads
   and evaluation procedures. The measured scaffold split has only 67 test
   compounds, producing wide intervals and no corrected separation.
5. **Mean pooling is imposed on every model**, including those whose authors
   recommend a different readout. This is deliberate for comparability, but §4b
   shows it is not free: on Fluorescence it costs the protein language models
   the task outright, because averaging over 237 residues erases the point
   mutations that carry the label. Any per-residue or mutation-aware readout
   would change that row substantially.
6. **Intervals cover test-set uncertainty only.** The reported 95% intervals are
   percentile bootstraps over the test set (1,000 resamples), which is the
   relevant source of noise for comparing models on a fixed split. They do
   **not** cover variance from the split itself; re-drawing the scaffold split
   under different seeds would widen the molecular intervals further, making the
   molecular non-separation conclusion stronger rather than weaker.
7. **The leader is selected on the test set that then judges it.** Each task's
   comparisons are made against whichever model scored highest on that task, so
   every leader-versus-challenger gap carries a winner's curse and is biased
   upward. Holm correction controls multiplicity across the models compared;
   it does not touch this selection bias. The direction is what matters for
   reading the results: a reported separation may be optimistic, while a
   reported **tie is if anything conservative** — so "these two cannot be told
   apart" is the safer of the two conclusions this suite produces, and it is
   the one most of the molecular table supports.
8. **Bootstrap p-values bottom out at 0.001.** With 1,000 replicates no smaller
   value is resolvable, so `p = 0.001` in `results/paired_comparisons.json`
   means "at the resolution floor", not an exact figure.
9. **Proteins are truncated at 512 residues**, below ESM-2's 1022 limit, which
    affects 38.6% of DeepLoc sequences. The cap is uniform across models so
    their comparison is fair, but it depresses absolute DeepLoc scores for
    every transformer while leaving the full-sequence 3-mer baseline untouched.
10. **Only two families of comparison were tested.** Each model against its
    task's leader, and each consecutive step of the ESM-2 scale ladder. Other
    pairs — ProtBERT against ESM-2 150M, say — carry no test here, and a
    difference between two of them should not be read as established merely
    because their scores differ.
11. **Concurrent runners previously lost results.** Each runner held a snapshot
   of the results file taken at start-up, so the last writer erased cells
   computed by the other; six MoLFormer-XL results were destroyed this way and
   had to be recomputed. Saving now merges against the file on disk. Any results
   produced before this fix should be regenerated rather than trusted.
