'use client';

import React, { useState, useMemo } from 'react';
import { EMBEDDINGS, RepresentationEntry, FixedDescriptor, LearnedEmbedding, HybridRepresentation } from './data/embeddings';

export default function Home() {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'directory' | 'wizard' | 'benchmarks'>('directory');

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
    datasetSize: '',
    resourceBudget: '',
  });

  // Unique options for dropdowns/filters
  const modalities = ['All', 'molecule', 'protein', 'complex'];
  const inputTypes = ['All', 'SMILES', 'graph', 'sequence', '3D', 'engineered_features', 'Pocket/3D'];
  const repTypes = ['All', 'learned_embedding', 'fixed_descriptor', 'hybrid_representation'];
  const licenses = ['All', 'MIT', 'Apache-2.0', 'Academic/Restrictive'];

  // Helper to extract dimensionality from any representation entry
  const getDim = (emb: RepresentationEntry): string | number => {
    if (emb.representationType === 'fixed_descriptor') {
      return (emb as FixedDescriptor).dimensionality;
    }
    return (emb as LearnedEmbedding | HybridRepresentation).embeddingDimension;
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

  // Code Copy Action
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Recommendation logic based on wizard answers
  const recommendedEmbeddings = useMemo(() => {
    if (wizardStep !== 5) return [];

    return EMBEDDINGS.filter((emb) => {
      // Modality match
      if (wizardAnswers.modality && emb.modality !== wizardAnswers.modality.toLowerCase()) {
        return false;
      }
      
      // Input type compatibility
      if (wizardAnswers.inputType === 'Graph' && emb.inputRepresentation !== 'graph' && emb.inputRepresentation !== '3D') {
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

      // Hardware/resource filters (dimension check)
      const dim = getDim(emb);
      if (wizardAnswers.resourceBudget === 'Low (Local CPU)' && typeof dim === 'number' && dim > 1200) {
        return false;
      }

      return true;
    }).slice(0, 3); // top 3 recommendations
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
    
    let formatted: any = {
      id: submitForm.name.toLowerCase().replace(/\s+/g, '_'),
      name: submitForm.name,
      developer: submitForm.developer,
      representationType: submitForm.representationType,
      modality: submitForm.modality,
      inputRepresentation: submitForm.inputRepresentation,
      yearReleased: new Date().getFullYear(),
      computeProfile: isFixed ? 'cpu' : 'gpu',
      dataLeakageRisk: 'unknown',
      reproducibilityScore: 1.0,
      domainGeneralization: 'medium',
      smallDataPerformance: 'medium',
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
      datasetSize: '',
      resourceBudget: '',
    });
  };

  return (
    <div className="app-container">
      {/* HEADER SECTION */}
      <header className="header">
        <div 
          className="logo-container" 
          style={{ cursor: 'pointer' }}
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
            <div className="logo-tagline">Biological & Chemical Vector Registry</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button className="badge-btn active" onClick={() => {
            setShowSubmitModal(true);
            setGeneratedJson(null);
          }}>
            + Add Representation
          </button>
          
          <div className="tabs-nav">
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
              Latent Finder
            </button>
            <button
              className={`tab-btn ${activeTab === 'benchmarks' ? 'active' : ''}`}
              onClick={() => setActiveTab('benchmarks')}
            >
              Benchmarks
            </button>
          </div>
        </div>
      </header>

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
                            {emb.representationType === 'fixed_descriptor' ? 'N/A (Hashed)' : (emb as any).trainingData?.size || 'N/A'}
                          </span>
                        </div>
                        <div className="meta-item">
                          <span className="meta-label">Repro Score</span>
                          <span className="meta-value" style={{ color: emb.reproducibilityScore > 0.9 ? 'var(--accent-emerald)' : 'var(--text-secondary)' }}>
                            {(emb.reproducibilityScore * 100).toFixed(0)}%
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
            <h2 className="wizard-title">Latent Space Finder</h2>
            <p className="wizard-tagline">Find the optimal chemical or biological vector representations for your target pipeline</p>
          </div>

          <div className="wizard-steps-indicator">
            {[1, 2, 3, 4, 5].map((step) => (
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
                <div className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Molecule')}>
                  <div className="wizard-option-title">Small Molecules</div>
                  <div className="wizard-option-desc">SMILES strings, Graphs, or 3D coordinate ligand vectors.</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Protein')}>
                  <div className="wizard-option-title">Proteins / Enzymes</div>
                  <div className="wizard-option-desc">Amino acid sequences, structural graphs, active pockets.</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('modality', 'Complex')}>
                  <div className="wizard-option-title">Complexes / Pockets</div>
                  <div className="wizard-option-desc">3D binding site structures and ligand-protein interaction complexes.</div>
                </div>
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
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'SMILES')}>
                      <div className="wizard-option-title">SMILES strings</div>
                      <div className="wizard-option-desc">Easiest to process text representations (e.g. Aspirin as CC(=O)OC1=CC=CC=C1C(=O)O).</div>
                    </div>
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Graph')}>
                      <div className="wizard-option-title">2D Molecular Graphs</div>
                      <div className="wizard-option-desc">Nodes representing atoms, edges representing bonds.</div>
                    </div>
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', '3D')}>
                      <div className="wizard-option-title">3D Conformers</div>
                      <div className="wizard-option-desc">Atomic coordinates (requires prior conformer generation).</div>
                    </div>
                  </>
                ) : wizardAnswers.modality === 'Complex' ? (
                  <>
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Pocket/3D')}>
                      <div className="wizard-option-title">Pocket / 3D Complex</div>
                      <div className="wizard-option-desc">3D spatial pocket coordinates and bounding box structures.</div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', 'Sequence')}>
                      <div className="wizard-option-title">FASTA Sequence</div>
                      <div className="wizard-option-desc">Pure amino acid string sequences (e.g., MSKGEE...).</div>
                    </div>
                    <div className="wizard-option-card" onClick={() => selectWizardOption('inputType', '3D')}>
                      <div className="wizard-option-title">3D PDB Structure</div>
                      <div className="wizard-option-desc">3D tertiary coordinates (e.g., from AlphaFold / PDB).</div>
                    </div>
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

          {/* STEP 3: Dataset Size */}
          {wizardStep === 3 && (
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, textAlign: 'center', marginBottom: '1rem', color: '#fff' }}>
                3. What is the size of your downstream screening dataset?
              </h3>
              <div className="wizard-option-grid">
                <div className="wizard-option-card" onClick={() => selectWizardOption('datasetSize', 'Low')}>
                  <div className="wizard-option-title">Low (&lt; 200 data points)</div>
                  <div className="wizard-option-desc">High risk of overfitting. Fixed descriptors or small learned models recommended.</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('datasetSize', 'Medium')}>
                  <div className="wizard-option-title">Medium (1k - 10k data points)</div>
                  <div className="wizard-option-desc">Optimal size for training lightweight top-heads or linear probing on static embeddings.</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('datasetSize', 'High')}>
                  <div className="wizard-option-title">High (&gt; 10k data points)</div>
                  <div className="wizard-option-desc">Possibility to fine-tune end-to-end representations or use large-dimensional outputs.</div>
                </div>
              </div>
              <div className="wizard-actions">
                <button className="btn-wizard-back" onClick={() => setWizardStep(2)}>
                  Back
                </button>
              </div>
            </div>
          )}

          {/* STEP 4: Resource Constraints */}
          {wizardStep === 4 && (
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, textAlign: 'center', marginBottom: '1rem', color: '#fff' }}>
                4. What is your compute environment budget?
              </h3>
              <div className="wizard-option-grid">
                <div className="wizard-option-card" onClick={() => selectWizardOption('resourceBudget', 'Low (Local CPU)')}>
                  <div className="wizard-option-title">Low (Local CPU)</div>
                  <div className="wizard-option-desc">Requires fast inference, lightweight models (dimension &lt; 1200, small parameter size).</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('resourceBudget', 'High (GPU Server)')}>
                  <div className="wizard-option-title">High (V100/A100 GPU)</div>
                  <div className="wizard-option-desc">Can host large language models, large graph networks, and high dimensional vectors.</div>
                </div>
              </div>
              <div className="wizard-actions">
                <button className="btn-wizard-back" onClick={() => setWizardStep(3)}>
                  Back
                </button>
              </div>
            </div>
          )}

          {/* STEP 5: Results */}
          {wizardStep === 5 && (
            <div className="wizard-results">
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, textTransform: 'uppercase', color: '#fff', marginBottom: '1.5rem', textAlign: 'center' }}>
                Recommended Representations
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
                {recommendedEmbeddings.map((emb, idx) => (
                  <div
                    key={emb.id}
                    className="glass-card"
                    style={{
                      borderLeft: idx === 0 ? '4px solid var(--accent-indigo)' : '1px solid var(--border-card)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '1.25rem'
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.25rem' }}>
                        <h4 style={{ fontWeight: 700, color: '#fff', fontSize: '1.1rem' }}>{emb.name}</h4>
                        {idx === 0 && (
                          <span style={{ fontSize: '0.7rem', background: 'rgba(99,102,241,0.2)', color: '#a5b4fc', padding: '0.1rem 0.4rem', borderRadius: '4px', border: '1px solid var(--accent-indigo)' }}>
                            Top Fit
                          </span>
                        )}
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
                    No exact matches found. Reset parameters and try less restrictive inputs.
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
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '0.5rem' }}>MoleculeNet Downstream Benchmarks</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
            Comparison of reported benchmark scores across molecular representations.
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th>Model / Fingerprint</th>
                  <th>Representation Type</th>
                  <th>Input Format</th>
                  <th>BBBP (ROC-AUC) ↑</th>
                  <th>ClinTox (ROC-AUC) ↑</th>
                  <th>CYP3A4 Substrate (ROC-AUC) ↑</th>
                </tr>
              </thead>
              <tbody>
                {EMBEDDINGS.filter(e => e.modality === 'molecule').map((emb) => {
                  const bbbp = emb.benchmarks.find(b => b.dataset.startsWith('BBBP'))?.score || 'N/A';
                  const clintox = emb.benchmarks.find(b => b.dataset.startsWith('ClinTox'))?.score || 'N/A';
                  const cyp3a4 = emb.benchmarks.find(b => b.dataset.startsWith('CYP3A4'))?.score || 'N/A';

                  return (
                    <tr key={emb.id}>
                      <td style={{ fontWeight: 700, color: '#fff' }}>{emb.name}</td>
                      <td>{formatLabel(emb.representationType)}</td>
                      <td>{formatLabel(emb.inputRepresentation)}</td>
                      <td><span className="score-badge">{bbbp}</span></td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-purple)', background: 'rgba(168,85,247,0.1)' }}>{clintox}</span></td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-cyan)', background: 'rgba(6,182,212,0.1)' }}>{cyp3a4}</span></td>
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
                  {selectedEmbedding.representationType !== 'fixed_descriptor' && (selectedEmbedding as any).trainingData && (
                    <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem', marginBottom: '2.0rem' }}>
                      <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700 }}>Training Dataset</h4>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        Pretrained on <strong>{(selectedEmbedding as any).trainingData.name}</strong> containing <strong>{(selectedEmbedding as any).trainingData.size}</strong>.
                      </p>
                    </div>
                  )}

                  {/* Utility & Quality Scores */}
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem', marginBottom: '2rem' }}>
                    <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '1rem', fontWeight: 700 }}>Reproduction & Safety Profile</h4>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Leakage Risk</div>
                        <span style={{
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: selectedEmbedding.dataLeakageRisk === 'high' ? 'var(--accent-purple)' : selectedEmbedding.dataLeakageRisk === 'low' ? 'var(--accent-emerald)' : 'var(--text-secondary)'
                        }}>
                          {selectedEmbedding.dataLeakageRisk.toUpperCase()}
                        </span>
                      </div>

                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Repro Index</div>
                        <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--accent-indigo)' }}>
                          {(selectedEmbedding.reproducibilityScore * 100).toFixed(0)}%
                        </span>
                      </div>

                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Generalization</div>
                        <span style={{
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: selectedEmbedding.domainGeneralization === 'high' ? 'var(--accent-emerald)' : 'var(--text-secondary)'
                        }}>
                          {selectedEmbedding.domainGeneralization.toUpperCase()}
                        </span>
                      </div>

                      <div className="glass-card" style={{ padding: '0.75rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Low-data QSAR</div>
                        <span style={{
                          fontWeight: 700,
                          fontSize: '0.9rem',
                          color: selectedEmbedding.smallDataPerformance === 'high' ? 'var(--accent-emerald)' : 'var(--text-secondary)'
                        }}>
                          {selectedEmbedding.smallDataPerformance.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </div>

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
