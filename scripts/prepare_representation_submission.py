#!/usr/bin/env python3
"""Validate a registry submission issue and add it to the TypeScript registry.

The script accepts only JSON produced by the public submission form. It never
executes submitted content, and it rejects benchmark claims because those
require manual source-level curation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


ISSUE_MARKER = "<!-- biolatent-representation-submission:v1 -->"
REGISTRY_MARKER = "\n];\n\n// Provenance is a build-time invariant"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
REPRESENTATION_TYPES = {
    "learned_embedding",
    "fixed_descriptor",
    "hybrid_representation",
}
MODALITIES = {"molecule", "protein", "complex", "reaction", "nucleic_acid"}
INPUT_TYPES = {
    "SMILES",
    "graph",
    "sequence",
    "3D",
    "engineered_features",
    "Pocket/3D",
    "reaction_smiles",
}
COMPUTE_PROFILES = {"cpu", "gpu", "mixed"}
BASE_KEYS = {
    "id",
    "name",
    "developer",
    "representationType",
    "modality",
    "inputRepresentation",
    "license",
    "yearReleased",
    "computeProfile",
    "codeRepositoryUrl",
    "weightsUrl",
    "paperUrl",
    "benchmarks",
    "tags",
    "codeSnippet",
}
TYPE_KEYS = {
    "learned_embedding": {
        "architectureType",
        "pretrainingObjective",
        "embeddingDimension",
        "trainingData",
    },
    "fixed_descriptor": {
        "descriptorFamily",
        "algorithmType",
        "vectorType",
        "dimensionality",
    },
    "hybrid_representation": {"embeddingDimension", "components"},
}


class SubmissionError(ValueError):
    """A validation failure that can be reported safely to the contributor."""


def require_text(value: object, field: str, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SubmissionError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise SubmissionError(f"{field} exceeds {maximum} characters")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise SubmissionError(f"{field} must be a single line")
    return value


def require_url(value: object, field: str) -> str:
    url = require_text(value, field, maximum=500)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SubmissionError(f"{field} must be a complete https:// URL")
    return url


def require_integer(value: object, field: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SubmissionError(f"{field} must be an integer")
    if value < lower or value > upper:
        raise SubmissionError(f"{field} must be between {lower} and {upper}")
    return value


def parse_issue(body: str) -> dict[str, object]:
    if ISSUE_MARKER not in body:
        raise SubmissionError("the BioLatent submission marker is missing")
    match = re.search(r"```json\s*(\{.*?\})\s*```", body, flags=re.DOTALL)
    if not match:
        raise SubmissionError("the issue must contain one fenced JSON object")
    try:
        entry = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise SubmissionError(f"the JSON payload is invalid: {error.msg}") from error
    if not isinstance(entry, dict):
        raise SubmissionError("the JSON payload must be an object")
    return entry


def validate_entry(entry: dict[str, object]) -> dict[str, object]:
    representation_type = require_text(
        entry.get("representationType"), "representationType"
    )
    if representation_type not in REPRESENTATION_TYPES:
        raise SubmissionError("representationType is not supported")

    allowed_keys = BASE_KEYS | TYPE_KEYS[representation_type]
    unknown = sorted(set(entry) - allowed_keys)
    if unknown:
        raise SubmissionError(f"unexpected fields: {', '.join(unknown)}")

    required_base = BASE_KEYS - {"weightsUrl", "paperUrl"}
    missing = sorted(required_base - set(entry))
    if missing:
        raise SubmissionError(f"missing required fields: {', '.join(missing)}")

    identifier = require_text(entry.get("id"), "id", maximum=64)
    if not ID_PATTERN.fullmatch(identifier):
        raise SubmissionError("id must contain only lowercase letters, digits and underscores")
    require_text(entry.get("name"), "name", maximum=150)
    require_text(entry.get("developer"), "developer", maximum=200)
    require_text(entry.get("license"), "license", maximum=100)
    require_integer(entry.get("yearReleased"), "yearReleased", 1990, 2100)

    modality = require_text(entry.get("modality"), "modality")
    if modality not in MODALITIES:
        raise SubmissionError("modality is not supported")
    input_type = require_text(entry.get("inputRepresentation"), "inputRepresentation")
    if input_type not in INPUT_TYPES:
        raise SubmissionError("inputRepresentation is not supported")
    compute = require_text(entry.get("computeProfile"), "computeProfile")
    if compute not in COMPUTE_PROFILES:
        raise SubmissionError("computeProfile must be cpu, gpu or mixed")

    require_url(entry.get("codeRepositoryUrl"), "codeRepositoryUrl")
    for optional_url in ("weightsUrl", "paperUrl"):
        if optional_url in entry:
            require_url(entry[optional_url], optional_url)

    if entry.get("benchmarks") != []:
        raise SubmissionError(
            "community submissions cannot add benchmark claims; submit an empty benchmarks array"
        )
    tags = entry.get("tags")
    if not isinstance(tags, list) or not 1 <= len(tags) <= 12:
        raise SubmissionError("tags must contain between 1 and 12 values")
    for index, tag in enumerate(tags):
        require_text(tag, f"tags[{index}]", maximum=60)
    require_text(entry.get("codeSnippet"), "codeSnippet", maximum=5000)

    missing_type_fields = sorted(TYPE_KEYS[representation_type] - set(entry))
    if missing_type_fields:
        raise SubmissionError(
            f"missing {representation_type} fields: {', '.join(missing_type_fields)}"
        )

    if representation_type == "learned_embedding":
        require_text(entry.get("architectureType"), "architectureType", maximum=150)
        require_text(
            entry.get("pretrainingObjective"), "pretrainingObjective", maximum=300
        )
        require_integer(entry.get("embeddingDimension"), "embeddingDimension", 1, 1_000_000)
        training_data = entry.get("trainingData")
        if not isinstance(training_data, dict):
            raise SubmissionError("trainingData must be an object")
        allowed_training = {"name", "size", "license"}
        if set(training_data) != allowed_training:
            raise SubmissionError("trainingData must contain name, size and license")
        for key in sorted(allowed_training):
            require_text(training_data.get(key), f"trainingData.{key}", maximum=300)
    elif representation_type == "fixed_descriptor":
        require_text(entry.get("descriptorFamily"), "descriptorFamily", maximum=200)
        if entry.get("algorithmType") not in {"hashed", "rule-based", "physicochemical"}:
            raise SubmissionError("algorithmType is not supported")
        if entry.get("vectorType") not in {"binary", "count", "continuous"}:
            raise SubmissionError("vectorType is not supported")
        require_integer(entry.get("dimensionality"), "dimensionality", 1, 1_000_000)
    else:
        require_integer(entry.get("embeddingDimension"), "embeddingDimension", 1, 1_000_000)
        components = entry.get("components")
        if not isinstance(components, dict):
            raise SubmissionError("components must be an object")
        if set(components) != {"learnedModel", "descriptorsUsed", "fusionMethod"}:
            raise SubmissionError(
                "components must contain learnedModel, descriptorsUsed and fusionMethod"
            )
        require_text(components.get("learnedModel"), "components.learnedModel", maximum=200)
        descriptors = components.get("descriptorsUsed")
        if not isinstance(descriptors, list) or not descriptors:
            raise SubmissionError("components.descriptorsUsed must be a non-empty list")
        for index, descriptor in enumerate(descriptors):
            require_text(
                descriptor, f"components.descriptorsUsed[{index}]", maximum=150
            )
        if components.get("fusionMethod") not in {
            "concatenation",
            "projection",
            "attention",
            "ensemble",
        }:
            raise SubmissionError("components.fusionMethod is not supported")

    return entry


def update_registry(registry_path: Path, entry: dict[str, object]) -> None:
    source = registry_path.read_text()
    existing_ids = set(re.findall(r'\bid:\s*["\']([^"\']+)["\']', source))
    if entry["id"] in existing_ids:
        raise SubmissionError(f"a representation with id {entry['id']} already exists")
    existing_names = {
        value.casefold()
        for value in re.findall(r'\bname:\s*["\']([^"\']+)["\']', source)
    }
    if str(entry["name"]).casefold() in existing_names:
        raise SubmissionError(f"a representation named {entry['name']} already exists")

    marker_position = source.rfind(REGISTRY_MARKER)
    if marker_position < 0:
        raise SubmissionError("the registry insertion marker could not be found")
    serialized = json.dumps(entry, ensure_ascii=False, indent=2)
    indented = "  " + serialized.replace("\n", "\n  ")
    updated = source[:marker_position] + ",\n" + indented + source[marker_position:]
    registry_path.write_text(updated)


def write_github_output(path: Path | None, entry: dict[str, object]) -> None:
    if path is None:
        return
    with path.open("a") as handle:
        handle.write(f"submission_id={entry['id']}\n")
        handle.write(f"submission_name={entry['name']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body-file", type=Path, required=True)
    parser.add_argument("--registry-file", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    try:
        entry = validate_entry(parse_issue(args.body_file.read_text()))
        update_registry(args.registry_file, entry)
        write_github_output(args.github_output, entry)
    except (OSError, SubmissionError) as error:
        print(f"Submission rejected: {error}", file=sys.stderr)
        return 1

    print(f"Prepared registry entry {entry['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
