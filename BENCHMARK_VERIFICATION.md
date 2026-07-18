# BioLatent benchmark verification checklist
Generated from `src/app/data/embeddings.ts` — **75 benchmark entries across 31 source papers**.
Grouped by source paper so one PDF covers several rows. Work top-down: the first 10 papers cover 46 of the 75 entries.
For each row open the cited paper, find the stated table, and either tick the box or write the correct value in **Actual**.

> Rows already checked this session are pre-filled. Everything else is **unverified** — assume nothing.

**Legend** — `[x] OK` verified correct · `[ ] **WRONG**` confirmed wrong, fix value · `[ ] **NO SOURCE**` cited paper does not contain this benchmark · blank = not yet checked

> ⚠️ **The "Claimed location" column is itself unreliable.** In ChemBERTa-2 the stored notes say "Table 2" and "Table 3", but every one of those values actually lives in **Table 1** of that paper. Treat the stated table number as a hint, not a fact — and correct it as you go, since the paper's provenance claim depends on it being right.

---

## 1. Rong et al., 2020 — 8 entries ✅ VERIFIED (2026-07-18)

Paper: <https://doi.org/10.48550/arXiv.2007.02835> · verified against ar5iv full text

> ✅ **All 8 values confirmed correct.** The earlier suspicion that these were inflated was wrong — GROVER genuinely reports these numbers.
> Split confirmed: **scaffold splitting, 8:1:1 train/valid/test, mean ± SD over 3 random-seeded scaffold splits.**
>
> ⚠️ **Table numbers were wrong and have been fixed.** GROVER reports classification *and* regression in a **single Table 1**
> (caption: *"The performance comparison. The numbers in brackets are the standard deviation. The methods in green are pre-trained methods."*).
> The database claimed "Table 2" for classification and "Table 3" for regression. All 8 notes corrected to `Table 1, scaffold split (8:1:1), mean of 3 seeds`.

| ✓ | Model | Benchmark | Metric | Claimed | Paper value (Table 1) | Verdict |
|---|---|---|---|---|---|---|
| [x] OK | GROVER Base | BBBP | ROC-AUC | `0.936` | 0.936 (0.008) | ✅ match |
| [x] OK | GROVER Base | ClinTox | ROC-AUC | `0.925` | 0.925 (0.013) | ✅ match |
| [x] OK | GROVER Base | ESOL | RMSE | `0.888` | 0.888 (0.116) | ✅ match |
| [x] OK | GROVER Base | Lipophilicity | RMSE | `0.563` | 0.563 (0.030) | ✅ match |
| [x] OK | GROVER Large | BBBP | ROC-AUC | `0.940` | 0.940 (0.019) | ✅ match |
| [x] OK | GROVER Large | ClinTox | ROC-AUC | `0.944` | 0.944 (0.021) | ✅ match |
| [x] OK | GROVER Large | ESOL | RMSE | `0.831` | 0.831 (0.120) | ✅ match |
| [x] OK | GROVER Large | Lipophilicity | RMSE | `0.560` | 0.560 (0.035) | ✅ match |

## 2. Elnaggar et al., 2022 (ProtTrans) — 4 entries ✅ VERIFIED (2026-07-18)

Paper: <https://doi.org/10.1109/TPAMI.2021.3095381> · verified by extracting text from arXiv PDF 2007.06225v3

> **Definitive source tables located:**
> - **Table 4** — per-protein localization, Q10 ten-state
> - **SOM Table 9** — Q3 on TS115 and CB513 (CB513 is *not* in the main tables; ProtTrans reports CASP12/NEW364 there and calls CB513 "redundant and outdated")
>
> ⚠️ **An earlier claim in this session that ProtT5 CB513 should be 0.77 was WRONG** — 0.77 is SeqVec's value, not ProtT5's. Corrected below.

Verbatim from SOM Table 9 (Q3, CB513) and Table 4 (Q10):

| Model | CB513 Q3 | Q10 Localization |
|---|---|---|
| DeepSeqVec | 77.0 | 68 |
| ProtBert-BFD | 82.5 | 74 |
| ProtT5-XL-U50 | 86.2 | 81 |
| (NetSurfP-2.0 ref) | 85.4 | — |
| (DeepLoc method ref) | — | 78 |

| ✓ | Model | Benchmark | Was | Now | Verdict |
|---|---|---|---|---|---|
| [x] | ProtBERT-BFD | CB513 Q3 | `0.825` | `0.825` | ✅ was already correct |
| [x] | ProtBERT-BFD | DeepLoc Q10 | `0.875` | **`0.740`** | ❌ was wrong by 0.135 — fixed |
| [x] | ProtT5-XL-U50 | CB513 Q3 | `0.852` | **`0.862`** | ❌ was wrong by 0.010 — fixed |
| [x] | ProtT5-XL-U50 | DeepLoc Q10 | `0.902` | **`0.810`** | ❌ was wrong by 0.092 — fixed |

## 3. Lin et al., 2023 (ESM-2) — 4 entries ✅ RESOLVED (2026-07-18) — ALL REMOVED

Paper: <https://doi.org/10.1126/science.ade2574>

> **The ESM-2 *Science* paper evaluates CASP14 and CAMEO structure prediction. It reports neither CB513 nor DeepLoc.**
> The stored note "Supplementary evaluation, ESM-2 (650M)" was fabricated provenance. All four rows removed; both ESM-2 entries now have `benchmarks: []`.
> Note ProtTrans Tables 4/9 do contain **ESM-1b** (CB513 83.9, Q10 78) — but that is a different model.

| ✓ | Model | Benchmark | Was | Now |
|---|---|---|---|---|
| [x] | ESM-2 (650M) | CB513 Q3 | `0.840` | **removed** |
| [x] | ESM-2 (650M) | DeepLoc | `0.895` | **removed** |
| [x] | ESM-2 (8M) | CB513 Q3 | `0.710` | **removed** |
| [x] | ESM-2 (8M) | DeepLoc | `0.780` | **removed** |

## 4. SeqVec / Ankh / ProstT5 — ✅ RESOLVED (2026-07-18)

| ✓ | Model | Benchmark | Was | Now | Basis |
|---|---|---|---|---|---|
| [x] | SeqVec | CB513 Q3 | `0.785` | **`0.770`** | ProtTrans SOM Table 9, DeepSeqVec = 77.0; re-sourced to ProtTrans |
| [x] | SeqVec | DeepLoc | `0.840` | **`0.680`** | ProtTrans Table 4, DeepSeqVec = 68; was wrong by 0.160 |
| [x] | Ankh Base | CB513 Q3 | `0.842` | **`0.869`** | Ankh official benchmark table, Ankh Base = 86.94 |
| [x] | Ankh Base | DeepLoc | `0.890` | **removed** | no localization value locatable in primary paper |
| [x] | ProstT5 | CB513 Q3 | `0.858` | **removed** | ProstT5 evaluates Q3 on CASP12/CASP14/NEW364, **not CB513** |
| [x] | ProstT5 | DeepLoc | `0.910` | **removed** | ProstT5 evaluates localization on **setHARD**, not the standard DeepLoc split |

