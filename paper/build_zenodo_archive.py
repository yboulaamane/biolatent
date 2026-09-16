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
    files = [ROOT / "LICENSE"]
    files.extend(sorted((ROOT / "results").glob("*.json")))
    files.extend(sorted((ROOT / "results" / "predictions").glob("*.npz")))
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

Data accompanying **BioLatent: An Uncertainty-Aware Benchmark of Frozen
Molecular, Protein, and Genomic Representations**.

## Release scope

- {tasks} real-data tasks, {models} frozen representations and {cells} measured model-task cells.
- Study-wide Holm-resolved comparisons: {counts['molecule'][0]}/{counts['molecule'][1]} molecular, {counts['protein'][0]}/{counts['protein'][1]} protein and {counts['genomics'][0]}/{counts['genomics'][1]} genomic.
- Aggregate result JSON, per-example compressed prediction arrays and figure source CSVs.

## Directory guide

- `results/`: benchmark scores, paired comparisons, sensitivity analyses,
  exposure proxies, run manifest and per-example predictions.
- `paper/figure_data/`: exact source tables plotted in every figure.
- `SHA256SUMS.txt`: file integrity hashes.

## Data provenance and redistribution

The benchmark uses public experimental/curated datasets from MoleculeNet,
Therapeutics Data Commons, DeepLoc 2.0, TAPE and the Nucleotide Transformer task
suite; the benchmark inputs are not synthetic. Raw third-party datasets and
pretrained embedding matrices are intentionally not redistributed in this
archive. Provenance documentation and pinned reproduction code are maintained at
https://github.com/yboulaamane/biolatent.

The MolCLR-ClinTox model-task cell is N/A because its native featurizer cannot
represent every retained structure; it is not imputed.

BioLatent code is licensed under MIT. Upstream datasets and pretrained models
remain subject to their respective source terms.
"""
    return text.encode("utf-8")


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
