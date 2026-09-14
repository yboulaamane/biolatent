"""Pinned MolCLR-GIN frozen-feature extraction.

The official checkpoint contains a 512-dimensional encoder feature followed by
a 256-dimensional contrastive projection head.  Downstream fine-tuning in the
official implementation attaches its prediction head to the encoder feature,
so BioLatent records that 512-dimensional vector, not the training-only
contrastive projection.
"""

import importlib.util
import os
import subprocess
import sys

import numpy as np


SOURCE_DIR = os.environ.get(
    "BIOLATENT_MOLCLR_SOURCE",
    os.path.expanduser("~/biolatent_model_sources/MolCLR"),
)
SOURCE_COMMIT = "3d3bc1912be27b0c97435fd9134f4d4c73d4c5ab"
CHECKPOINT_RELATIVE_PATH = "ckpt/pretrained_gin/checkpoints/model.pth"
CHECKPOINT_SHA256 = (
    "93bc4f02ea8847cd44fa21ec3f65600ff2f4a7ae6d3a85e8519a5bcc56afc20a"
)


def _verify_source():
    checkpoint = os.path.join(SOURCE_DIR, CHECKPOINT_RELATIVE_PATH)
    if not os.path.isfile(checkpoint):
        raise RuntimeError(
            f"MolCLR checkpoint is missing at {checkpoint}; no substitute is used"
        )
    try:
        commit = subprocess.run(
            ["git", "-C", SOURCE_DIR, "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Cannot verify the MolCLR source checkout: {exc}") from exc
    if commit != SOURCE_COMMIT:
        raise RuntimeError(
            f"MolCLR source is at {commit}, expected pinned commit {SOURCE_COMMIT}"
        )
    return checkpoint


def _molecule_graph(smiles, row_index):
    import torch
    from rdkit import Chem
    from torch_geometric.data import Data

    molecule = Chem.MolFromSmiles(str(smiles))
    if molecule is None:
        raise ValueError(f"MolCLR row {row_index}: invalid SMILES")
    # This matches the official MolCLR dataset featurisation.
    molecule = Chem.AddHs(molecule)
    atom_numbers = list(range(1, 119))
    chiralities = [
        Chem.rdchem.ChiralType.CHI_UNSPECIFIED,
        Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CW,
        Chem.rdchem.ChiralType.CHI_TETRAHEDRAL_CCW,
        Chem.rdchem.ChiralType.CHI_OTHER,
    ]
    bond_types = [
        Chem.rdchem.BondType.SINGLE,
        Chem.rdchem.BondType.DOUBLE,
        Chem.rdchem.BondType.TRIPLE,
        Chem.rdchem.BondType.AROMATIC,
    ]
    bond_directions = [
        Chem.rdchem.BondDir.NONE,
        Chem.rdchem.BondDir.ENDUPRIGHT,
        Chem.rdchem.BondDir.ENDDOWNRIGHT,
    ]

    atom_features = []
    for atom in molecule.GetAtoms():
        try:
            atom_features.append([
                atom_numbers.index(atom.GetAtomicNum()),
                chiralities.index(atom.GetChiralTag()),
            ])
        except ValueError as exc:
            raise ValueError(
                f"MolCLR row {row_index}: unsupported atom or chirality"
            ) from exc

    edges, edge_features = [], []
    for bond in molecule.GetBonds():
        try:
            feature = [
                bond_types.index(bond.GetBondType()),
                bond_directions.index(bond.GetBondDir()),
            ]
        except ValueError as exc:
            raise ValueError(
                f"MolCLR row {row_index}: unsupported bond type or direction"
            ) from exc
        start, end = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        edges.extend(((start, end), (end, start)))
        edge_features.extend((feature, feature))

    edge_index = (
        torch.tensor(edges, dtype=torch.long).t().contiguous()
        if edges else torch.empty((2, 0), dtype=torch.long)
    )
    edge_attr = (
        torch.tensor(edge_features, dtype=torch.long)
        if edge_features else torch.empty((0, 2), dtype=torch.long)
    )
    return Data(
        x=torch.tensor(atom_features, dtype=torch.long),
        edge_index=edge_index,
        edge_attr=edge_attr,
    )


def embed(smiles_list, batch_size=256):
    import torch
    from torch_geometric.loader import DataLoader

    checkpoint = _verify_source()
    module_path = os.path.join(SOURCE_DIR, "models", "ginet_molclr.py")
    module_spec = importlib.util.spec_from_file_location(
        "biolatent_official_molclr_ginet", module_path
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"Cannot load the pinned MolCLR model from {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    GINet = module.GINet

    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    graphs = [_molecule_graph(smiles, index)
              for index, smiles in enumerate(smiles_list)]

    model = GINet(
        num_layer=5, emb_dim=300, feat_dim=512, drop_ratio=0, pool="mean"
    )
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    model.eval().to(device)

    vectors = []
    loader = DataLoader(graphs, batch_size=batch_size, shuffle=False)
    with torch.inference_mode():
        for batch in loader:
            encoder_feature, _projection = model(batch.to(device))
            vectors.append(encoder_feature.float().cpu().numpy())
    matrix = np.concatenate(vectors, axis=0).astype(np.float32, copy=False)
    metadata = {
        "source_commit": SOURCE_COMMIT,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "inference_device_type": device.type,
        "inference_parameter_dtype": str(next(model.parameters()).dtype),
        "atom_featurisation": "official MolCLR categorical atom/bond features",
        "hydrogen_policy": "explicit hydrogens added by RDKit",
        "graph_pooling": "mean over final-layer atom vectors",
        "representation_layer": (
            "512-dimensional encoder feature before the contrastive projection head"
        ),
    }
    return matrix, metadata
