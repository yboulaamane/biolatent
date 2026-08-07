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
import json
import os
import platform
import subprocess
import sys

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors

RDLogger.DisableLog("rdApp.*")

EMB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "embeddings")
os.makedirs(EMB_DIR, exist_ok=True)

MAX_LEN = {"protein": 512, "genomics": 512, "molecule": 256}
RAW_MAX = {"protein": 510, "genomics": 510, "molecule": None}
RARE_AA_TRANSLATION = str.maketrans({residue: "X" for residue in "UZOB"})
EMBED_PROTOCOL_VERSION = 2
MOLFORMER_ENV = os.path.expanduser("~/biolatent_molformer_env/bin/python")

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

    # --- proteins: classical baseline ---
    "kmer3_protein": {"kind": "kmer", "modality": "protein", "k": 3,
                      "label": "3-mer frequency"},
    # --- proteins: pretrained language models ---
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
    "hyenadna": {"kind": "hf", "modality": "genomics",
                 "checkpoint": "LongSafari/hyenadna-tiny-1k-seqlen-hf",
                 "revision": "e8c1effa8673814e257e627d2e1eda9ea5a373f6",
                 "trust_remote_code": True, "label": "HyenaDNA tiny"},
}


def cache_path(model_id, dataset):
    return os.path.join(EMB_DIR, f"{model_id}__{dataset}.npy")


# ------------------------------------------------------------ classical

def embed_ecfp4(smiles_list, n_bits=1024, radius=2):
    from rdkit import DataStructs
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
    hidden = model(**enc).last_hidden_state

    mask = enc.get("attention_mask")
    if mask is None:
        mask = torch.ones(hidden.shape[:2], device=device)
    if special_mask is None:
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
    if spec["modality"] != modality:
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
        content_matches = (
            cached.shape[0] == len(inputs)
            and meta.get("input_sha256") == input_sha256
            and meta.get("protocol_version") == EMBED_PROTOCOL_VERSION
            and meta.get("revision") == spec.get("revision")
            and (not spec.get("replace_rare_amino_acids")
                 or meta.get("rare_amino_acid_mapping") == "UZOB->X")
            and ("inference_seed" not in spec
                 or meta.get("inference_seed") == spec["inference_seed"])
        )
        if content_matches:
            return cached
        print(f"      stale cache for {model_id}/{dataset_name}; regenerating",
              flush=True)

    kind = spec["kind"]
    extra_meta = {}

    if kind == "hf" and isolate:
        interpreter = spec.get("interpreter", sys.executable)
        if not os.path.exists(interpreter):
            raise RuntimeError(
                f"{model_id}: declared interpreter {interpreter} does not "
                f"exist; the model is not evaluated rather than substituted")
        command = [interpreter, "-u", os.path.abspath(__file__),
                   model_id, dataset_name]
        if force:
            command.append("--force")
        subprocess.run(
            command,
            check=True, env={**os.environ, "PYTHONPATH": ""},
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
    else:
        raise ValueError(f"Unknown model kind '{kind}' for {model_id}")

    if mat.shape[0] != len(inputs):
        raise RuntimeError(
            f"{model_id}/{dataset_name}: produced {mat.shape[0]} rows for "
            f"{len(inputs)} inputs")

    np.save(path, mat)
    runtime = None
    if kind == "hf":
        import torch
        import transformers
        runtime = {"python": platform.python_version(),
                   "torch": torch.__version__,
                   "transformers": transformers.__version__}
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
        "inference_precision_policy": (
            "float32 on all devices" if spec.get("force_float32")
            else "float16 on CUDA; float32 when CUDA is unavailable"),
        "pooling": ("mean over attention-mask tokens with tokenizer special "
                    "tokens excluded" if kind == "hf" else "n/a"),
        "max_token_length_including_special_tokens": (
            MAX_LEN[modality] if kind == "hf" else None),
        "raw_character_limit_before_tokenisation": (
            RAW_MAX[modality] if kind == "hf" else None),
        "n_raw_inputs_truncated": (int(sum(
            RAW_MAX[modality] is not None and len(str(value)) > RAW_MAX[modality]
            for value in inputs)) if kind == "hf" and RAW_MAX[modality] is not None
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
    from benchmark.datasets import load_benchmark_dataset

    _model_id, _dataset = sys.argv[1], sys.argv[2]
    _data = load_benchmark_dataset(_dataset)
    generate(_model_id, _dataset, _data["inputs"], _data["modality"],
             force="--force" in sys.argv[3:], isolate=False)
