"""
BioLatent Phase A: Frozen Embedding Generation
==============================================

Runs each pretrained model once over each dataset it is applicable to and
caches the resulting frozen representation matrix to ``data/embeddings/``.

Three rules make the comparison fair, and all three are choices that would
otherwise silently vary between models:

1. **Pooling is fixed.** Every transformer is mean-pooled over its non-padding
   tokens, special tokens excluded. Pooling is a hidden hyperparameter -- CLS
   versus mean pooling can move a score by several points -- so it is pinned
   rather than chosen per model.
2. **Truncation is fixed** per modality and recorded, so a model is never
   silently advantaged by seeing more of a sequence than another.
3. **A model is only run on its own modality.** A protein language model has no
   way to embed a SMILES string; the correct entry is N/A, not a number.

Every matrix is written with a sidecar JSON recording the checkpoint, its
revision hash, pooling, truncation and dtype, so any row can be regenerated.
"""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys

import numpy as np

EMB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "embeddings")
os.makedirs(EMB_DIR, exist_ok=True)

MAX_LEN = {"protein": 512, "genomics": 512, "molecule": 256}
RAW_MAX = {"protein": 510, "genomics": 510, "molecule": None}
RARE_AA_TRANSLATION = str.maketrans({residue: "X" for residue in "UZOB"})
EMBED_PROTOCOL_VERSION = 2
MOLFORMER_ENV = os.path.expanduser("~/biolatent_molformer_env/bin/python")
UNIMOL_ENV = os.environ.get(
    "BIOLATENT_UNIMOL_PYTHON",
    os.path.expanduser("~/miniforge3/envs/unimol/bin/python"),
)
GRAPH_ENV = os.environ.get(
    "BIOLATENT_GRAPH_PYTHON",
    os.path.expanduser("~/biolatent_graph_env/bin/python"),
)
MULTIMOLECULE_ENV = os.environ.get(
    "BIOLATENT_MULTIMOLECULE_PYTHON",
    os.path.expanduser("~/biolatent_multimolecule_env/bin/python"),
)
UNIREP_ENV = os.environ.get(
    "BIOLATENT_UNIREP_PYTHON",
    os.path.expanduser("~/biolatent_unirep_env/bin/python"),
)
ESMC_ENV = os.environ.get(
    "BIOLATENT_ESMC_PYTHON",
    os.path.expanduser("~/biolatent_esmc_env/bin/python"),
)

