"""
Download Real Benchmark Datasets for BioLatent
==============================================

Fetches all nine benchmark datasets from their primary sources and writes them
to ``data/benchmark_datasets/<Task>.csv``.

Design rule: **official splits are preserved whenever the source defines one.**
Re-splitting a dataset that ships an author-defined split silently changes the
task -- most severely for Fluorescence, where the TAPE protocol trains on
low-mutation variants and tests on distant ones. A random split there turns a
generalisation benchmark into an interpolation benchmark and inflates every
score. Datasets with a published split therefore carry a ``split`` column;
datasets without one (the MoleculeNet tasks) are scaffold-split downstream by
``datasets.py``.

No dataset is ever synthesised. If a source is unreachable the download fails
loudly rather than substituting a fallback of different provenance.
"""

import os
import subprocess
import sys

import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_datasets")
os.makedirs(DATA_DIR, exist_ok=True)
PYTHON = sys.executable


def _run_hf_download(script_body, output_csv):
    """Run a HuggingFace download in a subprocess.

    Isolating the call is necessary because this package contains a module
    named ``datasets``, which shadows the HuggingFace library on import.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    result = subprocess.run(
        [PYTHON, "-c", script_body],
        capture_output=True, text=True, env=env, timeout=1800,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-800:])
    return pd.read_csv(output_csv)


def _write(out, name, expect_min):
    if len(out) < expect_min:
        raise RuntimeError(
            f"{name}: got {len(out)} rows, expected at least {expect_min}. "
            f"Refusing to write a degenerate dataset."
        )
    path = os.path.join(DATA_DIR, f"{name}.csv")
    out.to_csv(path, index=False)
    counts = dict(out["split"].value_counts()) if "split" in out.columns else {}
    print(f"   OK  {name}: {len(out)} rows {counts}")


# ---------------------------------------------------------------- molecules

def download_moleculenet():
    """BBBP, ClinTox, BACE, ESOL, Lipophilicity from DeepChem's MoleculeNet.

    These ship no official split; scaffold splitting is applied downstream.
    """
    print("[1/4] MoleculeNet (BBBP, ClinTox, BACE, ESOL, Lipophilicity)...")
    base = "https://deepchemdata.s3.us-west-1.amazonaws.com/datasets"
    sources = {
        "BBBP": ("BBBP.csv", "smiles", "p_np"),
        "ClinTox": ("clintox.csv.gz", "smiles", "FDA_APPROVED"),
        "BACE": ("bace.csv", "mol", "Class"),
        "ESOL": ("delaney-processed.csv", "smiles",
                 "measured log solubility in mols per litre"),
        "Lipophilicity": ("Lipophilicity.csv", "smiles", "exp"),
    }
    for name, (fname, smi_col, tgt_col) in sources.items():
        path = os.path.join(DATA_DIR, f"{name}.csv")
        if os.path.exists(path):
            print(f"   .. {name} already present, skipping")
            continue
        df = pd.read_csv(f"{base}/{fname}")
        out = pd.DataFrame({"smiles": df[smi_col], "target": df[tgt_col]}).dropna()
        _write(out.reset_index(drop=True), name, 1000)


def download_cyp3a4():
    """TDC CYP3A4 substrate prediction with TDC's scaffold split.

    This is the same task used by the audited CYP3A4 literature column. The
    larger ``CYP3A4_Veith`` dataset measures inhibition and is intentionally
    not substituted: substrate and inhibition are different biological labels.
    """
    dataset_id = "CYP3A4_Substrate_CarbonMangels"
    print(f"[2/4] CYP3A4 substrate (TDC {dataset_id}, scaffold split)...")
    from tdc.single_pred import ADME
    data = ADME(name=dataset_id)
    split = data.get_split(method="scaffold", seed=42, frac=[0.8, 0.1, 0.1])
    frames = []
    for key, tag in [("train", "train"), ("valid", "val"), ("test", "test")]:
        d = split[key]
        frames.append(pd.DataFrame({
            "smiles": d["Drug"], "target": d["Y"].astype(int), "split": tag,
        }))
    _write(pd.concat(frames, ignore_index=True), "CYP3A4", 600)


# ----------------------------------------------------------------- proteins

def download_deeploc():
    """DeepLoc subcellular localisation, official train/validation/test split.

    The source is multi-label over ten compartments; we take the argmax
    compartment as a single-label 10-class target. This is a documented
    simplification, not the original multi-label task.
    """
    print("[3/4] DeepLoc subcellular localisation (official split)...")
    csv_tmp = "/tmp/_deeploc_raw.csv"
    script = f'''
import datasets, pandas as pd
frames = []
for split, tag in [("train","train"),("validation","val"),("test","test")]:
    ds = datasets.load_dataset("bloyal/deeploc", split=split)
    d = ds.to_pandas(); d["split"] = tag
    frames.append(d)
pd.concat(frames, ignore_index=True).to_csv("{csv_tmp}", index=False)
'''
    df = _run_hf_download(script, csv_tmp)
    loc_cols = ["Cytoplasm", "Nucleus", "Extracellular", "Cell membrane",
                "Mitochondrion", "Plastid", "Endoplasmic reticulum",
                "Lysosome/Vacuole", "Golgi apparatus", "Peroxisome"]
    cols = [c for c in loc_cols if c in df.columns]
    if not cols:
        raise RuntimeError(f"DeepLoc: no localisation columns found in {list(df.columns)}")
    out = pd.DataFrame({
        "sequence": df["Sequence"].str.upper().str.strip(),
        "target": df[cols].fillna(0).values.argmax(axis=1),
        "split": df["split"],
    }).dropna()
    out = out[out["sequence"].str.len().between(30, 2000)].reset_index(drop=True)
    _write(out, "DeepLoc", 10000)


def download_fluorescence():
    """TAPE GFP fluorescence landscape, official split.

    The official partition is the point of the benchmark: training variants sit
    close to wild-type while the test set is dominated by distant, higher-order
    mutants, so the task measures extrapolation. The test split is deliberately
    larger than train.
    """
    print("[4/4] Fluorescence -- TAPE GFP landscape (official split)...")
    csv_tmp = "/tmp/_fluorescence_raw.csv"
    script = f'''
import datasets, pandas as pd
frames = []
for split, tag in [("train","train"),("valid","val"),("test","test")]:
    ds = datasets.load_dataset("proteinglm/fluorescence_prediction", split=split)
    d = ds.to_pandas(); d["split"] = tag
    frames.append(d)
pd.concat(frames, ignore_index=True).to_csv("{csv_tmp}", index=False)
'''
    df = _run_hf_download(script, csv_tmp)
    seq_col = next(c for c in df.columns if c.lower() in ("seq", "sequence", "primary"))
    tgt_col = next(c for c in df.columns
                   if c.lower() in ("label", "target", "log_fluorescence", "y"))
    out = pd.DataFrame({
        "sequence": df[seq_col].str.upper().str.strip(),
        "target": pd.to_numeric(df[tgt_col], errors="coerce"),
        "split": df["split"],
    }).dropna().reset_index(drop=True)
    _write(out, "Fluorescence", 20000)


# ----------------------------------------------------------------- genomics

def download_promoters():
    """Human promoter detection, Nucleotide Transformer ``promoter_all``.

    The benchmark now ships one 'default' config carrying every task in a
    ``task`` column; the older per-task config names no longer resolve. The
    official train/test partition is preserved.
    """
    print("[5/5] Human promoters (NT promoter_all, official split)...")
    csv_tmp = "/tmp/_promoters_raw.csv"
    script = f'''
import datasets, pandas as pd
frames = []
for split, tag in [("train","train"),("test","test")]:
    ds = datasets.load_dataset(
        "InstaDeepAI/nucleotide_transformer_downstream_tasks_revised",
        "default", split=split, trust_remote_code=True)
    ds = ds.filter(lambda r: r["task"] == "promoter_all")
    d = ds.to_pandas()[["sequence","label"]]; d["split"] = tag
    frames.append(d)
pd.concat(frames, ignore_index=True).to_csv("{csv_tmp}", index=False)
'''
    df = _run_hf_download(script, csv_tmp)
    out = pd.DataFrame({
        "sequence": df["sequence"].str.upper().str.strip(),
        "target": df["label"].astype(int),
        "split": df["split"],
    }).dropna().drop_duplicates(subset=["sequence"]).reset_index(drop=True)
    _write(out, "Promoters", 10000)


def verify_all():
    print("\n" + "=" * 72)
    print("VERIFICATION")
    print("=" * 72)
    for name in ["BBBP", "ClinTox", "BACE", "ESOL", "Lipophilicity",
                 "CYP3A4", "DeepLoc", "Fluorescence", "Promoters"]:
        path = os.path.join(DATA_DIR, f"{name}.csv")
        if not os.path.exists(path):
            print(f"  MISSING  {name}")
            continue
        df = pd.read_csv(path)
        col = "smiles" if "smiles" in df.columns else df.columns[0]
        uniq = df[col].nunique()
        split = f" splits={dict(df['split'].value_counts())}" if "split" in df.columns else " (scaffold-split downstream)"
        flag = "  DEGENERATE" if uniq / max(len(df), 1) < 0.01 else ""
        print(f"  {name:14s} {len(df):6d} rows, {uniq:6d} unique{split}{flag}")
    print("=" * 72)


if __name__ == "__main__":
    download_moleculenet()
    download_cyp3a4()
    download_deeploc()
    download_fluorescence()
    download_promoters()
    verify_all()
