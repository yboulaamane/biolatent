'use client';

import React, { useState } from 'react';
import literatureComparison from '../../../results/literature_measured_comparison.json';
import {
  EXPOSURE,
  EXPOSURE_SAMPLE,
  MODALITY_LABEL,
  MODEL_LABELS,
  Modality,
  PAIRED,
  RESOLUTION,
  RESOLUTION_REPEATS,
  RESULTS,
  ResolutionPoint,
  Row,
  Verdict,
  formatPct,
  formatScore,
  separationSummary,
  taskRows,
  tasksByModality,
  topGroupCounts,
  totalCells,
  totalModels,
} from '../data/study';

/**
 * The measured study. Every score on this tab was generated locally under the
 * benchmark protocol, unlike the Literature Registry tab which transcribes
 * published values. Matched registry records are compared descriptively, but
 * values from different protocols are never pooled into a common ranking.
 */

const CORPUS_LABELS: Record<string, string> = {
  zinc: 'ZINC', pubchem: 'PubChem', chembl: 'ChEMBL', swissprot: 'Swiss-Prot',
  uniref50: 'UniRef50', uniref100: 'UniRef100',
  human_ref_genome: 'human reference genome',
};

const VERDICT_STYLE: Record<Verdict, { bg: string; fg: string; text: string }> = {
  reference: { bg: 'rgba(99, 102, 241, 0.18)', fg: '#a5b4fc', text: 'validation reference' },
  indistinguishable: { bg: 'rgba(148, 163, 184, 0.12)', fg: '#94a3b8', text: 'not resolved' },
  better: { bg: 'rgba(16, 185, 129, 0.14)', fg: '#34d399', text: 'better than reference' },
  worse: { bg: 'rgba(244, 63, 94, 0.14)', fg: '#fb7185', text: 'worse than reference' },
  descriptive: { bg: 'rgba(245, 158, 11, 0.14)', fg: '#fbbf24', text: 'descriptive only' },
};

function exposureFraction(value: { fraction?: number; measures?: Record<string, { fraction: number }> }) {
  return value.measures?.any_proxy_hit?.fraction ?? value.fraction;
}

function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const s = VERDICT_STYLE[verdict];
  return (
    <span style={{
      background: s.bg, color: s.fg, padding: '0.15rem 0.55rem',
      borderRadius: '999px', fontSize: '0.7rem', fontWeight: 700,
      whiteSpace: 'nowrap',
    }}>
      {s.text}
    </span>
  );
}

function Stat({ value, label, tone }: { value: string; label: string; tone?: string }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-card)',
      borderRadius: '12px', padding: '1rem 1.25rem', flex: '1 1 160px',
    }}>
      <div style={{
        fontSize: '1.6rem', fontWeight: 800,
        color: tone ?? '#fff', lineHeight: 1.1,
      }}>{value}</div>
      <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem', marginTop: '0.35rem' }}>
        {label}
      </div>
    </div>
  );
}

function Finding({ title, text, tone }: { title: string; text: string; tone: string }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-card)',
      borderRadius: '12px', padding: '1rem 1.15rem', flex: '1 1 240px',
    }}>
      <div style={{ color: tone, fontSize: '0.95rem', fontWeight: 800, marginBottom: '0.35rem' }}>
        {title}
      </div>
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', lineHeight: 1.55 }}>
        {text}
      </div>
    </div>
  );
}