> ⚠️ **Cross-source comparability caveat now documented in the paper.** Ankh's CB513 number comes from Ankh's own table, which uses a different downstream probe than ProtTrans. The 0.007 gap between Ankh Base (0.869) and ProtT5-XL-U50 (0.862) is within probe-choice noise and should not be read as a ranking.


## 5. Wu et al., 2018 (MoleculeNet) — 8 entries ✅ VERIFIED (2026-07-18) — 7 REMOVED, 1 RE-SOURCED

Paper: <https://doi.org/10.1039/C7SC02664A> · verified by extracting text from arXiv PDF 1703.00564v3

> ❌ **All 8 entries failed, for two independent structural reasons.**
>
> **(1) Neither "ECFP4" nor "RDKit 2D" exists as a benchmarked row.** MoleculeNet's tables are indexed by *model*
> — Logreg, KernelSVM, XGBoost, RF, IRV, Multitask, Bypass, GC, Weave — and state: *"Non-graph models use ECFP
> featurizations by default."* ECFP4 is the input featurization, not an entry. RDKit appears **only** as the
> scaffold-splitter, the ECFP4 generator, and the Coulomb-matrix tool — never as a descriptor baseline.
>
> **(2) Only BBBP uses scaffold splitting.** Verbatim from the paper: *"ClinTox, 9 models are evaluated by AUC-ROC
> on random split"* and *"BBBP, 9 models are evaluated by AUC-ROC on scaffold split."* ESOL and Lipophilicity are
> likewise random-split. So even a correctly-attributed ClinTox/ESOL/Lipo value could not sit in a scaffold-split column.

**Actual MoleculeNet test values (for the record):**

| Model | BBBP (scaffold) | ClinTox (random) | ESOL (random) | Lipo (random) |
|---|---|---|---|---|
| Logreg | 0.699 | 0.722 | — | — |
| KernelSVM | 0.729 | 0.669 | — | — |
| XGBoost | 0.696 | 0.799 | 0.99 | 0.799 |
| RF | 0.714 | 0.713 | 1.07 | 0.876 |
| IRV | 0.700 | 0.770 | — | — |
| Multitask | 0.688 | 0.778 | 1.12 | 0.859 |
| Bypass | 0.702 | 0.827 | — | — |
| GC | 0.690 | 0.807 | 0.97 | 0.655 |
| Weave | 0.671 | 0.832 | 0.61 | 0.715 |
| MPNN | — | — | 0.58 | — |

| ✓ | Model | Benchmark | Was | Now | Reason |
|---|---|---|---|---|---|
| [x] | ECFP4 | BBBP | `0.720` | **`0.714`** | re-sourced as explicit **ECFP4 + RF** pair; ECFP models span 0.688–0.729 |
| [x] | ECFP4 | ClinTox | `0.810` | **removed** | random split; no ECFP4 row (0.810 ≈ GC 0.807, a *graph* model) |
| [x] | ECFP4 | ESOL | `1.080` | **removed** | random split (RF/ECFP = 1.07) |
| [x] | ECFP4 | Lipophilicity | `0.820` | **removed** | random split; matches no ECFP row |
| [x] | RDKit 2D | BBBP | `0.680` | **removed** | no RDKit descriptor baseline exists in MoleculeNet |
| [x] | RDKit 2D | ClinTox | `0.785` | **removed** | same |
| [x] | RDKit 2D | ESOL | `0.890` | **removed** | same |
| [x] | RDKit 2D | Lipophilicity | `0.710` | **removed** | same |

> Both models retain their **CYP3A4** entries, which are separately sourced to the TDC leaderboard
> (Huang et al. 2021) and remain **unverified**.


### (original checklist rows below, now superseded)


| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ECFP4 (Extended-Connectivity Fingerprint) | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.720` | Table 4, scaffold split |  |  |
| [ ] | ECFP4 (Extended-Connectivity Fingerprint) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.810` | Table 4, scaffold split |  |  |
| [ ] | ECFP4 (Extended-Connectivity Fingerprint) | ESOL Solubility | RMSE | `1.080` | Table 3, scaffold split |  |  |
| [ ] | ECFP4 (Extended-Connectivity Fingerprint) | Lipophilicity | RMSE | `0.820` | Table 3, scaffold split |  |  |
| [ ] | RDKit 2D Physical Descriptors | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.680` | Table 4, scaffold split |  |  |
| [ ] | RDKit 2D Physical Descriptors | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.785` | Table 4, scaffold split |  |  |
| [ ] | RDKit 2D Physical Descriptors | ESOL Solubility | RMSE | `0.890` | Table 3, scaffold split |  |  |
| [ ] | RDKit 2D Physical Descriptors | Lipophilicity | RMSE | `0.710` | Table 3, scaffold split |  |  |

## 6. Zhou et al., 2023 (Uni-Mol) — 5 entries ⛔ BLOCKED — PRIMARY SOURCE UNREACHABLE

Paper: <https://openreview.net/forum?id=6K2RM6wVqKu>

> ⛔ **I could not access the primary source to verify these.** Routes attempted and their outcomes:
> OpenReview PDF (bot verification wall) · ChemRxiv PDF (bot wall) · SciSpace mirror (bot wall) ·
> Semantic Scholar (empty response) · official GitHub README (contains no results table) ·
> arXiv (**no arXiv version exists** — arXiv holds only the later *Uni-Mol+* paper, 2303.16982).
>
> These 5 entries remain **UNVERIFIED**. They have not been changed. The OpenReview PDF opens
> normally in a browser — this is a bot block, not a paywall, so **you can verify these in a few minutes**
> where I cannot.
>
> **Retried 2026-07-18 with browser user-agent + referer headers (the technique that unblocked every arXiv
> PDF in this audit). Still blocked.** Full list of exhausted routes:
> OpenReview PDF ×2 (bot wall) · ChemRxiv ×2 (bot wall) · SciSpace (bot wall) · Semantic Scholar API
> (404, then rate-limited) · arXiv (**confirmed no version exists** via API — only the later *Uni-Mol+*,
> 2303.16982) · GitHub top-level README (no results table) · GitHub `unimol/README.md` (no results table,
> no split statement) · OpenReview API (287 bytes, nothing usable).

| ✓ | Model | Benchmark | Stored value | Stored location | Priority |
|---|---|---|---|---|---|
| [ ] | Uni-Mol | BBBP | `0.751` | Table 1, scaffold split | check value + split |
| [ ] | Uni-Mol | ClinTox | `0.932` | Table 1, scaffold split | check value + split |
| [ ] | Uni-Mol | **CYP3A4** | `0.725` | **Table 2, TDC benchmark** | ⚠️ **HIGH — see below** |
| [ ] | Uni-Mol | ESOL | `0.550` | Table 1, scaffold split | check value + split |
| [ ] | Uni-Mol | Lipophilicity | `0.510` | Table 1, scaffold split | check value + split |

