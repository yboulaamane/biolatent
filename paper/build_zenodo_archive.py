"""Build a deterministic Zenodo-ready BioLatent benchmark data deposit."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026.09.16"
RELEASE_DATE = "2026-09-16"
ARCHIVE_ROOT = f"biolatent-benchmark-{VERSION}"
OUTPUT = ROOT / "dist" / f"biolatent-benchmark-{RELEASE_DATE}.zip"
FIXED_TIME = (2026, 9, 16, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def required_files() -> list[Path]:
    files = [
        ROOT / name
        for name in (
            "README.md",
            "STUDY.md",
            "DATA_PROVENANCE_AUDIT.md",
            "LICENSE",
            "CITATION.cff",
        )
    ]
    for optional in ("BENCHMARK_PROPOSAL.md", "BENCHMARK_VERIFICATION.md"):
        path = ROOT / optional
        if path.exists():
            files.append(path)
    files.extend(sorted((ROOT / "benchmark").glob("*.py")))
    files.extend(sorted((ROOT / "benchmark").glob("*.sh")))
    files.append(ROOT / "benchmark" / "requirements.txt")
    files.extend(sorted((ROOT / "results").glob("*.json")))
    files.extend(sorted((ROOT / "results" / "predictions").glob("*.npz")))
    files.extend(
        [
            ROOT / "paper" / "generate_figures.py",
            ROOT / "paper" / "generate_manuscript.py",
            ROOT / "paper" / "FIGURE_LEGENDS.md",
            ROOT / "paper" / "BioLatent_methods_revised.docx",
        ]
    )
    files.extend(sorted((ROOT / "paper" / "figures").glob("*.png")))
    files.extend(sorted((ROOT / "paper" / "figures").glob("*.svg")))
    files.extend(sorted((ROOT / "paper" / "figure_data").glob("*.csv")))
    missing = [path for path in files if not path.is_file()]
    if missing:
        names = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Required deposit files are missing:\n{names}")
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def release_summary() -> tuple[int, int, int, dict[str, tuple[int, int]]]:
    results = json.loads((ROOT / "results" / "benchmark_results.json").read_text())
    paired = json.loads((ROOT / "results" / "paired_comparisons.json").read_text())
    model_ids = {
        model for task in results.values() for model in task["models"]
    }
    cells = sum(len(task["models"]) for task in results.values())
    counts: dict[str, tuple[int, int]] = {}
    for modality in ("molecule", "protein", "genomics"):
        task_names = [
            name for name, task in results.items() if task["modality"] == modality
        ]
        comparisons = [
            value
            for name in task_names
            for value in paired[name]["comparisons"].values()
        ]
        resolved = sum(
            bool(value.get("significant_global", value["significant"]))
            for value in comparisons
        )
        counts[modality] = (resolved, len(comparisons))
    return len(results), len(model_ids), cells, counts


def zenodo_readme() -> bytes:
    tasks, models, cells, counts = release_summary()
    text = f"""# BioLatent benchmark data release {VERSION}

This deposit is the publication companion for **What can a frozen-embedding
benchmark resolve? A validation-selected, uncertainty-aware comparison of
molecular, protein and genomic representations**.

## Release scope

- {tasks} real-data tasks, {models} frozen representations and {cells} measured model-task cells.
- Study-wide Holm-resolved comparisons: {counts['molecule'][0]}/{counts['molecule'][1]} molecular, {counts['protein'][0]}/{counts['protein'][1]} protein and {counts['genomics'][0]}/{counts['genomics'][1]} genomic.
- Complete aggregate result JSON and per-example compressed prediction arrays.
- Publication figures in PNG and editable SVG form, plotted source data in CSV form, complete legends and the generated DOCX manuscript.
- Evaluation, inference, validation and figure-generation source code.

## Directory guide

- `results/`: benchmark scores, paired comparisons, sensitivity analyses,
  exposure proxies, run manifest and per-example predictions.