# ---------------------------------------------------------------------------
# Model registry. Every entry is a real, downloadable checkpoint or a
# deterministic classical featuriser -- nothing here is a placeholder.
# ---------------------------------------------------------------------------
MODEL_REGISTRY = {
    # --- molecules: classical baselines ---
    "ecfp4":        {"kind": "ecfp4",  "modality": "molecule", "dim": 1024,
                     "label": "ECFP4 (Morgan, r=2, 1024 bits)"},
    "rdkit2d":      {"kind": "rdkit",  "modality": "molecule", "dim": 210,
                     "label": "RDKit 2D descriptors"},
    # --- molecules: pretrained transformers ---
    "chemberta_77m": {"kind": "hf", "modality": "molecule",
                      "checkpoint": "DeepChem/ChemBERTa-77M-MLM",
                      "revision": "ed8a5374f2024ec8da53760af91a33fb8f6a15ff",
                      "label": "ChemBERTa-2 77M MLM"},
    "chemberta_zinc": {"kind": "hf", "modality": "molecule",
                       "checkpoint": "seyonec/ChemBERTa-zinc-base-v1",
                       "revision": "761d6a18cf99db371e0b43baf3e2d21b3e865a20",
                       "label": "ChemBERTa ZINC base"},
    # Remote-code models are still isolated in a subprocess, but use the same
    # pinned project interpreter as the rest of the suite.
    "molformer_xl": {"kind": "hf", "modality": "molecule",
                     "checkpoint": "ibm/MoLFormer-XL-both-10pct",
                     "revision": "361063d0ad524ef77cf39b08469f6be770dc550f",
                     "trust_remote_code": True,
                     "force_float32": True,
                     "inference_seed": 42,
                     "interpreter": MOLFORMER_ENV,
                     "label": "MoLFormer-XL"},
    "unimol_v1": {"kind": "unimol", "modality": "molecule", "dim": 512,
                  "checkpoint": ("https://github.com/deepmodeling/Uni-Mol/"
                                 "releases/download/v0.1/"
                                 "mol_pre_all_h_220816.pt"),
                  "revision": ("sha256:7f5f14bb28bf479a0b8f38ebab4bb9d7"
                               "ae867383f14c4d694d056500fa3446a7"),
                  "weight_filename": "mol_pre_all_h_220816.pt",
                  "weight_sha256": ("7f5f14bb28bf479a0b8f38ebab4bb9d7"
                                    "ae867383f14c4d694d056500fa3446a7"),
                  "dictionary_filename": "mol.dict.txt",
                  "dictionary_sha256": ("94135cb9a9198f988de684cb61e2c3728"
                                        "82a3bd59b8320effbae704c38057127"),
                  "conformer_seed": 42, "max_atoms": 256,
                  "interpreter": UNIMOL_ENV,
                  "label": "Uni-Mol v1 84M (mean atom pooling)"},
    "molclr_gin": {"kind": "molclr", "modality": "molecule", "dim": 512,
                   "checkpoint": ("https://github.com/yuyangw/MolCLR/blob/"
                                  "3d3bc1912be27b0c97435fd9134f4d4c73d4c5ab/"
                                  "ckpt/pretrained_gin/checkpoints/model.pth"),
                   "revision": "3d3bc1912be27b0c97435fd9134f4d4c73d4c5ab",
                   "checkpoint_sha256": ("93bc4f02ea8847cd44fa21ec3f65600ff"
                                         "2f4a7ae6d3a85e8519a5bcc56afc20a"),
                   "supported_tasks": ["BBBP", "BACE", "ESOL",
                                       "Lipophilicity", "CYP3A4"],
                   "interpreter": GRAPH_ENV,
                   "label": "MolCLR GIN (encoder feature)"},
    "grover_base": {"kind": "grover", "modality": "molecule", "dim": 3200,
                    "checkpoint": ("https://drive.google.com/file/d/"
                                   "1hiGwOzoRfbJQPWj0V_mtOffsqIIAMgjl/view"),
                    "revision": "40b6d97098e4508687912f3c05eca369fc2c6213",
                    "checkpoint_sha256": ("47e095880d71baf29ea6f6253473cd56"
                                          "d5406213fa82959c6e14ea469e06b1de"),
                    "interpreter": GRAPH_ENV,
                    "label": "GROVER Base (both fingerprint)"},
    "grover_large": {"kind": "grover", "modality": "molecule", "dim": 4800,
                     "checkpoint": ("https://drive.google.com/file/d/"
                                    "1bMg_ntUKEoOmHM0KoUi1XYJvzPBnHeWw/view"),
                     "revision": "40b6d97098e4508687912f3c05eca369fc2c6213",
                     "checkpoint_sha256": ("4b0c436fbd6ed8539fa92a0c9f890878"
                                           "f5e3dd8591d959315e773efb6302baaa"),
                     "interpreter": GRAPH_ENV,
                     "label": "GROVER Large (both fingerprint)"},

    # --- proteins: classical baseline ---
    "kmer3_protein": {"kind": "kmer", "modality": "protein", "k": 3,
                      "label": "3-mer frequency"},
    # --- proteins: pretrained language models ---
    "unirep_1900": {"kind": "unirep", "modality": "protein", "dim": 1900,
                    "checkpoint": "jax-unirep bundled UniRef50 weights",
                    "revision": "jax-unirep-3.0.0",
                    "interpreter": UNIREP_ENV,
                    "label": "UniRep 1900-unit"},
    "esm2_8m":   {"kind": "hf", "modality": "protein",
                  "checkpoint": "facebook/esm2_t6_8M_UR50D",
                  "revision": "c731040fcd8d73dceaa04b0a8e6329b345b0f5df",
                  "label": "ESM-2 8M"},
    "esm2_35m":  {"kind": "hf", "modality": "protein",
                  "checkpoint": "facebook/esm2_t12_35M_UR50D",
                  "revision": "6fbf070e65b0b7291e7bbcd451118c216cff79d8",
                  "label": "ESM-2 35M"},
    "esm2_150m": {"kind": "hf", "modality": "protein",
                  "checkpoint": "facebook/esm2_t30_150M_UR50D",
                  "revision": "a695f6045e2e32885fa60af20c13cb35398ce30c",
                  "label": "ESM-2 150M"},
    "esm2_650m": {"kind": "hf", "modality": "protein",
                  "checkpoint": "facebook/esm2_t33_650M_UR50D",
                  "revision": "08e4846e537177426273712802403f7ba8261b6c",
                  "label": "ESM-2 650M"},
    "esm1v_650m": {"kind": "hf", "modality": "protein",
                    "checkpoint": "facebook/esm1v_t33_650M_UR90S_1",
                    "revision": "8bfdb1892536cc77bd0760b9c25ddced2cd0b4c8",
                    "label": "ESM-1v 650M"},
    "proteinbert": {"kind": "hf", "modality": "protein",
                    "checkpoint": "multimolecule/proteinbert",
                    "revision": "d462d5c059e083678c182f161096c64987b8b863",
                    "register_multimolecule": True,
                    "interpreter": MULTIMOLECULE_ENV,
                    "label": "ProteinBERT"},
    "carp_640m": {"kind": "hf", "modality": "protein",
                  "checkpoint": "multimolecule/carp-640m",
                  "revision": "672cb98418fb703abb3ad704b457d97deea761f4",
                  "register_multimolecule": True,
                  "force_float32": True,
                  "interpreter": MULTIMOLECULE_ENV,
                  "label": "CARP 640M"},
    "esmc_300m": {"kind": "esmc", "modality": "protein", "dim": 960,
                  "checkpoint": "biohub/esmc-300m-2024-12",
                  "revision": "7f10b20ae75017b2dbc884070e03434515709a8d",
                  "model_name": "esmc_300m",
                  "interpreter": ESMC_ENV,
                  "label": "ESM-C 300M"},
    "protrek_650m": {"kind": "protrek", "modality": "protein", "dim": 1024,
                     "checkpoint": "westlake-repl/ProTrek_650M",
                     "revision": "f2a9d59f333f191fd9268c0f8faf41a1100937c3",
                     "implementation_revision":
                         "48715468b8daa08236d05ff3310cd61db1896e94",
                     "label": "ProTrek 650M sequence encoder"},
    "protbert":  {"kind": "hf", "modality": "protein", "space_tokens": True,
                  "replace_rare_amino_acids": True,
                  "checkpoint": "Rostlab/prot_bert",
                  "revision": "7a894481acdc12202f0a415dd567f6cfdb698908",
                  "label": "ProtBERT"},

    # --- genomics: classical baseline ---
    "kmer5_dna": {"kind": "kmer", "modality": "genomics", "k": 5,
                  "label": "5-mer frequency"},
    # --- genomics: pretrained models ---
    "nucleotide_transformer": {"kind": "hf", "modality": "genomics",
                               "checkpoint": "InstaDeepAI/nucleotide-transformer-500m-human-ref",
                               "revision": "f87b5d7233295242e79c951873d290f4cf992045",
                               "trust_remote_code": True,
                               "label": "Nucleotide Transformer 500M"},
    "dnabert2": {"kind": "hf", "modality": "genomics",
                  "checkpoint": "zhihan1996/DNABERT-2-117M",
                  "revision": "7bce263b15377fc15361f52cfab88f8b586abda0",
                  "trust_remote_code": True,
                  "disable_remote_flash_attention": True,
                  "force_float32": True,
                  "interpreter": os.path.expanduser(
                      "~/biolatent_dnabert2_env/bin/python"),
                  "label": "DNABERT-2 117M"},
    "caduceus": {"kind": "hf", "modality": "genomics",
                  "checkpoint": ("kuleshov-group/"
                                 "caduceus-ps_seqlen-131k_d_model-256_n_layer-16"),
                  "revision": "d89eeb853136ea64da7feb3d0c8e909771b17ae6",
                  "trust_remote_code": True,
                  "label": "Caduceus-PS 131K"},
    "gena_lm": {"kind": "hf", "modality": "genomics",
                 "checkpoint": "AIRI-Institute/gena-lm-bert-large-t2t",
                 "revision": "f997a8a7c1ba5feb6d11de46354a41c51ffe9660",
                 "trust_remote_code": True,
                 "hidden_states_output": True,
                 "label": "GENA-LM BERT Large"},
    "grover_dna": {"kind": "hf", "modality": "genomics",
                    "checkpoint": "PoetschLab/GROVER",
                    "revision": "6b223110f0d6963e849f55bc2a2f3cff0e38c7a4",
                    "label": "GROVER DNA"},
    "evo1_7b": {"kind": "evo1", "modality": "genomics",
                 "checkpoint": "togethercomputer/evo-1-131k-base",
                 "revision": "78c715ab81852e02ec3b1c7e795dc7250d8c7625",
                 "interpreter": os.path.expanduser(
                     "~/biolatent_evo1_env/bin/python"),
                 "label": "Evo 1 7B"},
    "evo2_7b": {"kind": "evo2", "modality": "genomics",
                 "checkpoint": "arcinstitute/evo2_7b",
                 "revision": "bda0089f92582d5baabf0f22d9fc85f3588f6b58",
                 "model_name": "evo2_7b",
                 "interpreter": os.path.expanduser(
                     "~/biolatent_evo2_env/bin/python"),
                 "label": "Evo 2 7B"},
    "hyenadna": {"kind": "hf", "modality": "genomics",
                 "checkpoint": "LongSafari/hyenadna-tiny-1k-seqlen-hf",
                 "revision": "e8c1effa8673814e257e627d2e1eda9ea5a373f6",
                 "trust_remote_code": True, "label": "HyenaDNA tiny"},
}


