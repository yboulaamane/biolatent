/**
 * Measured frozen-embedding study — typed view over the committed result files.
 *
 * The result JSON files are imported from `results/` rather than copied into
 * `src/`, so the page and the manuscript are rendered from the same artefacts
 * the evaluation suite writes. Nothing here restates a number; every value is
 * read from disk at build time.
 *
 *   results/benchmark_results.json   scores, intervals, MLP diagnostic
 *   results/paired_comparisons.json  validation-selected paired inference
 *   results/exposure_report.json     pretraining input-exposure proxies
 *   results/resolution_curves.json   fixed-test-set subsampling stability
 */

import benchmarkResultsRaw from '../../../results/benchmark_results.json';
import pairedRaw from '../../../results/paired_comparisons.json';
import exposureRaw from '../../../results/exposure_report.json';
import resolutionRaw from '../../../results/resolution_curves.json';

export type Modality = 'molecule' | 'protein' | 'genomics';

export interface ProbeResult {
  metric: string;
  score: number;
  accuracy?: number;
  macro_f1?: number;
  rmse?: number;
  r2?: number;
  ci_low?: number;
  ci_high?: number;
  ci_width?: number;
  embedding_dim: number;
  n_train?: number;
  n_test?: number;
}

export interface ModelCell {
  label: string;
  embedding_sha256: string;
  linear: ProbeResult;
  mlp?: { score: number };
  linear_mlp_gap?: number;
  embed_seconds?: number;
}

export interface TaskResult {
  dataset_label?: string;
  dataset_source?: string;
  dataset_sha256?: string;
  modality: Modality;
  task_type: 'classification' | 'multilabel' | 'regression';
  dataset_variant?: string;
  split_source: string;
  n_total: number;
  n_train: number;
  n_test: number;
  models: Record<string, ModelCell>;
}

export interface Comparison {
  score: number;
  delta: number;
  ci_low: number;
  ci_high: number;
  p_raw: number;
  p_holm: number;
  significant: boolean;
  p_holm_task?: number;
  p_holm_modality?: number;
  p_holm_global?: number;
  significant_global?: boolean;
}

export interface LadderStep {
  delta: number;
  ci_low: number;
  ci_high: number;
  p_raw: number;
  p_holm: number;
  direction: 'improves' | 'REGRESSES' | 'no reliable difference';
  significant: boolean;
}

export interface PairedTask {
  reference: string;
  reference_selection: string;
  reference_selection_score: number;
  reference_test_score: number;
  observed_test_best: string;
  observed_test_best_score: number;
  n_test: number;
  n_boot: number;
  n_permutations: number;
  n_resampling_groups: number;
  resampling_unit: string;
  primary_correction: string;
  comparisons: Record<string, Comparison>;
  ladders?: Record<string, { rungs: string[]; steps: Record<string, LadderStep> }>;
}

export interface ExposureMeasure {
  n_flagged: number;
  fraction: number;
  basis: string;
}

export interface ExposureEmpirical extends Partial<ExposureMeasure> {
  affected_models?: string[];
  sample_role?: string;
  measures?: Record<string, ExposureMeasure>;
}

export interface ExposureTask {
  modality: Modality;
  n_test: number;
  empirical: Record<string, ExposureEmpirical>;
  structural: Record<string, { affected_models: string[]; claim: string }>;
}

export interface ResolutionPoint {
  requested_n: number;
  median_effective_n: number;
  median_delta: number;
  central_95_low: number;
  central_95_high: number;
  central_95_width: number;
  sign_consistency: number;
  valid_repeats: number;
}

export interface ResolutionTask {
  n_test: number;
  reference: string;
  comparisons: Record<string, {
    full_test_delta: number;
    curve: ResolutionPoint[];
  }>;
}

export const RESULTS = benchmarkResultsRaw as unknown as Record<string, TaskResult>;
export const PAIRED = pairedRaw as unknown as Record<string, PairedTask>;
export const EXPOSURE = (exposureRaw as unknown as {
  sample_size: number;
  tasks: Record<string, ExposureTask>;
}).tasks;
export const EXPOSURE_SAMPLE = (exposureRaw as unknown as { sample_size: number }).sample_size;
export const RESOLUTION = (resolutionRaw as unknown as {
  repeats: number;
  tasks: Record<string, ResolutionTask>;
}).tasks;
export const RESOLUTION_REPEATS = (resolutionRaw as unknown as { repeats: number }).repeats;

