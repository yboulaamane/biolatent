#!/usr/bin/env python3
"""Build the descriptive literature-to-measured comparison artefact.

The literature registry is intentionally broader than the measured benchmark.
Only records with the same named representation family, endpoint and
performance measure are matched. The resulting values remain descriptive
because dataset preparation, the exact partition and the fitted predictor can
differ between publications.
"""

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "src" / "app" / "data" / "embeddings.ts"
MEASURED = ROOT / "results" / "benchmark_results.json"
OUTPUT = ROOT / "results" / "literature_measured_comparison.json"
MANIFEST = ROOT / "results" / "run_manifest.json"

REPRESENTATION_MAP = {
    "chemberta_77m": "chemberta_77m",
    "molclr": "molclr_gin",
    "grover_base": "grover_base",
    "grover_large": "grover_large",
    "uni_mol": "unimol_v1",
    "ecfp4_fingerprint": "ecfp4",
    "rdkit_descriptors": "rdkit2d",
    "molformer_xl": "molformer_xl",
}

DATASET_MAP = {
    "BBBP (Blood-Brain Barrier)": "BBBP",
    "ClinTox (FDA Approval / Tox)": "ClinTox",
    "BACE": "BACE",
    "ESOL Solubility": "ESOL",
    "Lipophilicity": "Lipophilicity",
    "CYP3A4 Substrate (TDC)": "CYP3A4",
}

MODEL_LABELS = {
    "chemberta_77m": "ChemBERTa-77M",
    "molclr_gin": "MolCLR GIN",
    "grover_base": "GROVER Base",
    "grover_large": "GROVER Large",
    "unimol_v1": "Uni-Mol v1",
    "ecfp4": "ECFP4",
    "rdkit2d": "RDKit2D",
    "molformer_xl": "MoLFormer-XL",
}


def field(pattern, line):
    match = re.search(pattern, line)
    return match.group(1) if match else None


def parse_registry():
    rows = []
    current_id = ""
    current_modality = ""
    for line in REGISTRY.read_text().splitlines():
        representation_id = field(r'^\s*id:\s*"([^"]+)"', line)
        if representation_id:
            current_id = representation_id
            current_modality = ""
        modality = field(r'^\s*modality:\s*"([^"]+)"', line)
        if modality:
            current_modality = modality
        if "dataset:" not in line or "metric:" not in line or "score:" not in line:
            continue
        dataset = field(r'dataset:\s*"([^"]+)"', line)
        metric = field(r'metric:\s*"([^"]+)"', line)
        score = field(r'score:\s*"([^"]+)"', line)
        short_ref = field(r'shortRef:\s*"([^"]+)"', line)
        doi = field(r'doi:\s*"([^"]+)"', line)
        note = field(r'note:\s*"([^"]+)"', line) or ""
        if not dataset or not metric or not score:
            raise RuntimeError(f"Could not parse registry benchmark row: {line}")
        lower_note = note.lower()
        partition = (
            "scaffold" if "scaffold" in lower_note
            else "random" if "random" in lower_note
            else "other or unstated"
        )
        rows.append({
            "registry_id": current_id,
            "modality": current_modality,
            "dataset": dataset,
            "metric": metric,
            "score": score,
            "source": short_ref,
            "source_url": doi,
            "note": note,
            "documented_partition": partition,
        })
    return rows


def ranks(values):
    """Return average ranks so the calculation remains valid if ties appear."""
    ordered = sorted(range(len(values)), key=values.__getitem__)
    output = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            output[index] = average_rank
        start = end
    return output


def pearson(left, right):
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left)
        * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator


def main():
    registry_rows = parse_registry()
    measured = json.loads(MEASURED.read_text())
    matches = []

    for row in registry_rows:
        measured_id = REPRESENTATION_MAP.get(row["registry_id"])
        measured_dataset = DATASET_MAP.get(row["dataset"])
        if not measured_id or not measured_dataset:
            continue
        dataset_results = measured.get(measured_dataset, {})
        model_result = dataset_results.get("models", {}).get(measured_id)
        if not model_result:
            continue
        measured_metric = model_result["linear"]["metric"]
        if row["metric"].casefold() != measured_metric.casefold():
            continue
        try:
            literature_score = float(row["score"])
        except ValueError as exc:
            raise RuntimeError(f"Non-numeric matched registry score: {row}") from exc
        measured_score = float(model_result["linear"]["score"])
        matches.append({
            "representation": MODEL_LABELS[measured_id],
            "registry_id": row["registry_id"],
            "measured_id": measured_id,
            "dataset": measured_dataset,
            "metric": measured_metric,
            "literature_score": literature_score,
            "measured_score": measured_score,
            "difference_measured_minus_literature": round(measured_score - literature_score, 4),
            "documented_literature_partition": row["documented_partition"],
            "literature_source": row["source"],
            "literature_source_url": row["source_url"],
            "literature_note": row["note"],
        })

    matches.sort(key=lambda row: (row["dataset"], row["representation"]))
    by_dataset = defaultdict(list)
    for match in matches:
        by_dataset[match["dataset"]].append(match)
    rank_concordance = {}
    for dataset, rows in sorted(by_dataset.items()):
        literature = [row["literature_score"] for row in rows]
        standardised = [row["measured_score"] for row in rows]
        rank_concordance[dataset] = {
            "n": len(rows),
            "spearman_rho": round(pearson(ranks(literature), ranks(standardised)), 3),
            "interpretation": "descriptive only; no inferential test was performed",
        }

    molecular_rows = [row for row in registry_rows if row["modality"] == "molecule"]
    partition_counts = Counter(row["documented_partition"] for row in registry_rows)
    molecular_partition_counts = Counter(row["documented_partition"] for row in molecular_rows)
    output = {
        "analysis_type": "descriptive registry-to-measured alignment",
        "matching_rule": (
            "Same named representation family, endpoint and performance measure; "
            "values were not pooled "
            "and no causal attribution or cross-study significance test was performed."
        ),
        "registry_summary": {
            "benchmark_records": len(registry_rows),
            "molecular_records": len(molecular_rows),
            "documented_partition_counts": dict(sorted(partition_counts.items())),
            "molecular_documented_partition_counts": dict(sorted(molecular_partition_counts.items())),
        },
        "matched_summary": {
            "pairs": len(matches),
            "measured_higher": sum(row["difference_measured_minus_literature"] > 0 for row in matches),
            "literature_higher": sum(row["difference_measured_minus_literature"] < 0 for row in matches),
            "equal": sum(row["difference_measured_minus_literature"] == 0 for row in matches),
            "documented_scaffold_pairs": sum(
                row["documented_literature_partition"] == "scaffold" for row in matches
            ),
        },
        "rank_concordance": rank_concordance,
        "matches": matches,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    manifest = json.loads(MANIFEST.read_text())
    manifest["public_artifacts"][OUTPUT.name] = hashlib.sha256(
        OUTPUT.read_bytes()
    ).hexdigest()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")
    print(f"Updated {MANIFEST}")


if __name__ == "__main__":
    main()