def cache_path(model_id, dataset):
    return os.path.join(EMB_DIR, f"{model_id}__{dataset}.npy")


def is_applicable(model_id, dataset, modality):
    """Whether a model natively supports this complete model-task cell."""
    spec = MODEL_REGISTRY[model_id]
    supported = spec.get("supported_tasks")
    return spec["modality"] == modality and (
        supported is None or dataset in supported
    )


def inference_precision_policy(spec):
    """Human-readable precision policy recorded beside every matrix."""
    if spec["kind"] in {"unimol", "molclr", "grover", "unirep"}:
        return "float32 model inference and output matrix"
    if spec["kind"] == "esmc":
        return "official bfloat16 CUDA inference; float32 output matrix"
    if spec["kind"] == "protrek":
        return "float16 CUDA inference; float32 output matrix"
    if spec["kind"] in {"evo1", "evo2"}:
        return "official bfloat16 inference runtime; float32 output matrix"
    if spec["kind"] != "hf":
        return "not applicable"
    if spec.get("force_float32"):
        return "float32 on all devices"
    return "float16 on CUDA; float32 when CUDA is unavailable"


# ------------------------------------------------------------ classical

def embed_ecfp4(smiles_list, n_bits=1024, radius=2):
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem

    RDLogger.DisableLog("rdApp.*")
    out = np.zeros((len(smiles_list), n_bits), dtype=np.float32)
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
        arr = np.zeros((n_bits,), dtype=np.int8)
        DataStructs.ConvertToNumpyArray(fp, arr)
        out[i] = arr
    return out


def embed_rdkit2d(smiles_list):
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors
    from rdkit.ML.Descriptors import MoleculeDescriptors

    RDLogger.DisableLog("rdApp.*")
    names = [x[0] for x in Descriptors._descList]
    calc = MoleculeDescriptors.MolecularDescriptorCalculator(names)
    out = np.zeros((len(smiles_list), len(names)), dtype=np.float32)
    for i, smi in enumerate(smiles_list):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        v = np.array(calc.CalcDescriptors(mol), dtype=np.float64)
        v = np.nan_to_num(v, nan=0.0, posinf=0.0, neginf=0.0)
        # A few descriptors (notably Ipc) grow beyond the float32 range on
        # larger molecules; clip rather than let the cast produce infinities.
        out[i] = np.clip(v, -3.0e38, 3.0e38).astype(np.float32)
    return out


def embed_kmer(sequences, k, modality):
    import itertools
    alphabet = list("ACGT") if modality == "genomics" else list("ACDEFGHIKLMNPQRSTVWY")
    kmers = {"".join(p): i for i, p in enumerate(itertools.product(alphabet, repeat=k))}
    out = np.zeros((len(sequences), len(kmers)), dtype=np.float32)
    for i, seq in enumerate(sequences):
        s = str(seq).upper()
        for j in range(len(s) - k + 1):
            idx = kmers.get(s[j:j + k])
            if idx is not None:
                out[i, idx] += 1.0
        total = out[i].sum()
        if total > 0:
            out[i] /= total
    return out


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def embed_unimol(smiles_list, spec):
    """Frozen Uni-Mol v1 atom embeddings under the common mean-pooling rule."""
    import torch
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem as UniMolAllChem
    from unimol_tools import UniMolRepr
    from unimol_tools.weights import get_weight_dir

    RDLogger.DisableLog("rdApp.*")

    weight_dir = get_weight_dir()
    weight_path = os.path.join(weight_dir, spec["weight_filename"])
    dictionary_path = os.path.join(weight_dir, spec["dictionary_filename"])
    for path, expected in ((weight_path, spec["weight_sha256"]),
                           (dictionary_path, spec["dictionary_sha256"])):
        if not os.path.exists(path):
            raise FileNotFoundError(f"required pinned Uni-Mol file is missing: {path}")
        observed = _file_sha256(path)
        if observed != expected:
            raise RuntimeError(
                f"Uni-Mol file hash mismatch for {path}: {observed} != {expected}")

    seed = spec["conformer_seed"]
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    runner = UniMolRepr(
        data_type="molecule", batch_size=32, remove_hs=False,
        use_cuda=torch.cuda.is_available(), model_name="unimolv1",
        pretrained_model_path=weight_path,
        pretrained_dict_path=dictionary_path,
        max_atoms=spec["max_atoms"],
    )
    output = runner.get_repr(list(smiles_list), return_atomic_reprs=True)
    rows = []
    for atomic, symbols in zip(output["atomic_reprs"],
                               output["atomic_symbol"]):
        # unimol-tools includes the terminal [SEP] vector in atomic_reprs.
        # Remove tokenizer special vectors before applying the benchmark's
        # common mean-pooling rule.
        keep = [index for index, symbol in enumerate(symbols)
                if symbol not in {"[CLS]", "[SEP]", "[PAD]"}]
        if not keep:
            raise RuntimeError("Uni-Mol produced no non-special atom vectors")
        rows.append(np.asarray(atomic, dtype=np.float32)[keep].mean(axis=0))

    atom_counts = []
    for smiles in smiles_list:
        molecule = Chem.MolFromSmiles(str(smiles))
        atom_counts.append(
            UniMolAllChem.AddHs(molecule).GetNumAtoms() if molecule else 0)
    matrix = np.vstack(rows).astype(np.float32)
    stats = {
        "inference_device_type": "cuda" if torch.cuda.is_available() else "cpu",
        "inference_parameter_dtype": str(next(runner.model.parameters()).dtype),
        "conformer_generation": "RDKit 3D, fixed seed 42; 2D fallback",
        "conformer_seed": seed,
        "hydrogen_policy": "explicit hydrogens retained",
        "maximum_atoms": spec["max_atoms"],
        "n_inputs_atom_truncated": int(sum(
            count > spec["max_atoms"] for count in atom_counts)),
        "weight_sha256": spec["weight_sha256"],
        "dictionary_sha256": spec["dictionary_sha256"],
    }
    return matrix, stats


