# BioLatent release handoff

**Updated:** 2026-09-13
**Branch:** `wip/protocol-v4-regeneration`
**Scientific release status:** validated locally
**Public deployment status:** an older, invalidated build is still live

## Current state

The protocol-v4 regeneration is complete. The release gate reports:

```text
Validated 9 tasks and 45 cells.
```

The production Next.js 16.3.5 build also passes. The corrected manuscript was
generated at `paper/BioLatent_methods_revised.docx`; its ZIP package and document
structure were checked successfully (93 paragraphs, 9 populated tables, 1
section).

The project uses `next build --webpack` and `next dev --webpack`. This host's
glibc is older than the native SWC binary required by Next.js 16.3.5, so Next
loads its WebAssembly compiler; current Next.js does not support Turbopack with
that fallback. The documented Webpack path builds and serves successfully.

The live Vercel site must not yet be described as the validated release. On
2026-09-13, `https://biolatent.vercel.app` still served the older results,
including the invalid causal sentence “The difference is test-set size, not
modality” and the old DeepLoc test count of 2,782. The corrected local build uses
5,963 DeepLoc test proteins and conditional, non-causal wording.

## What was completed

- All nine task files were checked against fresh public upstream sources. See
  `DATA_PROVENANCE_AUDIT.md` for row-level transformations and exact CSV hashes.
- All 45 compatible embedding matrices pass protocol, input, checkpoint, shape,
  and full content-hash checks. The refreshed inventory is
  `handoff/embedding_cache_inventory.json` (`valid: 45`, `stale: 0`).
- Every benchmark cell was regenerated under probe protocol v4 and now stores
  the SHA-256 of the exact embedding matrix used.
- All nine prediction bundles were regenerated. The validator checks their test
  labels and resampling groups against the real datasets and recomputes their
  metrics before comparing them with both result surfaces.
- Paired inference uses validation-selected references, dependence-aware
  bootstrap intervals, paired randomisation, and a primary study-wide Holm
  correction.
- Exposure proxies, five-seed molecular split sensitivity, and empirical
  test-size resolution curves are complete.
- The stale numerical `STUDY.md` was replaced with the protocol-v4 snapshot.
- Registry benchmark rows now fail the site build unless both a direct source
  URL and a provenance note are present.
- Site lint, TypeScript compilation, static generation, and API route generation
  pass.
- Next.js and its lint configuration were upgraded from 16.2.10 to 16.3.5;
  `npm audit` reports zero known vulnerabilities.

## Result snapshot

The study has 36 validation-reference comparisons. After the primary
study-wide correction:

| Modality | Resolved | Total |
|---|---:|---:|
| Molecules | 3 | 24 |
| Proteins | 10 | 10 |
| Genomics | 0 | 2 |
| **All** | **13** | **36** |

These are resolution counts for this protocol, model roster, and task set—not
evidence that a modality is inherently easier. Numerical test bests remain
descriptive.

The ESM-2 ladder improves at all three scale steps on DeepLoc. Fluorescence
improves from 8M to 35M, regresses from 35M to 150M, and improves from 150M to
650M. All six pre-specified ladder steps survive their within-ladder Holm
correction, so the effect of scale is task-conditional.

## Authoritative artifacts

- `results/benchmark_results.json`
- `results/paired_comparisons.json`
- `results/exposure_report.json`
- `results/split_seed_sensitivity.json`
- `results/resolution_curves.json`
- `results/run_manifest.json`
- `results/predictions/*.npz`
- `DATA_PROVENANCE_AUDIT.md`
- `BENCHMARK_VERIFICATION.md`
- `STUDY.md`
- `paper/BioLatent_methods_revised.docx` (generated, intentionally ignored)

Do not edit result numbers by hand. The JSON is authoritative and the website
and manuscript compute their headline counts from it.

## Reproduction and release gate

Run in this order:

```bash
python benchmark/download_real_datasets.py
python benchmark/run_study.py --embeddings-only
python benchmark/run_study.py
python benchmark/paired_test.py
python benchmark/run_leakage.py --sample 200000
python benchmark/resolution_analysis.py
python benchmark/split_sensitivity.py
python benchmark/run_study.py --refresh-metadata
python benchmark/validate_release.py --full-hash
npm run lint
npm run build
python paper/generate_manuscript.py
```

The manifest command must remain last among result-producing analyses because it
hashes every public JSON and prediction bundle.

Main benchmark environment at validation: Python 3.11.15, PyTorch
2.8.0+cu128, Transformers 4.50.3, scikit-learn 1.8.0, SciPy 1.17.1,
RDKit 2023.09.6, and MMseqs2 18.8cc5c. Individual embedding sidecars retain the
actual software/device/precision context that produced each cached matrix.

## Publication steps not performed

No commit, push, branch merge, or Vercel deployment was made as part of this
validation. Publishing is an external state change and should happen only after
reviewing the diff. The safe release sequence is:

1. Review the working-tree diff, leaving the user-owned untracked `.claude/`
   directory untouched.
2. Commit the validated files on a release branch.
3. Merge or promote that commit to the branch used by Vercel.
4. Verify that the deployed page reports DeepLoc test `n = 5,963`, 45 measured
   cells, and 3/24 molecular, 10/10 protein, and 0/2 genomic comparisons.
5. Recheck `/api/representations` and the literature/measured separation.

## Remaining external QA

LibreOffice is not installed on this host, so the generated DOCX could not be
rendered to pages for visual inspection. Package integrity, section/table
structure, required content, and all result-derived counts pass. A final visual
review in Word or LibreOffice remains advisable before manuscript submission.

Raw datasets and embedding matrices remain local and gitignored. Public hosting
of those large artifacts (for example, a versioned archive with checksums) is a
separate distribution task; the repository can deterministically regenerate
them from pinned sources and checkpoints.
