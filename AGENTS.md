<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# BioLatent Platform Memory Log

This log registers the core design rules, constraints, and features established during development for future agent sessions.

## 1. Design & Branding Philosophy
* **Minimalist Aesthetic**: The user explicitly requested a clean, minimalist layout with NO heavy AI-generated illustrations. 
* **Logo & Favicon**: Logo is a clean, code-only inline vector SVG of a chemical benzene ring. Favicon is configured in `src/app/icon.svg`.
* **Dark Mode Theme**: Built using a premium glassmorphic dark palette (deep slate/navy backgrounds, HSL indigo/violet accents, transparent cards).

## 2. Scientific Data Integrity
* **NO Placeholder Scores**: All benchmark scores in `embeddings.ts` must correspond to real, peer-reviewed scores published in their source papers or official databases (TDC, MoleculeNet, FLIP).
* **Missing Scores (N/A)**: If a model was not evaluated on a task (e.g. structural models like AlphaFold 2 on 2D property classifiers), report `N/A`. Do not synthesize values to fill empty grid fields.

## 3. Implemented Features
* **Measured Benchmark tab (landing tab)**: Renders the frozen-embedding study from `results/*.json` via `src/app/data/study.ts` and `src/app/components/StudyTab.tsx`. Scores, 95% intervals, paired-bootstrap verdicts against each task leader, ESM-2 scale ladders and the leakage audit. **Never mix these with registry values** — these were measured here, registry values were transcribed from papers under incompatible protocols. Headline counts (45 cells, 6/24, 10/10) are *computed* from the JSON, never hardcoded, so they cannot go stale when the study is re-run.
* **Registry & Filter Sidebar**: Fully searchable directory filtering by biological modality, license, representation type, and input format.
* **Selection Wizard**: Rules recommending optimal representations based on targets, datasets, and hardware budgets.
* **Interactive SVG Scatter Plot**: Maps embedding dimension size (log-scale X-axis) against scores (linear Y-axis) with custom hover tooltips.
* **Dynamic Table Sorting**: Both Molecule and Protein tables are sortable in ascending/descending order with indicators.
* **JSON GET API Route**: `/api/representations` allows dynamic programmatic representation lookups.

## 4. Active Benchmarking Vision (Frozen Embedding Suite)
* **Architecture Proposal**: Documented in `BENCHMARK_PROPOSAL.md`.
* **Concept**: Transition BioLatent from a literature registry to an active benchmarking suite using **Frozen Embedding Probing** (separating inference from evaluation).
* **Multi-Modal Task Suite**: 9 curated tasks across Molecules (BBBP, ClinTox, BACE, ESOL, Lipophilicity, CYP3A4), Proteins (DeepLoc, Fluorescence), and Genomics (Promoters). CB513 was dropped (per Design Decision D2 in `BENCHMARK_PROPOSAL.md`) in favour of a whole-protein regression task so the entire suite uses one per-object probing harness.
* **Zero Infrastructure Cost**: Evaluation requires < 90s on CPU per submission, run via GitHub Actions on hosted Hugging Face Datasets.


