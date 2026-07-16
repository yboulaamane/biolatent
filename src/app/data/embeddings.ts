export type RepresentationType = 'learned_embedding' | 'fixed_descriptor' | 'hybrid_representation';

export interface BaseRepresentation {
  id: string;
  name: string;
  aliases?: string[];
  version?: string;
  yearReleased?: number;
  maintainer?: string;
  developer?: string;
  representationType: RepresentationType;
  modality: 'molecule' | 'protein' | 'complex' | 'reaction';
  inputRepresentation: 'SMILES' | 'graph' | 'sequence' | '3D' | 'engineered_features' | 'Pocket/3D';
  license: string;
  
  // Availability
  weightsUrl?: string;
  codeRepositoryUrl?: string;
  librarySupport?: string;

  // Usage constraints
  inferenceRequirements?: string;
  computeProfile: 'cpu' | 'gpu' | 'mixed';

  // Evaluation & Utility
  dataLeakageRisk: 'low' | 'medium' | 'high' | 'unknown';
  reproducibilityScore: number; // 0 to 1
  domainGeneralization: 'low' | 'medium' | 'high';
  smallDataPerformance: 'low' | 'medium' | 'high';
  
  // Downstream task scores
  benchmarks: {
    dataset: string;
    metric: string;
    score: string;
  }[];

  tags: string[];
  codeSnippet: string;
}

export interface LearnedEmbedding extends BaseRepresentation {
  representationType: 'learned_embedding';
  architectureType: string; // Transformer, GNN, VAE, etc.
  pretrainingObjective: string;
  parameterCount?: string;
  embeddingDimension: number;
  
  // Training data
  trainingData: {
    name: string;
    size: string;
    preprocessingSteps?: string;
    license: string;
  };
}

export interface FixedDescriptor extends BaseRepresentation {
  representationType: 'fixed_descriptor';
  descriptorFamily: string; // ECFP, MACCS, RDKit2D, etc.
  algorithmType: 'hashed' | 'rule-based' | 'physicochemical';
  vectorType: 'binary' | 'count' | 'continuous';
  dimensionality: number | string;
}

export interface HybridRepresentation extends BaseRepresentation {
  representationType: 'hybrid_representation';
  embeddingDimension: number;
  components: {
    learnedModel: string;
    descriptorsUsed: string[];
    fusionMethod: 'concatenation' | 'projection' | 'attention' | 'ensemble';
  };
  // Optional training data if learned elements require it
  trainingData?: {
    name: string;
    size: string;
    license: string;
  };
}

export type RepresentationEntry = LearnedEmbedding | FixedDescriptor | HybridRepresentation;

