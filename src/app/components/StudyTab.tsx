'use client';

import React, { useState } from 'react';
import {
  LEAKAGE,
  LEAKAGE_SAMPLE,
  MODALITY_LABEL,
  MODEL_LABELS,
  Modality,
  PAIRED,
  RESULTS,
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
 * The measured study. Every score on this tab was produced by running the
 * model, unlike the Literature Registry tab which transcribes published
 * values. The two are deliberately never mixed.
 */

const CORPUS_LABELS: Record<string, string> = {
  zinc: 'ZINC', pubchem: 'PubChem', swissprot: 'Swiss-Prot',
  uniref50: 'UniRef50', human_ref_genome: 'human reference genome',
};

const VERDICT_STYLE: Record<Verdict, { bg: string; fg: string; text: string }> = {
  leader: { bg: 'rgba(99, 102, 241, 0.18)', fg: '#a5b4fc', text: 'leader' },
  tied: { bg: 'rgba(148, 163, 184, 0.12)', fg: '#94a3b8', text: 'tied with leader' },
  below: { bg: 'rgba(244, 63, 94, 0.14)', fg: '#fb7185', text: 'below leader' },
};

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

function TaskCard({ task }: { task: string }) {
  const meta = RESULTS[task];
  const paired = PAIRED[task];
  const rows = taskRows(task);
  const leak = LEAKAGE[task];
  const metric = rows[0] ? RESULTS[task].models[rows[0].model].linear.metric : '';

  const leakBits: string[] = [];
  if (leak) {
    for (const [corpus, v] of Object.entries(leak.empirical)) {
      leakBits.push(`${CORPUS_LABELS[corpus] ?? corpus} ${formatPct(v.fraction)}`);
    }
    if (Object.keys(leak.structural).length > 0 && leakBits.length === 0) {
      leakBits.push('total by construction');
    }
  }

  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem',
      }}>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>{task}</h3>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>
          {metric} · test n = {meta.n_test.toLocaleString()} · {meta.split_source} split
        </div>
      </div>

      <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginTop: '0.4rem' }}>
        {paired
          ? <>Compared against <strong style={{ color: '#a5b4fc' }}>{rows[0]?.label}</strong> by
            paired bootstrap ({paired.n_boot.toLocaleString()} resamples), {paired.correction}.</>
          : <>No paired comparison available for this task.</>}
        {leakBits.length > 0 && (
          <> Pretraining overlap of the test split: <strong style={{ color: '#fbbf24' }}>
            {leakBits.join(', ')}</strong>.</>
        )}
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="benchmark-table">
          <thead>
            <tr>
              <th>Representation</th>
              <th style={{ textAlign: 'right' }}>Dim</th>
              <th style={{ textAlign: 'right' }}>Linear probe</th>
              <th>95% interval</th>
              <th>vs leader</th>
              <th style={{ textAlign: 'right' }}>MLP gap</th>
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
                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {r.dim.toLocaleString()}
                </td>
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
                <td>
                  <VerdictBadge verdict={r.verdict} />
                  {r.verdict === 'below' && r.pHolm !== undefined && (
                    <span style={{
                      marginLeft: '0.5rem', color: 'var(--text-muted)',
                      fontSize: '0.72rem', fontVariantNumeric: 'tabular-nums',
                    }}>
                      Δ {r.delta?.toFixed(4)} · p {r.pHolm.toFixed(3)}
                    </span>
                  )}
                </td>
                <td style={{
                  textAlign: 'right', fontVariantNumeric: 'tabular-nums',
                  color: (r.gap ?? 0) < 0 ? '#94a3b8' : '#34d399',
                }}>
                  {r.gap !== undefined ? (r.gap > 0 ? '+' : '') + r.gap.toFixed(4) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
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
        pre-specified family corrected within itself. The same four checkpoints
        under the same probe give <strong style={{ color: '#fff' }}>opposite
        answers</strong> on the two protein tasks.
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
                    {step.p_holm.toFixed(3)}
                  </td>
                  <td>
                    <span style={{
                      background: regress ? 'rgba(244,63,94,0.16)' : 'rgba(16,185,129,0.14)',
                      color: regress ? '#fb7185' : '#34d399',
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

function LeakagePanel() {
  const rows = Object.entries(LEAKAGE);
  return (
    <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#fff' }}>
        Pretraining leakage audit
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0.5rem 0 1rem' }}>
        Fraction of each <strong style={{ color: '#fff' }}>test split</strong> recoverable
        from the corpora the models declare. Molecules: Bemis-Murcko scaffold identity or
        ECFP4 Tanimoto ≥ 0.9 against random {LEAKAGE_SAMPLE.toLocaleString()}-molecule
        samples, so every molecular figure is a <em>lower bound</em>. Proteins: MMseqs2
        alignment at ≥ 50% identity and ≥ 50% coverage against the whole of Swiss-Prot.
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
                const hot = v.fraction >= 0.5;
                return (
                  <span style={{ color: hot ? '#f87171' : '#fbbf24', fontWeight: 700 }}>
                    {formatPct(v.fraction)}
                  </span>
                );
              };
              const structural = Object.keys(e.structural);
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
                    {structural.length > 0
                      ? `${structural.map((s) => CORPUS_LABELS[s] ?? s).join(', ')}: covered by construction`
                      : ''}
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
        How often each representation is in the tied top group
      </h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '0.5rem 0 0.75rem' }}>
        Deliberately a count, not a ranking. A representation is in the top group when the
        paired test cannot separate it from that task&apos;s leader.
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

export default function StudyTab() {
  const [modality, setModality] = useState<Modality>('molecule');
  const mol = separationSummary('molecule');
  const prot = separationSummary('protein');
  const tasks = tasksByModality(modality);

  return (
    <div>
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#fff', marginBottom: '0.4rem' }}>
          Measured Benchmark — Frozen Embedding Study
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6 }}>
          Every number below was produced by running the model on this hardware, not
          transcribed from a paper. {totalModels()} representations were embedded once
          per dataset and evaluated with one standardised linear probe — the same
          regularisation grid, folds and seed for all of them — across {Object.keys(RESULTS).length} tasks,
          giving {totalCells()} model-task cells. Each model is then compared against its
          task leader by <strong style={{ color: '#fff' }}>paired bootstrap</strong> with
          Holm correction, because all models are scored on the same test items and
          comparing independent intervals is markedly less powerful.
        </p>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1.25rem' }}>
          <Stat value={`${mol.reliable} of ${mol.total}`}
                label="molecular comparisons that are statistically reliable"
                tone="#fb7185" />
          <Stat value={`${prot.reliable} of ${prot.total}`}
                label="protein comparisons that are statistically reliable"
                tone="#34d399" />
          <Stat value={`${mol.leadersSeparatedFromRunnerUp} of ${mol.tasks}`}
                label="molecular tasks where the leader beats its runner-up"
                tone="#fb7185" />
          <Stat value={`${totalCells()}`} label="model-task cells, all really run" />
        </div>

        <div style={{
          marginTop: '1.25rem', padding: '1rem 1.25rem',
          background: 'rgba(244, 63, 94, 0.07)',
          border: '1px solid rgba(244, 63, 94, 0.2)', borderRadius: '12px',
        }}>
          <div style={{ color: '#fb7185', fontWeight: 800, fontSize: '0.9rem', marginBottom: '0.35rem' }}>
            The headline result is about the benchmarks, not the models
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
            On the molecular tasks, {mol.reliable} of {mol.total} comparisons survive
            correction and <strong style={{ color: '#fff' }}>not one separates a task
            leader from its runner-up</strong>. The same protocol on the protein tasks
            resolves {prot.reliable} of {prot.total}, including gaps as small as 0.014.
            The difference is test-set size, not modality: ClinTox cannot establish a
            0.113 gap on 148 molecules, while Fluorescence establishes a 0.014 gap on
            27,217 sequences.
          </div>
        </div>
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

      <TopGroupPanel modality={modality} />
      {modality === 'protein' && <LadderPanel />}
      <LeakagePanel />

      <div className="glass-card">
        <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#fff' }}>
          How to read these numbers
        </h3>
        <ul style={{
          color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.7,
          paddingLeft: '1.25rem', marginTop: '0.6rem',
        }}>
          <li><strong style={{ color: '#fff' }}>&ldquo;Tied&rdquo; does not mean equal.</strong> It
            means the paired test could not separate that model from the leader on this
            test set.</li>
          <li><strong style={{ color: '#fff' }}>Ties are the safer conclusion.</strong> Each
            task&apos;s leader is selected as the maximum on the same test set that then
            judges it, so leader-versus-challenger gaps carry a winner&apos;s curse and are
            biased upward. A reported separation may be optimistic; a reported tie is
            conservative.</li>
          <li><strong style={{ color: '#fff' }}>Intervals cover the test set only</strong>, not
            variance from the split itself.</li>
          <li><strong style={{ color: '#fff' }}>The MLP column is a diagnostic, never ranked.</strong> Ranking
            it would measure the MLP&apos;s capacity rather than the representation; the
            informative part is its gap to the linear probe.</li>
          <li><strong style={{ color: '#fff' }}>Values are internally comparable, not externally.</strong> The
            balanced scaffold split is easier than DeepChem&apos;s deterministic splitter,
            so these numbers sit above commonly cited figures for the same task names.
            That is the point: benchmark values do not transfer across protocols.</li>
        </ul>
      </div>
    </div>
  );
}