/** Display names. The registry uses different ids, so this map is local. */
export const MODEL_LABELS: Record<string, string> = {
  ecfp4: 'ECFP4',
  rdkit2d: 'RDKit2D',
  chemberta_77m: 'ChemBERTa-77M',
  chemberta_zinc: 'ChemBERTa-ZINC',
  molformer_xl: 'MoLFormer-XL',
  kmer3_protein: '3-mer frequency',
  esm2_8m: 'ESM-2 8M',
  esm2_35m: 'ESM-2 35M',
  esm2_150m: 'ESM-2 150M',
  esm2_650m: 'ESM-2 650M',
  protbert: 'ProtBERT',
  kmer5_dna: '5-mer frequency',
  nucleotide_transformer: 'Nucleotide Transformer 500M',
  hyenadna: 'HyenaDNA-tiny',
};

/** Baselines that involve no pretraining, highlighted wherever they win. */
export const BASELINES = new Set(['ecfp4', 'rdkit2d', 'kmer3_protein', 'kmer5_dna']);

export const TASK_ORDER = [
  'BBBP', 'ClinTox', 'BACE', 'ESOL', 'Lipophilicity', 'CYP3A4',
  'DeepLoc', 'Fluorescence', 'Promoters',
];

export const MODALITY_LABEL: Record<Modality, string> = {
  molecule: 'Molecules',
  protein: 'Proteins',
  genomics: 'Genomics',
};

export type Verdict = 'reference' | 'indistinguishable' | 'better' | 'worse';

export interface Row {
  model: string;
  label: string;
  dim: number;
  score: number;
  ciLow?: number;
  ciHigh?: number;
  mlp?: number;
  gap?: number;
  verdict: Verdict;
  delta?: number;
  pHolm?: number;
  isBaseline: boolean;
}

/**
 * Rows for one task, ordered by score, each carrying its verdict against the
 * representation selected on validation data.
 */
export function taskRows(task: string): Row[] {
  const result = RESULTS[task];
  const paired = PAIRED[task];
  if (!result) return [];

  return Object.entries(result.models)
    .map(([model, cell]) => {
      const comparison = paired?.comparisons?.[model];
      const isReference = paired?.reference === model;
      const significant = comparison?.significant_global ?? comparison?.significant;
      const verdict: Verdict = isReference
        ? 'reference'
        : significant
          ? comparison.delta > 0 ? 'worse' : 'better'
          : 'indistinguishable';
      return {
        model,
        label: MODEL_LABELS[model] ?? cell.label ?? model,
        dim: cell.linear.embedding_dim,
        score: cell.linear.score,
        ciLow: cell.linear.ci_low,
        ciHigh: cell.linear.ci_high,
        mlp: cell.mlp?.score,
        gap: cell.linear_mlp_gap,
        verdict,
        delta: comparison?.delta,
        pHolm: comparison?.p_holm,
        isBaseline: BASELINES.has(model),
      };
    })
    .sort((a, b) => b.score - a.score);
}

export function tasksByModality(modality: Modality): string[] {
  return TASK_ORDER.filter((t) => RESULTS[t]?.modality === modality);
}

/** Headline counts, computed rather than stated, so they cannot go stale. */
export function separationSummary(modality: Modality) {
  let reliable = 0;
  let total = 0;
  let referencesDifferFromTestBest = 0;
  const tasks = tasksByModality(modality);
  for (const task of tasks) {
    const paired = PAIRED[task];
    if (!paired) continue;
    const comparisons = Object.values(paired.comparisons);
    total += comparisons.length;
    reliable += comparisons.filter((c) => c.significant).length;
    const bestComparison = paired.comparisons[paired.observed_test_best];
    if (bestComparison?.significant) referencesDifferFromTestBest += 1;
  }
  return { reliable, total, tasks: tasks.length, referencesDifferFromTestBest };
}

/** How often a representation is not resolved as worse than the reference. */
export function topGroupCounts(modality: Modality) {
  const tasks = tasksByModality(modality);
  const counts = new Map<string, { top: number; total: number }>();
  for (const task of tasks) {
    for (const row of taskRows(task)) {
      const entry = counts.get(row.model) ?? { top: 0, total: 0 };
      entry.total += 1;
      if (row.verdict !== 'worse') entry.top += 1;
      counts.set(row.model, entry);
    }
  }
  return [...counts.entries()]
    .map(([model, c]) => ({
      model,
      label: MODEL_LABELS[model] ?? model,
      isBaseline: BASELINES.has(model),
      ...c,
    }))
    .sort((a, b) => b.top - a.top || a.label.localeCompare(b.label));
}

export function totalCells(): number {
  return Object.values(RESULTS).reduce((n, t) => n + Object.keys(t.models).length, 0);
}

export function totalModels(): number {
  const seen = new Set<string>();
  for (const task of Object.values(RESULTS)) {
    Object.keys(task.models).forEach((m) => seen.add(m));
  }
  return seen.size;
}

export function formatScore(x: number): string {
  return x.toFixed(4);
}

export function formatPct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}
