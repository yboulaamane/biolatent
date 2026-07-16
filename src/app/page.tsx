'use client';

import React, { useState, useMemo } from 'react';
import { EMBEDDINGS, EmbeddingEntry } from './data/embeddings';

export default function Home() {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'directory' | 'wizard' | 'benchmarks'>('directory');

  // Search & Filtering States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModality, setSelectedModality] = useState<string>('All');
  const [selectedInputType, setSelectedInputType] = useState<string>('All');
  const [selectedLicense, setSelectedLicense] = useState<string>('All');

  // Details Modal State
  const [selectedEmbedding, setSelectedEmbedding] = useState<EmbeddingEntry | null>(null);
  const [modalTab, setModalTab] = useState<'details' | 'code'>('details');
  const [copied, setCopied] = useState(false);

  // Community Submission Drawer/Form State
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitForm, setSubmitForm] = useState({
    name: '',
    developer: '',
    modality: 'Molecule',
    inputType: 'SMILES',
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
  const modalities = ['All', 'Molecule', 'Protein', 'Complex'];
  const inputTypes = ['All', 'SMILES', 'Amino Acid Sequence', '3D Coordinates', 'Graph', 'Substructure', 'Pocket/3D'];
  const licenses = ['All', 'MIT', 'Apache-2.0', 'Academic/Restrictive'];

  // Filtered embeddings selector
  const filteredEmbeddings = useMemo(() => {
    return EMBEDDINGS.filter((emb) => {
      const matchesSearch =
        emb.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        emb.developer.toLowerCase().includes(searchQuery.toLowerCase()) ||
        emb.pretrainingObjective.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesModality = selectedModality === 'All' || emb.modality === selectedModality;
      const matchesInputType = selectedInputType === 'All' || emb.inputType === selectedInputType;
      
      let matchesLicense = true;
      if (selectedLicense !== 'All') {
        if (selectedLicense === 'Academic/Restrictive') {
          matchesLicense = emb.license !== 'MIT' && emb.license !== 'Apache-2.0';
        } else {
          matchesLicense = emb.license === selectedLicense;
        }
      }

      return matchesSearch && matchesModality && matchesInputType && matchesLicense;
    });
  }, [searchQuery, selectedModality, selectedInputType, selectedLicense]);

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
      // Modality match (Molecule / Protein)
      if (wizardAnswers.modality && emb.modality !== wizardAnswers.modality) {
        return false;
      }
      
      // Input type compatibility
      if (wizardAnswers.inputType === 'Graph' && emb.inputType !== 'Graph' && emb.inputType !== '3D Coordinates') {
        return false;
      }
      if (wizardAnswers.inputType === 'SMILES' && emb.inputType !== 'SMILES' && emb.inputType !== 'Substructure') {
        return false;
      }
      if (wizardAnswers.inputType === '3D' && emb.inputType !== '3D Coordinates') {
        return false;
      }
      if (wizardAnswers.inputType === 'Sequence' && emb.inputType !== 'Amino Acid Sequence') {
        return false;
      }
      if (wizardAnswers.inputType === 'Pocket/3D' && emb.inputType !== 'Pocket/3D') {
        return false;
      }

      // Hardware/resource filters (e.g. low-resource cannot run massive model ESM-2 3B easily)
      if (wizardAnswers.resourceBudget === 'Low (Local CPU)' && emb.dimension > 1500) {
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
    const formatted = {
      id: submitForm.name.toLowerCase().replace(/\s+/g, '-'),
      name: submitForm.name,
      developer: submitForm.developer,
      modality: submitForm.modality,
      inputType: submitForm.inputType,
      dimension: parseInt(submitForm.dimension) || 300,
      trainingData: {
        name: submitForm.datasetName,
        size: submitForm.datasetSize,
      },
      pretrainingObjective: submitForm.objective,
      license: submitForm.license,
      links: {
        huggingface: submitForm.huggingface || undefined,
        github: submitForm.github || undefined,
        paper: submitForm.paper || undefined,
      },
      typicalTasks: submitForm.typicalTasks.split(',').map(t => t.trim()).filter(Boolean),
      benchmarks: [],
      codeSnippet: `# Loading code for ${submitForm.name}`,
    };
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
        <div className="logo-container">
          <div className="logo-icon">B</div>
          <div>
            <div className="logo-text">BioLatent</div>
            <div className="logo-tagline">Registry of Biological Latent Vectors</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button className="badge-btn active" onClick={() => setShowSubmitModal(true)}>
            + Submit Embedding
          </button>
          
          <div className="tabs-nav">
            <button
              className={`tab-btn ${activeTab === 'directory' ? 'active' : ''}`}
              onClick={() => setActiveTab('directory')}
            >
              Catalog
            </button>
            <button
              className={`tab-btn ${activeTab === 'wizard' ? 'active' : ''}`}
              onClick={() => {
                setActiveTab('wizard');
                resetWizard();
              }}
            >
              Rec Engine
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

      {/* ==================== TAB 1: DIRECTORY ==================== */}
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
                    {m}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">Input Representation</span>
              <div className="filter-options">
                {inputTypes.map(i => (
                  <button
                    key={i}
                    className={`badge-btn ${selectedInputType === i ? 'active' : ''}`}
                    onClick={() => setSelectedInputType(i)}
                  >
                    {i === 'Amino Acid Sequence' ? 'Sequence' : i}
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
              Showing {filteredEmbeddings.length} of {EMBEDDINGS.length} registered embeddings.
            </div>
          </aside>

          {/* CATALOG MAIN GRID */}
          <main>
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
              <div className="search-wrapper">
                <svg className="search-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search embeddings by name, developer, objective..."
                  className="search-input"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {filteredEmbeddings.length === 0 ? (
              <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No embeddings match your filter criteria. Try expanding your search queries.
              </div>
            ) : (
              <div className="embeddings-list">
                {filteredEmbeddings.map((emb) => (
                  <div key={emb.id} className="glass-card embedding-card">
                    <div>
                      <div className="card-header">
                        <span className={`modality-badge ${emb.modality.toLowerCase()}`}>
                          {emb.modality}
                        </span>
                        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent-indigo)' }}>
                          {emb.dimension} dims
                        </span>
                      </div>
                      
                      <h4 className="card-title">{emb.name}</h4>
                      <span className="card-developer">by {emb.developer}</span>
                      
                      <div className="card-meta-grid">
                        <div className="meta-item">
                          <span className="meta-label">Input</span>
                          <span className="meta-value">{emb.inputType}</span>
                        </div>
                        <div className="meta-item">
                          <span className="meta-label">Pretrained Size</span>
                          <span className="meta-value">{emb.trainingData.size}</span>
                        </div>
                      </div>
                      
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4, margin: '0.5rem 0 1rem 0' }}>
                        {emb.pretrainingObjective.substring(0, 75)}...
                      </p>
                    </div>

                    <div className="card-footer">
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

      {/* ==================== TAB 2: RECOMMENDATION WIZARD ==================== */}
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

          {/* STEP 2: Input Data Format */}
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
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center', marginBottom: '1.5rem' }}>
                Large pre-trained representations perform differently depending on the available supervision size.
              </p>
              <div className="wizard-option-grid">
                <div className="wizard-option-card" onClick={() => selectWizardOption('datasetSize', 'Low')}>
                  <div className="wizard-option-title">Low (&lt; 200 data points)</div>
                  <div className="wizard-option-desc">High risk of overfitting. Simpler embeddings with high regularization or zero-shot recommended.</div>
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
                  <div className="wizard-option-desc">Requires fast inference, lightweight models (dimension &lt; 800, small parameter size).</div>
                </div>
                <div className="wizard-option-card" onClick={() => selectWizardOption('resourceBudget', 'High (GPU Server)')}>
                  <div className="wizard-option-title">High (V100/A100 GPU)</div>
                  <div className="wizard-option-desc">Can host large ESM language models, large graph networks, and high dimensional vectors.</div>
                </div>
              </div>
              <div className="wizard-actions">
                <button className="btn-wizard-back" onClick={() => setWizardStep(3)}>
                  Back
                </button>
              </div>
            </div>
          )}

          {/* STEP 5: Recommendation Results */}
          {wizardStep === 5 && (
            <div className="wizard-results">
              <h3 style={{ fontSize: '1.5rem', fontWeight: 800, textTransform: 'uppercase', color: '#fff', marginBottom: '1.5rem', textAlign: 'center' }}>
                Recommended Embeddings
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
                        Input: {emb.inputType} • Dimension: {emb.dimension} • License: {emb.license}
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
                    No exact matches found. Reset filters and try less restrictive parameters.
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'center' }}>
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
            Comparison of public benchmark scores achieved using the embedding vectors directly in linear probing or simple random forest models.
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table className="benchmark-table">
              <thead>
                <tr>
                  <th>Embedding Model</th>
                  <th>Input Representation</th>
                  <th>BBBP (ROC-AUC) ↑</th>
                  <th>ClinTox (ROC-AUC) ↑</th>
                  <th>ESOL Solubility (RMSE) ↓</th>
                  <th>Lipophilicity (RMSE) ↓</th>
                </tr>
              </thead>
              <tbody>
                {EMBEDDINGS.filter(e => e.modality === 'Molecule').map((emb) => {
                  const bbbp = emb.benchmarks.find(b => b.dataset.startsWith('BBBP'))?.score || 'N/A';
                  const clintox = emb.benchmarks.find(b => b.dataset.startsWith('ClinTox'))?.score || 'N/A';
                  const esol = emb.benchmarks.find(b => b.dataset.startsWith('ESOL'))?.score || 'N/A';
                  const lipo = emb.benchmarks.find(b => b.dataset.startsWith('Lipophilicity'))?.score || 'N/A';

                  return (
                    <tr key={emb.id}>
                      <td style={{ fontWeight: 700, color: '#fff' }}>{emb.name}</td>
                      <td>{emb.inputType}</td>
                      <td><span className="score-badge">{bbbp}</span></td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-purple)', background: 'rgba(168,85,247,0.1)' }}>{clintox}</span></td>
                      <td><span className="score-badge" style={{ color: 'var(--accent-emerald)', background: 'rgba(16,185,129,0.1)' }}>{esol}</span></td>
                      <td><span className="score-badge" style={{ color: '#f59e0b', background: 'rgba(245,158,11,0.1)' }}>{lipo}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================== EMBEDDING INSPECTOR MODAL ==================== */}
      {selectedEmbedding && (
        <div className="modal-overlay" onClick={() => setSelectedEmbedding(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelectedEmbedding(null)}>×</button>
            
            <div className="modal-body">
              <div className="modal-title-row">
                <div>
                  <span className={`modality-badge ${selectedEmbedding.modality.toLowerCase()}`} style={{ marginBottom: '0.5rem', display: 'inline-block' }}>
                    {selectedEmbedding.modality}
                  </span>
                  <h2 className="modal-title-main">{selectedEmbedding.name}</h2>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Developed by {selectedEmbedding.developer}</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--accent-indigo)' }}>
                    {selectedEmbedding.dimension}d
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
                  Model Profile
                </button>
                <button
                  className={`modal-tab-btn ${modalTab === 'code' ? 'active' : ''}`}
                  onClick={() => setModalTab('code')}
                >
                  Python Loader Snippet
                </button>
              </div>

              {/* MODAL TAB 1: DETAILS */}
              {modalTab === 'details' && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
                    <div>
                      <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700, letterSpacing: '0.05em' }}>Pretraining Objective</h4>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>{selectedEmbedding.pretrainingObjective}</p>
                    </div>

                    <div>
                      <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700, letterSpacing: '0.05em' }}>Pretraining Dataset</h4>
                      <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        <strong>{selectedEmbedding.trainingData.name}</strong> ({selectedEmbedding.trainingData.size})
                      </p>
                    </div>
                  </div>

                  <div style={{ marginBottom: '2rem' }}>
                    <h4 style={{ color: '#fff', fontSize: '0.9rem', textTransform: 'uppercase', marginBottom: '0.5rem', fontWeight: 700, letterSpacing: '0.05em' }}>Typical Downstream Targets</h4>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {selectedEmbedding.typicalTasks.map((t) => (
                        <span
                          key={t}
                          style={{
                            fontSize: '0.8rem',
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.06)',
                            color: 'var(--text-secondary)',
                            padding: '0.3rem 0.6rem',
                            borderRadius: '6px'
                          }}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1.5rem' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      License Constraints: <strong style={{ color: 'var(--text-secondary)' }}>{selectedEmbedding.license}</strong>
                    </div>
                    
                    <div style={{ display: 'flex', gap: '0.75rem', marginLeft: 'auto' }}>
                      {selectedEmbedding.links.paper && (
                        <a href={selectedEmbedding.links.paper} target="_blank" rel="noopener noreferrer" className="btn-details" style={{ textDecoration: 'none' }}>
                          Read Paper
                        </a>
                      )}
                      {selectedEmbedding.links.github && (
                        <a href={selectedEmbedding.links.github} target="_blank" rel="noopener noreferrer" className="btn-details" style={{ textDecoration: 'none' }}>
                          GitHub Code
                        </a>
                      )}
                      {selectedEmbedding.links.huggingface && (
                        <a href={selectedEmbedding.links.huggingface} target="_blank" rel="noopener noreferrer" className="btn-details" style={{ textDecoration: 'none', background: 'var(--gradient-latent)', borderColor: 'transparent' }}>
                          HF Weights
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* MODAL TAB 2: CODE */}
              {modalTab === 'code' && (
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                    Copy this minimal code snippet to load the weights and embed molecular structures or amino acid sequences.
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

      {/* ==================== SUBMISSION Drawer / Overlay ==================== */}
      {showSubmitModal && (
        <div className="modal-overlay" onClick={() => setShowSubmitModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '650px' }}>
            <button className="modal-close" onClick={() => setShowSubmitModal(false)}>×</button>
            <div className="modal-body">
              <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', marginBottom: '0.25rem' }}>Submit an Embedding</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                Fill out the metadata schema below to generate a standardized catalog entry suitable for a GitHub Pull Request.
              </p>

              <form onSubmit={handleFormSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Model Name</label>
                    <input type="text" name="name" required placeholder="e.g. ESM-3" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.name} onChange={handleFormChange} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Developer/Team</label>
                    <input type="text" name="developer" required placeholder="e.g. EvolutionaryScale" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.developer} onChange={handleFormChange} />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Modality</label>
                    <select name="modality" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.modality} onChange={handleFormChange}>
                      <option value="Molecule">Molecule</option>
                      <option value="Protein">Protein</option>
                      <option value="Complex">Complex</option>
                    </select>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Input Type</label>
                    <select name="inputType" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.inputType} onChange={handleFormChange}>
                      <option value="SMILES">SMILES</option>
                      <option value="Amino Acid Sequence">Amino Acid Sequence</option>
                      <option value="3D Coordinates">3D Coordinates</option>
                      <option value="Graph">Graph</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Dimension</label>
                    <input type="number" name="dimension" required placeholder="e.g. 1024" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.dimension} onChange={handleFormChange} />
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

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Dataset Name</label>
                    <input type="text" name="datasetName" required placeholder="e.g. UniRef90" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.datasetName} onChange={handleFormChange} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Dataset Size</label>
                    <input type="text" name="datasetSize" required placeholder="e.g. 120M sequences" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.datasetSize} onChange={handleFormChange} />
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Pretraining Objective</label>
                  <input type="text" name="objective" required placeholder="e.g. Masked language modeling on protein sequence strings" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.objective} onChange={handleFormChange} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>HuggingFace Checkpoint URL (Optional)</label>
                  <input type="text" name="huggingface" placeholder="e.g. https://huggingface.co/evolutionaryscale/esm-3" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.huggingface} onChange={handleFormChange} />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Typical Tasks (Comma separated)</label>
                  <input type="text" name="typicalTasks" placeholder="e.g. Mutational effect, secondary structure prediction" className="search-input" style={{ padding: '0.5rem 0.75rem' }} value={submitForm.typicalTasks} onChange={handleFormChange} />
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
                  <div className="code-container" style={{ maxHeight: '200px' }}>
                    <pre className="code-block">
                      <code>{generatedJson}</code>
                    </pre>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem', textAlign: 'center' }}>
                    Submit this JSON payload by opening a Pull Request on our GitHub repository.
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