function TaskCard({ task }: { task: string }) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const meta = RESULTS[task];
  const paired = PAIRED[task];
  const rows = taskRows(task);
  const exposure = EXPOSURE[task];
  const metric = rows[0] ? RESULTS[task].models[rows[0].model].linear.metric : '';

  const exposureBits: string[] = [];
  if (exposure) {
    for (const [corpus, v] of Object.entries(exposure.empirical)) {
      const fraction = exposureFraction(v);
      if (fraction !== undefined) {
        exposureBits.push(`${CORPUS_LABELS[corpus] ?? corpus} ${formatPct(fraction)}`);
      }
    }
    if (Object.keys(exposure.structural).length > 0 && exposureBits.length === 0) {
      exposureBits.push('input exposure by construction');
    }
  }

  return (
    <details className="glass-card" style={{ marginBottom: '0.85rem' }}>
      <summary style={{ cursor: 'pointer', listStylePosition: 'outside' }}>
        <span style={{
          display: 'inline-flex', justifyContent: 'space-between', alignItems: 'baseline',
          flexWrap: 'wrap', gap: '0.5rem', width: 'calc(100% - 1.25rem)', marginLeft: '0.35rem',
        }}>
          <strong style={{ fontSize: '1.05rem', color: '#fff' }}>
            {meta.dataset_label ?? task}
          </strong>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
            {rows.length} representations · {metric} · test n = {meta.n_test.toLocaleString()}
          </span>
        </span>
      </summary>

      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', marginTop: '1rem',
      }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
          {meta.split_source}
          {meta.dataset_source ? ` · ${meta.dataset_source}` : ''}
        </div>
        <button
          type="button"
          onClick={() => setShowAdvanced((value) => !value)}
          style={{
            border: '1px solid rgba(99,102,241,0.45)', background: 'rgba(99,102,241,0.08)',
            color: '#c7d2fe', borderRadius: '8px', padding: '0.4rem 0.7rem',
            fontSize: '0.75rem', fontWeight: 700, cursor: 'pointer',
          }}
        >
          {showAdvanced ? 'Hide advanced columns' : 'Show advanced columns'}
        </button>
      </div>

      <details style={{ marginTop: '0.7rem' }}>
        <summary style={{
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700,
        }}>
          Dataset and statistical details
        </summary>
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '0.45rem', lineHeight: 1.55 }}>
          {meta.dataset_variant && (
            <>Variant: <strong style={{ color: '#fff' }}>{meta.dataset_variant}</strong>. </>
          )}
          {paired
            ? <>Reference selected on held-out data: <strong style={{ color: '#a5b4fc' }}>
              {MODEL_LABELS[paired.reference] ?? paired.reference}</strong>.{' '}
              {paired.inference_status === 'descriptive_only'
                ? <>Differences and intervals are descriptive: {paired.inference_note}</>
                : <>Difference intervals use paired {paired.resampling_unit.toLowerCase()} bootstrap
                  ({paired.n_boot.toLocaleString()} resamples); p-values use{' '}
                  {paired.n_permutations.toLocaleString()} paired randomisations with study-wide
                  Holm correction. {paired.inference_note}</>}
            </>
            : <>No paired comparison available for this task.</>}
          {exposureBits.length > 0 && (
            <> Pretraining input-exposure proxy: <strong style={{ color: '#fbbf24' }}>
              {exposureBits.join(', ')}</strong>.</>
          )}
        </div>
      </details>

      <div style={{ overflowX: 'auto' }}>
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Representation</th>
              {showAdvanced && <th style={{ textAlign: 'right' }}>Dim</th>}
              <th style={{ textAlign: 'right' }}>Score</th>
              <th>95% interval</th>
              {showAdvanced && <th>vs validation reference</th>}
              {showAdvanced && <th style={{ textAlign: 'right' }}>MLP gap</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((r: Row) => (
              <tr key={r.model}>
                <td style={{ color: '#fff', fontWeight: 600 }}>
                  {r.label}
                  {r.isBaseline && (
                    <span style={{
                      marginLeft: '0.5rem', fontSize: '0.65rem', fontWeight: 700,
                      color: '#34d399', background: 'rgba(16,185,129,0.12)',
                      padding: '0.1rem 0.4rem', borderRadius: '4px',
                    }}>no pretraining</span>
                  )}
                </td>
                {showAdvanced && (
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {r.dim.toLocaleString()}
                  </td>
                )}
                <td style={{
                  textAlign: 'right', color: '#fff', fontWeight: 700,
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {formatScore(r.score)}
                </td>
                <td style={{ fontVariantNumeric: 'tabular-nums', fontSize: '0.82rem' }}>
                  {r.ciLow !== undefined && r.ciHigh !== undefined
                    ? `[${formatScore(r.ciLow)}, ${formatScore(r.ciHigh)}]`
                    : '—'}
                </td>
                {showAdvanced && (
                  <td>
                    <VerdictBadge verdict={r.verdict} />
                    {(r.verdict === 'worse' || r.verdict === 'better') && r.pHolm !== undefined && (
                      <span style={{
                        marginLeft: '0.5rem', color: 'var(--text-muted)',
                        fontSize: '0.72rem', fontVariantNumeric: 'tabular-nums',
                      }}>
                        Δ {r.delta?.toFixed(4)} · p {r.pHolm.toFixed(3)}
                      </span>
                    )}
                  </td>
                )}
                {showAdvanced && (
                  <td style={{
                    textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                    color: (r.gap ?? 0) < 0 ? '#94a3b8' : '#34d399',
                  }}>
                    {r.gap !== undefined ? (r.gap > 0 ? '+' : '') + r.gap.toFixed(4) : '—'}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function LadderPanel() {
  const entries: { task: string; name: string; steps: [string, ReturnType<typeof stepOf>][] }[] = [];
  function stepOf(task: string, ladder: string, key: string) {
    return PAIRED[task].ladders![ladder].steps[key];
  }
  for (const [task, paired] of Object.entries(PAIRED)) {
    if (!paired.ladders) continue;
    for (const [name, ladder] of Object.entries(paired.ladders)) {
      entries.push({
        task,
        name,
        steps: Object.keys(ladder.steps).map((k) => [k, stepOf(task, name, k)]),
      });
    }
  }
  if (entries.length === 0) return null;

  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
        Does scale help? Tested step by step
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0.5rem 0 1rem' }}>
        Each consecutive ESM-2 checkpoint is tested against the one below it, as a
        pre-specified family corrected within itself. This separates an observed
        scale trend from a claim that larger checkpoints are universally better.
        DeepLoc uses formal homology-cluster inference; Fluorescence is descriptive because
        its test variants form one connected homology component at the prespecified threshold.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Task</th><th>Step</th>
              <th style={{ textAlign: 'right' }}>Δ</th>
              <th>95% CI</th>
              <th style={{ textAlign: 'right' }}>Holm p</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {entries.flatMap((e) => e.steps.map(([key, step]) => {
              const [from, to] = key.split('->');
              const regress = step.direction === 'REGRESSES';
              const descriptive = step.direction === 'descriptive only';
              return (
                <tr key={`${e.task}-${key}`}>
                  <td style={{ color: '#fff' }}>{e.task}</td>
                  <td>{MODEL_LABELS[from] ?? from} → {MODEL_LABELS[to] ?? to}</td>
                  <td style={{
                    textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                    color: regress ? '#fb7185' : '#fff', fontWeight: 700,
                  }}>
                    {step.delta > 0 ? '+' : ''}{step.delta.toFixed(4)}
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', fontSize: '0.82rem' }}>
                    [{step.ci_low > 0 ? '+' : ''}{step.ci_low.toFixed(4)},{' '}
                    {step.ci_high > 0 ? '+' : ''}{step.ci_high.toFixed(4)}]
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {step.p_holm === null ? '—' : step.p_holm.toFixed(3)}
                  </td>
                  <td>
                    <span style={{
                      background: descriptive ? 'rgba(245,158,11,0.14)'
                        : regress ? 'rgba(244,63,94,0.16)' : 'rgba(16,185,129,0.14)',
                      color: descriptive ? '#fbbf24' : regress ? '#fb7185' : '#34d399',
                      padding: '0.15rem 0.55rem', borderRadius: '999px',
                      fontSize: '0.7rem', fontWeight: 700,
                    }}>
                      {regress ? 'reliably worse' : step.direction}
                    </span>
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ExposurePanel() {
  const rows = Object.entries(EXPOSURE);
  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
        Pretraining input-exposure audit
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0.5rem 0 1rem' }}>
        This measures input familiarity, not downstream label leakage. Molecular values are
        exact identity / near-duplicate / shared-scaffold fractions against random{' '}
        {EXPOSURE_SAMPLE.toLocaleString()}-molecule database samples, which are proxies rather
        than the checkpoints&apos; exact dated training subsets. Protein values are homology
        proxies from MMseqs2 at ≥ 50% identity and ≥ 50% coverage against Swiss-Prot.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Task</th>
              <th style={{ textAlign: 'right' }}>Test n</th>
              <th style={{ textAlign: 'right' }}>ZINC</th>
              <th style={{ textAlign: 'right' }}>PubChem</th>
              <th style={{ textAlign: 'right' }}>Swiss-Prot</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([task, e]) => {
              const cell = (key: string) => {
                const v = e.empirical[key];
                if (!v) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
                const fraction = exposureFraction(v);
                if (fraction === undefined) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
                const hot = fraction >= 0.5;
                const measures = v.measures;
                return (
                  <span style={{ color: hot ? '#f87171' : '#fbbf24', fontWeight: 700 }}>
                    {measures
                      ? `${formatPct(measures.exact_identity.fraction)} / ${formatPct(measures.near_duplicate.fraction)} / ${formatPct(measures.shared_scaffold.fraction)}`
                      : formatPct(fraction)}
                  </span>
                );
              };
              const structural = Object.keys(e.structural);
              const unmeasured = Object.entries(e.unmeasured ?? {});
              const affected = [...new Set(Object.values(e.empirical)
                .flatMap((value) => value.affected_models ?? []))]
                .map((model) => MODEL_LABELS[model] ?? model);
              const note = structural.length > 0
                ? `${structural.map((s) => CORPUS_LABELS[s] ?? s).join(', ')}: input exposure by construction; labels not implied`
                : affected.length > 0 ? `proxy applies to declared corpora for ${affected.join(', ')}` : '';
              const missing = unmeasured.map(([corpus, value]) => {
                const models = value.affected_models
                  .map((model) => MODEL_LABELS[model] ?? model).join(', ');
                return `${CORPUS_LABELS[corpus] ?? corpus}: unmeasured for ${models}`;
              }).join('; ');
              return (
                <tr key={task}>
                  <td style={{ color: '#fff', fontWeight: 600 }}>{task}</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {e.n_test.toLocaleString()}
                  </td>
                  <td style={{ textAlign: 'right' }}>{cell('zinc')}</td>
                  <td style={{ textAlign: 'right' }}>{cell('pubchem')}</td>
                  <td style={{ textAlign: 'right' }}>{cell('swissprot')}</td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    {[note, missing].filter(Boolean).join('; ')}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TopGroupPanel({ modality }: { modality: Modality }) {
  const counts = topGroupCounts(modality);
  if (counts.length === 0) return null;
  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>
        How often each representation is not resolved as worse than the reference
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '0.5rem 0 0.75rem' }}>
        Deliberately a count, not a ranking. The comparator is selected on held-out
        validation data, so the test set is not used to choose the reference it judges.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {counts.map((c) => (
          <div key={c.model} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{ width: '190px', color: '#fff', fontSize: '0.85rem', fontWeight: 600 }}>
              {c.label}
              {c.isBaseline && (
                <span style={{ marginLeft: '0.4rem', fontSize: '0.62rem', color: '#34d399' }}>
                  baseline
                </span>
              )}
            </div>
            <div style={{
              flex: 1, height: '10px', background: 'rgba(255,255,255,0.05)',
              borderRadius: '999px', overflow: 'hidden',
            }}>
              <div style={{
                width: `${(c.top / c.total) * 100}%`, height: '100%',
                background: 'var(--gradient-latent)', borderRadius: '999px',
              }} />
            </div>
            <div style={{
              width: '64px', textAlign: 'right', color: 'var(--text-secondary)',
              fontSize: '0.8rem', fontVariantNumeric: 'tabular-nums',
            }}>
              {c.top} of {c.total}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResolutionPanel({ modality }: { modality: Modality }) {
  const rows = tasksByModality(modality).flatMap((task) => {
    const entry = RESOLUTION[task];
    if (!entry) return [];
    const curves = Object.values(entry.comparisons)
      .map((comparison) => comparison.curve)
      .filter((curve) => curve.length > 0);
    if (curves.length === 0) return [];
    const nearest = (curve: ResolutionPoint[], target: number) =>
      curve.reduce((best, point) =>
        Math.abs(point.median_effective_n - target)
          < Math.abs(best.median_effective_n - target) ? point : best);
    const median = (values: number[]) => {
      const sorted = [...values].sort((a, b) => a - b);
      const middle = Math.floor(sorted.length / 2);
      return sorted.length % 2
        ? sorted[middle]
        : (sorted[middle - 1] + sorted[middle]) / 2;
    };
    const lowPoints = curves.map((curve) => nearest(curve, 100));
    const highPoints = curves.map((curve) => curve.at(-1)!);
    return [{
      task,
      nTest: entry.n_test,
      lowN: Math.round(median(lowPoints.map((point) => point.median_effective_n))),
      lowSign: median(lowPoints.map((point) => point.sign_consistency)),
      highN: Math.round(median(highPoints.map((point) => point.median_effective_n))),
      highSign: median(highPoints.map((point) => point.sign_consistency)),
      highWidth: median(highPoints.map((point) => point.central_95_width)),
    }];
  });
  if (rows.length === 0) return null;

  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>
        Fixed-test-set subsampling stability
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '0.5rem 0 0.75rem' }}>
        Across {RESOLUTION_REPEATS.toLocaleString()} repeated subsets, this shows the median
        consistency of each reference comparison&apos;s direction. It is conditional on the
        observed test set and is not a causal estimate of how adding data would change a task.
        Molecular subsets retain whole scaffold groups and DeepLoc subsets retain whole MMseqs2
        homology clusters, so their effective n can exceed the target.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Task</th>
              <th style={{ textAlign: 'right' }}>Test n</th>
              <th style={{ textAlign: 'right' }}>Direction at smaller n</th>
              <th style={{ textAlign: 'right' }}>Direction at larger n</th>
              <th style={{ textAlign: 'right' }}>Median central-range width</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.task}>
                <td style={{ color: '#fff', fontWeight: 600 }}>{row.task}</td>
                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {row.nTest.toLocaleString()}
                </td>
                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {formatPct(row.lowSign)} at n ≈ {row.lowN.toLocaleString()}
                </td>
                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {formatPct(row.highSign)} at n ≈ {row.highN.toLocaleString()}
                </td>
                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {row.highWidth.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function StudyTab() {
  const [modality, setModality] = useState<Modality>('molecule');
  const mol = separationSummary('molecule');
  const prot = separationSummary('protein');
  const genomic = separationSummary('genomics');
  const tasks = tasksByModality(modality);
  const resolved = mol.reliable + prot.reliable + genomic.reliable;
  const eligible = mol.total + prot.total + genomic.total;

  return (
    <div>
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', marginBottom: '0.4rem' }}>
          Compare representations on equal terms
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6 }}>
          BioLatent combines a registry of published results with a controlled benchmark of{' '}
          {totalModels()} representations across {Object.keys(RESULTS).length} public datasets.
        </p>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1.1rem' }}>
          <Finding
            title="No universal winner"
            text="The leading representation changes with the biological or chemical endpoint."
            tone="#a78bfa"
          />
          <Finding
            title="Classical methods remain competitive"
            text="Fingerprints and calculated descriptors remain strong baselines for molecular prediction."
            tone="#34d399"
          />
          <Finding
            title="Many rankings remain uncertain"
            text={`${resolved} of ${eligible} eligible comparisons were distinguishable after correction.`}
            tone="#fbbf24"
          />
        </div>

        <details style={{
          marginTop: '1rem', padding: '0.8rem 1rem',
          background: 'rgba(99, 102, 241, 0.06)',
          border: '1px solid rgba(99, 102, 241, 0.22)', borderRadius: '10px',
        }}>
          <summary style={{ color: '#c7d2fe', cursor: 'pointer', fontWeight: 800, fontSize: '0.86rem' }}>
            How the benchmark works
          </summary>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.84rem', lineHeight: 1.6, marginTop: '0.7rem' }}>
            <p>
              The measured results were generated under one prespecified procedure rather than
              transcribed from papers. Each compatible representation was calculated once and
              evaluated with the same standardised linear model, regularisation search, folds and seed.
              The comparison method was chosen using validation data before the test set was examined.
            </p>
            <p style={{ marginTop: '0.6rem' }}>
              Difference intervals use paired cluster bootstrap, p-values use paired randomisation,
              and eligible comparisons are adjusted together using Holm correction. Molecular tests
              resample Bemis–Murcko scaffolds and DeepLoc resamples MMseqs2 homology clusters.
              Fluorescence is descriptive because its test variants do not form independent clusters
              at the prespecified threshold.
            </p>
            <p style={{ marginTop: '0.6rem' }}>
              <strong style={{ color: '#fff' }}>Literature comparison.</strong>{' '}
              {literatureComparison.matched_summary.pairs} registry records matched by representation
              family, endpoint and metric. All used documented scaffold splits. The measured value was
              higher in {literatureComparison.matched_summary.measured_higher} pairs and the literature
              value in {literatureComparison.matched_summary.literature_higher}. This describes how
              results transfer across protocols; it does not test random-split inflation.
            </p>
            <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginTop: '0.85rem' }}>
              <Stat value={`${mol.reliable}/${mol.total}`} label="molecular comparisons resolved" tone="#fb7185" />
              <Stat value={`${prot.reliable}/${prot.total}`} label="eligible protein comparisons resolved" tone="#34d399" />
              <Stat value={`${genomic.reliable}/${genomic.total}`} label="genomic comparisons resolved" tone="#fbbf24" />
              <Stat value={`${totalCells()}`} label="measured model–dataset evaluations" />
            </div>
          </div>
        </details>
      </div>

      <div style={{ marginBottom: '0.9rem' }}>
        <h2 style={{ color: '#fff', fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.25rem' }}>
          Results by dataset
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem' }}>
          Choose a domain, then open a dataset to inspect its scores.
        </p>
      </div>

      <div className="tabs-nav" style={{ marginBottom: '1.25rem' }}>
        {(['molecule', 'protein', 'genomics'] as Modality[]).map((m) => (
          <button key={m}
            className={`tab-btn ${modality === m ? 'active' : ''}`}
            onClick={() => setModality(m)}>
            {MODALITY_LABEL[m]}
          </button>
        ))}
      </div>

      {tasks.map((t) => <TaskCard key={t} task={t} />)}

      <details className="glass-card" style={{ marginTop: '1.25rem' }}>
        <summary style={{ color: '#fff', cursor: 'pointer', fontWeight: 800, fontSize: '1rem' }}>
          Additional analyses and interpretation
        </summary>
        <div style={{ marginTop: '1rem' }}>
          <TopGroupPanel modality={modality} />
          <ResolutionPanel modality={modality} />
          {modality === 'protein' && <LadderPanel />}
          <ExposurePanel />

          <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>
            How to read these numbers
          </h3>
          <ul style={{
            color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.7,
            paddingLeft: '1.25rem', marginTop: '0.6rem',
          }}>
            <li><strong style={{ color: '#fff' }}>&ldquo;Not resolved&rdquo; does not mean equal.</strong> It
              means this test set could not separate the model from the validation-selected
              reference at the stated multiplicity correction.</li>
            <li><strong style={{ color: '#fff' }}>&ldquo;Descriptive only&rdquo; means no formal population claim.</strong>{' '}
              The score and interval describe the observed panel, but no p-value is reported when
              suitable independent resampling units are unavailable.</li>
            <li><strong style={{ color: '#fff' }}>The numerical test best is descriptive.</strong>{' '}
              It is shown for orientation but is not selected and tested on the same outcomes.</li>
            <li><strong style={{ color: '#fff' }}>Intervals cover the test set only</strong>, not
              variance from the split itself.</li>
            <li><strong style={{ color: '#fff' }}>The MLP column is a diagnostic, never ranked.</strong> Ranking
              it would measure the MLP&apos;s capacity rather than the representation; the
              informative part is its gap to the linear model.</li>
            <li><strong style={{ color: '#fff' }}>Values are internally comparable, not externally.</strong> Every
              dataset variant and split is stated beside its result. These values must
              not be mixed with literature values produced under different protocols.</li>
          </ul>
        </div>
      </details>
    </div>
  );
}
