# BioLatent — Remediation Handoff

**Written:** 2026-08-07 · **Branch:** `main` · **Last commit:** `67cafbf`

This file exists so the in-flight remediation can be picked up on another machine.
Read it top to bottom before running anything.

---

## 1. What is happening

A methodological audit found real defects in the benchmark *definitions* and in the
inference pipeline — not wording problems. Fixing them changes the numbers, so every
published result must be **regenerated**, not relabelled.

The code fixes are **done and uncommitted** in the working tree. The **regeneration is
roughly 20% complete**. Nothing here is publishable until section 5 is finished.

### Defects fixed (all already in the working tree)

| # | Defect | Fix | Invalidates |
|---|---|---|---|
| 1 | CYP3A4 rows duplicated / not canonicalised before the TDC split | canonicalize + dedupe → exactly 667 unique molecules | CYP3A4 cells |
| 2 | ClinTox collapsed to one endpoint | both official endpoints retained (multilabel) | ClinTox cells |
| 3 | DeepLoc used a *derived random* HF partition, not the paper's homology folds | original DeepLoc 2.0 SwissProt file + pre-specified published homology folds; all 10 labels | all DeepLoc cells |
| 4 | Molecular CIs treated related compounds as independent | cluster bootstrap over Murcko scaffold groups | all molecular CIs |
| 5 | Transformer pooling averaged over special tokens (`[CLS]`/`[SEP]`) | mean over attention-mask tokens with special tokens excluded | every transformer matrix |
| 6 | ProtBERT documented as UniRef50; it is **UniRef100**, and needs `U/Z/O/B → X` | corrected corpus attribution + preprocessing | ProtBERT cells + exposure report |
| 7 | CV scaled features on the full training partition before folding | `Pipeline(StandardScaler → model)` so each fold learns its own scaling | every probe score |
| 8 | Leader selected on the **test set** (winner's curse) | reference selected on **validation**; test-best reported separately | all paired inference |
| 9 | Empty Murcko scaffold string matched all acyclic molecules together | empty-scaffold chemotype excluded, covered by a smoke test | exposure audit |
| 10 | MoleculeNet inputs were canonicalised, collapsing distinct source rows (some with conflicting labels) | canonicalisation removed for MoleculeNet | molecular splits |

**Framing consequence:** input-familiarity is **not** label leakage. The audit is now
named `exposure_report.json` / `pretraining_input_exposure_proxy` and must never be
described as leakage. Test size is **one contributor** to resolution, not a causal
explanation on its own.

---

## 1a. How to move this

All work-in-progress is committed to the branch **`wip/protocol-v4-regeneration`**.
`main` is deliberately left at `67cafbf` — the half-regenerated results and the
currently-unbuildable site must not land on it.

```bash
git checkout wip/protocol-v4-regeneration      # on the cloud box, after cloning
```

Git carries the code, docs and result JSON. It does **not** carry `data/` (6.6 G,
gitignored). Copy that separately if you want to keep the 35 valid embedding matrices:

```bash
rsync -av --progress data/ <cloud>:<repo>/data/     # or just data/embeddings/
```

Without it, step 5.1 re-embeds all 45 cells instead of 10.

---

## 2. Read this before you move anything

- **`data/` is 6.6 GB and is gitignored.** It does *not* travel with `git clone`.
  - `data/embeddings` 4.1 G — **35 of 45 matrices are still valid**, worth copying.
  - `data/corpora` 2.6 G — PubChem `cid-smiles.gz`, `zinc_full.csv`, `sprot.fasta`.
    Re-downloadable via `benchmark/download_real_datasets.py`, but slow.
  - `data/benchmark_datasets` 40 M.
  - If you copy only one thing, copy `data/embeddings` — it is the expensive artefact.
- **The site cannot build right now.** `src/app/data/study.ts` imports
  `results/exposure_report.json` and `results/resolution_curves.json`; **neither
  exists yet**. `next build` will fail on an unresolved import until step 5.4/5.5 run.
- **Manuscripts stay local, never committed.** `BioLatent*.docx` and `paper.*` are
  gitignored, deliberately. `BioLatent.docx` and `BioLatent_methods.docx` are the
  originals and must not be overwritten — the generator only reads them as templates.
- Killing a running embedding job **is safe**. `np.save` is not atomic, but the sidecar
  JSON is written *after* the matrix, so an interrupted cell fails its cache guard on
  the next run and regenerates. A truncated `.npy` wastes disk, nothing more.

---

## 3. Current state

### Regeneration progress

`PROBE_PROTOCOL_VERSION = 4`, `EMBED_PROTOCOL_VERSION = 2`, `INFERENCE_PROTOCOL_VERSION = 4`.
Anything not at those versions is stale by definition.

| Task | Probe protocol | Status |
|---|---|---|
| BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4 | **v4** | **all 6 molecular tasks done, 30 cells** |
| DeepLoc | v2 | pending (needs ProtBERT re-embed first) |
| Fluorescence | none | pending (needs all 6 re-embeds first) |
| Promoters | none | pending (needs all 3 re-embeds first) |

Scores move substantially under v4 — BBBP ChemBERTa-77M went 0.893 → 0.9538,
ChemBERTa-ZINC 0.9048 → 0.9713. Expected: the final fit now uses all non-test labels
and scaling is learned inside each fold. **Do not treat old numbers as a baseline.**

### Embedding caches — 35 valid, 10 stale

Full detail with hashes: `handoff/embedding_cache_inventory.json`.

Stale, must be re-embedded (this is what the killed job was doing):

```
protbert__DeepLoc                  (also carried the wrong split: n=27783, should be 28303)
esm2_8m__Fluorescence   esm2_35m__Fluorescence
esm2_150m__Fluorescence esm2_650m__Fluorescence
kmer3_protein__Fluorescence        protbert__Fluorescence
hyenadna__Promoters     kmer5_dna__Promoters    nucleotide_transformer__Promoters
```

All 30 molecular matrices and the 5 non-ProtBERT DeepLoc matrices are current.

Regenerate the inventory any time with the snippet at the bottom of this file.

### Result artefacts

Present:
- `results/benchmark_results.json` — molecular tasks at v4, protein/genomics still stale.
- `results/run_manifest.json` — regenerated after the manifest bug was fixed. Its
  `public_artifacts` map currently lists only the two files that exist, so it **must be
  rewritten at step 5.7** once the rest are produced.
- `results/paired_comparisons.json` — **stale, v2-era. Do not read it.** It was produced
  under test-set leader selection and independent-item bootstrap, both now replaced.

**Missing, and all required by `benchmark/validate_release.py`:**
`exposure_report.json`, `resolution_curves.json`, `split_seed_sensitivity.json`,
`results/predictions/*.npz`.

### Jobs running at snapshot time

Both were **still alive** when this was written and will not survive the move. Neither
had finished. Nothing needs rescuing — both are resumable, so just relaunch per section 5.
The probe pass merges per-task into `benchmark_results.json`, so completed tasks persist;
the embedding job hash-checks and skips finished cells.

- `run_study.py --embeddings-only DeepLoc Promoters Fluorescence` → log `run_embed_v4.log`.
  Reached ProtBERT/DeepLoc ~10000/28303 — i.e. still on the *first* of 10 stale cells.
- `run_study.py BBBP ClinTox BACE ESOL Lipophilicity CYP3A4` → log `run_probe_mol_v4.log`.
  Completed BBBP, ClinTox, BACE, ESOL; was on Lipophilicity, with CYP3A4 to follow.

Check what actually landed before relaunching — the snapshot above may lag:

```bash
python3 -c "
import json
for t,v in json.load(open('results/benchmark_results.json')).items():
    print('%-14s protocol_v%s cells=%d'%(t,v.get('protocol_version'),len(v.get('models',{}))))"
```

Known benign noise: ESOL/Lipophilicity ridge fits emit
`LinAlgWarning: ill-conditioned matrix (rcond ~1e-7)`. Expected for high-dimensional
fingerprints under weak regularisation; not a failure.

---

## 4. Environment

```
conda env : cdd          python 3.11.15
torch 2.13.0+cu130   transformers 4.50.3   scikit-learn 1.8.0
numpy 1.26.4         rdkit 2023.09.6       MMseqs2 18.8cc5c (on PATH)
```

- Pins: `benchmark/requirements.txt`.
- **MoLFormer-XL needs a second interpreter** (`transformers==5.14.1`) because its remote
  code imports `transformers.masking_utils`. Build it with
  `bash benchmark/setup_molformer_env.sh`. Only needed if you re-embed MoLFormer —
  its 6 matrices are currently valid.
- Local GPU was a 4 GB RTX A1000, which is why protein embedding is the long pole.
  A larger card will change the runtime picture completely; molecular work is CPU-bound.
- `nproc` 20, 31 GB RAM. Probe jobs were thread-capped (`OMP_NUM_THREADS=8`) only to
  coexist with the GPU job; drop the cap if running alone.

---

## 5. Runbook — run in this order

Order is not cosmetic. Dependencies are called out; violating them produces artefacts
that look fine and are wrong.

```bash
# 5.1  Re-embed the 10 stale cells. Long pole; GPU-bound. Resumable — valid caches
#      are hash-checked and skipped in seconds.
python3 benchmark/run_study.py --embeddings-only DeepLoc Promoters Fluorescence

# 5.2  Probe pass, all 9 tasks, protocol v4. Molecular tasks can run before 5.1
#      finishes (their caches are valid); protein/genomics cannot.
python3 -u benchmark/run_study.py            # all tasks, or name them individually

# 5.3  Paired inference. MUST be run over the FULL suite in one invocation.
#      The single-task branch skips apply_familywise_corrections(), which is what
#      writes p_holm_global / significant_global — and the aliases p_holm /
#      significant that the website reads. A per-task run silently yields a site
#      reporting zero separations.
python3 -u benchmark/paired_test.py

# 5.4  Exposure audit  -> results/exposure_report.json   (needs data/corpora + MMseqs2)
python3 -u benchmark/run_leakage.py

# 5.5  Resolution curves -> results/resolution_curves.json
#      DEPENDS ON 5.3: reads results/predictions/*.npz, written by paired_test.py.
python3 -u benchmark/resolution_analysis.py

# 5.6  Split-seed sensitivity -> results/split_seed_sensitivity.json (molecular only)
python3 -u benchmark/split_sensitivity.py

# 5.7  Manifest LAST. write_manifest() hashes every public artefact, so running it
#      before 5.3-5.6 records hashes of files that no longer exist in that form.
#      (--refresh-metadata was added for exactly this; run() also writes a manifest,
#      which is why 5.2 alone is not sufficient.)
python3 benchmark/run_study.py --refresh-metadata

# 5.8  Gate. Fails loudly on any missing artefact, version mismatch, split overlap,
#      sidecar/hash disagreement, or manifest drift.
python3 benchmark/validate_release.py          # --full-hash to also verify matrices
```

Then, only once 5.8 passes:

```bash
npx next build                                  # will fail before 5.4/5.5 exist
python3 paper/generate_manuscript.py            # -> paper/BioLatent_methods_revised.docx
```

---

## 6. Non-obvious things already discovered — don't rediscover them

- **`import datasets` inside `benchmark/` resolves to `benchmark/datasets.py`, not
  HuggingFace.** Running `python3 benchmark/run_study.py` puts `benchmark/` first on
  `sys.path`. This crashed `write_manifest()` with
  `AttributeError: module 'datasets' has no attribute '__version__'` — *after* scores
  were saved, so it looked like a successful run that silently produced no manifest.
  Fixed by reading `importlib.metadata.version(...)` instead of module attributes.
  Do not reintroduce bare `import datasets` anywhere under `benchmark/`.
- **`.gitignore` narrowing un-ignored the manuscripts.** A working-tree change had
  replaced `BioLatent*.docx` with `/BioLatent_methods.docx`, which left both
  `BioLatent.docx` and the generated `paper/BioLatent_methods_revised.docx` tracked-able;
  `git add -A` would have committed them. Restored to the unanchored pattern. Verify with
  `git check-ignore -q <file>` after any change to that block.
- **`.gitignore` `data/` was unanchored** and silently matched `src/app/data/`, excluding
  application source from a commit and breaking the Vercel build. It is now `/data/`.
  Keep the anchor.
- **`paired_test.py` must run over the full suite** — see 5.3. This is the single easiest
  way to publish a wrong site.
- **The manifest must be written last** — see 5.7.
- **`pkill -f <pattern>` kills its own shell** here, because the wrapper's command line
  contains the pattern. Iterate explicit PIDs instead.
- Same trap in wait-loops: `until ! pgrep -f "foo.py"` never exits, it matches itself.
  Poll the output file's contents instead.
- `ps ... | head -1` grabs the wrapper bash, not the Python process. Iterate all PIDs.
- Per-task subprocess isolation plus `n_jobs=1` for protein/genomics is what stopped the
  earlier exit-137 OOM. RSS stayed ~500-700 MB. Keep it.
- The old `data/leakage/*__zinc_mask.npy` files use the previous naming scheme
  (`{task}__{corpus}__{measure}.npy` is current). They are harmless leftovers.

---

## 7. Standing constraints (from AGENTS.md — these override defaults)

- **Never mix measured study values with the literature registry.** Registry values were
  transcribed from papers under incompatible protocols. They live on a separate tab
  behind a warning banner.
- **No placeholder scores.** Registry entries must be real published values; report `N/A`
  for unevaluated model/task pairs. Never synthesise.
- **Headline counts are computed from JSON, never hardcoded** — in the site *and* in the
  manuscript generator.
- **CYP3A4 is the substrate benchmark** (`CYP3A4_Substrate_CarbonMangels`). Do not
  substitute the distinct `CYP3A4_Veith` inhibition task. Both surfaces use substrate.
- Next.js here has breaking changes vs training data — read `node_modules/next/dist/docs/`
  before touching site code.

---

## 8. Still outstanding after the rerun

- [ ] **`STUDY.md` hardcodes 47 numeric claims** from the v2 run — score tables,
      separation counts, ladder deltas, exposure fractions. Every one is invalidated.
      Rewrite from the regenerated JSON. `README.md` has 2 more.
- [ ] Manuscript references **[13]–[27] were added from memory and their DOIs are
      unverified.** A "NOTE TO AUTHOR" paragraph in the References section flags the
      exact range; delete it once checked.
- [ ] Manuscript placeholders: `[Institution]`, and the inherited
      `yassir.boulaamane@uab.cat` address.
- [ ] **No LibreOffice on the old box**, so the document workflow's render-and-inspect
      gate was never satisfied — visual QA of the DOCX remains an open external gate.
      Install `libreoffice` in the cloud env to close it.
- [ ] Three commits (`de6cd15`, `8c24654`, `fc0ea4c`) were unpushed as of `67cafbf`;
      push needs credentials (no `gh`, no credential helper on the old box).
- [ ] Zenodo / HuggingFace hosting for `data/` is still unsolved.
- [ ] No submission mechanism (GitHub Actions leaderboard) — deliberately deferred.

---

## Appendix — regenerate the cache inventory

```bash
python3 -c "
import json, os
from benchmark import embed
from benchmark.datasets import ALL_DATASETS
inv={'embed_protocol_version':embed.EMBED_PROTOCOL_VERSION,'cells':{}}
for task in ALL_DATASETS:
    for model in embed.MODEL_REGISTRY:
        p=embed.cache_path(model,task); m=p.replace('.npy','.json')
        if not (os.path.exists(p) and os.path.exists(m)): continue
        d=json.load(open(m))
        inv['cells'][f'{model}__{task}']={
            'valid': d.get('protocol_version')==embed.EMBED_PROTOCOL_VERSION,
            'protocol_version':d.get('protocol_version'),'pooling':d.get('pooling'),
            'n':d.get('n'),'dim':d.get('dim'),'input_sha256':d.get('input_sha256'),
            'matrix_sha256':d.get('sha256'),'bytes':os.path.getsize(p)}
v=sum(c['valid'] for c in inv['cells'].values())
inv['summary']={'valid':v,'stale_needs_reembed':len(inv['cells'])-v}
json.dump(inv,open('handoff/embedding_cache_inventory.json','w'),indent=2)
print(inv['summary'])
"
```
