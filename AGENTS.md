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
* **Registry & Filter Sidebar**: Fully searchable directory filtering by biological modality, license, representation type, and input format.
* **Selection Wizard**: Rules recommending optimal representations based on targets, datasets, and hardware budgets.
* **Interactive SVG Scatter Plot**: Maps embedding dimension size (log-scale X-axis) against scores (linear Y-axis) with custom hover tooltips.
* **Dynamic Table Sorting**: Both Molecule and Protein tables are sortable in ascending/descending order with indicators.
* **JSON GET API Route**: `/api/representations` allows dynamic programmatic representation lookups.

