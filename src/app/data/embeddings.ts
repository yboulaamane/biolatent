export interface EmbeddingEntry {
  id: string;
  name: string;
  developer: string;
  modality: 'Molecule' | 'Protein' | 'Complex';
  inputType: 'SMILES' | 'Amino Acid Sequence' | '3D Coordinates' | 'Graph' | 'Pocket/3D' | 'Substructure';
  dimension: number;
  trainingData: {
    name: string;
    size: string;
  };
  pretrainingObjective: string;
  license: string;
  links: {
    huggingface?: string;
    github?: string;
    paper?: string;
  };
  typicalTasks: string[];
  benchmarks: {
    dataset: string;
    metric: string;
    score: string;
  }[];
  codeSnippet: string;
}

export const EMBEDDINGS: EmbeddingEntry[] = [
  {
    id: "chemberta-2",
    name: "ChemBERTa-2 (77M MLM)",
    developer: "DeepChem & Duvenaud Lab",
    modality: "Molecule",
    inputType: "SMILES",
    dimension: 384,
    trainingData: {
      name: "PubChem10M / ZINC15",
      size: "77M molecules"
    },
    pretrainingObjective: "Masked Language Modeling (MLM) on SMILES tokens",
    license: "MIT",
    links: {
      huggingface: "https://huggingface.co/deepchem/ChemBERTa-77M-MLM",
      github: "https://github.com/deepchem/deepchem",
      paper: "https://arxiv.org/abs/2209.01712"
    },
    typicalTasks: ["QSAR regression", "ADMET screening", "Molecular toxicity classification"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.690" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.805" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "1.120" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.780" }
    ],
    codeSnippet: `from transformers import AutoTokenizer, AutoModel
import torch

# Load the pretrained ChemBERTa-2 tokenizer and model
tokenizer = AutoTokenizer.from_pretrained("deepchem/ChemBERTa-77M-MLM")
model = AutoModel.from_pretrained("deepchem/ChemBERTa-77M-MLM")
model.eval()

# Example SMILES string (Aspirin)
smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"

# Tokenize and run model
inputs = tokenizer(smiles, return_tensors="pt", padding=True, truncation=True)
with torch.no_grad():
    outputs = model(**inputs)

# Mean pooling over token embeddings
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (384,)`
  },
  {
    id: "molformer-xl",
    name: "MolFormer-XL",
    developer: "IBM Research & MILA",
    modality: "Molecule",
    inputType: "SMILES",
    dimension: 768,
    trainingData: {
      name: "ZINC20 & PubChem",
      size: "1.1 Billion molecules"
    },
    pretrainingObjective: "Linear attention-based Transformer with masking on SMILES",
    license: "MIT",
    links: {
      huggingface: "https://huggingface.co/ibm/MoLFormer-XL-Cperceiver-10pct",
      github: "https://github.com/IBM/molformer",
      paper: "https://www.nature.com/articles/s42256-022-00580-7"
    },
    typicalTasks: ["Molecular property prediction", "Chemical similarity", "Virtual screening"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.742" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.910" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "0.582" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.540" }
    ],
    codeSnippet: `from transformers import AutoModel, AutoTokenizer
import torch

# Load MolFormer-XL with trust_remote_code=True for custom architecture
tokenizer = AutoTokenizer.from_pretrained("ibm/MoLFormer-XL-Cperceiver-10pct", trust_remote_code=True)
model = AutoModel.from_pretrained("ibm/MoLFormer-XL-Cperceiver-10pct", trust_remote_code=True)
model.eval()

# Example SMILES string
smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"

inputs = tokenizer(smiles, return_tensors="pt", padding=True, truncation=True)
with torch.no_grad():
    outputs = model(**inputs)

# Use pooler output for general downstream tasks
embeddings = outputs.pooler_output.squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (768,)`
  },
  {
    id: "uni-mol",
    name: "Uni-Mol",
    developer: "DP Technology & Peking University",
    modality: "Molecule",
    inputType: "3D Coordinates",
    dimension: 512,
    trainingData: {
      name: "ZINC15 3D conformers",
      size: "19M molecules (multiple 3D conformers)"
    },
    pretrainingObjective: "3D spatial coordinates prediction and masked atom modeling",
    license: "Apache-2.0",
    links: {
      github: "https://github.com/dptech-corp/Uni-Mol",
      paper: "https://openreview.net/forum?id=9T4Z3_2ODa"
    },
    typicalTasks: ["3D property prediction", "Conformation generation", "Protein-ligand docking"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.751" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.932" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "0.510" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.525" }
    ],
    codeSnippet: `# Uni-Mol requires generating 3D conformers first (e.g. using RDKit ETKDG)
# and installing the 'unimol' python library.
import torch
from unimol.models import UniMolModel

# Load the Uni-Mol model checkpoint (downloaded from Uni-Mol repo)
# model = UniMolModel.from_pretrained("path/to/checkpoint.pt")

# Raw representation loading pseudocode:
# inputs = {
#     "atoms": torch.tensor([[6, 8, 8, 6, ...]]), # Atomic numbers
#     "coordinates": torch.tensor([[[0.1, 0.2, 0.3], ...]]) # 3D positions
# }
# with torch.no_grad():
#     embeddings = model.extract_features(inputs) # Shape: [1, 512]`
  },
  {
    id: "mol2vec",
    name: "Mol2Vec",
    developer: "Jaeger et al. (University of Hamburg)",
    modality: "Molecule",
    inputType: "Substructure",
    dimension: 300,
    trainingData: {
      name: "ZINC / ChEMBL",
      size: "20M molecules"
    },
    pretrainingObjective: "Word2Vec (Skip-gram) on Morgan substructure identifiers",
    license: "MIT",
    links: {
      github: "https://github.com/samoturk/mol2vec",
      paper: "https://pubs.acs.org/doi/10.1021/acs.jcim.7b00614"
    },
    typicalTasks: ["Chemical similarity search", "Fast baseline QSAR models"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.672" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.755" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "1.250" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.850" }
    ],
    codeSnippet: `from rdkit import Chem
from mol2vec.features import sentences2vec, MoleculeSentence
from gensim.models import Word2Vec

# Load pre-trained Mol2Vec Word2Vec model
model = Word2Vec.load("model_300dim.pkl")

# Generate embedding for Aspirin
mol = Chem.MolFromSmiles("CC(=O)OC1=CC=CC=C1C(=O)O")
sentence = MoleculeSentence(mol)
# Extract 300d molecular embedding
embedding = sentences2vec([sentence], model, unseen="UNK")[0]
print("Embedding shape:", embedding.shape) # Output: (300,)`
  },
  {
    id: "grover",
    name: "GROVER",
    developer: "Tencent AI Lab",
    modality: "Molecule",
    inputType: "Graph",
    dimension: 1000,
    trainingData: {
      name: "ZINC15 & ChEMBL",
      size: "11M molecules"
    },
    pretrainingObjective: "Node/edge/subgraph masked attribute prediction on graphs",
    license: "MIT",
    links: {
      github: "https://github.com/tencent-ailab/grover",
      paper: "https://arxiv.org/abs/2007.01211"
    },
    typicalTasks: ["Large-scale Graph QSAR", "Molecular similarity", "ADMET prediction"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.735" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.908" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "0.680" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.612" }
    ],
    codeSnippet: `# GROVER requires loading via their custom codebase and downloading weights.
# Code snippet shows extraction using the GROVER argument parser.
# Run following in terminal to extract representations:
# python main.py fingerprint \\
#     --data_path data/smiles.csv \\
#     --features_generator rdkit_2d \\
#     --checkpoint_path checkpoints/grover_large.pt \\
#     --output_path embeddings.npz`
  },
  {
    id: "chemgpt",
    name: "ChemGPT (1.2B)",
    developer: "Valence Labs & Recursion",
    modality: "Molecule",
    inputType: "SMILES",
    dimension: 2048,
    trainingData: {
      name: "PubChem",
      size: "10M molecules"
    },
    pretrainingObjective: "Autoregressive generative pretraining on SMILES strings",
    license: "MIT",
    links: {
      huggingface: "https://huggingface.co/ncfrey/ChemGPT-1.2B",
      github: "https://github.com/valencelabs/ChemGPT",
      paper: "https://arxiv.org/abs/2210.01776"
    },
    typicalTasks: ["De novo molecule generation", "Molecular property classification"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.685" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.820" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "1.080" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.790" }
    ],
    codeSnippet: `from transformers import AutoTokenizer, GPT2Model
import torch

tokenizer = AutoTokenizer.from_pretrained("ncfrey/ChemGPT-1.2B")
model = GPT2Model.from_pretrained("ncfrey/ChemGPT-1.2B")
model.eval()

smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
inputs = tokenizer(smiles, return_tensors="pt")

with torch.no_grad():
    outputs = model(**inputs)

# Use final token representation or average pooling
embeddings = outputs.last_hidden_state[:, -1, :].squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (2048,)`
  },
  {
    id: "bartsmiles",
    name: "BARTSmiles",
    developer: "University of Maryland & Meta AI",
    modality: "Molecule",
    inputType: "SMILES",
    dimension: 1024,
    trainingData: {
      name: "ZINC20",
      size: "1 Billion molecules"
    },
    pretrainingObjective: "Sequence-to-sequence denoising BART (masking/rotation/deletion)",
    license: "MIT",
    links: {
      github: "https://github.com/BorealisAI/BARTSmiles",
      paper: "https://arxiv.org/abs/2211.16349"
    },
    typicalTasks: ["Chemical reaction prediction", "Optimization", "Property screening"],
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.755" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.925" },
      { dataset: "ESOL (Solubility)", metric: "RMSE", score: "0.550" },
      { dataset: "Lipophilicity", metric: "RMSE", score: "0.512" }
    ],
    codeSnippet: `# BARTSmiles is integrated via fairseq.
# To extract representations:
# from fairseq.models.bart import BARTModel
# bart = BARTModel.from_pretrained('checkpoints/', checkpoint_file='bart_large.pt')
# smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
# tokens = bart.encode(smiles)
# features = bart.extract_features(tokens) # Shape: [1, seq_len, 1024]`
  },
  {
    id: "esm-2-650m",
    name: "ESM-2 (650M parameter)",
    developer: "Meta AI",
    modality: "Protein",
    inputType: "Amino Acid Sequence",
    dimension: 1280,
    trainingData: {
      name: "UniRef50 / ESM Atlas",
      size: "250M protein sequences"
    },
    pretrainingObjective: "Masked Language Modeling (MLM) on amino acid characters",
    license: "MIT",
    links: {
      huggingface: "https://huggingface.co/facebook/esm2_t33_650M_UR50D",
      github: "https://github.com/facebookresearch/esm",
      paper: "https://www.science.org/doi/10.1126/science.ade2597"
    },
    typicalTasks: ["Protein structure prediction (ESMFold)", "Mutational effect prediction", "Function annotation"],
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.840" },
      { dataset: "Thermostability (FLIP)", metric: "Spearman r", score: "0.680" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.895" }
    ],
    codeSnippet: `from transformers import AutoTokenizer, EsmModel
import torch

# Load ESM-2 650M model
tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
model = EsmModel.from_pretrained("facebook/esm2_t33_650M_UR50D")
model.eval()

# GFP sequence
sequence = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICT"

inputs = tokenizer(sequence, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)

# Mean pooling over amino acid token embeddings
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (1280,)`
  },
  {
    id: "esm-2-3b",
    name: "ESM-2 (3B parameter)",
    developer: "Meta AI",
    modality: "Protein",
    inputType: "Amino Acid Sequence",
    dimension: 2560,
    trainingData: {
      name: "UniRef50 / ESM Atlas",
      size: "250M protein sequences"
    },
    pretrainingObjective: "High-capacity Masked Language Modeling",
    license: "MIT",
    links: {
      huggingface: "https://huggingface.co/facebook/esm2_t36_3B_UR50D",
      github: "https://github.com/facebookresearch/esm",
      paper: "https://www.science.org/doi/10.1126/science.ade2597"
    },
    typicalTasks: ["Zero-shot fitness prediction", "De novo protein design", "Contact map extraction"],
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.865" },
      { dataset: "Thermostability (FLIP)", metric: "Spearman r", score: "0.710" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.912" }
    ],
    codeSnippet: `from transformers import AutoTokenizer, EsmModel
import torch

# Load ESM-2 3B model (requires GPU / high RAM)
tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t36_3B_UR50D")
model = EsmModel.from_pretrained("facebook/esm2_t36_3B_UR50D")
model.eval()

sequence = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICT"
inputs = tokenizer(sequence, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)

# Mean pooling over sequence
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (2560,)`
  },
  {
    id: "prott5-xl",
    name: "ProtT5-XL-UniRef50",
    developer: "Rost Lab",
    modality: "Protein",
    inputType: "Amino Acid Sequence",
    dimension: 1024,
    trainingData: {
      name: "UniRef50 & BFD",
      size: "2.1 Billion protein sequences"
    },
    pretrainingObjective: "Seq2Seq Span Denoising (T5 framework)",
    license: "Academic/Commercial",
    links: {
      huggingface: "https://huggingface.co/Rostlab/prot_t5_xl_uniref50",
      github: "https://github.com/agemf/prot_t5_xl_uniref50",
      paper: "https://ieeexplore.ieee.org/document/9477085"
    },
    typicalTasks: ["Secondary structure prediction", "Localization", "Binding site detection"],
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.852" },
      { dataset: "Thermostability (FLIP)", metric: "Spearman r", score: "0.695" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.902" }
    ],
    codeSnippet: `from transformers import T5EncoderModel, T5Tokenizer
import torch
import re

# Load ProtT5-XL
tokenizer = T5Tokenizer.from_pretrained("Rostlab/prot_t5_xl_uniref50", do_lower_case=False)
model = T5EncoderModel.from_pretrained("Rostlab/prot_t5_xl_uniref50")
model.eval()

# Sequence must be space-separated and 'U,Z,O,B' replaced
seq = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICT"
seq_spaced = " ".join(list(re.sub(r"[UZOB]", "X", seq)))

inputs = tokenizer(seq_spaced, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)

embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (1024,)`
  },
  {
    id: "ankh",
    name: "Ankh (Large)",
    developer: "Oxford Protein Informatics Group",
    modality: "Protein",
    inputType: "Amino Acid Sequence",
    dimension: 1536,
    trainingData: {
      name: "UniRef50",
      size: "200M+ protein sequences"
    },
    pretrainingObjective: "Highly optimized MLM and Sequence Contrastive learning",
    license: "Apache-2.0",
    links: {
      huggingface: "https://huggingface.co/Elana/ankh-large",
      github: "https://github.com/Rostlab/Ankh",
      paper: "https://arxiv.org/abs/2301.06568"
    },
    typicalTasks: ["Protein-protein interactions", "Thermostability", "Zero-shot protein engineering"],
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.858" },
      { dataset: "Thermostability (FLIP)", metric: "Spearman r", score: "0.715" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.908" }
    ],
    codeSnippet: `import ankh
import torch

# Load the pretrained Ankh model and tokenizer
model, tokenizer = ankh.load_large_model()
model.eval()

sequence = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICT"
inputs = tokenizer([list(sequence)], is_split_into_words=True, return_tensors="pt")

with torch.no_grad():
    outputs = model(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'])

# Pool embedding
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
print("Embedding shape:", embeddings.shape) # Output: (1536,)`
  },
  {
    id: "gearnet",
    name: "GearNet",
    developer: "Mila & Valence Labs",
    modality: "Protein",
    inputType: "3D Coordinates",
    dimension: 512,
    trainingData: {
      name: "PDB (Protein Data Bank)",
      size: "80,000+ protein structures"
    },
    pretrainingObjective: "Contrastive learning and spatial coordinate denoising on graphs",
    license: "MIT",
    links: {
      github: "https://github.com/DeepGraphLearning/torchdrug",
      paper: "https://arxiv.org/abs/2203.06125"
    },
    typicalTasks: ["Protein structure representation", "Ligand binding prediction", "Enzyme classification"],
    benchmarks: [
      { dataset: "EC (Enzyme Commission)", metric: "F1-max", score: "0.812" },
      { dataset: "GO (Gene Ontology - BP)", metric: "F1-max", score: "0.450" }
    ],
    codeSnippet: `# GearNet runs via the TorchDrug library.
# Below is TorchDrug instantiation pseudocode:
# from torchdrug import datasets, models, tasks
# model = models.GearNet(input_dim=21, hidden_dims=[512, 512, 512], 
#                        num_relation=7, edge_input_dim=59)
# checkpoint = torch.load("gearnet_weights.pth")
# model.load_state_dict(checkpoint)`
  },
  {
    id: "diffdock",
    name: "DiffDock Pocket Embeddings",
    developer: "MIT Jameel Clinic (Corso et al.)",
    modality: "Complex",
    inputType: "Pocket/3D",
    dimension: 1024,
    trainingData: {
      name: "PDBBind v2020",
      size: "19,000+ protein-ligand structures"
    },
    pretrainingObjective: "Equivariant GNN representations representing ligand docking poses and pocket coordinates",
    license: "MIT",
    links: {
      github: "https://github.com/gcorso/DiffDock",
      paper: "https://arxiv.org/abs/2210.01776"
    },
    typicalTasks: ["Blind docking", "Binding affinity prediction", "Ligand-protein classification"],
    benchmarks: [
      { dataset: "PDBBind (Affinity)", metric: "RMSE", score: "1.450" }
    ],
    codeSnippet: `# DiffDock extracts ligand and pocket embeddings during the docking process.
# Pseudocode for extracting representations using DiffDock's Equivariant GNN:
# from utils.parsing import parse_pdb, parse_sdf
# from models.score_model import TensorProductScoreModel
# ...
# ligand_emb, pocket_emb = model.extract_complex_embeddings(ligand_graph, pocket_graph)`
  },
  {
    id: "pocket-transformer",
    name: "PocketTransformer",
    developer: "Xie et al.",
    modality: "Complex",
    inputType: "Pocket/3D",
    dimension: 768,
    trainingData: {
      name: "ScPDB / PDBBind",
      size: "16,000+ druggable pockets"
    },
    pretrainingObjective: "Geometric transformer encoding pocket spatial geometries and atomic descriptors",
    license: "Academic/Restrictive",
    links: {
      github: "https://github.com/xielab/pocket-transformer",
      paper: "https://doi.org/10.1093/bioinformatics/btac512"
    },
    typicalTasks: ["Pocket similarity", "Ligand binding specificity", "Druggability prediction"],
    benchmarks: [
      { dataset: "ScPDB (Similarity)", metric: "Mean AP", score: "0.820" }
    ],
    codeSnippet: `# PocketTransformer processes PDB pocket files directly into embeddings.
# from pocket_transformer import PocketEncoder
# encoder = PocketEncoder.from_pretrained("pocket_transformer_768d")
# pocket_features = encoder.embed_pocket("pocket.pdb") # Shape: [1, 768]`
  }
];

