/**
 * Measured frozen-embedding study — typed view over the committed result files.
 *
 * The three JSON files are imported from `results/` rather than copied into
 * `src/`, so the page and the manuscript are rendered from the same artefacts
 * the evaluation suite writes. Nothing here restates a number; every value is
 * read from disk at build time.
 *
 *   results/benchmark_results.json   scores, intervals, MLP diagnostic
 *   results/paired_comparisons.json  paired bootstrap vs each task's leader
 *   results/leakage_report.json      test-split overlap with pretraining corpora
 */

import benchmarkResultsRaw from '../../../results/benchmark_results.json';
import pairedRaw from '../../../results/paired_comparisons.json';
import leakageRaw from '../../../results/leakage_report.json';

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
  linear: ProbeResult;
  mlp?: { score: number };
  linear_mlp_gap?: number;
  embed_seconds?: number;
}

export interface TaskResult {
  modality: Modality;
  task_type: 'classification' | 'regression';
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
  leader: string;
  leader_score: number;
  n_test: number;
  n_boot: number;
  correction: string;
  comparisons: Record<string, Comparison>;
  ladders?: Record<string, { rungs: string[]; steps: Record<string, LadderStep> }>;
}

export interface LeakageTask {
  modality: Modality;
  n_test: number;
  empirical: Record<string, { n_flagged: number; fraction: number; basis: string }>;
  structural: Record<string, { affected_models: string[]; claim: string }>;
}

export const RESULTS = benchmarkResultsRaw as unknown as Record<string, TaskResult>;
export const PAIRED = pairedRaw as unknown as Record<string, PairedTask>;
export const LEAKAGE = (leakageRaw as unknown as {
  sample_size: number;
  tasks: Record<string, LeakageTask>;
}).tasks;
export const LEAKAGE_SAMPLE = (leakageRaw as unknown as { sample_size: number }).sample_size;

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

export type Verdict = 'leader' | 'tied' | 'below';

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
 * task leader. `tied` means the paired test could not separate it from the
 * leader — not that the scores are equal.
 */
export function taskRows(task: string): Row[] {
  const result = RESULTS[task];
  const paired = PAIRED[task];
  if (!result) return [];

  return Object.entries(result.models)
    .map(([model, cell]) => {
      const comparison = paired?.comparisons?.[model];
      const isLeader = paired?.leader === model;
      const verdict: Verdict = isLeader
        ? 'leader'
        : comparison?.significant
          ? 'below'
          : 'tied';
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
  let leadersSeparatedFromRunnerUp = 0;
  const tasks = tasksByModality(modality);
  for (const task of tasks) {
    const paired = PAIRED[task];
    if (!paired) continue;
    const comparisons = Object.values(paired.comparisons);
    total += comparisons.length;
    reliable += comparisons.filter((c) => c.significant).length;
    // The runner-up is the smallest positive delta from the leader.
    const runnerUp = comparisons.reduce<Comparison | null>(
      (best, c) => (best === null || c.delta < best.delta ? c : best), null);
    if (runnerUp?.significant) leadersSeparatedFromRunnerUp += 1;
  }
  return { reliable, total, tasks: tasks.length, leadersSeparatedFromRunnerUp };
}

/** How often a representation sits in the statistically tied top group. */
export function topGroupCounts(modality: Modality) {
  const tasks = tasksByModality(modality);
  const counts = new Map<string, { top: number; total: number }>();
  for (const task of tasks) {
    for (const row of taskRows(task)) {
      const entry = counts.get(row.model) ?? { top: 0, total: 0 };
      entry.total += 1;
      if (row.verdict !== 'below') entry.top += 1;
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
