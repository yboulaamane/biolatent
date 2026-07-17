# BioLatent

An open-access registry, selection wizard, and interactive benchmark dashboard for chemical and biological vector representations.

[![Vercel Deployment](https://img.shields.io/badge/deploy-vercel-blueviolet)](https://vercel.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

In computer-aided drug discovery and computational biology, the landscape of foundation models (molecules, proteins, nucleic acids) has expanded rapidly. However, comparing representation dimensions, data budgets, and downstream performance remains fragmented. 

**BioLatent** is a unified, standardized index cataloging representations across five primary modalities: **Small Molecules**, **Proteins**, **Complexes**, **Chemical Reactions**, and **Nucleic Acids (DNA/RNA)**. 

### Key Features
1. **Interactive Registry**: Browse, filter, and search representations by modality, licensing, pretraining sizes, and compute requirements.
2. **Latent Finder Wizard**: A decision-support recommendation tool that guides researchers to the optimal vector embeddings based on target inputs, screening sizes, and hardware budgets.
3. **Interactive Benchmark Chart**: A log-scale SVG scatter plot mapping embedding dimensions against standard benchmarks (MoleculeNet BBBP classification for molecules, and Q3 accuracy on CB513 for proteins).
4. **Curated Methods & Citations**: Collapsible details providing direct links to primary literature papers (e.g. TDC, MoleculeNet, FLIP).
5. **Programmatic JSON API**: Exposes query-parameter filters to fetch representation metadata dynamically (e.g. `/api/representations?modality=protein`).

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
curl "https://your-domain.vercel.app/api/representations?modality=molecule&representationType=learned_embedding"
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
      "dataLeakageRisk": "high",
      "reproducibilityScore": 0.95,
      "domainGeneralization": "medium",
      "smallDataPerformance": "medium",
      "benchmarks": [
        { "dataset": "BBBP (Blood-Brain Barrier)", "metric": "ROC-AUC", "score": "0.690" },
        { "dataset": "ClinTox (FDA Approval / Tox)", "metric": "ROC-AUC", "score": "0.805" },
        { "dataset": "CYP3A4 Substrate (TDC)", "metric": "ROC-AUC", "score": "0.655" },
        { "dataset": "ESOL Solubility", "metric": "RMSE", "score": "0.850" },
        { "dataset": "Lipophilicity", "metric": "RMSE", "score": "0.680" }
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

## Curation Methodology & Safety Rubrics

To maintain reproducibility and clinical safety standards, representation properties are indexed against the following criteria:

* **Data Leakage Risk**: Evaluated based on whether train/test splits in downstream evaluations utilize sequence identity clustering (for proteins) or Bemis-Murcko scaffold clustering (for molecules) to prevent structural leakage.
* **Reproduction Index**: Assesses availability of open-source model weights, inference scripts, and environments (0.0 to 1.0).
* **Generalization**: Determined by model performance across out-of-distribution drug-discovery cohorts.

---

## Citation

If you use BioLatent in your research, please cite:

```bibtex
@article{boulaamane2026biolatent,
  title={BioLatent: An Interactive Registry and Selection Wizard for Biological and Molecular Representations},
  author={Boulaamane, Yassir and contributors},
  journal={Bioinformatics},
  volume={xx},
  pages={xx},
  year={2026},
  publisher={Oxford University Press}
}
```