export const EMBEDDINGS: RepresentationEntry[] = [
  // ==================== 1. SMALL MOLECULES ====================
  {
    id: "chemberta_v1",
    name: "ChemBERTa-v1 (MLM)",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "Masked Language Modeling (MLM)",
    embeddingDimension: 768,
    yearReleased: 2020,
    trainingData: {
      name: "ZINC15 subset",
      size: "10M molecules",
      license: "Restrictive (ZINC)"
    },
    codeRepositoryUrl: "https://github.com/deepchem/deepchem",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.85,
    domainGeneralization: "medium",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.643" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.760" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.635" }
    ],
    tags: ["Transformer", "SMILES", "BERT"],
    codeSnippet: `from transformers import AutoTokenizer, AutoModel
import torch

tokenizer = AutoTokenizer.from_pretrained("deepchem/chemberta-77m-mlm") # v1 fallback
model = AutoModel.from_pretrained("deepchem/chemberta-77m-mlm")
model.eval()

inputs = tokenizer("CC(=O)OC1=CC=CC=C1C(=O)O", return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()`
  },
  {
    id: "chemberta_77m",
    name: "ChemBERTa-2 (77M MLM)",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "Masked Language Modeling (MLM) on SMILES tokens",
    embeddingDimension: 384,
    yearReleased: 2022,
    trainingData: {
      name: "PubChem10M / ZINC15",
      size: "77M molecules",
      license: "CC0 / Mixed"
    },
    codeRepositoryUrl: "https://github.com/deepchem/deepchem",
    weightsUrl: "https://huggingface.co/deepchem/ChemBERTa-77M-MLM",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.95,
    domainGeneralization: "medium",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.690" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.805" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.655" }
    ],
    tags: ["BERT", "SMILES", "Transformers"],
    codeSnippet: `from transformers import AutoTokenizer, AutoModel
tokenizer = AutoTokenizer.from_pretrained("deepchem/ChemBERTa-77M-MLM")
model = AutoModel.from_pretrained("deepchem/ChemBERTa-77M-MLM")
inputs = tokenizer("CC(=O)OC1=CC=CC=C1C(=O)O", return_tensors="pt")
outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().detach().numpy()`
  },
  {
    id: "smiles_transformer",
    name: "SMILES Transformer",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "Seq2Seq SMILES reconstruction",
    embeddingDimension: 1024,
    yearReleased: 2019,
    trainingData: {
      name: "ChEMBL24",
      size: "1.7M molecules",
      license: "CC BY-SA 3.0"
    },
    codeRepositoryUrl: "https://github.com/honda-research-institute/smiles-transformer",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.70,
    domainGeneralization: "low",
    smallDataPerformance: "low",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.620" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.612" }
    ],
    tags: ["Seq2Seq", "SMILES", "Autoencoder"],
    codeSnippet: `# Requires custom repository implementation cloning smiles-transformer.
# import smiles_transformer as st
# model = st.load_model("weights.pt")
# embedding = model.embed("CC(=O)OC1=CC=CC=C1C(=O)O")`
  },
  {
    id: "molclr",
    name: "MolCLR (GNN Contrastive)",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "graph",
    license: "MIT",
    architectureType: "GNN (GIN / GCN)",
    pretrainingObjective: "Molecular Contrastive Learning (MolCLR)",
    embeddingDimension: 512,
    yearReleased: 2021,
    trainingData: {
      name: "PubChem10M subset",
      size: "10M molecules",
      license: "CC0"
    },
    codeRepositoryUrl: "https://github.com/yuyangw/MolCLR",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.88,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.736" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.890" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.690" }
    ],
    tags: ["Contrastive", "Graph", "GIN", "PyG"],
    codeSnippet: `# Clone and import from MolCLR repository:
# from models.ginet_finetune import GINet
# model = GINet(num_layer=5, emb_dim=300, feat_dim=512)
# model.load_state_dict(torch.load("pretrained_weights.pth"))
# model.eval()
# out_emb = model(molecular_graph)`
  },
  {
    id: "grover_base",
    name: "GROVER Base",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "graph",
    license: "MIT",
    architectureType: "GNN + Transformer",
    pretrainingObjective: "Masked subgraph node/edge classification",
    embeddingDimension: 1000,
    yearReleased: 2020,
    trainingData: {
      name: "ZINC15 & ChEMBL",
      size: "11M molecules",
      license: "Mixed"
    },
    codeRepositoryUrl: "https://github.com/tencent-ailab/grover",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.80,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.722" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.890" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.702" }
    ],
    tags: ["Graph", "Self-Supervised", "Grover"],
    codeSnippet: `# Extracted via terminal using GROVER argument parser:
# python main.py fingerprint --data_path smiles.csv \\
#     --checkpoint_path checkpoints/grover_base.pt \\
#     --output_path embeddings.npz`
  },
  {
    id: "grover_large",
    name: "GROVER Large",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "graph",
    license: "MIT",
    architectureType: "GNN + Transformer",
    pretrainingObjective: "Masked subgraph node/edge classification (Larger params)",
    embeddingDimension: 2000,
    yearReleased: 2020,
    trainingData: {
      name: "ZINC15 & ChEMBL",
      size: "11M molecules",
      license: "Mixed"
    },
    codeRepositoryUrl: "https://github.com/tencent-ailab/grover",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.80,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.735" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.908" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.712" }
    ],
    tags: ["Graph", "Self-Supervised", "Grover-Large"],
    codeSnippet: `# Run in shell terminal to output large 2000d fingerprint files:
# python main.py fingerprint --data_path smiles.csv \\
#     --checkpoint_path checkpoints/grover_large.pt \\
#     --output_path embeddings.npz`
  },
  {
    id: "gin_supervised_contextpred",
    name: "GIN Supervised + ContextPred",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "graph",
    license: "MIT",
    architectureType: "GIN (Graph Isomorphism Network)",
    pretrainingObjective: "Contextual topology matching + supervised molecular task pretraining",
    embeddingDimension: 300,
    yearReleased: 2019,
    trainingData: {
      name: "ZINC15 (unlabeled) + MoleculeNet (labeled)",
      size: "2M molecules + 450K supervised targets",
      license: "CC0 / Public Domain"
    },
    codeRepositoryUrl: "https://github.com/snap-stanford/pretrain-gnns",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.710" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.850" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.680" }
    ],
    tags: ["GNN", "GIN", "Context-Prediction"],
    codeSnippet: `# Uses snap-stanford torchGNN pipelines
# from models import GNN_drug
# model = GNN_drug(num_layer=5, emb_dim=300, GNN_type='gin')
# model.load_state_dict(torch.load('supervised_contextpred.pth'))`
  },
  {
    id: "graphormer_mol",
    name: "Graphormer Molecule",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "graph",
    license: "MIT",
    architectureType: "Graph Transformer",
    pretrainingObjective: "Atom/node type prediction and shortest-path distance encoding",
    embeddingDimension: 512,
    yearReleased: 2021,
    trainingData: {
      name: "PCBA / PubChem",
      size: "10M molecules",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/microsoft/Graphormer",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.85,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.725" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.895" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.695" }
    ],
    tags: ["Microsoft", "Graph-Transformer", "Attention"],
    codeSnippet: `# Graphormer runs using the fairseq interface or MS-Graphormer API
# from graphormer.models.graphormer import GraphormerModel
# model = GraphormerModel.from_pretrained('graphormer_base')`
  },
  {
    id: "dmpnn_chemprop",
    name: "D-MPNN (Chemprop)",
    representationType: "hybrid_representation",
    modality: "molecule",
    inputRepresentation: "engineered_features",
    license: "MIT",
    components: {
      learnedModel: "Directed MPNN (graph-encoder)",
      descriptorsUsed: ["200 RDKit molecular descriptors", "Morgan Fingerprints (ECFP4)"],
      fusionMethod: "concatenation"
    },
    embeddingDimension: 500,
    yearReleased: 2019,
    codeRepositoryUrl: "https://github.com/chemprop/chemprop",
    computeProfile: "mixed",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.98,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.730" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.905" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.730" }
    ],
    tags: ["Directed-MPNN", "Hybrid", "Physicochemical", "Chemprop"],
    codeSnippet: `import chemprop
# Chemprop runs via CLI or python API:
# arguments = ['--data_path', 'data.csv', '--dataset_type', 'regression', '--save_dir', 'checkpoints']
# args = chemprop.args.TrainArgs().parse_args(arguments)
# chemprop.train.run_training(args)`
  },
  {
    id: "mpnn_dti",
    name: "MPNN DTI",
    representationType: "learned_embedding",
    modality: "complex",
    inputRepresentation: "graph",
    license: "Academic/Restrictive",
    architectureType: "Message Passing Neural Network",
    pretrainingObjective: "Supervised drug-target interaction affinity regression",
    embeddingDimension: 128,
    yearReleased: 2018,
    trainingData: {
      name: "KIBA / Davis",
      size: "120,000+ binding affinities",
      license: "Academic Use"
    },
    codeRepositoryUrl: "https://github.com/lifesciencetrust/deep-dti",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.75,
    domainGeneralization: "low",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "Davis (Affinity)", metric: "CI (Concordance Index)", score: "0.880" }
    ],
    tags: ["DTI", "Binding", "Affinity", "MPNN"],
    codeSnippet: `# MPNN is usually integrated as a sub-model in target binding pipelines:
# from models import MPNN
# model = MPNN(num_edge_features=10, num_node_features=40)`
  },
  {
    id: "uni_mol",
    name: "Uni-Mol (3D)",
    representationType: "hybrid_representation",
    modality: "molecule",
    inputRepresentation: "3D",
    license: "Apache-2.0",
    components: {
      learnedModel: "3D Spatial Transformer",
      descriptorsUsed: ["RDKit conformation 3D atomic coordinates", "Pairwise spatial matrices"],
      fusionMethod: "concatenation"
    },
    embeddingDimension: 512,
    yearReleased: 2022,
    trainingData: {
      name: "ZINC15 3D conformers",
      size: "19M molecules (multiple conformers)",
      license: "Academic/Commercial"
    },
    codeRepositoryUrl: "https://github.com/dptech-corp/Uni-Mol",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.751" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.932" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.725" }
    ],
    tags: ["3D", "Transformer", "Conformation"],
    codeSnippet: `# Conformer input representation extraction:
# atoms = torch.tensor([[6, 8, 8, 6]]) # Aspirin skeleton
# coordinates = torch.tensor([[[0.1, 0.2, 0.3], [1.1, 1.2, 1.3], ...]])
# features = unimol_model.extract_features(atoms, coordinates)`
  },
  {
    id: "ecfp4_fingerprint",
    name: "ECFP4 (Extended-Connectivity Fingerprint)",
    representationType: "fixed_descriptor",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    descriptorFamily: "ECFP",
    algorithmType: "hashed",
    vectorType: "binary",
    dimensionality: 2048,
    yearReleased: 2010,
    codeRepositoryUrl: "https://github.com/rdkit/rdkit",
    computeProfile: "cpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 1.0,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.720" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.810" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.685" }
    ],
    tags: ["Classical", "Fingerprint", "RDKit", "Baseline"],
    codeSnippet: `from rdkit import Chem
from rdkit.ChemicalFeatures import GetMorganFingerprintAsBitVect

mol = Chem.MolFromSmiles("CC(=O)OC1=CC=CC=C1C(=O)O")
# Radius 2 matches ECFP4 fingerprint specification
fp = GetMorganFingerprintAsBitVect(mol, radius=2, nBits=2048)
fingerprint_array = list(fp)
print("Vector size:", len(fingerprint_array)) # Output: 2048`
  },
  {
    id: "rdkit_descriptors",
    name: "RDKit 2D Physical Descriptors",
    representationType: "fixed_descriptor",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    descriptorFamily: "RDKit2D",
    algorithmType: "physicochemical",
    vectorType: "continuous",
    dimensionality: 200,
    yearReleased: 2006,
    codeRepositoryUrl: "https://github.com/rdkit/rdkit",
    computeProfile: "cpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 1.0,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.680" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.785" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.692" }
    ],
    tags: ["Classical", "Descriptors", "Physicochemical", "RDKit"],
    codeSnippet: `from rdkit import Chem
from rdkit.Chem.Descriptors import CalcMolDescriptors

mol = Chem.MolFromSmiles("CC(=O)OC1=CC=CC=C1C(=O)O")
descriptors = CalcMolDescriptors(mol) # Returns dictionary of 200+ features
values = list(descriptors.values())
print("Descriptor count:", len(values))`
  },

  // ==================== 2. PROTEINS ====================
  {
    id: "esm2_t33_650M",
    name: "ESM-2 (650M parameter)",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "Masked Language Modeling (MLM)",
    embeddingDimension: 1280,
    yearReleased: 2022,
    trainingData: {
      name: "UniRef50 / ESM Atlas",
      size: "250M protein sequences",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/facebookresearch/esm",
    weightsUrl: "https://huggingface.co/facebook/esm2_t33_650M_UR50D",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.98,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.840" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.895" }
    ],
    tags: ["Meta", "Protein-LM", "Transformer", "ESM"],
    codeSnippet: `from transformers import AutoTokenizer, EsmModel
import torch

tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t33_650M_UR50D")
model = EsmModel.from_pretrained("facebook/esm2_t33_650M_UR50D")
inputs = tokenizer("MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGD", return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()`
  },
  {
    id: "esm2_t6_8M",
    name: "ESM-2 (8M parameter)",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "Masked Language Modeling (MLM) (Lightweight)",
    embeddingDimension: 320,
    yearReleased: 2022,
    trainingData: {
      name: "UniRef50 / ESM Atlas",
      size: "250M protein sequences",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/facebookresearch/esm",
    weightsUrl: "https://huggingface.co/facebook/esm2_t6_8M_UR50D",
    computeProfile: "cpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.98,
    domainGeneralization: "medium",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.710" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.780" }
    ],
    tags: ["Meta", "Protein-LM", "ESM-Light"],
    codeSnippet: `from transformers import AutoTokenizer, EsmModel
tokenizer = AutoTokenizer.from_pretrained("facebook/esm2_t6_8M_UR50D")
model = EsmModel.from_pretrained("facebook/esm2_t6_8M_UR50D")
inputs = tokenizer("MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGD", return_tensors="pt")
outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().detach().numpy()`
  },
  {
    id: "prot_bert_bfd",
    name: "ProtBERT BFD",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Academic/Restrictive",
    architectureType: "Transformer",
    pretrainingObjective: "Masked Language Modeling (MLM)",
    embeddingDimension: 1024,
    yearReleased: 2020,
    trainingData: {
      name: "BFD (Big Fantastic Database)",
      size: "2.1 Billion sequences",
      license: "Academic Use"
    },
    codeRepositoryUrl: "https://github.com/agemf/prot_t5_xl_uniref50",
    weightsUrl: "https://huggingface.co/Rostlab/prot_bert_bfd",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.95,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.825" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.875" }
    ],
    tags: ["Rostlab", "BERT", "Protein-LM"],
    codeSnippet: `from transformers import AutoTokenizer, BertModel
import torch

# Sequence must be spaced
tokenizer = AutoTokenizer.from_pretrained("Rostlab/prot_bert_bfd", do_lower_case=False)
model = BertModel.from_pretrained("Rostlab/prot_bert_bfd")
seq = "M S K G E E L F T"
inputs = tokenizer(seq, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()`
  },
  {
    id: "prot_t5_xl_uniref50",
    name: "ProtT5-XL-UniRef50",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Academic/Commercial",
    architectureType: "Transformer (T5 encoder)",
    pretrainingObjective: "Span Denoising Autoencoding",
    embeddingDimension: 1024,
    yearReleased: 2021,
    trainingData: {
      name: "UniRef50 & BFD",
      size: "2.1 Billion sequences",
      license: "Academic/Commercial"
    },
    codeRepositoryUrl: "https://github.com/agemf/prot_t5_xl_uniref50",
    weightsUrl: "https://huggingface.co/Rostlab/prot_t5_xl_uniref50",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.96,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.852" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.902" }
    ],
    tags: ["Rostlab", "T5", "Protein-LM"],
    codeSnippet: `from transformers import T5EncoderModel, T5Tokenizer
import torch
import re

tokenizer = T5Tokenizer.from_pretrained("Rostlab/prot_t5_xl_uniref50", do_lower_case=False)
model = T5EncoderModel.from_pretrained("Rostlab/prot_t5_xl_uniref50")
seq = " ".join(list(re.sub(r"[UZOB]", "X", "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGD")))
inputs = tokenizer(seq, return_tensors="pt")
with torch.no_grad():
    outputs = model(**inputs)
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()`
  },
  {
    id: "seqvec",
    name: "SeqVec",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Academic/Restrictive",
    architectureType: "Bi-directional LSTM (ELMo)",
    pretrainingObjective: "Autoregressive language modeling (Next token prediction)",
    embeddingDimension: 1024,
    yearReleased: 2019,
    trainingData: {
      name: "UniRef50",
      size: "93M protein sequences",
      license: "Academic Use"
    },
    codeRepositoryUrl: "https://github.com/rostlab/SeqVec",
    computeProfile: "cpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.85,
    domainGeneralization: "low",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.785" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.840" }
    ],
    tags: ["ELMo", "LSTM", "Rostlab"],
    codeSnippet: `# Requires the allennlp implementation from RostLab
# from seqvec import SeqVecEmbedder
# embedder = SeqVecEmbedder()
# embedding = embedder.embed_sentence("MSKGEELFTGVVPIL") # Returns [seq_len, 1024]`
  },
  {
    id: "ankh_base",
    name: "Ankh Base",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Apache-2.0",
    architectureType: "Transformer",
    pretrainingObjective: "MLM and Sequence-level contrastive alignment",
    embeddingDimension: 768,
    yearReleased: 2023,
    trainingData: {
      name: "UniRef50",
      size: "200M sequences",
      license: "Apache-2.0"
    },
    codeRepositoryUrl: "https://github.com/Rostlab/Ankh",
    weightsUrl: "https://huggingface.co/Elana/ankh-base",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.94,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.842" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.890" }
    ],
    tags: ["Ankh", "Contrastive", "Oxford"],
    codeSnippet: `import ankh
model, tokenizer = ankh.load_base_model()
model.eval()
inputs = tokenizer([list("MSKGEELFTG")], is_split_into_words=True, return_tensors="pt")
outputs = model(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'])
embeddings = outputs.last_hidden_state.mean(dim=1).squeeze().detach().numpy()`
  },
  {
    id: "msa_transformer",
    name: "MSA Transformer",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "MIT",
    architectureType: "Transformer (Axial Attention)",
    pretrainingObjective: "Masked language modeling on Multiple Sequence Alignments",
    embeddingDimension: 768,
    yearReleased: 2021,
    trainingData: {
      name: "UniRef50 alignments",
      size: "26M MSAs",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/facebookresearch/esm",
    weightsUrl: "https://huggingface.co/facebook/esm-msa",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Contact Prediction", metric: "Top-L Precision", score: "0.810" }
    ],
    tags: ["MSA", "Multiple-Sequence-Alignment", "Meta"],
    codeSnippet: `# Requires a list of aligned homologous sequences
# import esm
# model, alphabet = esm.pretrained.esm_msa1b_t12_100M_UR50S()
# batch_converter = alphabet.get_batch_converter()
# data = [("msa1", ["M-KTV", "MK-TV", "MKT-V"])]
# labels, strs, tokens = batch_converter(data)`
  },

  // ==================== 3. STRUCTURE / 3D MODELS ====================
  {
    id: "alphafold2_representations",
    name: "AlphaFold 2 Evoformer Latents",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "3D",
    license: "Apache-2.0",
    architectureType: "Evoformer (Spatial Transformer)",
    pretrainingObjective: "Supervised 3D coordinate structure regression",
    embeddingDimension: 256,
    yearReleased: 2021,
    trainingData: {
      name: "PDB structures + self-distillation",
      size: "100,000 PDB structures + 350,000 predictions",
      license: "Apache-2.0"
    },
    codeRepositoryUrl: "https://github.com/google-deepmind/alphafold",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.92,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "GDT-TS (CASP14)", metric: "Average GDT", score: "0.924" }
    ],
    tags: ["DeepMind", "AlphaFold2", "Evoformer", "3D"],
    codeSnippet: `# AlphaFold latents can be extracted from custom OpenFold or AlphaFold runs.
# From the results dictionary:
# representation = results['representations']['evoformer'] # Shape: [N_res, N_res, 256]`
  },
  {
    id: "openfold_single_chain",
    name: "OpenFold Single Chain",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Apache-2.0",
    architectureType: "Evoformer - Single Chain Variant",
    pretrainingObjective: "Structural prediction of single protein chains without MSAs",
    embeddingDimension: 384,
    yearReleased: 2022,
    trainingData: {
      name: "PDB + CAMEO",
      size: "120,000 structures",
      license: "Apache-2.0"
    },
    codeRepositoryUrl: "https://github.com/aqlaboratory/openfold",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "TM-score", metric: "TM-score", score: "0.780" }
    ],
    tags: ["OpenFold", "Single-Chain", "Evoformer", "3D"],
    codeSnippet: `# Extracted from OpenFold runner without MSA queries:
# from openfold.model.model import AlphaFold
# openfold_runner = AlphaFold(config)`
  },

  // ==================== 4. INTERACTION / PROTEIN-LIGAND MODELS ====================
  {
    id: "proteinmpnn_embedding",
    name: "ProteinMPNN Encoder Representations",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "3D",
    license: "MIT",
    architectureType: "Message Passing GNN (Structural)",
    pretrainingObjective: "Sequence generation given 3D structural backbone (Inverse Folding)",
    embeddingDimension: 128,
    yearReleased: 2022,
    trainingData: {
      name: "PDB structures (backbone coords)",
      size: "80,000 structures",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/dauparas/ProteinMPNN",
    computeProfile: "mixed",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.99,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Inverse Folding Recovery", metric: "Sequence Recovery", score: "0.524" }
    ],
    tags: ["ProteinMPNN", "Baker-Lab", "Inverse-Folding", "3D"],
    codeSnippet: `# Requires ProteinMPNN helper parser (parse_PDB.py)
# from protein_mpnn_utils import ProteinMPNN
# model = ProteinMPNN(node_features=128, edge_features=128)
# encoder_latents = model.encode(backbone_coordinates, mask)`
  },
  {
    id: "ligandmpnn_embedding",
    name: "LigandMPNN",
    representationType: "learned_embedding",
    modality: "complex",
    inputRepresentation: "Pocket/3D",
    license: "MIT",
    architectureType: "Heterogeneous Message Passing GNN",
    pretrainingObjective: "Protein design and sequence recovery conditioned on ligand pocket complexes",
    embeddingDimension: 256,
    yearReleased: 2023,
    trainingData: {
      name: "PDB complexes + small molecule coordinates",
      size: "95,000 protein-ligand structures",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/dauparas/LigandMPNN",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.95,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Sequence Recovery (Complexes)", metric: "Recovery", score: "0.570" }
    ],
    tags: ["LigandMPNN", "Baker-Lab", "Drug-Design", "Inverse-Folding"],
    codeSnippet: `# LigandMPNN design and representation loader
# from ligand_mpnn_utils import LigandMPNN
# model = LigandMPNN(node_features=256, edge_features=256)
# embedding = model.encode(protein_coords, ligand_coords, ligand_types)`
  },
  {
    id: "esm3_1.4b",
    name: "ESM-3 (1.4B parameter)",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "3D",
    license: "Academic/Restrictive",
    architectureType: "Transformer",
    pretrainingObjective: "Generative masked language modeling on sequence, structure, and function coordinates",
    embeddingDimension: 1536,
    yearReleased: 2024,
    trainingData: {
      name: "ESM-Atlas (UniRef + structures)",
      size: "2.7 Billion sequences / structures",
      license: "Non-commercial Research License"
    },
    codeRepositoryUrl: "https://github.com/evolutionaryscale/esm",
    weightsUrl: "https://huggingface.co/EvolutionaryScale/esm3-open-1.4b",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Structure Recovery (TM-score)", metric: "TM-score", score: "0.830" }
    ],
    tags: ["ESM-3", "EvolutionaryScale", "Multimodal", "Protein-Design"],
    codeSnippet: `from esm.models.esm3 import ESM3
from esm.sdk.api import ESM3InferenceClient, GenerationConfig
import torch

model: ESM3InferenceClient = ESM3.from_pretrained("esm3-open-1.4b")`
  },
  {
    id: "molformer_xl",
    name: "MolFormer-XL",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    architectureType: "Transformer (Linear Attention)",
    pretrainingObjective: "MLM with relative positional embeddings on SMILES",
    embeddingDimension: 768,
    yearReleased: 2022,
    trainingData: {
      name: "ZINC20 & PubChem",
      size: "1.1 Billion molecules",
      license: "CC0 / Mixed"
    },
    codeRepositoryUrl: "https://github.com/IBM/molformer",
    weightsUrl: "https://huggingface.co/ibm/MoLFormer-XL-Cperceiver-10pct",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.95,
    domainGeneralization: "medium",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.742" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.910" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.710" }
    ],
    tags: ["IBM", "Mila", "SMILES", "Linear-Attention"],
    codeSnippet: `from transformers import AutoModel, AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("ibm/MoLFormer-XL-Cperceiver-10pct", trust_remote_code=True)
model = AutoModel.from_pretrained("ibm/MoLFormer-XL-Cperceiver-10pct", trust_remote_code=True)`
  },
  {
    id: "prost_t5",
    name: "ProstT5 (Bilingual Seq-Struct)",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "Academic/Commercial",
    architectureType: "Transformer (T5 Encoder)",
    pretrainingObjective: "Translation translation of sequence to 3Di structural strings",
    embeddingDimension: 1024,
    yearReleased: 2023,
    trainingData: {
      name: "UniRef50 & Foldseek 3Di strings",
      size: "19M protein structures",
      license: "Academic/Commercial"
    },
    codeRepositoryUrl: "https://github.com/agemf/ProstT5",
    weightsUrl: "https://huggingface.co/Rostlab/ProstT5",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.94,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Secondary Structure (CB513)", metric: "Accuracy", score: "0.858" },
      { dataset: "Subcellular Localization (DeepLoc)", metric: "Accuracy", score: "0.910" }
    ],
    tags: ["Rostlab", "T5", "Structure-Sequence", "3Di"],
    codeSnippet: `from transformers import T5EncoderModel, T5Tokenizer
tokenizer = T5Tokenizer.from_pretrained("Rostlab/ProstT5", do_lower_case=False)
model = T5EncoderModel.from_pretrained("Rostlab/ProstT5")`
  },
  {
    id: "gearnet_structure",
    name: "GearNet",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "3D",
    license: "MIT",
    architectureType: "Relational GNN",
    pretrainingObjective: "Multi-relational spatial graph contrastive learning",
    embeddingDimension: 512,
    yearReleased: 2022,
    trainingData: {
      name: "PDB (Protein Data Bank)",
      size: "80,000+ protein structures",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/DeepGraphLearning/torchdrug",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "EC (Enzyme Commission)", metric: "F1-max", score: "0.812" },
      { dataset: "GO (Gene Ontology - BP)", metric: "F1-max", score: "0.450" }
    ],
    tags: ["Mila", "TorchDrug", "GNN", "Protein-Structure"],
    codeSnippet: `# from torchdrug import models
# model = models.GearNet(input_dim=21, hidden_dims=[512, 512, 512])`
  },
  {
    id: "antiberty",
    name: "AntiBERTy (Antibody Model)",
    representationType: "learned_embedding",
    modality: "protein",
    inputRepresentation: "sequence",
    license: "MIT",
    architectureType: "Transformer",
    pretrainingObjective: "MLM on immunoglobulin variable region sequences",
    embeddingDimension: 512,
    yearReleased: 2022,
    trainingData: {
      name: "OAS (Observed Antibody Space)",
      size: "350M antibody sequences",
      license: "Creative Commons Attribution 4.0"
    },
    codeRepositoryUrl: "https://github.com/jerryji1993/antiBERTy",
    weightsUrl: "https://huggingface.co/jerryji1993/antiBERTy",
    computeProfile: "gpu",
    dataLeakageRisk: "medium",
    reproducibilityScore: 0.95,
    domainGeneralization: "medium",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "Antibody Binding Affinity", metric: "Spearman r", score: "0.620" }
    ],
    tags: ["Antibody", "Immunoglobulin", "Therapeutic", "BERT"],
    codeSnippet: `from antiberty import AntiBERTyRunner
runner = AntiBERTyRunner()`
  },
  {
    id: "chemgpt",
    name: "ChemGPT (1.2B)",
    representationType: "learned_embedding",
    modality: "molecule",
    inputRepresentation: "SMILES",
    license: "MIT",
    architectureType: "GPT-2 (Autoregressive)",
    pretrainingObjective: "Autoregressive generation on SMILES strings",
    embeddingDimension: 2048,
    yearReleased: 2022,
    trainingData: {
      name: "PubChem",
      size: "10M molecules",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/valencelabs/ChemGPT",
    weightsUrl: "https://huggingface.co/ncfrey/ChemGPT-1.2B",
    computeProfile: "gpu",
    dataLeakageRisk: "high",
    reproducibilityScore: 0.85,
    domainGeneralization: "medium",
    smallDataPerformance: "medium",
    benchmarks: [
      { dataset: "BBBP (Blood-Brain Barrier)", metric: "ROC-AUC", score: "0.685" },
      { dataset: "ClinTox (FDA Approval / Tox)", metric: "ROC-AUC", score: "0.820" },
      { dataset: "CYP3A4 Substrate (TDC)", metric: "ROC-AUC", score: "0.650" }
    ],
    tags: ["Generative", "GPT", "SMILES", "Valence-Labs"],
    codeSnippet: `from transformers import AutoTokenizer, GPT2Model
tokenizer = AutoTokenizer.from_pretrained("ncfrey/ChemGPT-1.2B")
model = GPT2Model.from_pretrained("ncfrey/ChemGPT-1.2B")`
  },
  {
    id: "diffdock",
    name: "DiffDock Pocket Embeddings",
    representationType: "learned_embedding",
    modality: "complex",
    inputRepresentation: "Pocket/3D",
    license: "MIT",
    architectureType: "Equivariant GNN",
    pretrainingObjective: "Score-based diffusion on binding coordinate distributions",
    embeddingDimension: 1024,
    yearReleased: 2022,
    trainingData: {
      name: "PDBBind v2020",
      size: "19,000 protein-ligand structures",
      license: "MIT"
    },
    codeRepositoryUrl: "https://github.com/gcorso/DiffDock",
    computeProfile: "gpu",
    dataLeakageRisk: "low",
    reproducibilityScore: 0.90,
    domainGeneralization: "high",
    smallDataPerformance: "high",
    benchmarks: [
      { dataset: "PDBBind (Binding Affinity)", metric: "RMSE", score: "1.450" }
    ],
    tags: ["Diffusion", "Docking", "Equivariant", "Pocket"],
    codeSnippet: `# ligand_emb, pocket_emb = score_model.extract_complex_embeddings(ligand_graph, pocket_graph)`
  }
];