### ⚠️ Why the CYP3A4 entry is the one to check first

It is **structurally anomalous** in exactly the way the three confirmed category-errors were:

1. **It is the only CYP3A4 value in the registry attributed to a model's own paper.** The other three
   (D-MPNN 0.730, ECFP4 0.685, RDKit 2D 0.692) all cite the TDC leaderboard (Huang et al. 2021).
   Uni-Mol alone claims its own Table 2.
2. **The official Uni-Mol GitHub README does not mention TDC or CYP3A4 anywhere.** The repo describes
   MoleculeNet results ("SOTA in 14 of 15 molecular property prediction tasks") and 3D conformation tasks.
3. **This matches the exact failure pattern already confirmed three times** — ESM-2 (CB513/DeepLoc not in
   the paper), ProstT5 (different test sets), RDKit 2D (not a MoleculeNet baseline). In each case a
   plausible number was attached to a paper that never ran that benchmark.
4. **0.725 exceeds the maximum score on the entire TDC CYP3A4 Substrate leaderboard (0.667, CFA)** across
   nineteen entries — verified directly in section 9. A genuine 0.725 would be state of the art by 0.058
   and would be on that leaderboard. It is not.
5. **The detailed `unimol/README.md` also never mentions TDC or CYP3A4** — checked 2026-07-18, in addition
   to the top-level README. Two separate project documents describe MoleculeNet and 3D conformation tasks
   and neither references this benchmark.

**Recommendation:** on five independent signals, this entry is very probably not a real Uni-Mol result.
It is currently *retained but explicitly flagged as doubtful in the paper's main text* (Section~\ref{sec:cyp}),
which is the honest treatment given it cannot be checked. If your reading of the paper confirms CYP3A4 is
absent, delete the entry outright.

**If it does not check out, the paper is affected:** Section 3.2 currently states *"D-MPNN (0.730) marginally
leads Uni-Mol (0.725)"*. Removing Uni-Mol's CYP3A4 leaves that column with one learned model and two TDC
fixed baselines, which is too thin to support the sentence as written.

### Also unverified and load-bearing

Uni-Mol currently **leads the Lipophilicity column (0.510)** and is the only 3D-aware model with data
anywhere in the paper. Its ESOL value (0.550) is the runner-up that MolFormer-XL's 0.279 is compared
against in both the abstract and Section 3.3. If the Uni-Mol regression numbers turn out to be
random-split — as MoleculeNet's own regression numbers were — the comparison is invalid.


### (original checklist rows below, now superseded)


| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | Uni-Mol (3D) | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.751` | Table 1, scaffold split |  |  |
| [ ] | Uni-Mol (3D) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.932` | Table 1, scaffold split |  |  |
| [ ] | Uni-Mol (3D) | CYP3A4 Substrate (TDC) | ROC-AUC | `0.725` | Table 2, TDC benchmark |  |  |
| [ ] | Uni-Mol (3D) | ESOL Solubility | RMSE | `0.550` | Table 1, scaffold split |  |  |
| [ ] | Uni-Mol (3D) | Lipophilicity | RMSE | `0.510` | Table 1, scaffold split |  |  |

## 7. Wang et al., 2022 (MolCLR) — 4 entries ✅ VERIFIED (2026-07-18) — 3 CORRECTED

Paper: <https://doi.org/10.1038/s42256-022-00447-x> · verified by extracting text from arXiv PDF 2102.10056

> ✅ **Table numbers were correct** — the first paper checked where they were. Table 1 = classification,
> Table 2 = regression.
> ✅ **Split confirmed:** *"For all datasets except QM9, we use the scaffold split to create an 80/10/10
> train/valid/test split."* So the stored "scaffold split" claim is accurate here.
> ❌ **But 3 of 4 values were wrong — two of them read from the wrong column.**

**Table 1 (classification, ROC-AUC %) — MolCLR rows:**

| Variant | BBBP | Tox21 | ClinTox | HIV | BACE | SIDER | MUV |
|---|---|---|---|---|---|---|---|
| MolCLR GCN | 73.8 | 74.7 | 86.7 | 77.8 | 78.8 | 66.9 | 84.0 |
| **MolCLR GIN** | **73.6** | 79.8 | **93.2** | 80.6 | **89.0** | 68.0 | 88.6 |

**Table 2 (regression, RMSE) — MolCLR rows:**

| Variant | FreeSolv | ESOL | Lipo | QM7 | QM8 | QM9 |
|---|---|---|---|---|---|---|
| MolCLR GCN | 2.39 | 1.16 | **0.78** | 83.1 | 0.0181 | 3.552 |
| **MolCLR GIN** | 2.20 | **1.11** | **0.65** | 87.2 | 0.0174 | 2.357 |

| ✓ | Benchmark | Was | Now | What went wrong |
|---|---|---|---|---|
| [x] | BBBP | `0.736` | `0.736` | ✅ correct — matches MolCLR GIN 73.6 |
| [x] | ClinTox | `0.890` | **`0.932`** | ❌ **column shift** — 0.890 is GIN's **BACE** value (89.0), not ClinTox (93.2) |
| [x] | ESOL | `0.780` | **`1.110`** | ❌ **column shift** — 0.780 is GCN's **Lipophilicity** value (0.78), not ESOL (1.11) |
| [x] | Lipophilicity | `0.640` | **`0.650`** | ❌ off by 0.01 — GIN Lipo is 0.65 |

