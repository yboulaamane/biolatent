"""Build reproducible protein-sequence dependence groups with MMseqs2.

DeepLoc inference resamples homology clusters rather than treating related
test proteins as independent.  The TAPE Fluorescence test set is clustered as
a diagnostic: at the prespecified 90% identity threshold it forms one connected
component, so its model comparisons are reported descriptively rather than
assigned inferential p-values.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.datasets import load_benchmark_dataset


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "sequence_clusters.json"
SETTINGS = {
    "DeepLoc": {"min_sequence_identity": 0.30, "coverage": 0.80},
    "Fluorescence": {"min_sequence_identity": 0.90, "coverage": 0.90},
}


def find_mmseqs(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("BIOLATENT_MMSEQS"),
        shutil.which("mmseqs"),
        str(Path.home() / "miniforge3" / "envs" / "cdd" / "bin" / "mmseqs"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise FileNotFoundError(
        "MMseqs2 was not found. Install mmseqs2 or set BIOLATENT_MMSEQS."
    )


def cluster_task(task: str, mmseqs: str, threads: int) -> dict[str, object]:
    data = load_benchmark_dataset(task)
    test_sequences = [data["inputs"][index] for index in data["test_idx"]]
    settings = SETTINGS[task]
    with tempfile.TemporaryDirectory(prefix=f"biolatent-{task.lower()}-") as directory:
        temporary = Path(directory)
        fasta = temporary / "test.fasta"
        prefix = temporary / "clusters"
        with fasta.open("w") as handle:
            for index, sequence in enumerate(test_sequences):
                handle.write(f">seq_{index}\n{sequence}\n")
        subprocess.run(
            [
                mmseqs,
                "easy-cluster",
                str(fasta),
                str(prefix),
                str(temporary / "work"),
                "--min-seq-id",
                str(settings["min_sequence_identity"]),
                "-c",
                str(settings["coverage"]),
                "--cov-mode",
                "0",
                "--cluster-mode",
                "1",
                "--cluster-reassign",
                "--shuffle",
                "0",
                "--threads",
                str(threads),
                "-v",
                "1",
            ],
            check=True,
        )
        members: dict[str, list[int]] = {}
        cluster_path = Path(f"{prefix}_cluster.tsv")
        for line in cluster_path.read_text().splitlines():
            representative, member = line.split("\t")
            members.setdefault(representative, []).append(int(member.removeprefix("seq_")))

    observed = sorted(index for values in members.values() for index in values)
    if observed != list(range(len(test_sequences))):
        raise RuntimeError(f"{task}: MMseqs2 clustering did not return every test sequence")
    ordered_clusters = sorted(members.values(), key=min)
    assignments = [""] * len(test_sequences)
    sizes = []
    for cluster_index, indices in enumerate(ordered_clusters, start=1):
        label = f"cluster_{cluster_index:05d}"
        sizes.append(len(indices))
        for index in indices:
            assignments[index] = label

    return {
        "dataset_input_sha256": data["input_sha256"],
        "n_test": len(test_sequences),
        "n_clusters": len(ordered_clusters),
        "n_singletons": sum(size == 1 for size in sizes),
        "largest_cluster": max(sizes),
        "settings": {
            **settings,
            "coverage_mode": "query_and_target",
            "cluster_mode": "connected_component",
            "cluster_reassignment": True,
        },
        "assignments": assignments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mmseqs")
    parser.add_argument("--threads", type=int, default=8)
    arguments = parser.parse_args()
    mmseqs = find_mmseqs(arguments.mmseqs)
    version = subprocess.run(
        [mmseqs, "version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    report = {
        "schema_version": 1,
        "tool": "MMseqs2",
        "tool_version": version,
        "interpretation": (
            "Dependence groups for protein test-set resampling. DeepLoc uses "
            "30% identity and 80% bidirectional coverage. Fluorescence is a "
            "diagnostic only because its test variants form one component at "
            "90% identity and 90% bidirectional coverage."
        ),
        "tasks": {},
    }
    for task in SETTINGS:
        report["tasks"][task] = cluster_task(task, mmseqs, arguments.threads)
        entry = report["tasks"][task]
        print(
            f"{task}: {entry['n_clusters']} clusters; "
            f"largest={entry['largest_cluster']}",
            flush=True,
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
