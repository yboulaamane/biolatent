# Remaining verification — 19 entries, 14 papers

> Updated 2026-07-18 after round 3. MSA Transformer is now **done** (was 0.570 → corrected to 0.448;
> the stored value appeared nowhere in the paper and the metric label was wrong too).
>
> **All 'paywalled' PDFs turned out to be freely downloadable.** The blocker is not access — it is that
> these particular PDFs render their tables as images or use font encodings my text extractor cannot read.
> You will be able to read every one of them by eye without trouble.

Direct PDF links where they exist. For each entry check **three** things, not just the value:

1. **Value** — does the number appear in the paper?
2. **Table** — which table/figure is it in? (wrong table numbers were found in 6 of 13 papers checked)
3. **Split** — scaffold or random? (3 of 6 regression sources turned out to be random-split)

Also check **which model variant** the row belongs to — variant/column mix-ups accounted for 5 errors so far.

---

## 🔴 Priority 1 — Uni-Mol (5 entries, blocked for me, holds top of both regression columns)

**PDF: https://openreview.net/pdf?id=6K2RM6wVqKu**
Forum: https://openreview.net/forum?id=6K2RM6wVqKu

| Benchmark | Stored | What to check |
|---|---|---|
| BBBP | `0.751` | value, table, split |
| ClinTox | `0.932` | value, table, split |
| **CYP3A4** | `0.725` | ⚠️ **search the PDF for "CYP" and "TDC" — if absent, delete this entry** |
| **ESOL** | `0.550` | ⚠️ **scaffold or random?** currently leads the column |
| **Lipophilicity** | `0.510` | ⚠️ **scaffold or random?** currently leads the column |

> CYP3A4 = 0.725 exceeds the maximum score on the entire TDC CYP3A4 leaderboard (0.667). Five independent
> signals say it isn't real. This is the single most likely deletion in the registry.

---

## 🟠 Priority 2 — arXiv, free PDFs, tables my extractor couldn't read

| Model | Benchmark | Stored | Direct PDF |
|---|---|---|---|
| DiffDock | PDBBind Top-1 % RMSD < 2 Å | `38.2%` | https://arxiv.org/pdf/2210.01776 |
| DNABERT-2 | GUE Average F1 | `0.668` | https://arxiv.org/pdf/2306.15006 |
| HyenaDNA | GenomicBenchmarks Avg Accuracy | `0.740` | https://arxiv.org/pdf/2306.15794 |
| Vilya-1 | Macrocycle NMR median heavy-atom RMSD (Å) | `0.85` | https://arxiv.org/pdf/2607.09998 |

> All four PDFs download fine — the result tables just didn't survive text extraction. Should be quick by eye.
> Vilya-1 is confirmed a real paper (*"An all-atom foundation model for macrocycle structure prediction and design"*);
> check whether the stored metric matches what they report (they discuss **ring RMSD**, and panel C is solution-NMR structures).

---

## 🟡 Priority 3 — free preprints (bioRxiv)

| Model | Benchmark | Stored | Direct PDF |
|---|---|---|---|
| ~~MSA Transformer~~ | ~~Contact Prediction~~ | ~~`0.570`~~ | ✅ **DONE** — corrected to `0.448` |
| OpenFold | CAMEO TM-score | `0.780` | https://www.biorxiv.org/content/10.1101/2022.11.20.517210v1.full.pdf |

> Both had **fabricated arXiv DOIs** pointing at unrelated papers (differential geometry, wearable robotics).
> DOIs fixed. MSA Transformer is now verified: `0.570` appeared **nowhere** in the paper, and the paper
> reports **long-range** contact precision only — there is no short-range table. Corrected to CASP13-FM
> top-L long-range = **0.448** (CAMEO top-L = 43.5). OpenFold's value is still unchecked.

---

## 🔵 Priority 4 — "paywalled" — but all eight have free routes (verified 2026-07-18)

Every DOI below was resolved against CrossRef/arXiv and confirmed to be the right paper.

| Model | Benchmark | Stored | Free full text |
|---|---|---|---|
| **D-MPNN** | BBBP ROC-AUC | `0.730` ⚠️ | **https://arxiv.org/pdf/1904.01561** |
| **D-MPNN** | ClinTox ROC-AUC | `0.906` | (same PDF) |
| **AlphaFold 2** | CASP14 Avg GDT-TS | `0.924` | **https://www.nature.com/articles/s41586-021-03819-2** — Nature, fully open access |
| **ProteinMPNN** | CATH Sequence Recovery | `0.524` | **https://doi.org/10.1101/2022.06.03.494563** — bioRxiv preprint |
| **LigandMPNN** | Protein-Ligand Seq Recovery | `0.570` | **https://doi.org/10.1101/2023.12.22.573103** — bioRxiv preprint |
| **ESM-3** | De novo generation Mean pTM | `0.52` | **https://doi.org/10.1101/2024.07.01.600583** — bioRxiv preprint |
| **Evo** | FLIP zero-shot Spearman ρ | `0.820` | **https://doi.org/10.1101/2024.02.27.582234** — bioRxiv preprint |
| **RXNMapper** | USPTO Atom Mapping Accuracy | `0.982` | **https://www.science.org/doi/10.1126/sciadv.abe4166** — *Science Advances*, fully open access |
| **DeepDTA** (MPNN DTI) | Davis Concordance Index | `0.878` | **https://arxiv.org/pdf/1801.10193** |

**bioRxiv tip:** the DOI link lands on the abstract page; the PDF is the "Download PDF" button, or append
`v1.full.pdf` to the article URL.

> ⚠️ **D-MPNN BBBP has a known conflict to settle.** Chemprop's tables are not machine-readable by
> extraction, but ChemBERTa (Chithrananda et al. 2020) independently reports **D-MPNN BBBP = 0.708** under
> DeepChem scaffold split, against our stored `0.730`. ClinTox `0.906` matches their reproduction exactly.
> The JCIM/arXiv tables will settle it — a human reading the PDF will see them fine even though extraction failed.

> **Note on the Science papers** (ProteinMPNN, ESM-3, Evo): preprint values occasionally differ from the
> final published version. If a number differs, prefer the published one and note the discrepancy.

---

## What to send back

For each entry, either **OK**, or the corrected value plus the table number and split. Also flag anything
where the paper doesn't run that benchmark at all — that has been the single most common defect
(7 of 17 removals were "the cited paper never evaluated this").
