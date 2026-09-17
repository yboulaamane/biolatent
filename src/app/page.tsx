'use client';

import React, { useState, useMemo } from 'react';
import { EMBEDDINGS, RepresentationEntry, FixedDescriptor, LearnedEmbedding, HybridRepresentation } from './data/embeddings';
import StudyTab from './components/StudyTab';

interface ChartPoint {
  id: string;
  name: string;
  type: RepresentationEntry['representationType'];
  dim: number;
  score: number;
  x: number;
  y: number;
}

interface SubmissionDraft {
  id: string;
  name: string;
  developer: string;
  representationType: string;
  modality: string;
  inputRepresentation: string;
  yearReleased: number;
  computeProfile: 'cpu' | 'gpu';
  benchmarks: never[];
  tags: string[];
  codeSnippet: string;
  architectureType?: string;
  pretrainingObjective?: string;
  embeddingDimension?: number;
  trainingData?: { name: string; size: string; license: string };
  descriptorFamily?: string;
  algorithmType?: 'hashed';
  vectorType?: 'binary';
  dimensionality?: number;
  components?: {
    learnedModel: string;
    descriptorsUsed: string[];
    fusionMethod: 'concatenation';
  };
}

export default function Home() {
  // Navigation Tabs. The measured study is the landing tab: it is the only
  // content on this site where results were generated locally under one protocol.
  const [activeTab, setActiveTab] = useState<'study' | 'directory' | 'wizard' | 'benchmarks'>('study');

  // Search & Filtering States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModality, setSelectedModality] = useState<string>('All');
  const [selectedInputType, setSelectedInputType] = useState<string>('All');
  const [selectedRepType, setSelectedRepType] = useState<string>('All');
  const [selectedLicense, setSelectedLicense] = useState<string>('All');

  // Details Modal State
  const [selectedEmbedding, setSelectedEmbedding] = useState<RepresentationEntry | null>(null);
  const [modalTab, setModalTab] = useState<'details' | 'code'>('details');
  const [copied, setCopied] = useState(false);

  // Community Submission Drawer/Form State
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitForm, setSubmitForm] = useState({
    name: '',
    developer: '',
    representationType: 'learned_embedding',
    modality: 'molecule',
    inputRepresentation: 'SMILES',
    dimension: '',
    datasetName: '',
    datasetSize: '',
    objective: '',
    license: 'MIT',
    huggingface: '',
    github: '',
    paper: '',
    typicalTasks: '',
  });
  const [generatedJson, setGeneratedJson] = useState<string | null>(null);

  // Wizard States
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardAnswers, setWizardAnswers] = useState({
    modality: '',
    inputType: '',
    resourceBudget: '',
  });

  // Chart Visualization States
  const [chartMetric, setChartMetric] = useState<'bbbp' | 'cb513'>('bbbp');
  const [hoveredPoint, setHoveredPoint] = useState<ChartPoint | null>(null);
  const [showMethodology, setShowMethodology] = useState(false);

  // Sorting States
  const [molSortConfig, setMolSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>({ key: 'bbbp', direction: 'desc' });
  const [protSortConfig, setProtSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>({ key: 'cb513', direction: 'desc' });

  // Unique options for dropdowns/filters
  const modalities = ['All', 'molecule', 'protein', 'complex', 'nucleic_acid', 'reaction'];
  const inputTypes = ['All', 'SMILES', 'graph', 'sequence', '3D', 'engineered_features', 'Pocket/3D', 'reaction_smiles'];
  const repTypes = ['All', 'learned_embedding', 'fixed_descriptor', 'hybrid_representation'];
  const licenses = ['All', 'MIT', 'Apache-2.0', 'Academic/Restrictive'];

  // Helper to extract dimensionality from any representation entry
  const getDim = (emb: RepresentationEntry): string | number => {
    if (emb.representationType === 'fixed_descriptor') {
      return (emb as FixedDescriptor).dimensionality;
    }
    return (emb as LearnedEmbedding | HybridRepresentation).embeddingDimension;
  };

  const artifactAvailability = (emb: RepresentationEntry): string => {
    if (emb.codeRepositoryUrl && emb.weightsUrl) return 'Code + weights';
    if (emb.codeRepositoryUrl) return 'Code linked';
    if (emb.weightsUrl) return 'Weights linked';
    return 'No artifact link';
  };

  // Helper to format labels
  const formatLabel = (val: string) => {
    if (val === 'learned_embedding') return 'Learned Embedding';
    if (val === 'fixed_descriptor') return 'Fixed Descriptor';
    if (val === 'hybrid_representation') return 'Hybrid Representation';
    if (val === 'engineered_features') return 'Engineered Features';
    if (val === 'molecule') return 'Molecule';
    if (val === 'protein') return 'Protein';
    if (val === 'complex') return 'Complex';
    if (val === 'nucleic_acid') return 'Nucleic Acid (DNA/RNA)';
    if (val === 'reaction') return 'Chemical Reaction';
    if (val === 'reaction_smiles') return 'Reaction SMILES';
    return val;
  };

  // Filtered embeddings selector
  const filteredEmbeddings = useMemo(() => {
    return EMBEDDINGS.filter((emb) => {
      const matchesSearch =
        emb.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (emb.developer?.toLowerCase() || '').includes(searchQuery.toLowerCase()) ||
        (emb.representationType === 'learned_embedding' &&
          (emb as LearnedEmbedding).pretrainingObjective.toLowerCase().includes(searchQuery.toLowerCase())) ||
        emb.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesModality = selectedModality === 'All' || emb.modality === selectedModality;
      
      const matchesInputType = selectedInputType === 'All' || emb.inputRepresentation === selectedInputType;
      
      const matchesRepType = selectedRepType === 'All' || emb.representationType === selectedRepType;
      
      let matchesLicense = true;
      if (selectedLicense !== 'All') {
        if (selectedLicense === 'Academic/Restrictive') {
          matchesLicense = emb.license !== 'MIT' && emb.license !== 'Apache-2.0';
        } else {
          matchesLicense = emb.license === selectedLicense;
        }
      }

      return matchesSearch && matchesModality && matchesInputType && matchesRepType && matchesLicense;
    });
  }, [searchQuery, selectedModality, selectedInputType, selectedRepType, selectedLicense]);

  // Interactive Chart Coordinate mapping
  const chartData = useMemo(() => {
    const minLog = Math.log(128);
    const maxLog = Math.log(4096);
    const svgWidth = 680;
    const svgHeight = 280;
    const margin = { top: 25, right: 30, bottom: 45, left: 55 };
    const plotWidth = svgWidth - margin.left - margin.right;
    const plotHeight = svgHeight - margin.top - margin.bottom;

    const yMin = chartMetric === 'bbbp' ? 0.55 : 0.65;
    const yMax = chartMetric === 'bbbp' ? 0.80 : 0.90;

    const points: ChartPoint[] = [];

    EMBEDDINGS.forEach((emb) => {
      const benchmark = emb.benchmarks.find((b) => b.dataset.startsWith(chartMetric === 'bbbp' ? 'BBBP' : 'Secondary Structure'));
      if (!benchmark) return;

      const scoreNum = parseFloat(benchmark.score);
      if (isNaN(scoreNum)) return;

      // Extract dimension
      const dim = parseInt(getDim(emb) as string) || 512;
      const logDim = Math.log(dim);

      // Map to SVG coordinates
      const x = margin.left + ((logDim - minLog) / (maxLog - minLog)) * plotWidth;
      const y = margin.top + plotHeight - ((scoreNum - yMin) / (yMax - yMin)) * plotHeight;

      points.push({
        id: emb.id,
        name: emb.name,
        type: emb.representationType,
        dim,
        score: scoreNum,
        x,
        y
      });
    });

    return { points, margin, plotWidth, plotHeight, yMin, yMax, svgWidth, svgHeight };
  }, [chartMetric]);

  // Sorting Logic for Leaderboards
  const sortData = (data: RepresentationEntry[], config: { key: string; direction: 'asc' | 'desc' } | null) => {
    if (!config) return data;

    return [...data].sort((a, b) => {
      let valA: string | number = '';
      let valB: string | number = '';

      if (config.key === 'name') {
        valA = a.name.toLowerCase();
        valB = b.name.toLowerCase();
      } else if (config.key === 'representationType') {
        valA = a.representationType.toLowerCase();
        valB = b.representationType.toLowerCase();
      } else if (config.key === 'inputRepresentation') {
        valA = a.inputRepresentation.toLowerCase();
        valB = b.inputRepresentation.toLowerCase();
      } else {
        // Benchmark dataset keys
        const metricA = a.benchmarks.find(b => b.dataset.toLowerCase().includes(config.key.toLowerCase()))?.score || 'N/A';
        const metricB = b.benchmarks.find(b => b.dataset.toLowerCase().includes(config.key.toLowerCase()))?.score || 'N/A';

        if (metricA === 'N/A' && metricB === 'N/A') return 0;
        if (metricA === 'N/A') return 1;
        if (metricB === 'N/A') return -1;

        valA = parseFloat(metricA);
        valB = parseFloat(metricB);
      }

      if (valA < valB) {
        return config.direction === 'asc' ? -1 : 1;
      }
      if (valA > valB) {
        return config.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
  };

  const requestSortMols = (key: string) => {
    let direction: 'asc' | 'desc' = 'desc';
    if (molSortConfig && molSortConfig.key === key && molSortConfig.direction === 'desc') {
      direction = 'asc';
    }
    setMolSortConfig({ key, direction });
  };

  const requestSortProts = (key: string) => {
    let direction: 'asc' | 'desc' = 'desc';
    if (protSortConfig && protSortConfig.key === key && protSortConfig.direction === 'desc') {
      direction = 'asc';
    }
    setProtSortConfig({ key, direction });
  };

  const getSortIcon = (config: { key: string; direction: 'asc' | 'desc' } | null, key: string) => {
    if (!config || config.key !== key) return ' ⇅';
    return config.direction === 'asc' ? ' ▲' : ' ▼';
  };

  // Code Copy Action
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Recommendation logic based on wizard answers
  const recommendedEmbeddings = useMemo(() => {
    if (wizardStep !== 4) return [];

    return EMBEDDINGS.filter((emb) => {
      // Modality match
      if (wizardAnswers.modality && emb.modality !== wizardAnswers.modality.toLowerCase()) {
        return false;
      }
      
      // Input type compatibility
      if (wizardAnswers.inputType === 'Graph' && emb.inputRepresentation !== 'graph') {
        return false;
      }
      if (wizardAnswers.inputType === 'SMILES' && emb.inputRepresentation !== 'SMILES' && emb.inputRepresentation !== 'engineered_features') {
        return false;
      }
      if (wizardAnswers.inputType === '3D' && emb.inputRepresentation !== '3D') {
        return false;
      }
      if (wizardAnswers.inputType === 'Sequence' && emb.inputRepresentation !== 'sequence') {
        return false;
      }
      if (wizardAnswers.inputType === 'Pocket/3D' && emb.inputRepresentation !== 'Pocket/3D') {
        return false;
      }

      // Embedding dimension is not a compute requirement. Only entries
      // explicitly catalogued as CPU-compatible pass the local CPU filter.
      if (wizardAnswers.resourceBudget === 'Low (Local CPU)' && emb.computeProfile !== 'cpu') {
        return false;
      }

      return true;
    }).sort((a, b) => a.name.localeCompare(b.name));
  }, [wizardStep, wizardAnswers]);

  // Handle Wizard Option Selection
  const selectWizardOption = (key: string, value: string) => {
    setWizardAnswers(prev => ({ ...prev, [key]: value }));
    setWizardStep(prev => prev + 1);
  };

  // Handle Community Submit Form Change
  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setSubmitForm(prev => ({ ...prev, [name]: value }));
  };

  // Generate community JSON pull request snippet
  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const isLearned = submitForm.representationType === 'learned_embedding';
    const isFixed = submitForm.representationType === 'fixed_descriptor';
    
    const formatted: SubmissionDraft = {
      id: submitForm.name.toLowerCase().replace(/\s+/g, '_'),
      name: submitForm.name,
      developer: submitForm.developer,
      representationType: submitForm.representationType,
      modality: submitForm.modality,
      inputRepresentation: submitForm.inputRepresentation,
      yearReleased: new Date().getFullYear(),
      computeProfile: isFixed ? 'cpu' : 'gpu',
      benchmarks: [],
      tags: [submitForm.inputRepresentation, submitForm.modality],
      codeSnippet: `# Python load code for ${submitForm.name}`,
    };

    if (isLearned) {
      formatted.architectureType = 'Transformer';
      formatted.pretrainingObjective = submitForm.objective;
      formatted.embeddingDimension = parseInt(submitForm.dimension) || 512;
      formatted.trainingData = {
        name: submitForm.datasetName,
        size: submitForm.datasetSize,
        license: submitForm.license,
      };
    } else if (isFixed) {
      formatted.descriptorFamily = submitForm.name;
      formatted.algorithmType = 'hashed';
      formatted.vectorType = 'binary';
      formatted.dimensionality = parseInt(submitForm.dimension) || 2048;
    } else {
      formatted.components = {
        learnedModel: 'Transformer',
        descriptorsUsed: [submitForm.inputRepresentation],
        fusionMethod: 'concatenation',
      };
      formatted.embeddingDimension = parseInt(submitForm.dimension) || 512;
    }

    setGeneratedJson(JSON.stringify(formatted, null, 2));
  };

  const resetWizard = () => {
    setWizardStep(1);
    setWizardAnswers({
      modality: '',
      inputType: '',
      resourceBudget: '',
    });
  };

  return (
    <div className="app-container">
      {/* HEADER SECTION */}
      <header className="header">
        <button
          type="button"
          aria-label="Open the BioLatent registry"
          className="logo-container" 
          style={{ cursor: 'pointer', background: 'none', border: 0, padding: 0, color: 'inherit' }}
          onClick={() => {
            setActiveTab('directory');
            setSearchQuery('');
            setSelectedModality('All');
            setSelectedInputType('All');
            setSelectedLicense('All');
            setSelectedRepType('All');
          }}
        >
          <svg width="38" height="38" viewBox="0 0 100 100" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-indigo)', filter: 'drop-shadow(0 0 8px rgba(99, 102, 241, 0.3))' }}>
            <polygon points="50,8 88,30 88,74 50,96 12,74 12,30" />
            <circle cx="50" cy="53" r="20" strokeWidth="4" strokeDasharray="6,5" />
          </svg>
          <div>
            <div className="logo-text">BioLatent</div>
            <div className="logo-tagline">Registry &amp; Measured Benchmark</div>
          </div>
        </button>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button className="badge-btn active" onClick={() => {
            setShowSubmitModal(true);
            setGeneratedJson(null);
          }}>
            + Add Representation
          </button>
          
          <div className="tabs-nav">
            <button
              className={`tab-btn ${activeTab === 'study' ? 'active' : ''}`}
              onClick={() => setActiveTab('study')}
            >
              Measured Benchmark
            </button>
            <button
              className={`tab-btn ${activeTab === 'directory' ? 'active' : ''}`}
              onClick={() => setActiveTab('directory')}
            >
              Registry
            </button>
            <button
              className={`tab-btn ${activeTab === 'wizard' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('wizard');
                resetWizard();
              }}
            >
              Compatibility Finder
            </button>
            <button
              className={`tab-btn ${activeTab === 'benchmarks' ? 'active' : ''}`}
              onClick={() => setActiveTab('benchmarks')}
            >
              Literature Registry
            </button>
          </div>
        </div>
      </header>

      {/* ==================== TAB 0: MEASURED STUDY ==================== */}
      {activeTab === 'study' && <StudyTab />}

      {/* ==================== TAB 1: REGISTRY DIRECTORY ==================== */}
      {activeTab === 'directory' && (
        <div className="layout-grid">
          {/* SIDEBAR FILTERS */}
          <aside className="filters-sidebar glass-card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.5rem', color: '#fff' }}>Filters</h3>
            
            <div className="filter-group">
              <span className="filter-label">Modality</span>
              <div className="filter-options">
                {modalities.map(m => (
                  <button
                    key={m}
                    className={`badge-btn ${selectedModality === m ? 'active' : ''}`}
                    onClick={() => setSelectedModality(m)}
                  >
                    {m === 'All' ? 'All' : formatLabel(m)}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">Representation Type</span>
              <div className="filter-options">
                {repTypes.map(rt => (
                  <button
                    key={rt}
                    className={`badge-btn ${selectedRepType === rt ? 'active' : ''}`}
                    onClick={() => setSelectedRepType(rt)}
                  >
                    {rt === 'All' ? 'All' : formatLabel(rt)}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">Input Type</span>
              <div className="filter-options">
                {inputTypes.map(i => (
                  <button
                    key={i}
                    className={`badge-btn ${selectedInputType === i ? 'active' : ''}`}
                    onClick={() => setSelectedInputType(i)}
                  >
                    {i === 'All' ? 'All' : formatLabel(i)}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">Licensing</span>
              <div className="filter-options">
                {licenses.map(l => (
                  <button
                    key={l}
                    className={`badge-btn ${selectedLicense === l ? 'active' : ''}`}
                    onClick={() => setSelectedLicense(l)}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>
            
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Showing {filteredEmbeddings.length} of {EMBEDDINGS.length} indices.
            </div>
          </aside>

          {/* MAIN GRID */}
          <main>
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
              <div className="search-wrapper">
                <svg className="search-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search representations by name, developer, framework, tags..."
                  className="search-input"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {filteredEmbeddings.length === 0 ? (
              <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No chemical representations match your filter criteria. Try expanding your search queries.
              </div>
            ) : (
              <div className="embeddings-list">
                {filteredEmbeddings.map((emb) => (
                  <div key={emb.id} className="glass-card embedding-card">
                    <div>
                      <div className="card-header">
                        <span className={`modality-badge ${emb.modality}`}>
                          {formatLabel(emb.modality)}
                        </span>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                          {formatLabel(emb.representationType)}
                        </span>
                      </div>
                      
                      <h4 className="card-title">{emb.name}</h4>
                      <span className="card-developer">by {emb.developer || 'Open Source Contributors'}</span>
                      
                      <div className="card-meta-grid">
                        <div className="meta-item">
                          <span className="meta-label">Input Format</span>
                          <span className="meta-value">{formatLabel(emb.inputRepresentation)}</span>
                        </div>
                        <div className="meta-item">
                          <span className="meta-label">Dimensions</span>
                          <span className="meta-value" style={{ color: 'var(--accent-indigo)' }}>
                            {getDim(emb)}d
                          </span>
                        </div>
                      </div>

                      <div className="card-meta-grid" style={{ marginTop: '0', borderTop: 'none', borderBottom: 'none' }}>
                        <div className="meta-item">
                          <span className="meta-label">Pretrained Size</span>
                          <span className="meta-value">
                            {emb.representationType === 'fixed_descriptor' ? 'N/A (Hashed)' : emb.trainingData?.size || 'N/A'}
                          </span>
                        </div>
                        <div className="meta-item">
                          <span className="meta-label">Artifacts</span>
                          <span className="meta-value" style={{ color: emb.codeRepositoryUrl || emb.weightsUrl ? 'var(--accent-emerald)' : 'var(--text-secondary)' }}>
                            {artifactAvailability(emb)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="card-footer" style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem' }}>
                      <span className="card-license">
                        <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ display: 'inline' }}>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                        {emb.license}
                      </span>
                      
                      <button
                        className="btn-details"
                        onClick={() => {
                          setSelectedEmbedding(emb);
                          setModalTab('details');
                        }}
                      >
                        Inspect & Code
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </main>
        </div>
      )}

      {/* ==================== TAB 2: LATENT FINDER WIZARD ==================== */}
      {activeTab === 'wizard' && (
        <div style={{ maxWidth: '700px', margin: '2rem auto' }} className="glass-card">
          <div className="wizard-header">
            <h2 className="wizard-title">Representation Compatibility Finder</h2>
            <p className="wizard-tagline">Filter by input compatibility and compute profile; validate performance on your own task</p>
          </div>

          <div className="wizard-steps-indicator">
            {[1, 2, 3, 4].map((step) => (
              <div
                key={step}
                className={`indicator-dot ${wizardStep === step ? 'active' : ''} ${
                  wizardStep > step ? 'completed' : ''
                }`}
              />
            ))}
          </div>

          {/* STEP 1: Modality Selection */}
          {wizardStep === 1 && (
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, textAlign: 'center', marginBottom: '1rem', color: '#fff' }}>
                1. What is your biological target modality?
              </h3>
              <div className="wizard-option-grid">
                <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Molecule')}>
                  <span className="wizard-option-title">Small Molecules</span>
                  <span className="wizard-option-desc">SMILES strings, Graphs, or 3D coordinate ligand vectors.</span>
                </button>
                <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Protein')}>
                  <span className="wizard-option-title">Proteins / Enzymes</span>
                  <span className="wizard-option-desc">Amino acid sequences, structural graphs, active pockets.</span>
                </button>
                <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Complex')}>
                  <span className="wizard-option-title">Complexes / Pockets</span>
                  <span className="wizard-option-desc">3D binding site structures and ligand-protein interaction complexes.</span>
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: Input Format */}
          {wizardStep === 2 && (
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, textAlign: 'center', marginBottom: '1rem', color: '#fff' }}>
                2. What data representation format do you have?
              </h3>
              <div className="wizard-option-grid">
                {wizardAnswers.modality === 'Molecule' ? (
                  <>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'SMILES')}>
                      <span className="wizard-option-title">SMILES strings</span>
                      <span className="wizard-option-desc">Easiest to process text representations (e.g. Aspirin as CC(=O)OC1=CC=CC=C1C(=O)O).</span>
                    </button>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Graph')}>
                      <span className="wizard-option-title">2D Molecular Graphs</span>
                      <span className="wizard-option-desc">Nodes representing atoms, edges representing bonds.</span>
                    </button>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', '3D')}>
                      <span className="wizard-option-title">3D Conformers</span>
                      <span className="wizard-option-desc">Atomic coordinates (requires prior conformer generation).</span>
                    </button>
                  </>
                ) : wizardAnswers.modality === 'Complex' ? (
                  <>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Pocket/3D')}>
                      <span className="wizard-option-title">Pocket / 3D Complex</span>
                      <span className="wizard-option-desc">3D spatial pocket coordinates and bounding box structures.</span>
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Sequence')}>
                      <span className="wizard-option-title">FASTA Sequence</span>
                      <span className="wizard-option-desc">Pure amino acid string sequences (e.g., MSKGEE...).</span>
                    </button>
                    <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('inputType', '3D')}>
                      <span className="wizard-option-title">3D PDB Structure</span>
                      <span className="wizard-option-desc">3D tertiary coordinates (e.g., from AlphaFold / PDB).</span>
                    </button>
                  </>
                )}
              </div>
              <div className="wizard-actions">
                <button className="btn-wizard-back" onClick={() => setWizardStep(1)}>
                  Back
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: Resource Constraints */}
          {wizardStep === 3 && (
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, textAlign: 'center', marginBottom: '1rem', color: '#fff' }}>
                3. What compute environment can generate the embeddings?
              </h3>
              <div className="wizard-option-grid">
                <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('resourceBudget', 'Low (Local CPU)')}>
                  <span className="wizard-option-title">Local CPU</span>
                  <span className="wizard-option-desc">Show only entries explicitly catalogued as CPU-compatible. Runtime still depends on input count, length and software version.</span>
                </button>
                <button type="button" className="wizard-option-card" onClick={() => selectWizardOption('resourceBudget', 'High (GPU Server)')}>
                  <span className="wizard-option-title">GPU Available</span>
                  <span className="wizard-option-desc">Include CPU, mixed and GPU profiles; memory and runtime are not guaranteed by this filter.</span>
                </button>
              </div>
              <div className="wizard-actions">
                <button className="btn-wizard-back" onClick={() => setWizardStep(2)}>
                  Back
                </button>
              </div>
            </div>
          )}

          {/* STEP 4: Compatible entries */}
          {wizardStep === 4 && (
            <div className="wizard-results">
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, textTransform: 'uppercase', color: '#fff', marginBottom: '1.5rem', textAlign: 'center' }}>
                Compatible Registry Entries
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.6, marginBottom: '1.25rem', textAlign: 'center' }}>
                Alphabetical, not ranked. Compatibility does not establish predictive performance;
                compare candidates under the same split and probe on your own endpoint.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
                {recommendedEmbeddings.map((emb) => (
                  <div
                    key={emb.id}
                    className="glass-card"
                    style={{
                      borderLeft: '1px solid var(--border-card)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '1.25rem'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <h4 style={{ fontWeight: 700, color: '#fff', fontSize: '1.1rem' }}>{emb.name}</h4>
                      </div>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        Type: {formatLabel(emb.representationType)} • Input: {formatLabel(emb.inputRepresentation)} • Dim: {getDim(emb)}d
                      </span>
                    </div>

                    <button
                      className="btn-details"
                      onClick={() => {
                        setSelectedEmbedding(emb);
                        setModalTab('details');
                      }}
                    >
                      Get Snippet
                    </button>
                  </div>
                ))}

                {recommendedEmbeddings.length === 0 && (
                  <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No catalog entries match those objective filters. Reset the finder and try another supported input or compute profile.
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyItems: 'center', justifyContent: 'center' }}>
                <button className="btn-wizard-back" onClick={resetWizard}>
                  Restart Wizard
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== TAB 3: BENCHMARKS ==================== */}
      {activeTab === 'benchmarks' && (
        <div className="glass-card">
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '0.5rem' }}>Literature Registry</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '1rem' }}>
            This registry records values reported in cited publications and official benchmark databases. Each entry includes its source and a provenance note.
          </p>
          <div style={{
            marginBottom: '1.5rem', padding: '0.9rem 1.15rem',
            background: 'rgba(251, 191, 36, 0.07)',
            border: '1px solid rgba(251, 191, 36, 0.22)', borderRadius: '12px',
            color: 'var(--text-secondary)', fontSize: '0.86rem', lineHeight: 1.6,
          }}>
            <strong style={{ color: '#fbbf24' }}>Do not compare these values directly.</strong>{' '}
            They were reported by different groups using different datasets, splits, readouts and predictive models.
            The displayed order can therefore reflect the evaluation procedure as much as the representation.
            These entries do not include a common uncertainty analysis or significance test. For results generated
            under one protocol, see the <strong style={{ color: '#fff' }}>Measured Benchmark</strong> tab.
          </div>

          {/* Scientific Methodology Card */}
          <div style={{ marginBottom: '2rem' }}>
            <button
              onClick={() => setShowMethodology(!showMethodology)}
              style={{
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid var(--border-card)',
                color: '#fff',
                padding: '0.75rem 1.25rem',
                borderRadius: '8px',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                width: '100%',
                justifyContent: 'space-between',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
            >
              <span>🔬 Scientific Methodology, Splits & Literature References</span>
              <span>{showMethodology ? 'Hide ▲' : 'Show Details ▼'}</span>
            </button>

            {showMethodology && (
              <div className="glass-card" style={{ marginTop: '0.75rem', background: 'rgba(9, 13, 26, 0.6)', padding: '1.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)', borderLeft: '3px solid var(--accent-indigo)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                  <div>
                    <h4 style={{ color: '#fff', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem' }}>Molecule Benchmarking Protocols</h4>
                    <p style={{ marginBottom: '0.75rem', lineHeight: '1.4' }}>
                      These values are transcribed from heterogeneous publications. Split
                      strategy, seed, readout and downstream tuning can differ by row; the
                      stored source note is authoritative. A shared task name does not make
                      two literature values directly comparable.
                    </p>
                    <ul style={{ paddingLeft: '1.25rem', lineHeight: '1.5', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <li><strong>BBBP, ClinTox, CYP3A4 Substrate</strong>: Evaluated using Classification Area Under the ROC Curve (ROC-AUC) ↑.</li>
                      <li><strong>ESOL (Solubility), Lipophilicity</strong>: Evaluated using Regression Root Mean Square Error (RMSE) ↓.</li>
                      <li style={{ color: '#fbbf24' }}><strong>Note on CYP3A4.</strong> Both this column and the Measured Benchmark tab now use TDC <code>CYP3A4_Substrate_CarbonMangels</code>. The measured and literature values still use different downstream protocols, so sharing a dataset does not make the scores directly comparable.</li>
                    </ul>
                  </div>
                  <div>
                    <h4 style={{ color: '#fff', fontWeight: 700, fontSize: '0.95rem', marginBottom: '0.75rem' }}>Protein & Genomics Protocols</h4>
                    <p style={{ marginBottom: '0.75rem', lineHeight: '1.4' }}>
                      Protein literature protocols also vary. Where authors use sequence-
                      identity clusters or CATH topology limits, those choices are recorded
                      in the source note; no uniform split is implied across this registry.
                    </p>
                    <p style={{ marginBottom: '0.75rem', lineHeight: '1.4', color: '#fbbf24' }}>
                      <strong>Measured clarification.</strong> A downstream homology split does
                      not answer whether related inputs occurred during self-supervised
                      pretraining. The Measured Benchmark tab therefore reports Swiss-Prot
                      homology as an input-exposure proxy. It is not proof of exact checkpoint
                      membership and does not imply that downstream labels were exposed.
                    </p>
                    <ul style={{ paddingLeft: '1.25rem', lineHeight: '1.5', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <li><strong>CB513 Secondary Structure</strong>: Predicts 3-state or 8-state amino acid structure, reported in 3-state Accuracy (Q3) ↑.</li>
                      <li><strong>DeepLoc</strong>: Predicts subcellular localization of proteins, reported in multi-class classification Accuracy ↑.</li>
                    </ul>
                  </div>
                </div>

                <div style={{ marginTop: '1.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '1rem' }}>
                  <h4 style={{ color: '#fff', fontWeight: 700, fontSize: '0.9rem', marginBottom: '0.5rem' }}>Literature References & Benchmarking Suites</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', fontSize: '0.8rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <span>• <strong>TDC (Therapeutic Data Commons)</strong>: <a href="https://arxiv.org/abs/2102.09548" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none' }}>Huang et al. (2021)</a></span>
                      <span>• <strong>MoleculeNet QSAR Suite</strong>: <a href="https://doi.org/10.1039/C7SC02664A" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none' }}>Wu et al. (2018)</a></span>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <span>• <strong>FLIP (Functional Landscapes)</strong>: <a href="https://doi.org/10.1101/2021.11.09.467895" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none' }}>Dallago et al. (2021)</a></span>
                      <span>• <strong>DeepLoc Architecture</strong>: <a href="https://doi.org/10.1093/bioinformatics/btx431" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none' }}>Almagro Armenteros et al. (2017)</a></span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Chart Metric Selector */}
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>Visualize Dimension vs. Score:</span>
            <button
              className={`badge-btn ${chartMetric === 'bbbp' ? 'active' : ''}`}
              onClick={() => setChartMetric('bbbp')}
            >
              Molecules: BBBP (ROC-AUC)
            </button>
            <button
              className={`badge-btn ${chartMetric === 'cb513' ? 'active' : ''}`}
              onClick={() => setChartMetric('cb513')}
            >
              Proteins: CB513 (Accuracy)
            </button>
          </div>

          {/* Interactive SVG Chart */}
          <div style={{ position: 'relative', marginBottom: '2.5rem', background: 'rgba(15, 23, 42, 0.3)', border: '1px solid var(--border-card)', borderRadius: '12px', padding: '1rem', overflow: 'hidden' }}>
            <svg viewBox={`0 0 ${chartData.svgWidth} ${chartData.svgHeight}`} width="100%" height="auto" style={{ overflow: 'visible' }}>
              {/* Grid Lines */}
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const y = chartData.margin.top + ratio * chartData.plotHeight;
                const scoreValue = chartData.yMax - ratio * (chartData.yMax - chartData.yMin);
                return (
                  <g key={ratio} opacity="0.15">
                    <line x1={chartData.margin.left} y1={y} x2={chartData.svgWidth - chartData.margin.right} y2={y} stroke="#fff" strokeWidth="1" strokeDasharray="4,4" />
                    <text x={chartData.margin.left - 8} y={y + 4} fill="#fff" fontSize="10" textAnchor="end" fontFamily="var(--font-mono)">
                      {scoreValue.toFixed(2)}
                    </text>
                  </g>
                );
              })}

              {/* X Axis Grid Lines & Labels (Log Scale dimensions) */}
              {[128, 256, 512, 1024, 2048, 4096].map((dim) => {
                const logDim = Math.log(dim);
                const minLog = Math.log(128);
                const maxLog = Math.log(4096);
                const x = chartData.margin.left + ((logDim - minLog) / (maxLog - minLog)) * chartData.plotWidth;
                return (
                  <g key={dim} opacity="0.15">
                    <line x1={x} y1={chartData.margin.top} x2={x} y2={chartData.svgHeight - chartData.margin.bottom} stroke="#fff" strokeWidth="1" strokeDasharray="4,4" />
                    <text x={x} y={chartData.svgHeight - chartData.margin.bottom + 16} fill="#fff" fontSize="10" textAnchor="middle" fontFamily="var(--font-mono)">
                      {dim}d
                    </text>
                  </g>
                );
              })}

              {/* X Axis Title */}
              <text x={chartData.margin.left + chartData.plotWidth / 2} y={chartData.svgHeight - 10} fill="var(--text-muted)" fontSize="10" fontWeight="700" textAnchor="middle">
                EMBEDDING DIMENSION (LOG SCALE)
              </text>

              {/* Y Axis Title */}
              <text transform={`rotate(-90) translate(${-chartData.margin.top - chartData.plotHeight / 2}, 15)`} fill="var(--text-muted)" fontSize="10" fontWeight="700" textAnchor="middle">
                {chartMetric === 'bbbp' ? 'BBBP ROC-AUC SCORE' : 'CB513 SECONDARY STRUCTURE ACCURACY'}
              </text>

              {/* Chart Points */}
              {chartData.points.map((pt) => {
                const isHovered = hoveredPoint?.id === pt.id;
                let color = '#8b5cf6'; // default learned
                if (pt.type === 'fixed_descriptor') color = '#10b981';
                if (pt.type === 'hybrid_representation') color = '#06b6d4';

                return (
                  <g key={pt.id}>
                    {/* Hover Glow */}
                    {isHovered && (
                      <circle cx={pt.x} cy={pt.y} r="12" fill={color} opacity="0.25" style={{ pointerEvents: 'none' }} />
                    )}
                    {/* Main Point */}
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={isHovered ? 8 : 6}
                      fill={color}
                      stroke="#0f172a"
                      strokeWidth="2"
                      style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
                      onMouseEnter={() => setHoveredPoint(pt)}
                      onMouseLeave={() => setHoveredPoint(null)}
                      onClick={() => {
                        const original = EMBEDDINGS.find(e => e.id === pt.id);
                        if (original) {
                          setSelectedEmbedding(original);
                          setModalTab('details');
                        }
                      }}
                    />
                  </g>
                );
              })}
            </svg>

            {/* Hover Tooltip Overlay */}
            {hoveredPoint && (
              <div
                style={{
                  position: 'absolute',
                  left: `${hoveredPoint.x + 10}px`,
                  top: `${hoveredPoint.y - 10}px`,
                  transform: 'translateY(-100%)',
                  background: '#090d1a',
                  border: '1px solid var(--border-card)',
                  borderRadius: '8px',
                  padding: '0.5rem 0.75rem',
                  fontSize: '0.8rem',
                  boxShadow: '0 10px 15px -3px rgba(0,0,0,0.5)',
                  pointerEvents: 'none',
                  zIndex: 10,
                  animation: 'fadeIn 0.15s ease-out'
                }}
              >
                <div style={{ fontWeight: 700, color: '#fff', marginBottom: '0.25rem' }}>{hoveredPoint.name}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  Dimension: <span style={{ color: '#fff', fontFamily: 'var(--font-mono)' }}>{hoveredPoint.dim}d</span>
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  Score: <span style={{ color: 'var(--accent-cyan)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{hoveredPoint.score}</span>
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.25rem', fontStyle: 'italic' }}>Click point to inspect details</div>
              </div>
            )}
          </div>

          {/* MOLECULES TABLE */}
          <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '2rem', marginBottom: '1rem' }}>Small Molecule Representations</h3>
          <div style={{ overflowX: 'auto', marginBottom: '3rem' }}>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('name')}>
                    Model / Fingerprint{getSortIcon(molSortConfig, 'name')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('representationType')}>
                    Type{getSortIcon(molSortConfig, 'representationType')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('inputRepresentation')}>
                    Input Format{getSortIcon(molSortConfig, 'inputRepresentation')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('BBBP')}>
                    BBBP (ROC-AUC) ↑{getSortIcon(molSortConfig, 'BBBP')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('ClinTox')}>
                    ClinTox (ROC-AUC) ↑{getSortIcon(molSortConfig, 'ClinTox')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('CYP3A4')}>
                    CYP3A4 Sub (ROC-AUC) ↑{getSortIcon(molSortConfig, 'CYP3A4')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('ESOL')}>
                    ESOL (RMSE) ↓{getSortIcon(molSortConfig, 'ESOL')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortMols('Lipophilicity')}>
                    Lipo (RMSE) ↓{getSortIcon(molSortConfig, 'Lipophilicity')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortData(EMBEDDINGS.filter(e => e.modality === 'molecule'), molSortConfig).map((emb) => {
                  const bbbpE = emb.benchmarks.find(b => b.dataset.startsWith('BBBP'));
                  const clintoxE = emb.benchmarks.find(b => b.dataset.startsWith('ClinTox'));
                  const cyp3a4E = emb.benchmarks.find(b => b.dataset.startsWith('CYP3A4'));
                  const esolE = emb.benchmarks.find(b => b.dataset.startsWith('ESOL'));
                  const lipoE = emb.benchmarks.find(b => b.dataset.startsWith('Lipophilicity'));
                  const citLink = (e: typeof bbbpE) => e?.citation?.doi
                    ? <a href={e.citation.doi} target="_blank" rel="noopener noreferrer" onClick={ev => ev.stopPropagation()} title={`${e.citation.shortRef}${e.citation.note ? ': ' + e.citation.note : ''}`} style={{ marginLeft: '3px', color: 'var(--accent-indigo)', fontSize: '0.6rem', textDecoration: 'none', verticalAlign: 'super', lineHeight: 1 }}>↗</a>
                    : null;

                  return (
                    <tr key={emb.id} style={{ cursor: 'pointer' }} onClick={() => { setSelectedEmbedding(emb); setModalTab('details'); }}>
                      <td style={{ fontWeight: 700, color: '#fff' }}>{emb.name}</td>
                      <td>{formatLabel(emb.representationType)}</td>
                      <td>{formatLabel(emb.inputRepresentation)}</td>
                      <td><span className="score-badge">{bbbpE?.score || 'N/A'}</span>{citLink(bbbpE)}</td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-purple)', background: 'rgba(168,85,247,0.1)' }}>{clintoxE?.score || 'N/A'}</span>{citLink(clintoxE)}</td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-cyan)', background: 'rgba(6,182,212,0.1)' }}>{cyp3a4E?.score || 'N/A'}</span>{citLink(cyp3a4E)}</td>
                      <td><span className="score-badge" style={{ color: '#f43f5e', background: 'rgba(244,63,94,0.1)' }}>{esolE?.score || 'N/A'}</span>{citLink(esolE)}</td>
                      <td><span className="score-badge" style={{ color: '#eab308', background: 'rgba(234,179,8,0.1)' }}>{lipoE?.score || 'N/A'}</span>{citLink(lipoE)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* PROTEINS & BIOLOGICALS TABLE */}
          <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginBottom: '1rem' }}>Protein & Biological Representations</h3>
          <div style={{ overflowX: 'auto' }}>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortProts('name')}>
                    Model / Model Family{getSortIcon(protSortConfig, 'name')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortProts('representationType')}>
                    Type{getSortIcon(protSortConfig, 'representationType')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortProts('inputRepresentation')}>
                    Input Format{getSortIcon(protSortConfig, 'inputRepresentation')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortProts('CB513')}>
                    CB513 Sec Structure (Acc) ↑{getSortIcon(protSortConfig, 'CB513')}
                  </th>
                  <th style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => requestSortProts('DeepLoc')}>
                    DeepLoc Localization (Acc) ↑{getSortIcon(protSortConfig, 'DeepLoc')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortData(EMBEDDINGS.filter(e => e.modality === 'protein' || e.modality === 'nucleic_acid' || e.modality === 'complex'), protSortConfig).map((emb) => {
                  const cb513E = emb.benchmarks.find(b => b.dataset.includes('CB513'));
                  const deeplocE = emb.benchmarks.find(b => b.dataset.includes('DeepLoc'));

                  // Skip if both are N/A (like structural designs or ligand designs with different benchmarks)
                  if (!cb513E && !deeplocE) return null;

                  const citLink = (e: typeof cb513E) => e?.citation?.doi
                    ? <a href={e.citation.doi} target="_blank" rel="noopener noreferrer" onClick={ev => ev.stopPropagation()} title={`${e.citation.shortRef}${e.citation.note ? ': ' + e.citation.note : ''}`} style={{ marginLeft: '3px', color: 'var(--accent-indigo)', fontSize: '0.6rem', textDecoration: 'none', verticalAlign: 'super', lineHeight: 1 }}>↗</a>
                    : null;

                  return (
                    <tr key={emb.id} style={{ cursor: 'pointer' }} onClick={() => { setSelectedEmbedding(emb); setModalTab('details'); }}>
                      <td style={{ fontWeight: 700, color: '#fff' }}>{emb.name}</td>
                      <td>{formatLabel(emb.representationType)}</td>
                      <td>{formatLabel(emb.inputRepresentation)}</td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-purple)', background: 'rgba(168,85,247,0.1)' }}>{cb513E?.score || 'N/A'}</span>{citLink(cb513E)}</td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-cyan)', background: 'rgba(6,182,212,0.1)' }}>{deeplocE?.score || 'N/A'}</span>{citLink(deeplocE)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer style={{ marginTop: '4rem', padding: '2rem 0 1rem', borderTop: '1px solid var(--border-card)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        <div>
          © {new Date().getFullYear()} BioLatent • Open Source Registry.
        </div>
        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          <a href="https://github.com/yboulaamane/biolatent" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}>GitHub</a>
          <span>Curated by <a href="https://github.com/yboulaamane" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none', fontWeight: 600 }}>yboulaamane</a></span>
        </div>
      </footer>

      {/* ==================== DETAIL INSPECTOR MODAL ==================== */}
      {selectedEmbedding && (
        <div className="modal-overlay" onClick={() => setSelectedEmbedding(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedEmbedding(null)}>×</button>
            
            <div className="modal-body">
              <div className="modal-title-row">
                <div>
                  <span className={`modality-badge ${selectedEmbedding.modality}`} style={{ marginBottom: '0.5rem', display: 'inline-block' }}>
                    {formatLabel(selectedEmbedding.modality)}
                  </span>
                  <h2 className="modal-title-main">{selectedEmbedding.name}</h2>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Developed by {selectedEmbedding.maintainer || 'Open Source / Authors'}</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-indigo)' }}>
                    {getDim(selectedEmbedding)}d
                  </span>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dimension</div>
                </div>
              </div>

              {/* Modal Tabs */}
              <div className="modal-tabs">
                <button
                  className={`modal-tab-btn ${modalTab === 'details' ? 'active' : ''}`}
                  onClick={() => setModalTab('details')}
                >
                  Representation Profile
                </button>
                <button
                  className={`modal-tab-btn ${modalTab === 'code' ? 'active' : ''}`}
                  onClick={() => setModalTab('code')}
                >
                  Integration Hook
                </button>
              </div>

              {/* DETAILS TAB */}
              {modalTab === 'details' && (
                <div>
                  {/* Categorical Details */}
                  {selectedEmbedding.representationType === 'learned_embedding' && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Pretraining Objective</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{(selectedEmbedding as LearnedEmbedding).pretrainingObjective}</p>
                      </div>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Architecture Type</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{(selectedEmbedding as LearnedEmbedding).architectureType}</p>
                      </div>
                    </div>
                  )}

                  {selectedEmbedding.representationType === 'fixed_descriptor' && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Descriptor Family</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{(selectedEmbedding as FixedDescriptor).descriptorFamily}</p>
                      </div>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Algorithm Type</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{formatLabel((selectedEmbedding as FixedDescriptor).algorithmType)}</p>
                      </div>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Vector Type</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{formatLabel((selectedEmbedding as FixedDescriptor).vectorType)}</p>
                      </div>
                    </div>
                  )}

                  {selectedEmbedding.representationType === 'hybrid_representation' && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1.5rem', marginBottom: '2rem' }}>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Fusion Method</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{formatLabel((selectedEmbedding as HybridRepresentation).components.fusionMethod)}</p>
                      </div>
                      <div>
                        <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Components Integrated</h4>
                        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                          Learned: <strong>{(selectedEmbedding as HybridRepresentation).components.learnedModel}</strong> <br />
                          Fixed Features: <strong>{(selectedEmbedding as HybridRepresentation).components.descriptorsUsed.join(', ')}</strong>
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Pretrained Metadata */}
                  {selectedEmbedding.representationType !== 'fixed_descriptor' && selectedEmbedding.trainingData && (
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem', marginBottom: '2.0rem' }}>
                      <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Training Dataset</h4>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        Pretrained on <strong>{selectedEmbedding.trainingData.name}</strong> containing <strong>{selectedEmbedding.trainingData.size}</strong>.
                      </p>
                    </div>
                  )}

                  {/* Objective availability metadata */}
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem', marginBottom: '2rem' }}>
                    <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '1rem', fontWeight: 700 }}>Availability & Evidence</h4>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', lineHeight: 1.5, marginBottom: '0.85rem' }}>
                      These are factual catalog fields, not inferred quality, safety or generalization scores.
                    </p>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Artifacts
                        </div>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--accent-indigo)' }}>
                          {artifactAvailability(selectedEmbedding)}
                        </span>
                      </div>

                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Compute profile
                        </div>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                          {selectedEmbedding.computeProfile.toUpperCase()}
                        </span>
                      </div>

                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                          Sourced benchmark rows
                        </div>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                          {selectedEmbedding.benchmarks.filter((entry) => entry.citation?.doi).length}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Reported Benchmarks */}
                  {selectedEmbedding.benchmarks.length > 0 && (
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem', marginBottom: '2rem' }}>
                      <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.75rem', fontWeight: 700 }}>Reported Benchmarks</h4>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                            <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem' }}>Dataset</th>
                            <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem' }}>Metric</th>
                            <th style={{ textAlign: 'center', padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem' }}>Score</th>
                            <th style={{ textAlign: 'left', padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', fontSize: '0.7rem' }}>Source</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedEmbedding.benchmarks.map((b, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                              <td style={{ padding: '0.4rem 0.5rem', color: 'var(--text-secondary)' }}>{b.dataset}</td>
                              <td style={{ padding: '0.4rem 0.5rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{b.metric}</td>
                              <td style={{ padding: '0.4rem 0.5rem', textAlign: 'center' }}>
                                <span style={{ fontWeight: 700, color: 'var(--accent-indigo)', fontFamily: 'var(--font-mono)' }}>{b.score}</span>
                              </td>
                              <td style={{ padding: '0.4rem 0.5rem' }}>
                                {b.citation ? (
                                  <a href={b.citation.doi || '#'} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-indigo)', textDecoration: 'none', fontSize: '0.75rem' }} title={b.citation.note}>
                                    {b.citation.shortRef} ↗
                                  </a>
                                ) : (
                                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Links / Download buttons */}
                  <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      License Constraints: <strong style={{ color: 'var(--text-secondary)' }}>{selectedEmbedding.license}</strong>
                    </div>
                    
                    <div style={{ display: 'flex', gap: '0.75rem', marginLeft: 'auto' }}>
                      {selectedEmbedding.codeRepositoryUrl && (
                        <a href={selectedEmbedding.codeRepositoryUrl} target="_blank" rel="noopener noreferrer" className="btn-details" style={{ textDecoration: 'none' }}>
                          Source Code
                        </a>
                      )}
                      {selectedEmbedding.weightsUrl && (
                        <a href={selectedEmbedding.weightsUrl} target="_blank" rel="noopener noreferrer" className="btn-details" style={{ textDecoration: 'none', background: 'var(--gradient-latent)', borderColor: 'transparent' }}>
                          HF / Weight Hub
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* CODE HOOK TAB */}
              {modalTab === 'code' && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                    Standardized copy-paste code hooks to load and compute chemical representations.
                  </p>

                  <div className="code-container">
                    <button
                      className="copy-btn"
                      onClick={() => copyToClipboard(selectedEmbedding.codeSnippet)}
                    >
                      {copied ? 'Copied!' : 'Copy Code'}
                    </button>
                    <pre className="code-block">
                      <code>{selectedEmbedding.codeSnippet}</code>
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================== PR SUBMISSION DIALOG ==================== */}
      {showSubmitModal && (
        <div className="modal-overlay" onClick={() => setShowSubmitModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '650px' }}>
            <button className="modal-close" onClick={() => setShowSubmitModal(false)}>×</button>
            <div className="modal-body">
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '0.25rem' }}>Submit a Representation</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                Fill out the metadata schema below to generate a standardized registry payload suitable for a GitHub Pull Request.
              </p>

              <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Representation Name</label>
                    <input type="text" name="name" required placeholder="e.g. ChemBERTa-3" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.name} onChange={handleFormChange} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Developer/Team</label>
                    <input type="text" name="developer" required placeholder="e.g. Stanford / Mila" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.developer} onChange={handleFormChange} />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Representation Type</label>
                    <select name="representationType" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.representationType} onChange={handleFormChange}>
                      <option value="learned_embedding">Learned Embedding</option>
                      <option value="fixed_descriptor">Fixed Descriptor</option>
                      <option value="hybrid_representation">Hybrid Representation</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Modality</label>
                    <select name="modality" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.modality} onChange={handleFormChange}>
                      <option value="molecule">Molecule</option>
                      <option value="protein">Protein</option>
                      <option value="complex">Complex</option>
                      <option value="reaction">Reaction</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Input Format</label>
                    <select name="inputRepresentation" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.inputRepresentation} onChange={handleFormChange}>
                      <option value="SMILES">SMILES</option>
                      <option value="sequence">Sequence</option>
                      <option value="3D">3D Coordinates</option>
                      <option value="graph">2D Graph</option>
                      <option value="engineered_features">Engineered Features</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Dimension / Length</label>
                    <input type="number" name="dimension" required placeholder="e.g. 768" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.dimension} onChange={handleFormChange} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>License</label>
                    <select name="license" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.license} onChange={handleFormChange}>
                      <option value="MIT">MIT</option>
                      <option value="Apache-2.0">Apache-2.0</option>
                      <option value="Academic/Restrictive">Academic/Restrictive</option>
                    </select>
                  </div>
                </div>

                {submitForm.representationType === 'learned_embedding' && (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Pretraining Dataset Name</label>
                        <input type="text" name="datasetName" placeholder="e.g. PubChem10M" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.datasetName} onChange={handleFormChange} />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Pretraining Dataset Size</label>
                        <input type="text" name="datasetSize" placeholder="e.g. 10M molecules" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.datasetSize} onChange={handleFormChange} />
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Pretraining Objective</label>
                      <input type="text" name="objective" placeholder="e.g. Masked atom reconstruction" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.objective} onChange={handleFormChange} />
                    </div>
                  </>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>GitHub Link</label>
                    <input type="text" name="github" placeholder="https://github.com/..." className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.github} onChange={handleFormChange} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Paper Link</label>
                    <input type="text" name="paper" placeholder="https://arxiv.org/..." className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.paper} onChange={handleFormChange} />
                  </div>
                </div>

                <button type="submit" className="btn-wizard-next" style={{ width: '100%', marginTop: '0.5rem' }}>
                  Generate Entry JSON
                </button>
              </form>

              {generatedJson && (
                <div style={{ marginTop: '1.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>JSON Payload</span>
                    <button className="badge-btn" onClick={() => copyToClipboard(generatedJson)}>
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <div className="code-container" style={{ maxHeight: '180px' }}>
                    <pre className="code-block" style={{ fontSize: '0.8rem' }}>
                      <code>{generatedJson}</code>
                    </pre>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem', textAlign: 'center' }}>
                    Copy this payload and submit a Pull Request to our repository inside `/src/app/data/embeddings.ts`.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