- `paper/figure_data/`: exact source tables plotted in every figure.
- `paper/figures/`: 300 dpi PNG and vector SVG publication figures.
- `paper/BioLatent_methods_revised.docx`: generated manuscript.
- `benchmark/` and `paper/*.py`: reproducibility and release-generation code.
- `MANIFEST.json` and `SHA256SUMS.txt`: file inventory and integrity hashes.
- `zenodo_metadata.json`: suggested Zenodo deposit metadata.

## Data provenance and redistribution

The benchmark uses public experimental/curated datasets from MoleculeNet,
Therapeutics Data Commons, DeepLoc 2.0, TAPE and the Nucleotide Transformer task
suite; the benchmark inputs are not synthetic. Raw third-party datasets and
pretrained embedding matrices are intentionally not redistributed in this
archive; `DATA_PROVENANCE_AUDIT.md`, `STUDY.md` and the pinned download code
describe how to retrieve and verify them. This avoids silently relicensing
upstream data while keeping the complete derived measurements reproducible.

The MolCLR-ClinTox model-task cell is N/A because its native featurizer cannot
represent every retained structure; it is not imputed.

## Reproduction

Create the pinned Python environment described in `README.md`, regenerate the
datasets and embeddings, then run the evaluation commands listed there. To
regenerate publication outputs from the committed results:

```bash
python paper/generate_figures.py
python paper/generate_manuscript.py
python paper/build_zenodo_archive.py
```

The code and original project documentation are licensed under MIT. Upstream
datasets and pretrained models remain subject to their respective source terms.
"""
    return text.encode("utf-8")


def zenodo_metadata() -> bytes:
    metadata = {
        "metadata": {
            "title": (
                "BioLatent: validation-selected, uncertainty-aware frozen-embedding "
                "benchmark data"
            ),
            "upload_type": "dataset",
            "publication_date": RELEASE_DATE,
            "version": VERSION,
            "creators": [
                {
                    "name": "Boulaamane, Yassir",
                    "affiliation": "Universitat Autònoma de Barcelona",
                }
            ],
            "description": (
                "Publication companion containing derived benchmark results, per-example "
                "predictions, figure source data, publication figures, the generated "
                "manuscript and reproducibility code for nine real-data molecular, protein "
                "and genomic tasks evaluated under one frozen-embedding protocol."
            ),
            "access_right": "open",
            "license": "MIT",
            "keywords": [
                "frozen embeddings",
                "molecular representations",
                "protein language models",
                "genomic foundation models",
                "benchmark uncertainty",
                "paired randomisation",
            ],
            "related_identifiers": [
                {
                    "identifier": "https://github.com/yboulaamane/biolatent",
                    "relation": "isSupplementTo",
                    "resource_type": "software",
                }
            ],
        }
    }
    return (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{name}", date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build() -> None:
    source_files = required_files()
    payload = {
        path.relative_to(ROOT).as_posix(): path.read_bytes() for path in source_files
    }
    payload["README_ZENODO.md"] = zenodo_readme()
    payload["zenodo_metadata.json"] = zenodo_metadata()

    manifest = {
        "release": VERSION,
        "created": RELEASE_DATE,
        "archive_root": ARCHIVE_ROOT,
        "files": [
            {"path": name, "bytes": len(data), "sha256": sha256(data)}
            for name, data in sorted(payload.items())
        ],
    }
    payload["MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    checksums = "".join(
        f"{sha256(data)}  {name}\n" for name, data in sorted(payload.items())
    )
    payload["SHA256SUMS.txt"] = checksums.encode("utf-8")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w") as archive:
        for name, data in sorted(payload.items()):
            write_member(archive, name, data)

    archive_hash = sha256(OUTPUT.read_bytes())
    print(f"Wrote {OUTPUT}")
    print(f"Files: {len(payload)}")
    print(f"Size: {OUTPUT.stat().st_size:,} bytes")
    print(f"SHA-256: {archive_hash}")


if __name__ == "__main__":
    build()
