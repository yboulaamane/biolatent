# BioLatent

An open-access registry, compatibility filter, and interactive benchmark dashboard for chemical and biological vector representations.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22813148.svg)](https://doi.org/10.5281/zenodo.22813148)

<img width="1862" height="976" alt="biolatent" src="https://github.com/user-attachments/assets/3bf8c24e-dd89-487d-8247-f41ed61815d3" />

---

## Overview

In computer-aided drug discovery and computational biology, the landscape of foundation models (molecules, proteins, nucleic acids) has expanded rapidly. However, comparing representation dimensions, data budgets, and downstream performance remains fragmented. 

**BioLatent** is a unified, provenance-aware index cataloging representations across five primary modalities: **Small Molecules**, **Proteins**, **Complexes**, **Chemical Reactions**, and **Nucleic Acids (DNA/RNA)**.

BioLatent began as a provenance-aware registry of representations and results reported in the literature. Those records showed that values assigned to the same endpoint often came from different datasets, splits, predictive models, and tuning procedures. They are useful as a catalogue but cannot be pooled into a controlled ranking. The later **Measured Benchmark** addresses this limitation by recomputing compatible frozen representations under one prespecified protocol. It reports uncertainty, validation-selected paired comparisons, split sensitivity, and pretraining input-exposure proxies. The two layers are connected through a descriptive analysis restricted to records with the same representation, endpoint, and metric; remaining protocol differences are retained explicitly and prevent causal attribution to any single design choice.

### Measured release snapshot

The benchmark snapshot was validated against its source data on 2026-09-20 and released as version 1.1.0. It contains **9 tasks, 18 representations, and 68 compatible model-task cells**. Every task uses an externally published dataset; missing or incompatible cells are never imputed. The complete data release is archived on Zenodo at [https://doi.org/10.5281/zenodo.22813148](https://doi.org/10.5281/zenodo.22813148).

| Modality | Tasks | Measured cells | Study-wide resolved/eligible comparisons |
|---|---:|---:|---:|
| Molecules | 6 | 53 | 14 of 47 |
| Proteins | 2 | 12 | 5 of 5; 5 Fluorescence comparisons descriptive |
| Genomics | 1 | 3 | 0 of 2 |

“Resolved” means that an eligible paired comparison with the validation-selected reference survived Holm correction across all 54 formal comparisons. Molecules are resampled by Bemis–Murcko scaffold and DeepLoc by MMseqs2 homology cluster. The five Fluorescence comparisons are descriptive because the related test variants form one connected component at the prespecified homology threshold. Unresolved does not mean equivalent, and scores from different metrics are not comparable. See [`STUDY.md`](STUDY.md) for the complete results and interpretation.

The molecular roster is ECFP4, RDKit2D, ChemBERTa-77M, ChemBERTa-ZINC, MoLFormer-XL, Uni-Mol v1, MolCLR GIN, and GROVER Base/Large. MolCLR is intentionally N/A on ClinTox because its official featurizer cannot represent every structure; no molecule was removed or rewritten to force that cell. Supervised task-trained systems such as standard Chemprop and ChemXTree are outside the frozen-representation estimand, while Graphormer is deferred until its legacy official stack can be reproduced without approximation.

### Key Features
1. **Interactive Registry**: Browse, filter, and search representations by modality, licensing, pretraining sizes, and compute requirements.
2. **Compatibility Finder**: An objective catalog filter for modality, available input representation, and declared compute profile. It covers molecules, proteins, complexes, nucleic acids, and reactions; distinguishes catalogued inputs from structures derived from SMILES; and explains why each result matched. Results are alphabetical rather than ranked and must be validated on the user’s endpoint.
3. **Interactive Literature Chart**: A log-scale SVG scatter plot mapping embedding dimensions against selected literature-reported benchmarks. These heterogeneous values are descriptive and separate from the measured study.
4. **Curated Methods & Citations**: Collapsible details providing direct links to primary literature papers (e.g. TDC, MoleculeNet, FLIP).
5. **Programmatic JSON API**: Exposes query-parameter filters to fetch representation metadata dynamically (e.g. `/api/representations?modality=protein`).
6. **Reproducible Measured Study**: Imports public JSON artefacts produced by the benchmark scripts, with checkpoint revisions, dataset hashes, pooling, truncation, and software versions recorded in `results/run_manifest.json`.
7. **Audited Data Provenance**: Every measured task was compared with a fresh upstream copy, and every literature row carries source-level provenance. See [`DATA_PROVENANCE_AUDIT.md`](DATA_PROVENANCE_AUDIT.md).
8. **Reviewable Community Submissions**: The website prepares a structured GitHub issue. A repository workflow validates the metadata, builds the site, and opens a pull request for curator review.

---

## API Documentation

### GET `/api/representations`

Fetch all curated representations or filter them programmatically using query parameters.

#### Query Parameters
* `search` (string): Filters models by name, developer, or tags.
* `modality` (string): `molecule` | `protein` | `complex` | `reaction` | `nucleic_acid`
* `representationType` (string): `learned_embedding` | `fixed_descriptor` | `hybrid_representation`
* `inputRepresentation` (string): `SMILES` | `graph` | `sequence` | `3D` | `engineered_features` | `Pocket/3D` | `reaction_smiles`

#### Example Request
```bash
curl "https://biolatent.org/api/representations?search=ChemBERTa-2&modality=molecule&representationType=learned_embedding"
```

#### Example Response
```json
{
  "count": 1,
  "results": [
    {
      "id": "chemberta_77m",
      "name": "ChemBERTa-2 (77M MLM)",
      "representationType": "learned_embedding",
      "modality": "molecule",
      "inputRepresentation": "SMILES",
      "license": "MIT",
      "architectureType": "Transformer",
      "pretrainingObjective": "Masked Language Modeling (MLM) on SMILES tokens",
      "embeddingDimension": 384,
      "yearReleased": 2022,
      "trainingData": {
        "name": "PubChem10M / ZINC15",
        "size": "77M molecules",
        "license": "CC0 / Mixed"
      },
      "codeRepositoryUrl": "https://github.com/deepchem/deepchem",
      "weightsUrl": "https://huggingface.co/deepchem/ChemBERTa-77M-MLM",
      "computeProfile": "gpu",
      "benchmarks": [
        {
          "dataset": "BBBP (Blood-Brain Barrier)",
          "metric": "ROC-AUC",
          "score": "0.698",
          "citation": {
            "shortRef": "Ahmad et al., 2022",
            "doi": "https://doi.org/10.48550/arXiv.2209.01712",
            "note": "Table 1, MLM-77M, DeepChem scaffold split 80/10/10"
          }
        }
      ],
      "tags": ["BERT", "SMILES", "Transformers"],
      "codeSnippet": "..."
    }
  ]
}
```

---

## Local Development

1. **Install Dependencies**:
   ```bash
   npm install
   ```

2. **Run Development Server**:
   ```bash
   npm run dev
   ```

3. **Build Static & Dynamic Assets**:
   ```bash
   npm run build
   ```

---

## Community representation submissions

The **Submit Representation** form creates a complete registry payload and opens a prefilled GitHub issue. After the contributor confirms the issue, `.github/workflows/representation-submission.yml` validates the payload with `scripts/prepare_representation_submission.py`, rebuilds the website, and opens a pull request. The workflow never merges submissions automatically.

Community submissions add descriptive representation metadata only. They cannot add literature benchmark values or enter the measured benchmark. Benchmark claims require separate source-level provenance review, and measured inclusion requires a compatible adapter and a complete benchmark run.

Repository maintainers must allow GitHub Actions to create pull requests using the repository `GITHUB_TOKEN`. If that permission is disabled, the issue remains available for manual review but the automated pull request step cannot complete.

---

## Reproducing the measured study

The raw datasets and embedding matrices are regenerated locally and are intentionally not committed. Public outputs in `results/` drive both the manuscript and website.

Install the pinned main evaluation environment first. The supplied requirements target the CUDA 12.8 environment used for this release; CPU-only or other CUDA systems need the matching PyTorch wheel while retaining the recorded package versions where possible.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r benchmark/requirements.txt
```

Most Hugging Face checkpoints download automatically at their pinned revisions. Four molecular encoders use isolated compatibility environments or official external source trees:

| Encoder | Required configuration |
|---|---|
| MoLFormer-XL | Run `benchmark/setup_molformer_env.sh`, or provide the resulting interpreter at `~/biolatent_molformer_env/bin/python`. |
| Uni-Mol v1 | Set `BIOLATENT_UNIMOL_PYTHON` to an interpreter containing `unimol_tools==0.1.6`; the adapter verifies the official weight and dictionary hashes. |
| MolCLR GIN | Set `BIOLATENT_GRAPH_PYTHON` and `BIOLATENT_MOLCLR_SOURCE`; the source checkout and official checkpoint must match the revision and hash pinned in the adapter. |
| GROVER Base/Large | Set `BIOLATENT_GRAPH_PYTHON`, `BIOLATENT_GROVER_SOURCE`, and `BIOLATENT_GROVER_CHECKPOINT_DIR`; both official checkpoints are hash-verified. |

The exact source commits, checkpoint URLs, hashes, pooling policies, and expected dimensions are enforced in [`benchmark/embed.py`](benchmark/embed.py), [`benchmark/molclr_adapter.py`](benchmark/molclr_adapter.py), and [`benchmark/grover_adapter.py`](benchmark/grover_adapter.py). Environment variables override portable defaults under the current user's home directory; no machine-specific path is required.

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
python scripts/build_literature_comparison.py
python paper/generate_figures.py
python paper/generate_manuscript.py
python paper/build_zenodo_archive.py
```

The figure generator writes publication-resolution PNG and editable SVG panels to `paper/figures/`, their plotted source values to `paper/figure_data/`, and complete legends to `paper/FIGURE_LEGENDS.md`. Figure 1 is maintained in the editable Draw.io source `paper/figures/figure1_study_design.drawio`; the generator checks its displayed release totals and preserves its PNG and SVG exports. The final manuscript is written to `paper/BioLatent_methods_revised.docx`. If the optional local `BioLatent_methods.docx` template is present it supplies the house style; a clean clone falls back to a standard Word document. The final command creates a versioned, checksum-verified Zenodo deposit under `dist/`; raw third-party datasets and embedding matrices are deliberately excluded and remain reproducible from their pinned sources.

MoLFormer requires its compatibility environment once:

```bash
bash benchmark/setup_molformer_env.sh /path/to/project/python
```

The full-hash release gate requires the regenerated embedding matrices and their sidecars. It reloads all nine datasets, checks split disjointness and provenance, verifies every matrix hash, and recomputes the ranked metric from the saved predictions. The committed public results can be inspected without downloading the local embedding cache.

## Curation methodology

Registry metadata are descriptive catalog fields, not empirical quality or clinical-validation scores.

* **Artifact availability** records whether code and/or weights are linked; it is not a reproducibility score.
* **Compute profile** is the declared CPU, GPU, or mixed execution category, not a runtime guarantee.
* **Reported benchmarks** retain a source link and row-level provenance note. Heterogeneous values are not pooled; the committed descriptive analysis matches only records with the same representation, endpoint, and metric.
* **Compatibility Finder** filters by modality, available input, and compute profile. It identifies catalogued or explicitly derivable input compatibility, lists matches alphabetically, and does not claim an optimal model.

---

## Citation

If you use BioLatent in your research, please cite:

```bibtex
@misc{boulaamane2026biolatent,
  title={BioLatent: A Standardised Benchmark of Frozen Molecular Representations with Protein and Genomic Extensions},
  author={Boulaamane, Yassir},
  year={2026},
  version={1.1.0},
  publisher={Zenodo},
  doi={10.5281/zenodo.22813148},
  url={https://doi.org/10.5281/zenodo.22813148}
}
```
