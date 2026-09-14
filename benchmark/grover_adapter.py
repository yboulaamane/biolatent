"""Pinned GROVER Base/Large fingerprint extraction via the official code."""

import hashlib
import os
import subprocess
import sys

import numpy as np


SOURCE_DIR = os.environ.get(
    "BIOLATENT_GROVER_SOURCE",
    os.path.expanduser("~/biolatent_model_sources/grover"),
)
SOURCE_COMMIT = "40b6d97098e4508687912f3c05eca369fc2c6213"
CHECKPOINT_DIR = os.environ.get(
    "BIOLATENT_GROVER_CHECKPOINT_DIR",
    os.path.expanduser("~/biolatent_model_sources/grover_checkpoints"),
)
CHECKPOINTS = {
    "grover_base": {
        "filename": "grover_base.pt",
        "sha256": "47e095880d71baf29ea6f6253473cd56d5406213fa82959c6e14ea469e06b1de",
        "dim": 3200,
    },
    "grover_large": {
        "filename": "grover_large.pt",
        "sha256": "4b0c436fbd6ed8539fa92a0c9f890878f5e3dd8591d959315e773efb6302baaa",
        "dim": 4800,
    },
}


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(model_id):
    if model_id not in CHECKPOINTS:
        raise ValueError(f"Unknown GROVER model {model_id}")
    try:
        commit = subprocess.run(
            ["git", "-C", SOURCE_DIR, "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Cannot verify the GROVER source checkout: {exc}") from exc
    if commit != SOURCE_COMMIT:
        raise RuntimeError(
            f"GROVER source is at {commit}, expected pinned commit {SOURCE_COMMIT}"
        )
    checkpoint = os.path.join(CHECKPOINT_DIR, CHECKPOINTS[model_id]["filename"])
    if not os.path.isfile(checkpoint):
        raise RuntimeError(
            f"GROVER checkpoint is missing at {checkpoint}; no substitute is used"
        )
    actual = _sha256(checkpoint)
    if actual != CHECKPOINTS[model_id]["sha256"]:
        raise RuntimeError(
            f"GROVER checkpoint hash {actual} does not match the pinned release"
        )
    return checkpoint


def embed(smiles_list, model_id, batch_size=32):
    import torch
    from torch.utils.data import DataLoader

    checkpoint = _verify(model_id)
    if SOURCE_DIR not in sys.path:
        sys.path.insert(0, SOURCE_DIR)
    from grover.data import MolCollator, MoleculeDatapoint, MoleculeDataset
    from grover.util.parsing import get_newest_train_args
    from grover.util.utils import build_model

    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # The release checkpoints predate some arguments expected by the final
    # official code. Start from that code's defaults, then overwrite every
    # architecture value stored inside the checkpoint.
    state = torch.load(checkpoint, map_location="cpu", weights_only=False)
    args = get_newest_train_args()
    for key, value in vars(state["args"]).items():
        setattr(args, key, value)
    args.parser_name = "fingerprint"
    args.fingerprint_source = "both"
    args.cuda = device.type == "cuda"
    args.bond_drop_rate = 0
    args.features_generator = None

    model = build_model(args)
    missing, unexpected = model.load_state_dict(state["state_dict"], strict=False)
    if missing != ["readout.cached_zero_vector"] or unexpected:
        raise RuntimeError(
            f"GROVER checkpoint mismatch: missing={missing}, unexpected={unexpected}"
        )
    model.eval().to(device)

    dataset = MoleculeDataset([
        MoleculeDatapoint([str(smiles)], args=args) for smiles in smiles_list
    ])
    collator = MolCollator(args=args, shared_dict={})
    loader = DataLoader(
        dataset, batch_size=batch_size, shuffle=False, num_workers=0,
        collate_fn=collator,
    )
    vectors = []
    with torch.inference_mode():
        for _, graph_batch, feature_batch, _, _ in loader:
            vectors.append(model(graph_batch, feature_batch).float().cpu().numpy())
    matrix = np.concatenate(vectors, axis=0).astype(np.float32, copy=False)
    expected_dim = CHECKPOINTS[model_id]["dim"]
    if matrix.shape != (len(smiles_list), expected_dim):
        raise RuntimeError(
            f"{model_id}: produced {matrix.shape}, expected "
            f"({len(smiles_list)}, {expected_dim})"
        )
    metadata = {
        "source_commit": SOURCE_COMMIT,
        "checkpoint_sha256": CHECKPOINTS[model_id]["sha256"],
        "inference_device_type": device.type,
        "inference_parameter_dtype": str(next(model.parameters()).dtype),
        "atom_featurisation": "official GROVER atom and bond features",
        "hydrogen_policy": "implicit hydrogens represented as atom features",
        "graph_pooling": "official mean readout",
        "fingerprint_source": "both atom-view and bond-view outputs",
    }
    return matrix, metadata