# ---------------------------------------------------------- transformers

def _token_budget_batches(order, sequences, max_len, budget):
    """Group length-sorted indices so that batch_size * padded_length <= budget.

    Fixed batch sizes are the wrong unit here. Protein lengths span 30..1022, so
    a batch size tuned for short sequences exhausts VRAM on long ones and a size
    tuned for long sequences wastes most of the card on short ones. Batching to
    a constant token budget keeps memory flat across the whole length range.
    """
    batch, batch_max = [], 0
    for i in order:
        length = min(len(str(sequences[i])), max_len) + 2
        new_max = max(batch_max, length)
        if batch and new_max * (len(batch) + 1) > budget:
            yield batch
            batch, batch_max = [i], length
        else:
            batch.append(i)
            batch_max = new_max
    if batch:
        yield batch


def _prepare_text(value, spec):
    text = str(value)
    if spec.get("replace_rare_amino_acids"):
        text = text.translate(RARE_AA_TRANSLATION)
    raw_max = RAW_MAX[spec["modality"]]
    if raw_max is not None:
        text = text[:raw_max]
    if spec.get("space_tokens"):
        text = " ".join(text)
    return text


def _forward_pooled(model, tok, batch, max_len, device, spec):
    """Tokenise, run, and mean-pool one batch. Returns a numpy array."""
    import torch

    texts = [_prepare_text(value, spec) for value in batch]

    enc = tok(texts, return_tensors="pt", padding=True,
              truncation=True, max_length=max_len,
              return_special_tokens_mask=True)
    enc = {k: v.to(device) for k, v in enc.items()}
    special_mask = enc.pop("special_tokens_mask", None)
    outputs = model(
        **enc,
        output_hidden_states=spec.get("hidden_states_output", False),
    )
    if spec.get("hidden_states_output"):
        hidden_states = getattr(outputs, "hidden_states", None)
        if not hidden_states:
            raise RuntimeError(
                f"{spec['checkpoint']} did not return requested hidden states")
        hidden = hidden_states[-1]
    elif hasattr(outputs, "last_hidden_state"):
        hidden = outputs.last_hidden_state
    elif isinstance(outputs, (tuple, list)) and outputs:
        # Some pinned remote-code models retain the legacy Transformers tuple
        # return type even when return_dict is enabled.
        hidden = outputs[0]
    else:
        raise RuntimeError(
            f"{spec['checkpoint']} did not expose a final hidden state")

    mask = enc.get("attention_mask")
    if mask is None:
        mask = torch.ones(hidden.shape[:2], device=device)
    # Some remote-code tokenizers (notably the pinned Nucleotide Transformer)
    # return a special-token mask one element wider than ``input_ids``. Never
    # broadcast or trim that malformed mask: rebuild it from the actual ids so
    # the pooling denominator describes exactly the tokens seen by the model.
    if special_mask is None or special_mask.shape != mask.shape:
        special_mask = torch.zeros_like(mask)
        input_ids = enc.get("input_ids")
        if input_ids is not None:
            for token_id in tok.all_special_ids:
                special_mask = torch.maximum(
                    special_mask, (input_ids == token_id).to(mask.dtype))
    mask = mask * (1 - special_mask.to(mask.dtype))
    mask = mask.unsqueeze(-1).to(hidden.dtype)
    pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
    return pooled.float().cpu().numpy()


def _forward_with_oom_retry(model, tok, seqs, max_len, device, spec, depth=0):
    """Run a batch, halving it on CUDA OOM rather than failing the model.

    A single oversized batch would otherwise abort the whole run, and -- worse
    -- an OOM can leave the CUDA context unusable so that every subsequent
    model fails instantly for an unrelated reason. Splitting keeps the failure
    local and the results identical, since pooling is per sequence.
    """
    import torch

    try:
        return _forward_pooled(model, tok, seqs, max_len, device, spec)
    except Exception as exc:
        # On this stack an allocation failure surfaces as AcceleratorError
        # ("CUDA error: out of memory") rather than torch.cuda.OutOfMemoryError,
        # so the retry keys on the message rather than the exception class.
        if "out of memory" not in str(exc).lower():
            raise
        torch.cuda.empty_cache()
        if len(seqs) == 1:
            raise
        mid = len(seqs) // 2
        if depth == 0:
            print(f"      OOM on batch of {len(seqs)}; splitting", flush=True)
        left = _forward_with_oom_retry(model, tok, seqs[:mid], max_len, device,
                                       spec, depth + 1)
        right = _forward_with_oom_retry(model, tok, seqs[mid:], max_len, device,
                                        spec, depth + 1)
        return np.vstack([left, right])