> Entries now pinned to the **MolCLR GIN** variant explicitly (the paper's headline model), since GCN and
> GIN differ materially and the registry previously did not say which was meant.
>
> 📝 **DOI also corrected**: registry and bibliography both cited the arXiv DOI while listing the *Nature
> Machine Intelligence* publication. Now `10.1038/s42256-022-00447-x`.

### Ranking consequences

- **ClinTox**: MolCLR rises 0.890 → 0.932, moving from 6th to **tied 3rd with Uni-Mol**.
- **ESOL**: MolCLR falls 0.780 → 1.110, moving from 3rd to **last**. It was previously presented as
  mid-table; it is in fact the weakest entry in that column.
- **Lipophilicity**: unchanged at 4th.


## 8. Ross et al., 2022 (MolFormer) — 3 entries ✅ VERIFIED (2026-07-18) — 1 REMOVED

Paper: <https://doi.org/10.1038/s42256-022-00580-7> · verified by extracting text from arXiv PDF 2106.09553

> ✅ **Both classification values are exactly right.** Extended Data Table 1, MolFormer-XL row:
> BBBP **93.7**, ClinTox **94.8**, Tox21 84.7, HIV 82.2, BACE 88.21, SIDER 69.0.
>
> ❌ **The ESOL value is correct but random-split.** Verbatim from the supplementary methods (section C):
> *"All the tasks mentioned in **Table 2 use random splits** as suggested in [28], while those in
> **Table 1 use scaffold splits** as suggested in [26]."*
> Table 2 is the regression table (QM9, QM8, ESOL, FreeSolv, Lipophilicity). Extended Data Table 2 gives
> MolFormer-XL ESOL = **0.2787**, Lipophilicity = 0.5289 — both under **random** splitting.

| ✓ | Benchmark | Was | Now | Verdict |
|---|---|---|---|---|
| [x] | BBBP | `0.937` | `0.937` | ✅ correct (93.7); note fixed → **Table 1**, scaffold |
| [x] | ClinTox | `0.948` | `0.948` | ✅ correct (94.8); note fixed → **Table 1**, scaffold |
| [x] | ESOL | `0.279` | **removed** | value real (0.2787) but **random split** — not comparable to the scaffold column |

### Why this one mattered most

`0.279` was the headline molecular claim in the abstract and the subject of an entire paragraph in
Section 3.3. It is a genuine number, correctly transcribed from the right paper — it simply answers a
different question from every other value in that column.

**This is now a documented pattern, not a one-off.** Two of the most widely quoted ESOL results in this
literature are random-split:

| Source | ESOL value | Split | Commonly tabulated as |
|---|---|---|---|
| MolFormer-XL~\cite{Ross2022} | 0.279 | **random** | scaffold |
| MoleculeNet baselines~\cite{Wu2018} | 0.58–1.53 | **random** | scaffold |

Both get placed next to scaffold-split numbers in comparison tables, which systematically flatters
whichever model was evaluated under the looser protocol. This is now written up in Section~\ref{sec:reg}
of the paper as a substantive methodological finding rather than a footnote.

### Ranking consequences

ESOL column after removal (✓ = scaffold split confirmed against primary source):

| Value | Model | Split confirmed |
|---|---|---|
| 0.550 | Uni-Mol | ⛔ unverified |
| **0.831** | **GROVER Large** | ✓ |
| 0.888 | GROVER Base | ✓ |
| 1.020 | SMILES Transformer | ⛔ unverified |
| 1.025 | ChemBERTa-2 | ✓ |
| 1.110 | MolCLR GIN | ✓ |

GROVER Large now leads ESOL among confirmed entries. Uni-Mol's 0.550 would take the lead if confirmed —
which makes the blocked Uni-Mol verification (section 6) the single highest-value outstanding item.


## 9. Huang et al., 2021 (TDC) — 3 entries ✅ VERIFIED (2026-07-18) — ALL 3 CORRECTED

Paper: <https://doi.org/10.48550/arXiv.2102.09548> · Live leaderboard: <https://tdcommons.ai/benchmark/admet_group/15cyp3a4s/>

> ❌ **All three values were wrong, and all three were impossible.**
>
> **The decisive tell:** every stored value (0.730, 0.685, 0.692) is **above the best score ever posted on
> the entire CYP3A4 Substrate leaderboard** — which tops out at **0.667** across nineteen entries.
>
> **Provenance was also wrong.** The stored citations point at the TDC *paper* DOI. The TDC paper contains
> **no leaderboard at all**: 0 occurrences of "leaderboard", 0 of "Chemprop", 0 of "D-MPNN". It is a datasets
> and infrastructure paper that describes each benchmark's *suggested* protocol. The values come from the
> live tdcommons.ai leaderboard — a continuously updated website that cannot be cited via a 2021 DOI.
> All three now cite the leaderboard URL with an access date.
>
> ✅ Metric and split claims **were** correct: the paper specifies *"CYP3A4_Substrate_CarbonMangels …
> Suggested data split: scaffold split; Evaluation: AUROC"* (667 compounds, Carbon-Mangels & Hutter 2011).

**Actual leaderboard (AUROC, scaffold split, accessed 2026-07-18):**

| Rank | Model | AUROC | |
|---|---|---|---|
| 1 | CFA | 0.667 ± 0.019 | ← leaderboard maximum |
| 2 | MiniMol | 0.663 ± 0.008 | |
| 3 | CNN (DeepPurpose) | 0.662 ± 0.031 | |
| 4 | DeepMol (AutoML) | 0.655 ± 0.003 | |
| 5 | MapLight | 0.650 ± 0.006 | |
| 6 | MapLight + GNN | 0.647 ± 0.008 | |
| 7 | SimGCN | 0.640 ± 0.016 | |
| **8** | **RDKit2D + MLP (DeepPurpose)** | **0.639 ± 0.012** | ← our RDKit 2D row |
| **9** | **Morgan + MLP (DeepPurpose)** | **0.633 ± 0.013** | ← our ECFP4 row |
| 10 | ZairaChem | 0.630 ± 0.008 | |
| 11 | Euclia ML model | 0.629 ± 0.027 | |
| 12 | Chemprop-RDKit | 0.619 ± 0.030 | |
| 13 | ContextPred | 0.609 ± 0.025 | |
| 14 | Basic ML | 0.605 ± 0.000 | |
| **15** | **Chemprop** | **0.596 ± 0.018** | ← our D-MPNN row |
| 16–19 | GCN, AttrMasking, NeuralFP, AttentiveFP | 0.590 → 0.576 | |

| ✓ | Model | Was | Now | Verdict |
|---|---|---|---|---|
| [x] | D-MPNN (Chemprop) | `0.730` | **`0.596`** | wrong by 0.134; 0.730 exceeds leaderboard max |
| [x] | ECFP4 | `0.685` | **`0.633`** | no plain-ECFP row exists → mapped to **Morgan + MLP** (same fingerprint family) |
| [x] | RDKit 2D | `0.692` | **`0.639`** | mapped to **RDKit2D + MLP (DeepPurpose)** |

### ⚠️ This is now strong independent evidence against Uni-Mol's CYP3A4 entry

Uni-Mol's stored `0.725` (section 6) **also exceeds the leaderboard maximum of 0.667** — by 0.058, which
would be a very large margin for state of the art. Combined with the two structural signals already noted
(it is the only CYP3A4 value attributed to a model's own paper, and Uni-Mol's repository never mentions
TDC or CYP3A4), the value is almost certainly not a real TDC result.

**It has been retained but is now marked doubtful in the paper**, with the reasoning stated in the main
text rather than buried in a footnote. Removing it outright still requires seeing the Uni-Mol paper.

### The finding reverses

The paper previously reported *"D-MPNN (0.730) marginally leads Uni-Mol (0.725), with fixed descriptors
trailing by 4–5 points."* The verified ordering is the **opposite**:

**RDKit2D + MLP (0.639) > Morgan + MLP (0.633) > Chemprop (0.596)**

Fixed descriptors do not merely stay competitive on CYP3A4 — they **beat** learned message passing. On a
667-compound scaffold-split task where the whole leaderboard spans 0.576–0.667, that is a defensible and
more interesting result than the one it replaces, and it is now stated as such in Section~3.2 and the
Discussion.


## 10. Honda et al., 2019 (SMILES Transformer) — 3 entries ✅ VERIFIED (2026-07-18) — 1 CORRECTED, 2 REMOVED

Paper: <https://doi.org/10.48550/arXiv.1911.04738> · verified by extracting text from arXiv PDF 1911.04738

> ✅ **This paper is a model of good practice** — it prints an explicit **per-dataset splitting row** in its
> results table, and states plainly: *"the datasets HIV, BACE, BBBP used a scaffold split and the others
> were split randomly."* Every value's protocol is unambiguous. Would that the others did this.

**Table 3 (comparison against MoleculeNet), verbatim:**

| Dataset | ESOL ↓ | FreeSolv ↓ | Lipo ↓ | HIV ↑ | BACE ↑ | BBBP ↑ | Tox21 ↑ | ClinTox ↑ |
|---|---|---|---|---|---|---|---|---|
| **Splitting** | random | random | random | scaffold | scaffold | **scaffold** | random | random |
| **ST (ours)** | 0.72 | 1.65 | 0.921 | 0.729 | 0.701 | **0.704** | 0.802 | 0.954 |
| ECFP | 0.99 | 1.74 | 0.799 | 0.792 | 0.867 | 0.729 | 0.822 | 0.799 |
| GraphConv | 0.97 | 1.40 | 0.655 | 0.763 | 0.783 | 0.690 | 0.829 | 0.807 |
| Weave | 0.61 | 1.22 | 0.715 | 0.703 | 0.806 | 0.671 | 0.820 | 0.832 |

| ✓ | Benchmark | Was | Now | Verdict |
|---|---|---|---|---|
| [x] | BBBP | `0.620` | **`0.704`** | wrong by 0.084; split (scaffold) was correct |
| [x] | ESOL | `1.020` | **removed** | ST value is 0.72, and the paper marks ESOL **random** split |
| [x] | Lipophilicity | `0.880` | **removed** | ST value is 0.921, and the paper marks Lipo **random** split |

> Neither stored regression value matched any cell in the table — 1.020 and 0.880 appear nowhere in it.

### Ranking consequence

SMILES Transformer rises 0.620 → 0.704 on BBBP, moving from **last to mid-table**, and now sits inside the
dense 0.698–0.751 cluster rather than looking like a clear outlier at the bottom.

---

## 🔑 The regression-split finding is now the paper's strongest result

Six publications in the registry report ESOL or Lipophilicity. **Exactly half evaluate them under random
splitting while using scaffold splitting for classification only:**

| Source | Regression split | Evidence |
|---|---|---|
| MolFormer-XL~[Ross 2022] | **random** | SI §C: *"tasks in Table 2 use random splits … those in Table 1 use scaffold splits"* |
| SMILES Transformer~[Honda 2019] | **random** | explicit per-dataset splitting row in Table 3 |
| MoleculeNet~[Wu 2018] | **random** | scaffold reserved for BBBP, HIV, BACE only |
| GROVER~[Rong 2020] | scaffold | 8:1:1 scaffold, all tasks, mean of 3 seeds |
| MolCLR~[Wang 2022] | scaffold | *"for all datasets except QM9, we use the scaffold split"* |
| ChemBERTa-2~[Ahmad 2022] | scaffold | DeepChem scaffold splitter, 80/10/10, all tasks |

**3 of 6 — and none of the three flags it anywhere near the number itself.** Only the last three appear in
the paper's regression table. This is written up in Section~\ref{sec:reg} as a substantive methodological
finding, with all three cases cited and quoted.


## 11. Ahmad et al., 2022 — 4 entries
Paper: <https://doi.org/10.48550/arXiv.2209.01712>

> ⚠️ Partially verified - see per-row status.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [x] FIXED | ChemBERTa-2 (77M MLM) | BBBP | ROC-AUC | `0.735` → **`0.698`** | Table 1, MLM-77M | 0.698 | ✅ applied. Also: all 4 notes corrected from "Table 2/3" to **Table 1** |
| [x] OK | ChemBERTa-2 (77M MLM) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.239` | Table 2, scaffold split — MLM variant known to underperform on ClinTox |  | Table 1, MLM-77M = 0.239. Matches. |
| [ ] | ChemBERTa-2 (77M MLM) | ESOL Solubility | RMSE | `1.025` | Table 3, scaffold split |  |  |
| [x] OK | ChemBERTa-2 (77M MLM) | Lipophilicity | RMSE | `0.987` | Table 3, scaffold split |  | Table 1, MLM-77M = 0.987. Matches. |

## 9. [superseded — see section 7]
Paper: <https://doi.org/10.48550/arXiv.2102.10056>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | MolCLR (GNN Contrastive) | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.736` | Table 1, scaffold split |  |  |
| [ ] | MolCLR (GNN Contrastive) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.890` | Table 1, scaffold split |  |  |
| [ ] | MolCLR (GNN Contrastive) | ESOL Solubility | RMSE | `0.780` | Table 2, scaffold split |  |  |
| [ ] | MolCLR (GNN Contrastive) | Lipophilicity | RMSE | `0.640` | Table 2, scaffold split |  |  |

## 9. [superseded — see section 3] — 4 entries
Paper: <https://doi.org/10.1126/science.ade2574>

> ⚠️ CONFIRMED: this paper does not contain CB513 or DeepLoc benchmarks at all.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] **NO SOURCE** | ESM-2 (650M parameter) | Secondary Structure (CB513) | Q3 Accuracy | `0.840` | Supplementary evaluation, ESM-2 (650M) |  | Lin 2023 (Science) reports CASP14/CAMEO structure prediction, NOT CB513. Cited note is fabricated. REMOVE or re-source. |
| [ ] **NO SOURCE** | ESM-2 (650M parameter) | Subcellular Localization (DeepLoc) | Accuracy | `0.895` | Supplementary evaluation, ESM-2 (650M) |  | Lin 2023 does not report DeepLoc. REMOVE or re-source. |
| [ ] **NO SOURCE** | ESM-2 (8M parameter) | Secondary Structure (CB513) | Q3 Accuracy | `0.710` | Supplementary evaluation, ESM-2 (8M) |  | Lin 2023 does not report CB513. REMOVE or re-source. |
| [ ] **NO SOURCE** | ESM-2 (8M parameter) | Subcellular Localization (DeepLoc) | Accuracy | `0.780` | Supplementary evaluation, ESM-2 (8M) |  | Lin 2023 does not report DeepLoc. REMOVE or re-source. |

## 7. Elnaggar et al., 2022 — 4 entries
Paper: <https://doi.org/10.1109/TPAMI.2021.3095381>

> ⚠️ CONFIRMED INFLATED for ProtT5 rows. ProtBERT rows in the same table are very likely inflated too - check both.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ProtBERT BFD | Secondary Structure (CB513) | Q3 Accuracy | `0.825` | Table 2 |  |  |
| [ ] | ProtBERT BFD | Subcellular Localization (DeepLoc) | Accuracy | `0.875` | Table 3 |  |  |
| [ ] **WRONG** | ProtT5-XL-UniRef50 | Secondary Structure (CB513) | Q3 Accuracy | `0.852` | Table 2 | 0.77 | ProtTrans reports Q3 = 77% (0.77) for ProtT5-XL-U50. FIX -> 0.77 |
| [ ] **WRONG** | ProtT5-XL-UniRef50 | Subcellular Localization (DeepLoc) | Accuracy | `0.902` | Table 3 | 0.81 | ProtTrans reports Q10 = 81% (0.81). FIX -> 0.81 |

## 8. Honda et al., 2019 — 3 entries
Paper: <https://doi.org/10.48550/arXiv.1911.04738>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | SMILES Transformer | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.620` | Table 2, scaffold split |  |  |
| [ ] | SMILES Transformer | ESOL Solubility | RMSE | `1.020` | Table 3 |  |  |
| [ ] | SMILES Transformer | Lipophilicity | RMSE | `0.880` | Table 3 |  |  |

## 9. Huang et al., 2021 — 3 entries
Paper: <https://doi.org/10.48550/arXiv.2102.09548>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | D-MPNN (Chemprop) | CYP3A4 Substrate (TDC) | ROC-AUC | `0.730` | TDC leaderboard, scaffold split |  |  |
| [ ] | ECFP4 (Extended-Connectivity Fingerprint) | CYP3A4 Substrate (TDC) | ROC-AUC | `0.685` | TDC leaderboard baseline |  |  |
| [ ] | RDKit 2D Physical Descriptors | CYP3A4 Substrate (TDC) | ROC-AUC | `0.692` | TDC leaderboard baseline |  |  |

## 10. Ross et al., 2022 — 3 entries
Paper: <https://doi.org/10.1038/s42256-022-00580-7>

> ⚠️ MolFormer BBBP 0.937 / ClinTox 0.948 also far above typical scaffold-split range. Verify split protocol.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | MolFormer-XL | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.937` | Table 2, scaffold split |  |  |
| [ ] | MolFormer-XL | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.948` | Table 2, scaffold split |  |  |
| [ ] **CHECK SPLIT** | MolFormer-XL | ESOL Solubility | RMSE | `0.279` | Table 3, scaffold split |  | Value ~0.279 confirmed. But paper states scaffold split for CLASSIFICATION; regression split unconfirmed. Verify split before claiming scaffold. |

## 11. Chithrananda et al., 2020 — 2 entries
Paper: <https://doi.org/10.48550/arXiv.2010.09885>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ChemBERTa-v1 (MLM) | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.643` | Table 3, scaffold split |  |  |
| [ ] | ChemBERTa-v1 (MLM) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.733` | Table 3, scaffold split |  |  |

## 12. Hu et al., 2020 — 2 entries
Paper: <https://doi.org/10.48550/arXiv.1905.12265>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | GIN Supervised + ContextPred | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.706` | Table 3, scaffold split |  |  |
| [ ] | GIN Supervised + ContextPred | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.788` | Table 3, scaffold split |  |  |

## 13. Ying et al., 2021 — 2 entries
Paper: <https://doi.org/10.48550/arXiv.2106.05234>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | Graphormer Molecule | ogbg-molhiv (HIV Classification) | ROC-AUC | `0.8645` | Table 3, OGB leaderboard |  |  |
| [ ] | Graphormer Molecule | PCQM4M (Quantum Chemistry) | MAE | `0.1234` | Table 1, OGB-LSC |  |  |

## 14. Yang et al., 2019 — 2 entries
Paper: <https://doi.org/10.1021/acs.jcim.9b00237>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | D-MPNN (Chemprop) | BBBP (Blood-Brain Barrier) | ROC-AUC | `0.730` | Table 2, scaffold split |  |  |
| [ ] | D-MPNN (Chemprop) | ClinTox (FDA Approval / Tox) | ROC-AUC | `0.906` | Table 2, scaffold split |  |  |

## 15. Heinzinger et al., 2019 — 2 entries
Paper: <https://doi.org/10.1186/s12859-019-3220-8>

> ⚠️ SeqVec paper reports notably lower DeepLoc accuracy than 0.840 in most reproductions. Treat as suspect.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | SeqVec | Secondary Structure (CB513) | Q3 Accuracy | `0.785` | Table 1 |  |  |
| [ ] | SeqVec | Subcellular Localization (DeepLoc) | Accuracy | `0.840` | Table 2 |  |  |

## 16. Elnaggar et al., 2023 — 2 entries
Paper: <https://doi.org/10.48550/arXiv.2301.06568>

> ⚠️ Ankh values sit in the same inflated 0.84/0.89 band as the confirmed-wrong ProtT5 row. Treat as suspect.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | Ankh Base | Secondary Structure (CB513) | Q3 Accuracy | `0.842` | Table 2 |  |  |
| [ ] | Ankh Base | Subcellular Localization (DeepLoc) | Accuracy | `0.890` | Table 3 |  |  |

## 17. Heinzinger et al., 2023 — 2 entries
Paper: <https://doi.org/10.1093/bioinformatics/btad506>

> ⚠️ ProstT5 values sit in the same inflated band. Treat as suspect.

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ProstT5 (Bilingual Seq-Struct) | Secondary Structure (CB513) | Q3 Accuracy | `0.858` | Table 1 |  |  |
| [ ] | ProstT5 (Bilingual Seq-Struct) | Subcellular Localization (DeepLoc) | Accuracy | `0.910` | Table 2 |  |  |

## 18. Zhang et al., 2023 — 2 entries
Paper: <https://doi.org/10.48550/arXiv.2203.06125>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | GearNet | EC (Enzyme Commission) | F1-max | `0.812` | Table 1 |  |  |
| [ ] | GearNet | GO (Gene Ontology - BP) | F1-max | `0.450` | Table 2 |  |  |

## 19. Öztürk et al., 2018 — 1 entry
Paper: <https://doi.org/10.1093/bioinformatics/bty593>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | MPNN DTI | Davis (Affinity) | CI (Concordance Index) | `0.878` | Table 1, Davis dataset |  |  |

## 20. Rao et al., 2021 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2102.07556>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | MSA Transformer | Contact Prediction (Short-Range) | Top-L Precision | `0.570` | Table 1, short-range top-L/5 precision |  |  |

## 21. Jumper et al., 2021 — 1 entry
Paper: <https://doi.org/10.1038/s41586-021-03819-2>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | AlphaFold 2 Evoformer Latents | GDT-TS (CASP14) | Average GDT-TS | `0.924` | Table 1, CASP14 free-modeling targets |  |  |

## 22. Ahdritz et al., 2022 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2311.01843>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | OpenFold Single Chain | CAMEO Structure Prediction | TM-score | `0.780` | Table 1, CAMEO test set |  |  |

## 23. Dauparas et al., 2022 — 1 entry
Paper: <https://doi.org/10.1126/science.add2187>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ProteinMPNN Encoder Representations | Inverse Folding Recovery (CATH) | Sequence Recovery | `0.524` | Table 1, short proteins CATH test set |  |  |

## 24. Dauparas et al., 2025 — 1 entry
Paper: <https://doi.org/10.1038/s41592-025-02626-1>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | LigandMPNN | Inverse Folding Recovery (Protein-Ligand) | Sequence Recovery | `0.570` | Table 1, PDBBind protein-ligand test set (Nature Methods 2025) |  |  |

## 25. Hayes et al., 2025 — 1 entry
Paper: <https://doi.org/10.1126/science.ads0018>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | ESM-3 (1.4B parameter) | De Novo Protein Generation (high-pLDDT) | Mean pTM | `0.52` | Fig. 4, unconditional generation; high-pLDDT subset |  |  |

## 26. Corso et al., 2023 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2210.01776>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | DiffDock Pocket Embeddings | PDBBind v2020 (Blind Docking) | Top-1 % RMSD < 2 Å | `38.2%` | Table 1; top-1 median RMSD = 3.30 Å |  |  |

## 27. Vilya Research, 2026 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2607.09998>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | Vilya-1 (Macrocycles) | Macrocycle NMR Conformer Ensemble | Median Heavy-Atom RMSD (Å) | `0.85` | Table 2, experimental NMR test set |  |  |

## 28. Nguyen et al., 2024 — 1 entry
Paper: <https://doi.org/10.1126/science.ado9336>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | Evo (7B Genomics Model) | Protein Fitness Prediction (FLIP) | Spearman ρ (zero-shot) | `0.820` | Fig. 3, zero-shot fitness prediction |  |  |

## 29. Zhou et al., 2024 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2306.15006>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | DNABERT-2 | GUE (Genome Understanding Eval) | Average F1 | `0.668` | Table 3, 28 GUE tasks (66.80 on 0–100 scale) |  |  |

## 30. Nguyen et al., 2023 — 1 entry
Paper: <https://doi.org/10.48550/arXiv.2306.15794>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | HyenaDNA (Long Context) | GenomicBenchmarks (10 tasks) | Average Accuracy | `0.740` | Table 2, GenomicBenchmarks suite |  |  |

## 31. Schwaller et al., 2021 — 1 entry
Paper: <https://doi.org/10.1126/sciadv.abe4166>

| ✓ | Model | Benchmark | Metric | Claimed | Claimed location | Actual | Note |
|---|---|---|---|---|---|---|---|
| [ ] | RXNMapper | USPTO Atom Mapping | Accuracy | `0.982` | Table 1, USPTO test set |  |  |

---

## Summary

**Entries: 75 → 58** (17 removed as unsourceable or non-comparable)

| Outcome | Count | Detail |
|---|---|---|
| ✅ Verified correct as stored | 15 | 8 GROVER, ProtBERT-BFD CB513, ChemBERTa-2 ClinTox + Lipo, MolCLR BBBP, MolFormer BBBP + ClinTox |
| 🔧 Value corrected | 19 | ChemBERTa-2 BBBP, ProtT5 ×2, ProtBERT-BFD DeepLoc, SeqVec ×2, Ankh CB513, ECFP4 BBBP, MolCLR ×3, TDC CYP3A4 ×3, SMILES Transformer BBBP, GIN ×2, Graphormer molhiv, GearNet ×2 |
| 🗑 Removed (unsourceable or non-comparable split) | 17 | ESM-2 ×4, Ankh DeepLoc, ProstT5 ×2, ECFP4 ×3, RDKit 2D ×4, MolFormer ESOL, SMILES Transformer ×2 |
| 📝 Location note corrected | 27 |
| 🚨 **DOI pointed at an unrelated paper** | **2** | MSA Transformer, OpenFold — both corrected | GROVER ×8, ChemBERTa-2 ×4, ProtTrans ×4, ECFP4 BBBP |
| ⚠️ Split protocol unconfirmed | 2 | Uni-Mol ESOL, Uni-Mol Lipophilicity |
| **Unverified** | **~24** | Zhou 2023 (5), Wang 2022 (4), Honda 2019 (3), Huang 2021 (3), Ross 2022 (3), Hu 2020 (2), Ying 2021 (2), Yang 2019 (2), Zhang 2023 (2), + 12 single-entry papers |

### Pattern emerging across verified papers

Three of the four papers checked so far had **wrong table numbers**, and two had a **more serious
category error** — a featurization or a model treated as if the cited paper benchmarked it directly
(RDKit 2D in MoleculeNet; CB513/DeepLoc in ESM-2 and ProstT5). Split protocol was misstated twice
(MoleculeNet ClinTox/ESOL/Lipo are random-split, not scaffold). Worth checking all three of these
things — value, table, split — on every remaining entry, not just the value.

### All location notes corrected
- GROVER ×8: "Table 2"/"Table 3" → **Table 1** (single combined table, scaffold 8:1:1, mean of 3 seeds) ✅ applied
- ChemBERTa-2 ×4: "Table 2"/"Table 3" → **Table 1** (MLM-77M, DeepChem scaffold 80/10/10) ✅ applied
- ProtTrans ×4: "Table 2"/"Table 3" → **Table 4** (Q10) / **SOM Table 9** (CB513) ✅ applied

### Still outstanding — highest value next
1. ⛔ **Zhou et al. 2023 (Uni-Mol)** — 5 entries, **BLOCKED for me, needs you** (browser opens the PDF fine).
   Start with the CYP3A4 entry — it is structurally anomalous. See section 6.
2. **Hu et al. 2020 (GIN ContextPred)** — 2 entries · **Ying et al. 2021 (Graphormer)** — 2 · **Yang et al. 2019 (D-MPNN)** — 2 · **Zhang et al. 2023 (GearNet)** — 2
3. Twelve single-entry papers (AlphaFold2, ProteinMPNN, LigandMPNN, ESM-3, MSA Transformer, OpenFold, DiffDock, Evo, DNABERT-2, HyenaDNA, RXNMapper, Vilya-1, MPNN DTI)

### Suggested order of work

1. **Rong et al. 2020 (GROVER)** — 8 entries, and the paper's headline claim rests on them.
2. **Elnaggar et al. 2022 (ProtTrans)** — 4 entries, 2 already confirmed wrong; check the ProtBERT pair too.
3. **Lin et al. 2023 (ESM-2)** — 4 entries, all need removing or re-sourcing to a paper that actually ran CB513/DeepLoc.
4. **Wu et al. 2018 (MoleculeNet)** — 8 entries (ECFP4 + RDKit baselines). Should be quick; these are the original benchmark tables.
5. **Zhou et al. 2023 (Uni-Mol)** — 5 entries.
6. Then work down the list by entry count.

### If a value cannot be traced

Set the score to `N/A` and leave the model in the registry rather than guessing or keeping an unsourced number. The registry's value is that every displayed number is traceable; an N/A is honest, a plausible-looking wrong number is not.

---

# Round 2 (2026-07-18): remaining multi-entry papers

## 11. Hu et al., 2020 (GIN ContextPred) — 2 entries ✅ VERIFIED — BOTH CORRECTED

Paper: <https://doi.org/10.48550/arXiv.1905.12265> · arXiv PDF extracted

Table 1, ROC-AUC (%), scaffold split ("out-of-distribution prediction"). Registry row = **Supervised ContextPred**:

| Variant | BBBP | ClinTox |
|---|---|---|
| ContextPred | 68.0 | 65.9 |
| **Supervised ContextPred** | **68.7** | **72.6** |

| ✓ | Benchmark | Was | Now |
|---|---|---|---|
| [x] | BBBP | `0.706` | **`0.687`** — matched no row; note also said Table 3, actually **Table 1** |
| [x] | ClinTox | `0.788` | **`0.726`** — matched no row |

## 12. Ying et al., 2021 (Graphormer) — 2 entries ✅ VERIFIED — 1 CORRECTED

Paper: <https://doi.org/10.48550/arXiv.2106.05234> · arXiv PDF extracted

| ✓ | Benchmark | Was | Now | Source |
|---|---|---|---|---|
| [x] | ogbg-molhiv | `0.8645` | **`0.8051`** | Table 3: Graphormer-FLAG = **80.51 ± 0.53** |
| [x] | PCQM4M | `0.1234` | `0.1234` | ✅ Table 1 correct — but it is **validate MAE**, now labelled as such (train MAE = 0.0582) |

## 13. Zhang et al., 2023 (GearNet) — 2 entries ✅ VERIFIED — BOTH CORRECTED

Paper: <https://doi.org/10.48550/arXiv.2203.06125> · arXiv PDF extracted

| Variant | EC | GO-BP | GO-MF | GO-CC |
|---|---|---|---|---|
| GearNet | 0.730 | 0.356 | 0.503 | 0.414 |
| **GearNet-Edge** | **0.810** | **0.403** | 0.580 | **0.450** |
| GearNet-Edge-IEConv | 0.810 | 0.400 | 0.581 | 0.430 |

| ✓ | Benchmark | Was | Now |
|---|---|---|---|
| [x] | EC | `0.812` | **`0.810`** — GearNet-Edge; variant now named (plain GearNet = 0.730) |
| [x] | GO-BP | `0.450` | **`0.403`** — ❗ **column shift**: 0.450 is the **GO-CC** column |

## 14. 🚨 Two DOIs pointed at completely unrelated papers

The most serious provenance defect found in the whole audit. Both are now corrected.

| Model | Stored DOI | What that DOI actually is |
|---|---|---|
| **MSA Transformer** | `arXiv 2102.07556` | *"Gaussian distributions on Riemannian symmetric spaces in the large N limit"* — differential geometry |
| **OpenFold** | `arXiv 2311.01843` | *"Adaptive Assistance with an Active and Soft Back-Support Exosuit…"* — wearable robotics |

Both were confirmed by downloading the PDFs and by querying the arXiv API. Corrected to:

- MSA Transformer → **bioRxiv 10.1101/2021.02.12.430858** (ICML 2021, PMLR 139:8844–8856) — no arXiv version exists
- OpenFold → **bioRxiv 10.1101/2022.11.20.517210** — no arXiv version exists

Registry and paper bibliography both updated. **The underlying score values for these two remain UNVERIFIED.**

## ⛔ Still outstanding

**Values not yet checked (~24 entries).** PDF text extraction succeeded but the specific result tables
could not be isolated for: DiffDock (38.2%), DNABERT-2 (0.668), HyenaDNA (0.740), Vilya-1 (0.85).
Vilya-1 **is a real paper** (arXiv 2607.09998, Vilya Research) reporting ring-RMSD macrocycle conformer
prediction, consistent with the stored metric — the exact value still needs confirming.

**Journal-only, not attempted** (likely need institutional access): AlphaFold2 (0.924), ProteinMPNN
(0.524), LigandMPNN (0.570), ESM-3 (0.52 pTM), Evo (0.820), RXNMapper (0.982), MPNN DTI / DeepDTA (0.878),
MSA Transformer (0.570), OpenFold (0.780).


---

## 15. Systematic DOI resolution check (2026-07-18)

Every citation identifier in the registry and the paper bibliography was resolved against the
**arXiv API** and the **CrossRef API** and compared with the paper it claims to cite.

**Result: 3 wrong DOIs found in total across the whole audit. All three now corrected.**

| Model | Stored DOI | What it actually resolved to | Corrected to |
|---|---|---|---|
| MSA Transformer | `arXiv 2102.07556` | *Gaussian distributions on Riemannian symmetric spaces in the large N limit* | `10.1101/2021.02.12.430858` (ICML 2021, PMLR 139:8844–8856) |
| OpenFold | `arXiv 2311.01843` | *Adaptive Assistance with an Active and Soft Back-Support Exosuit…* | `10.1101/2022.11.20.517210` |
| **ProstT5** | `10.1093/bioinformatics/btad506` | ***StarPep Toolbox: an open-source software to assist chemical…*** | `10.1093/nargab/lqae150` (NAR Genomics and Bioinformatics **6**, lqae150, 2024) |

### Everything else resolves correctly

**12/12 arXiv DOIs ✅** — 1905.12265 (Hu/GIN), 1911.04738 (SMILES Transformer), 2007.02835 (GROVER),
2010.09885 (ChemBERTa), 2106.05234 (Graphormer), 2203.06125 (GearNet), 2209.01712 (ChemBERTa-2),
2210.01776 (DiffDock), 2301.06568 (Ankh), 2306.15006 (DNABERT-2), 2306.15794 (HyenaDNA),
2607.09998 (Vilya-1).

**14/14 journal DOIs ✅** — Chemprop, AlphaFold2, LigandMPNN, MolCLR, MolFormer, MoleculeNet, DeepDTA,
MSA Transformer (fixed), OpenFold (fixed), ProtTrans, RXNMapper, ProteinMPNN, Evo, ESM-3.

**Bibliography-only DOIs ✅** — Rogers2010 (ECFP), Lin2023 (ESM-2), Heinzinger2019 (SeqVec),
Huang2021 (TDC), Hu2021 (OGB).

**URLs ✅** — Uni-Mol OpenReview forum, TDC ADMET leaderboard.

### Note on the pattern

All three bad DOIs were for papers with **no arXiv version** (MSA Transformer, OpenFold and ProstT5 all
published via bioRxiv/journal routes). Two were plausible-looking but fabricated arXiv IDs; the third was
a real DOI belonging to an unrelated paper in a nearby journal. **A quick sanity check worth keeping:
before trusting a `10.48550/arXiv.*` DOI, confirm the paper was ever on arXiv at all.**
