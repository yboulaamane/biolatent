# BioLatent data and score provenance audit

**Audit date:** 2026-09-14
**Scope:** the nine-task measured benchmark and all literature-score rows in
`src/app/data/embeddings.ts`.

## Conclusion

The measured benchmark uses real, externally published datasets. No dataset
row, label, sequence, molecule, split, or reported numeric result is
fabricated or filled with synthetic placeholder data. Fresh upstream copies
were compared with the local benchmark files; the only transformations are the
documented column selection, invalid-row filtering, canonical identity
deduplication, split mapping, and within-split deduplication below. Neural
embeddings are, by design, actual outputs of the named public checkpoints on
those real inputs; benchmark scores are computed directly from probe
predictions and labels.

This establishes source provenance and rules out a locally synthetic fallback.
It cannot independently re-audit how each upstream research group originally
collected its assays or annotations; that remains the responsibility of the
cited dataset publishers.

## Dataset-by-dataset verification

| Task | Local rows | Upstream evidence and equality check | Local CSV SHA-256 |
|---|---:|---|---|
| BBBP | 2,039 usable | Fresh `BBBP.csv` from DeepChem MoleculeNet; selected SMILES and `p_np` labels match row-for-row after the 11 documented RDKit-invalid inputs are excluded at load time. | `caefe5d4f5ee781e1150b21a03ca3c17cc1613092f2a84716f339bca5787b3b9` |
| ClinTox | 1,480 usable | Fresh `clintox.csv.gz` from DeepChem MoleculeNet; SMILES and both official endpoints (`FDA_APPROVED`, `CT_TOX`) match row-for-row after four documented invalid inputs are excluded. | `5ec8263ab0979b0d3b2cd3cf2c135535b23671c4be8046a94edac16f47b3de87` |
| BACE | 1,513 | Fresh `bace.csv` from DeepChem MoleculeNet; molecule strings and binary `Class` labels match exactly. | `4666a966319b599fd04869c3406c9ee772d206fa97049c2494e9d2d93a5e4cb2` |
| ESOL | 1,128 | Fresh `delaney-processed.csv` from DeepChem MoleculeNet; SMILES and measured log-solubility targets match exactly. | `cb325f87455b79cc23f6a3ffa89587a15795d7c042afacca925dfcbd6d77e76e` |
| Lipophilicity | 4,200 | Fresh `Lipophilicity.csv` from DeepChem MoleculeNet; SMILES and experimental `exp` targets match exactly. | `03dc89d2bc667660da4cc6949e898361a24164f64fc54d97ba825f031ae5bc4a` |
| CYP3A4 Substrate | 667 | The TDC raw file is byte-identical to Harvard Dataverse file ID `4259581`. Canonicalisation produces 667 unique molecules with no label conflicts. Two canonical SMILES spellings that differ under the newer RDKit release have identical InChIKeys, so their chemical identity is unchanged. The task is `CYP3A4_Substrate_CarbonMangels`, not the distinct Veith inhibition dataset. | `1e8de92e605aeb4eda0fdcff66bd297f480454ba6b9733185634f49f3799c650` |
| DeepLoc 2.0 | 28,303 | Fresh official DTU `Swissprot_Train_Validation_dataset.csv`; sequences, ten localisation labels, and published homology partitions match exactly after deterministic column renaming and fold mapping (0 test, 1 validation, 2–4 train). | `402e2f2690d70298b7d1c986ccfbee51f33fa9f607ea71c1ce59821af6840d94` |
| Fluorescence | 54,025 | Fresh `proteinglm/fluorescence_prediction` at revision `d2a150fc808dbb02330c5fff6c4cb4807efe1979`; sequences and author splits match exactly. Target differences are only CSV floating-point round-trip noise below `9e-16`. | `d433037fc1da850b7f29888a18b8fc61f00d181f44870db345a60a6316063a86` |
| Promoters | 31,443 | Fresh `InstaDeepAI/nucleotide_transformer_downstream_tasks_revised` at revision `851f9946252e90c665cdb3cc3eedb78f1f26197c`; `promoter_all` sequences, labels, and author train/test split match after removing 141 exact duplicates within their original split. There is no train/test exact-sequence overlap. | `3998422fb9e71fe6cd9437ed53df4328517b0b0ca8709c139442678ab02084a1` |

Primary download endpoints are encoded in
`benchmark/download_real_datasets.py`. Hugging Face datasets and every neural
checkpoint are pinned to immutable revision hashes rather than floating branch
names.

## Split and identity checks

The release validator reloads every local dataset and fails if:

- a dataset hash or ordered-input hash differs from the reported result;
- any train/test exact input overlap exists;
- a molecular train/test Murcko scaffold overlap exists;
- a required model-task cell, prediction bundle, or public analysis is absent;
- an embedding sidecar disagrees with its dataset input hash, checkpoint
  revision, protocol version, or full matrix content hash; or
- a reported score is not cryptographically bound to that exact embedding
  matrix.

The final release command is:

```bash
python benchmark/validate_release.py --full-hash
```

It passed on 2026-09-14 with `Validated 9 tasks and 68 cells.` The validator
also recomputed the ranked metric from every saved prediction bundle and
confirmed agreement with both the paired-inference report and the measured
benchmark table.

## Why the measured benchmark is not synthetic

- `benchmark/download_real_datasets.py` has no data generator or fallback. A
  missing or unreachable source raises an error.
- `benchmark/datasets.py` refuses missing, empty, degenerate, or malformed task
  files.
- `benchmark/embed.py` either computes a named deterministic descriptor or
  runs the pinned public checkpoint. It contains no Gaussian projection,
  imputation, placeholder representation, or substitute model.
- `benchmark/run_study.py` leaves failed cells absent. It does not invent a
  score, and the release validator rejects an incomplete grid.
- Measured values and literature values are stored and rendered from separate
  artifacts. They are never combined into one leaderboard.

The repository history records removal of the former synthetic projection
prototype. Its outputs are not accepted by the current embedding protocol or
release gate.

## Literature registry audit

The registry currently contains 61 score rows. Every row has a direct source
URL/DOI and a location/protocol note. The detailed human verification history
is in `BENCHMARK_VERIFICATION.md`: 56 original rows were checked against their
papers, with fabricated or mismatched rows removed and incorrect values
corrected. Five later rows added in commit `47941a3` were also checked against
their sources:

- ChemXTree BBBP `0.756`, ClinTox `0.923`, and CYP3A4 Substrate `0.696` are
  reported in Xu et al. (2024), DOI `10.1021/acs.jcim.4c01186`.
- Uni-Mol layer 13 `0.688` and MolFormer layer 9 `0.699` on
  `cyp3a4-substrate-carbonmangels` are reported in Pinto (2025), arXiv
  `2506.06443`.

These registry numbers remain literature transcriptions under heterogeneous
protocols. They are provenance-audited, but they are not directly comparable
with one another or with BioLatent's measured scores.