def embed_hf(sequences, spec, modality, token_budget=2048, progress_every=5000):
    """Mean-pooled frozen embeddings from a HuggingFace checkpoint.

    Sequences are processed in length-sorted, token-budgeted batches and
    restored to input order afterwards.
    """
    import torch
    if spec.get("register_multimolecule"):
        # Registers MultiMolecule's parity-checked ProteinBERT/CARP model types
        # with the Transformers auto classes in this isolated environment.
        # When this file is executed directly, ``benchmark/datasets.py`` would
        # otherwise shadow Hugging Face's ``datasets`` package during import.
        script_directory = os.path.dirname(os.path.abspath(__file__))
        original_path = list(sys.path)
        try:
            sys.path[:] = [entry for entry in sys.path
                           if os.path.abspath(entry or os.getcwd()) !=
                           script_directory]
            import multimolecule  # noqa: F401
        finally:
            sys.path[:] = original_path
    from transformers import AutoModel, AutoTokenizer

    inference_seed = spec.get("inference_seed", 42)
    torch.manual_seed(inference_seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(inference_seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = (torch.float16 if device == "cuda" and not spec.get("force_float32")
             else torch.float32)
    kw = {"revision": spec["revision"]}
    if spec.get("trust_remote_code"):
        kw["trust_remote_code"] = True

    tok = AutoTokenizer.from_pretrained(spec["checkpoint"], **kw)
    model = AutoModel.from_pretrained(spec["checkpoint"], torch_dtype=dtype, **kw)
    if spec.get("disable_remote_flash_attention"):
        # DNABERT-2's pinned remote implementation imports a Triton kernel that
        # is incompatible with Picard's Triton build. Its own documented
        # PyTorch attention fallback is mathematically equivalent at inference.
        module = sys.modules.get(model.__class__.__module__)
        if module is None or not hasattr(module, "flash_attn_qkvpacked_func"):
            raise RuntimeError(
                f"{spec['checkpoint']}: cannot locate the pinned attention "
                "implementation to select its PyTorch fallback")
        module.flash_attn_qkvpacked_func = None
    # ``torch_dtype`` controls checkpoint parameters but not necessarily
    # floating buffers created by remote model code. MoLFormer's random-feature
    # projection is one such buffer; cast the complete module so its attention
    # operands cannot mix float16 parameters with a float32 buffer.
    model.eval().to(device=device, dtype=dtype)

    max_len = MAX_LEN[modality]
    order = sorted(range(len(sequences)), key=lambda i: len(str(sequences[i])))
    pooled_by_index = [None] * len(sequences)
    done = 0

    try:
        with torch.no_grad():
            for idx_batch in _token_budget_batches(order, sequences, max_len,
                                                   token_budget):
                pooled = _forward_with_oom_retry(
                    model, tok, [sequences[i] for i in idx_batch],
                    max_len, device, spec)

                for slot, row in zip(idx_batch, pooled):
                    pooled_by_index[slot] = row

                prev, done = done, done + len(idx_batch)
                if done // progress_every > prev // progress_every:
                    print(f"      {done}/{len(sequences)}", flush=True)
    finally:
        # Always release the model, so one model's failure cannot starve the
        # next one of VRAM.
        del model
        if device == "cuda":
            torch.cuda.empty_cache()

    missing = [i for i, v in enumerate(pooled_by_index) if v is None]
    if missing:
        raise RuntimeError(
            f"{spec.get('checkpoint')}: {len(missing)} sequences produced no "
            f"embedding (first index {missing[0]})")
    # Measure truncation with the pinned tokenizer. This is deliberately kept
    # separate from raw-character truncation because tokenizers use different
    # vocabularies and therefore consume different token budgets for the same
    # sequence.
    token_lengths = []
    for start in range(0, len(sequences), 512):
        texts = [_prepare_text(value, spec)
                 for value in sequences[start:start + 512]]
        encoded = tok(texts, add_special_tokens=True, truncation=False,
                      return_length=True)
        lengths = encoded.get("length")
        if lengths is None:
            lengths = [len(ids) for ids in encoded["input_ids"]]
        token_lengths.extend(int(length) for length in lengths)
    stats = {
        "inference_device_type": device,
        "inference_parameter_dtype": str(dtype),
        "n_tokenized_inputs_truncated": int(sum(
            length > max_len for length in token_lengths)),
        "maximum_untruncated_token_length": int(max(token_lengths, default=0)),
    }
    return np.vstack(pooled_by_index).astype(np.float32), stats


def embed_unirep(sequences, spec, batch_size=32, progress_every=1000):
    """Return the canonical average hidden state from frozen UniRep 1900.

    Sequences are grouped by exact post-truncation length because the reference
    JAX implementation does not mask padding. Small chunks cap host/device
    memory while preserving the published ``h_avg`` representation exactly.
    """
    from jax_unirep.featurize import rep_same_lengths
    from jax_unirep.models import load_model

    prepared = [str(value).upper()[:RAW_MAX["protein"]]
                for value in sequences]
    groups = {}
    for index, sequence in enumerate(prepared):
        groups.setdefault(len(sequence), []).append(index)

    model = load_model(paper_weights=1900)
    rows = [None] * len(prepared)
    done = 0
    for length in sorted(groups):
        indices = groups[length]
        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start:start + batch_size]
            h_avg, _h_final, _c_final = rep_same_lengths(
                [prepared[index] for index in batch_indices], model)
            for index, row in zip(batch_indices, h_avg):
                rows[index] = row
            previous, done = done, done + len(batch_indices)
            if done // progress_every > previous // progress_every:
                print(f"      {done}/{len(prepared)}", flush=True)

    return np.vstack(rows).astype(np.float32), {
        "inference_device_type": "JAX default device",
        "inference_parameter_dtype": "float32",
        "embedding_layer": "published UniRep average hidden state (h_avg)",
        "n_tokenized_inputs_truncated": int(sum(
            len(str(value)) > RAW_MAX["protein"] for value in sequences)),
        "maximum_untruncated_token_length": int(max(
            (len(str(value)) for value in sequences), default=0)),
    }


def embed_esmc(sequences, spec, token_budget=2048, progress_every=5000):
    """Mean-pool the pinned ESM-C 300M final residue representations."""
    from pathlib import Path

    import torch
    from huggingface_hub import snapshot_download
    import esm.pretrained as esm_pretrained
    from esm.models.esmc import ESMC

    if not torch.cuda.is_available():
        raise RuntimeError("ESM-C benchmark requires a CUDA allocation")
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    device = torch.device("cuda")

    snapshot = snapshot_download(
        repo_id=spec["checkpoint"], revision=spec["revision"])
    # The official loader otherwise resolves the repository's moving default
    # branch. Route it to the exact snapshot recorded in the sidecar metadata.
    esm_pretrained.data_root = lambda _model: Path(snapshot)
    model = ESMC.from_pretrained(spec["model_name"], device=device).eval()

    prepared = [str(value).upper()[:RAW_MAX["protein"]]
                for value in sequences]
    order = sorted(range(len(prepared)), key=lambda index: len(prepared[index]))
    rows = [None] * len(prepared)
    done = 0
    try:
        with torch.no_grad():
            for indices in _token_budget_batches(
                    order, prepared, MAX_LEN["protein"], token_budget):
                texts = [prepared[index] for index in indices]
                tokens = model._tokenize(texts)
                attention = tokens != model.tokenizer.pad_token_id
                output = model(sequence_tokens=tokens, sequence_id=attention)
                hidden = output.embeddings
                keep = attention.clone()
                for token_id in model.tokenizer.all_special_ids:
                    keep &= tokens != token_id
                weights = keep.unsqueeze(-1).to(hidden.dtype)
                pooled = ((hidden * weights).sum(1)
                          / weights.sum(1).clamp(min=1)).float().cpu().numpy()
                for index, row in zip(indices, pooled):
                    rows[index] = row
                previous, done = done, done + len(indices)
                if done // progress_every > previous // progress_every:
                    print(f"      {done}/{len(prepared)}", flush=True)
    finally:
        del model
        torch.cuda.empty_cache()

    return np.vstack(rows).astype(np.float32), {
        "inference_device_type": "cuda",
        "inference_parameter_dtype": "torch.bfloat16",
        "embedding_layer": "ESM-C final residue representations",
        "n_tokenized_inputs_truncated": int(sum(
            len(str(value)) > RAW_MAX["protein"] for value in sequences)),
        "maximum_untruncated_token_length": int(max(
            (len(str(value)) for value in sequences), default=0)),
    }


def embed_protrek(sequences, spec, token_budget=1536, progress_every=5000):
    """Run ProTrek's frozen sequence tower and official CLS projection."""
    import torch
    from huggingface_hub import snapshot_download
    from torch.nn.functional import normalize
    from transformers import EsmConfig, EsmForMaskedLM, EsmTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("ProTrek benchmark requires a CUDA allocation")
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    device = torch.device("cuda")
    snapshot = snapshot_download(
        repo_id=spec["checkpoint"], revision=spec["revision"])
    protein_config = os.path.join(snapshot, "esm2_t33_650M_UR50D")
    checkpoint_path = os.path.join(snapshot, "ProTrek_650M.pt")

    config = EsmConfig.from_pretrained(protein_config)
    backbone = EsmForMaskedLM(config)
    # Match the pinned ProTrek ProteinEncoder definition exactly. These heads
    # are removed before its checkpoint is loaded and do not contribute to the
    # sequence representation.
    backbone.esm.contact_head = None
    if config.position_embedding_type == "rotary":
        backbone.esm.embeddings.position_embeddings = None
    projection = torch.nn.Linear(config.hidden_size, spec["dim"])
    checkpoint = torch.load(checkpoint_path, map_location="cpu",
                            weights_only=False)
    weights = checkpoint.get("model", checkpoint)
    # The official model stores a ParameterList as temperature, protein tower,
    # text tower, and structure tower. ProteinEncoder is therefore prefix 1.
    protein_weights = {
        key[2:]: value for key, value in weights.items()
        if key.startswith("1.")
    }
    # Older Transformers versions persisted this deterministic arange buffer;
    # current versions regenerate it and therefore do not expose it in the
    # state dict. It is not learned checkpoint information.
    protein_weights.pop("model.esm.embeddings.position_ids", None)
    expected = {f"model.{key}" for key in backbone.state_dict()}
    expected.update({f"out.{key}" for key in projection.state_dict()})
    if set(protein_weights) != expected:
        missing = sorted(expected - set(protein_weights))
        extra = sorted(set(protein_weights) - expected)
        raise RuntimeError(
            "ProTrek sequence-tower checkpoint mismatch: "
            f"missing={missing}, extra={extra}")
    backbone.load_state_dict({
        key[len("model."):]: value for key, value in protein_weights.items()
        if key.startswith("model.")
    })
    projection.load_state_dict({
        key[len("out."):]: value for key, value in protein_weights.items()
        if key.startswith("out.")
    })
    del checkpoint, weights, protein_weights

    dtype = torch.float16
    backbone.eval().to(device=device, dtype=dtype)
    projection.eval().to(device=device, dtype=dtype)
    tokenizer = EsmTokenizer.from_pretrained(protein_config)
    prepared = [str(value).upper()[:RAW_MAX["protein"]]
                for value in sequences]
    order = sorted(range(len(prepared)), key=lambda index: len(prepared[index]))
    rows = [None] * len(prepared)
    done = 0
    try:
        with torch.no_grad():
            for indices in _token_budget_batches(
                    order, prepared, MAX_LEN["protein"], token_budget):
                encoded = tokenizer(
                    [prepared[index] for index in indices],
                    return_tensors="pt", padding=True, truncation=True,
                    max_length=MAX_LEN["protein"])
                encoded = {key: value.to(device)
                           for key, value in encoded.items()}
                hidden = backbone.esm(**encoded).last_hidden_state
                pooled = normalize(projection(hidden[:, 0, :]), dim=-1)
                pooled = pooled.float().cpu().numpy()
                for index, row in zip(indices, pooled):
                    rows[index] = row
                previous, done = done, done + len(indices)
                if done // progress_every > previous // progress_every:
                    print(f"      {done}/{len(prepared)}", flush=True)
    finally:
        del backbone, projection
        torch.cuda.empty_cache()

    return np.vstack(rows).astype(np.float32), {
        "inference_device_type": "cuda",
        "inference_parameter_dtype": "torch.float16",
        "embedding_layer": "official ProTrek CLS projection, L2 normalized",
        "implementation_revision": spec["implementation_revision"],
        "n_tokenized_inputs_truncated": int(sum(
            len(str(value)) > RAW_MAX["protein"] for value in sequences)),
        "maximum_untruncated_token_length": int(max(
            (len(str(value)) for value in sequences), default=0)),
    }


def embed_evo1(sequences, spec, token_budget=1536, progress_every=1000):
    """Mean-pool Evo 1's final normalized contextual states.

    The Hugging Face wrapper exposes logits but not hidden states. A forward
    hook on the final backbone norm captures the representation immediately
    before the tied vocabulary projection, preserving the same final-layer,
    mean-pooling rule used for the encoder models.
    """
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    device = "cuda"
    kw = {"revision": spec["revision"], "trust_remote_code": True}
    config = AutoConfig.from_pretrained(spec["checkpoint"], **kw)
    config.use_cache = False
    tokenizer = AutoTokenizer.from_pretrained(spec["checkpoint"], **kw)
    model = AutoModelForCausalLM.from_pretrained(
        spec["checkpoint"], config=config, torch_dtype=torch.bfloat16, **kw)
    model.eval().to(device)

    raw = [str(value)[:RAW_MAX["genomics"]] for value in sequences]
    order = sorted(range(len(raw)), key=lambda index: len(raw[index]))
    pooled_by_index = [None] * len(raw)
    captured = []

    def capture_final_norm(_module, _inputs, output):
        captured.append(output.detach())

    handle = model.backbone.norm.register_forward_hook(capture_final_norm)
    done = 0
    try:
        with torch.no_grad():
            for indices in _token_budget_batches(
                    order, raw, MAX_LEN["genomics"], token_budget):
                texts = [raw[index] for index in indices]
                use_padding = tokenizer.pad_token_id is not None
                if not use_padding and len({len(text) for text in texts}) != 1:
                    raise RuntimeError(
                        "Evo 1 has no padding token; batching therefore "
                        "requires equal-length sequences")
                encoded = tokenizer(
                    texts, return_tensors="pt", padding=use_padding,
                    truncation=True, max_length=MAX_LEN["genomics"],
                    return_special_tokens_mask=True)
                encoded = {key: value.to(device)
                           for key, value in encoded.items()}
                special = encoded.pop("special_tokens_mask", None)
                # Evo's byte tokenizer emits segment identifiers for
                # Transformers compatibility, but StripedHyena has no segment
                # embeddings and its forward method intentionally omits them.
                encoded.pop("token_type_ids", None)
                captured.clear()
                model(**encoded, use_cache=False)
                if len(captured) != 1:
                    raise RuntimeError(
                        f"Evo 1 final norm hook fired {len(captured)} times")
                hidden = captured[0]
                mask = encoded.get("attention_mask")
                if mask is None:
                    mask = torch.ones(hidden.shape[:2], device=device)
                if special is not None and special.shape == mask.shape:
                    mask = mask * (1 - special.to(mask.dtype))
                mask = mask.unsqueeze(-1).to(hidden.dtype)
                pooled = ((hidden * mask).sum(1)
                          / mask.sum(1).clamp(min=1)).float().cpu().numpy()
                for index, row in zip(indices, pooled):
                    pooled_by_index[index] = row
                done += len(indices)
                if done % progress_every < len(indices):
                    print(f"      {done}/{len(raw)}", flush=True)
    finally:
        handle.remove()
        del model
        torch.cuda.empty_cache()

    return np.vstack(pooled_by_index).astype(np.float32), {
        "inference_device_type": device,
        "inference_parameter_dtype": "torch.bfloat16",
        "embedding_layer": "backbone.norm output before vocabulary projection",
        "n_tokenized_inputs_truncated": int(sum(
            len(value) > RAW_MAX["genomics"] for value in sequences)),
        "maximum_untruncated_token_length": int(max(
            (len(str(value)) for value in sequences), default=0)),
    }


def embed_evo2(sequences, spec, progress_every=250):
    """Mean-pool Evo 2's final normalized contextual states.

    Evo 2's official 7B configuration supports one sequence per forward pass.
    Its public embedding interface can hook named layers; ``norm`` is the final
    representation before the vocabulary projection and is therefore the
    architecture-matched counterpart of an encoder's last hidden state.
    """
    import torch
    from evo2 import Evo2

    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    model = Evo2(spec["model_name"])
    device = next(model.model.parameters()).device
    rows = []
    for index, value in enumerate(sequences, start=1):
        text = str(value)[:RAW_MAX["genomics"]]
        input_ids = torch.tensor(
            model.tokenizer.tokenize(text), dtype=torch.int,
        ).unsqueeze(0).to(device)
        _logits, embeddings = model(
            input_ids, return_embeddings=True, layer_names=["norm"])
        hidden = embeddings["norm"]
        rows.append(hidden.mean(dim=1).float().cpu().numpy()[0])
        if index % progress_every == 0:
            print(f"      {index}/{len(sequences)}", flush=True)
    del model
    torch.cuda.empty_cache()
    return np.vstack(rows).astype(np.float32), {
        "inference_device_type": "cuda",
        "inference_parameter_dtype": "official Evo 2 bfloat16 policy",
        "embedding_layer": "final norm output before vocabulary projection",
        "n_tokenized_inputs_truncated": int(sum(
            len(str(value)) > RAW_MAX["genomics"] for value in sequences)),
        "maximum_untruncated_token_length": int(max(
            (len(str(value)) for value in sequences), default=0)),
    }


# ------------------------------------------------------------------ driver

def generate(model_id, dataset_name, inputs, modality, force=False,
             isolate=True):
    """Generate (or load from cache) the frozen matrix for one model/dataset.

    Neural checkpoints are embedded in a subprocess by default. An allocation
    failure on this stack surfaces as a CUDA context error rather than a clean
    Python exception, and once it occurs every later CUDA call in the same
    process fails too -- so one oversized model would otherwise take down every
    model queued behind it. Isolating each run confines that to its own cell.
    """
    spec = MODEL_REGISTRY[model_id]
    if not is_applicable(model_id, dataset_name, modality):
        return None  # not applicable -- reported as N/A, never imputed

    path = cache_path(model_id, dataset_name)
    input_sha256 = hashlib.sha256(
        "\0".join(str(value) for value in inputs).encode("utf-8")
    ).hexdigest()
    if os.path.exists(path) and not force:
        cached = np.load(path)
        meta_path = path.replace(".npy", ".json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as fh:
                meta = json.load(fh)
        expected_policy = inference_precision_policy(spec)
        content_matches = (
            cached.shape[0] == len(inputs)
            and meta.get("input_sha256") == input_sha256
            and meta.get("protocol_version") == EMBED_PROTOCOL_VERSION
            and meta.get("revision") == spec.get("revision")
            and ("checkpoint_sha256" not in spec
                 or meta.get("checkpoint_sha256") ==
                 spec["checkpoint_sha256"])
            and (not spec.get("replace_rare_amino_acids")
                 or meta.get("rare_amino_acid_mapping") == "UZOB->X")
            and ("inference_seed" not in spec
                 or meta.get("inference_seed") == spec["inference_seed"])
            and meta.get("inference_precision_policy") == expected_policy
        )
        if content_matches:
            return cached
        print(f"      stale cache for {model_id}/{dataset_name}; regenerating",
              flush=True)

    kind = spec["kind"]
    extra_meta = {}

    if kind in {"hf", "unimol", "molclr", "grover", "evo1", "evo2",
                "unirep", "esmc", "protrek"} and isolate:
        interpreter = spec.get("interpreter", sys.executable)
        if not os.path.exists(interpreter):
            raise RuntimeError(
                f"{model_id}: declared interpreter {interpreter} does not "
                f"exist; the model is not evaluated rather than substituted")
        command = [interpreter, "-u", os.path.abspath(__file__),
                   model_id, dataset_name]
        if force:
            command.append("--force")
        child_env = {**os.environ, "PYTHONPATH": ""}
        environment_root = os.path.dirname(os.path.dirname(
            os.path.abspath(interpreter)))
        environment_libraries = [
            os.path.join(environment_root, "lib"),
            os.path.join(environment_root, "targets", "x86_64-linux", "lib"),
        ]
        library_path = [path for path in environment_libraries
                        if os.path.isdir(path)]
        if child_env.get("LD_LIBRARY_PATH"):
            library_path.append(child_env["LD_LIBRARY_PATH"])
        child_env["LD_LIBRARY_PATH"] = os.pathsep.join(library_path)
        subprocess.run(
            command,
            check=True, env=child_env,
        )
        if not os.path.exists(path):
            raise RuntimeError(
                f"{model_id}/{dataset_name}: isolated embedding run produced "
                f"no cache file")
        return np.load(path)
    if kind == "ecfp4":
        mat = embed_ecfp4(inputs)
    elif kind == "rdkit":
        mat = embed_rdkit2d(inputs)
    elif kind == "kmer":
        mat = embed_kmer(inputs, spec["k"], modality)
    elif kind == "hf":
        mat, extra_meta = embed_hf(inputs, spec, modality)
    elif kind == "unirep":
        mat, extra_meta = embed_unirep(inputs, spec)
    elif kind == "esmc":
        mat, extra_meta = embed_esmc(inputs, spec)
    elif kind == "protrek":
        mat, extra_meta = embed_protrek(inputs, spec)
    elif kind == "evo1":
        mat, extra_meta = embed_evo1(inputs, spec)
    elif kind == "evo2":
        mat, extra_meta = embed_evo2(inputs, spec)
    elif kind == "unimol":
        mat, extra_meta = embed_unimol(inputs, spec)
    elif kind == "molclr":
        from benchmark.molclr_adapter import embed as embed_molclr
        mat, extra_meta = embed_molclr(inputs)
    elif kind == "grover":
        from benchmark.grover_adapter import embed as embed_grover
        mat, extra_meta = embed_grover(inputs, model_id)
    else:
        raise ValueError(f"Unknown model kind '{kind}' for {model_id}")

    if mat.shape[0] != len(inputs):
        raise RuntimeError(
            f"{model_id}/{dataset_name}: produced {mat.shape[0]} rows for "
            f"{len(inputs)} inputs")

    np.save(path, mat)
    runtime = None
    if kind in {"hf", "unimol", "molclr", "grover", "evo1", "evo2",
                "unirep", "esmc", "protrek"}:
        import torch
        runtime = {"python": platform.python_version(),
                   "torch": torch.__version__}
        if kind in {"hf", "evo1"}:
            import transformers
            runtime["transformers"] = transformers.__version__
            if spec.get("register_multimolecule"):
                runtime["multimolecule"] = importlib.metadata.version(
                    "multimolecule")
        elif kind == "evo2":
            runtime["evo2"] = importlib.metadata.version("evo2")
        elif kind == "unimol":
            from rdkit import rdBase
            runtime.update({
                "unimol_tools": importlib.metadata.version("unimol_tools"),
                "rdkit": rdBase.rdkitVersion,
            })
        elif kind == "unirep":
            runtime.update({
                "jax": importlib.metadata.version("jax"),
                "jax_unirep": importlib.metadata.version("jax-unirep"),
            })
        elif kind == "esmc":
            runtime.update({
                "esm": importlib.metadata.version("esm"),
            })
        elif kind == "protrek":
            import transformers
            runtime.update({
                "transformers": transformers.__version__,
            })
        else:
            from rdkit import rdBase
            runtime.update({
                "torch_geometric": importlib.metadata.version("torch-geometric"),
                "rdkit": rdBase.rdkitVersion,
            })
    meta = {
        "model_id": model_id,
        "label": spec["label"],
        "dataset": dataset_name,
        "kind": kind,
        "checkpoint": spec.get("checkpoint"),
        "revision": spec.get("revision"),
        "protocol_version": EMBED_PROTOCOL_VERSION,
        "modality": modality,
        "n": int(mat.shape[0]),
        "dim": int(mat.shape[1]),
        "matrix_dtype": str(mat.dtype),
        "inference_precision_policy": inference_precision_policy(spec),
        "pooling": (
            "mean over attention-mask tokens with tokenizer special tokens excluded"
            if kind == "hf" else
            "mean over final normalized contextual states"
            if kind in {"evo1", "evo2"} else
            "published average hidden state over the protein sequence (h_avg)"
            if kind == "unirep" else
            "mean over final residue representations with special tokens excluded"
            if kind == "esmc" else
            "official projected CLS representation with L2 normalization"
            if kind == "protrek" else
            "mean over Uni-Mol atom vectors with tokenizer special vectors excluded"
            if kind == "unimol" else
            "official mean atom pooling before the contrastive projection head"
            if kind == "molclr" else
            "official concatenated atom-view and bond-view mean readouts"
            if kind == "grover" else "n/a"),
        "max_token_length_including_special_tokens": (
            MAX_LEN[modality]
            if kind in {"hf", "evo1", "evo2", "unirep", "esmc", "protrek"}
            else None),
        "raw_character_limit_before_tokenisation": (
            RAW_MAX[modality]
            if kind in {"hf", "evo1", "evo2", "unirep", "esmc", "protrek"}
            else None),
        "n_raw_inputs_truncated": (int(sum(
            RAW_MAX[modality] is not None and len(str(value)) > RAW_MAX[modality]
            for value in inputs))
            if kind in {"hf", "evo1", "evo2", "unirep", "esmc", "protrek"}
            and RAW_MAX[modality] is not None
            else None),
        "input_sha256": input_sha256,
        "inference_seed": spec.get("inference_seed"),
        "rare_amino_acid_mapping": (
            "UZOB->X" if spec.get("replace_rare_amino_acids") else None),
        "sha256": hashlib.sha256(mat.tobytes()).hexdigest(),
        "embedding_runtime": runtime,
        **extra_meta,
    }
    with open(path.replace(".npy", ".json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return mat


if __name__ == "__main__":
    # Entry point for the isolated per-model embedding run invoked by
    # generate(). Loads one dataset, embeds it with one model, writes the cache.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _model_id, _dataset = sys.argv[1], sys.argv[2]
    from benchmark.datasets import load_benchmark_dataset
    _data = load_benchmark_dataset(_dataset)
    generate(_model_id, _dataset, _data["inputs"], _data["modality"],
             force="--force" in sys.argv[3:], isolate=False)
