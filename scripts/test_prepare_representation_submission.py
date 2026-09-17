import copy
import tempfile
import unittest
from pathlib import Path

from scripts import prepare_representation_submission as submission


VALID_ENTRY = {
    "id": "example_representation",
    "name": "Example Representation",
    "developer": "Example Laboratory",
    "representationType": "learned_embedding",
    "modality": "molecule",
    "inputRepresentation": "SMILES",
    "license": "MIT",
    "yearReleased": 2026,
    "computeProfile": "gpu",
    "codeRepositoryUrl": "https://github.com/example/representation",
    "paperUrl": "https://doi.org/10.1000/example",
    "benchmarks": [],
    "tags": ["SMILES", "molecule"],
    "codeSnippet": "# Loading example pending curator review",
    "architectureType": "Transformer",
    "pretrainingObjective": "Masked structure modelling",
    "embeddingDimension": 512,
    "trainingData": {
        "name": "Example molecules",
        "size": "1 million molecules",
        "license": "CC0",
    },
}


def issue_body(entry):
    import json

    return (
        f"{submission.ISSUE_MARKER}\n"
        "## Representation metadata\n\n"
        f"```json\n{json.dumps(entry, indent=2)}\n```\n"
    )


class SubmissionTests(unittest.TestCase):
    def test_valid_entry_is_inserted_as_data(self):
        source = (
            "export const EMBEDDINGS = [\n"
            '  { id: "existing", name: "Existing Representation" }\n'
            "];\n\n// Provenance is a build-time invariant\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "embeddings.ts"
            path.write_text(source)
            entry = submission.validate_entry(copy.deepcopy(VALID_ENTRY))
            submission.update_registry(path, entry)
            updated = path.read_text()
        self.assertIn('"id": "example_representation"', updated)
        self.assertIn('"paperUrl": "https://doi.org/10.1000/example"', updated)
        self.assertIn("// Provenance is a build-time invariant", updated)

    def test_issue_marker_is_required(self):
        with self.assertRaisesRegex(submission.SubmissionError, "marker"):
            submission.parse_issue("```json\n{}\n```")

    def test_benchmark_claims_are_rejected(self):
        entry = copy.deepcopy(VALID_ENTRY)
        entry["benchmarks"] = [{"dataset": "BBBP", "metric": "ROC-AUC", "score": "1.0"}]
        with self.assertRaisesRegex(submission.SubmissionError, "benchmark claims"):
            submission.validate_entry(entry)

    def test_duplicate_identifier_is_rejected(self):
        source = (
            "export const EMBEDDINGS = [\n"
            '  { id: "example_representation", name: "Existing Representation" }\n'
            "];\n\n// Provenance is a build-time invariant\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "embeddings.ts"
            path.write_text(source)
            with self.assertRaisesRegex(submission.SubmissionError, "already exists"):
                submission.update_registry(path, copy.deepcopy(VALID_ENTRY))

    def test_unknown_fields_are_rejected(self):
        entry = copy.deepcopy(VALID_ENTRY)
        entry["unreviewedCode"] = "console.log('not data')"
        with self.assertRaisesRegex(submission.SubmissionError, "unexpected fields"):
            submission.validate_entry(entry)

    def test_valid_issue_round_trip(self):
        parsed = submission.parse_issue(issue_body(VALID_ENTRY))
        validated = submission.validate_entry(parsed)
        self.assertEqual(validated["id"], "example_representation")


if __name__ == "__main__":
    unittest.main()
