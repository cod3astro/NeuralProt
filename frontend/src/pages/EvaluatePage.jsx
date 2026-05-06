import { useState, useRef } from 'react';
import { evaluateFmax } from '../services/api';

// ── File drop zone ─────────────────────────────────────────────────────────
function FileZone({ label, description, accept, file, onChange }) {
  const ref = useRef();
  return (
    <div style={fz.wrap}>
      <div style={fz.label}>{label}</div>
      <div
        style={{ ...fz.zone, borderColor: file ? 'var(--teal)' : 'var(--border-2)' }}
        onClick={() => ref.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) onChange(f); }}
      >
        {file ? (
          <div style={fz.content}>
            <span style={fz.filename}>{file.name}</span>
            <span style={fz.size}>{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div style={fz.content}>
            <span style={fz.icon}>📄</span>
            <span style={fz.hint}>Click or drag to upload</span>
          </div>
        )}
        <input ref={ref} type="file" accept={accept} style={{ display: 'none' }} onChange={(e) => onChange(e.target.files[0])} />
      </div>
      <div style={fz.desc}>{description}</div>
    </div>
  );
}
const fz = {
  wrap:     { display: 'flex', flexDirection: 'column', gap: '6px' },
  label:    { fontSize: '14px', fontWeight: '700', color: 'var(--text-2)', letterSpacing: '0.02em' },
  zone: {
    border: '2px dashed', borderRadius: 'var(--radius-md)', padding: '20px',
    textAlign: 'center', cursor: 'pointer', background: 'var(--surface-2)',
    transition: 'border-color 0.15s',
  },
  content: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' },
  icon:     { fontSize: '24px' },
  hint:     { fontSize: '15px', fontWeight: '500', color: 'var(--text-3)' },
  filename: { fontSize: '15px', fontWeight: '700', color: 'var(--teal-deep)', wordBreak: 'break-all' },
  size:     { fontSize: '13px', color: 'var(--text-3)' },
  desc:     { fontSize: '13px', color: 'var(--text-3)', lineHeight: '1.5' },
};

// ── Metric card ────────────────────────────────────────────────────────────
function MetricCard({ label, value, sub, color }) {
  return (
    <div style={mc.card}>
      <div style={mc.label}>{label}</div>
      <div style={{ ...mc.value, color: color || 'var(--text-1)' }}>{value}</div>
      {sub && <div style={mc.sub}>{sub}</div>}
    </div>
  );
}
const mc = {
  card:  { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '20px 22px', boxShadow: 'var(--shadow-sm)' },
  label: { fontSize: '14px', fontWeight: '600', color: 'var(--text-3)', marginBottom: '8px' },
  value: { fontSize: '28px', fontWeight: '700', fontFamily: 'var(--font-mono)', lineHeight: 1, marginBottom: '5px' },
  sub:   { fontSize: '13px', color: 'var(--text-3)' },
};

// ── Bar chart row ──────────────────────────────────────────────────────────
function ChartRow({ name, valA, valB, maxVal, labelA, labelB, colorA, colorB }) {
  return (
    <div style={ch.row}>
      <div style={ch.name}>{name.replace(/_/g, ' ')}</div>
      <div style={ch.bars}>
        <div style={ch.barWrap}>
          <div style={ch.track}>
            <div style={{ ...ch.bar, width: `${(valA / maxVal) * 100}%`, background: colorA }} />
          </div>
          <span style={{ ...ch.val, color: colorA }}>{valA.toFixed(3)}</span>
        </div>
        <div style={ch.barWrap}>
          <div style={ch.track}>
            <div style={{ ...ch.bar, width: `${(valB / maxVal) * 100}%`, background: colorB }} />
          </div>
          <span style={{ ...ch.val, color: 'var(--text-3)' }}>{valB.toFixed(3)}</span>
        </div>
      </div>
    </div>
  );
}
const ch = {
  row:    { display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '10px' },
  name:   { fontSize: '14px', fontWeight: '500', color: 'var(--text-2)', width: '180px', flexShrink: 0, wordBreak: 'break-word' },
  bars:   { flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' },
  barWrap:{ display: 'flex', alignItems: 'center', gap: '8px' },
  track:  { flex: 1, height: '9px', background: 'var(--surface-3)', borderRadius: '4px', overflow: 'hidden' },
  bar:    { height: '100%', borderRadius: '4px', transition: 'width 0.6s cubic-bezier(0.16,1,0.3,1)' },
  val:    { fontFamily: 'var(--font-mono)', fontSize: '14px', fontWeight: '700', minWidth: '44px', textAlign: 'right' },
};

// ── Per-group table ────────────────────────────────────────────────────────
function GroupTable({ groups }) {
  const sorted = Object.entries(groups)
    .sort((a, b) => b[1].NeuralProt.fmax - a[1].NeuralProt.fmax);

  return (
    <div style={gt.wrap}>
      <div style={gt.head}>
        <span>Group</span>
        <span>NP Fmax</span>
        <span>BL Fmax</span>
        <span>Gain</span>
        <span>NP Smin</span>
        <span>BL Smin</span>
        <span>Smin ↓</span>
        <span>Proteins</span>
      </div>
      {sorted.map(([group, r]) => {
        const gain     = r.fmax_gain_over_baseline;
        const sminImp  = r.smin_improvement;
        const beats    = gain > 0;
        return (
          <div key={group} style={gt.row}>
            <span style={gt.groupName}>{group.replace(/_/g, ' ')}</span>
            <span style={{ ...gt.fmax, color: beats ? 'var(--teal-deep)' : 'var(--text-1)', fontWeight: beats ? '700' : '500' }}>
              {r.NeuralProt.fmax.toFixed(3)}
            </span>
            <span style={gt.cell}>{r.baseline.fmax.toFixed(3)}</span>
            <span style={{ ...gt.gain, color: beats ? 'var(--teal-deep)' : '#9B1C1C', background: beats ? '#E1F5EE' : '#FEF2F2' }}>
              {gain >= 0 ? '+' : ''}{gain.toFixed(3)}
            </span>
            <span style={gt.cell}>{r.NeuralProt.smin.toFixed(3)}</span>
            <span style={gt.cell}>{r.baseline.smin.toFixed(3)}</span>
            <span style={{ ...gt.gain, color: sminImp > 0 ? 'var(--teal-deep)' : '#9B1C1C', background: sminImp > 0 ? '#E1F5EE' : '#FEF2F2' }}>
              {sminImp >= 0 ? '+' : ''}{sminImp.toFixed(3)}
            </span>
            <span style={gt.cell}>{r.n_test_proteins}</span>
          </div>
        );
      })}
    </div>
  );
}
const gt = {
  wrap: { border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', overflow: 'hidden' },
  head: {
    display: 'grid', gridTemplateColumns: '1fr 80px 80px 70px 80px 80px 70px 70px',
    gap: '8px', padding: '10px 16px', background: 'var(--surface-2)',
    fontSize: '12px', fontWeight: '700', color: 'var(--text-3)',
    letterSpacing: '0.05em', textTransform: 'uppercase', borderBottom: '1px solid var(--border)',
  },
  row: {
    display: 'grid', gridTemplateColumns: '1fr 80px 80px 70px 80px 80px 70px 70px',
    gap: '8px', padding: '11px 16px', borderBottom: '1px solid var(--border)',
    alignItems: 'center', fontSize: '14px',
  },
  groupName: { fontSize: '14px', fontWeight: '500', color: 'var(--text-1)', wordBreak: 'break-word' },
  fmax:      { fontFamily: 'var(--font-mono)', fontSize: '14px', textAlign: 'right' },
  cell:      { fontFamily: 'var(--font-mono)', fontSize: '14px', color: 'var(--text-2)', textAlign: 'right' },
  gain:      { fontFamily: 'var(--font-mono)', fontSize: '13px', fontWeight: '700', padding: '2px 6px', borderRadius: '5px', textAlign: 'center' },
};

// ── Main page ──────────────────────────────────────────────────────────────
export default function EvaluatePage() {
  const [fastaFile,  setFastaFile]  = useState(null);
  const [testTsv,    setTestTsv]    = useState(null);
  const [trainTsv,   setTrainTsv]   = useState(null);
  const [propagate,  setPropagate]  = useState(true);
  const [status,     setStatus]     = useState('idle');
  const [results,    setResults]    = useState(null);
  const [error,      setError]      = useState('');

  const canRun = fastaFile && testTsv && trainTsv && status !== 'loading';

  async function handleEvaluate() {
    if (!canRun) return;
    setError(''); setStatus('loading'); setResults(null);
    try {
      const res = await evaluateFmax(fastaFile, testTsv, trainTsv, propagate);
      console.log('Evaluate response:', JSON.stringify(res, null, 2));
      setResults(res);
      setStatus('done');
    } catch (e) {
      setError(e.message || 'Evaluation failed.');
      setStatus('error');
    }
  }

  function downloadResults() {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'neuralprot_evaluation.json'; a.click();
    URL.revokeObjectURL(url);
  }

  // Derived chart data
const groupEntries = results
  ? Object.entries(results.group_results || {}).filter(
      ([, r]) => r?.NeuralProt?.fmax !== undefined && r?.baseline?.fmax !== undefined
    )
  : [];

const fmaxSorted = [...groupEntries].sort(
  (a, b) => (b[1].NeuralProt.fmax ?? 0) - (a[1].NeuralProt.fmax ?? 0)
);
const sminSorted = [...groupEntries].sort(
  (a, b) => (a[1].NeuralProt.smin ?? 0) - (b[1].NeuralProt.smin ?? 0)
);
const maxFmax = groupEntries.length > 0
  ? Math.max(...groupEntries.map(([, r]) => Math.max(r.NeuralProt.fmax ?? 0, r.baseline.fmax ?? 0)), 0.01)
  : 1;
const maxSmin = groupEntries.length > 0
  ? Math.max(...groupEntries.map(([, r]) => Math.max(r.NeuralProt.smin ?? 0, r.baseline.smin ?? 0)), 0.01)
  : 1;

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.h1}>Evaluate on your dataset</h1>
        <p style={styles.sub}>
          Upload a labelled protein dataset to benchmark NeuralProt using Fmax and Smin.
          The CAFA protein-centric standard metrics. Results include a frequency baseline
          comparison for every group.
        </p>
      </div>

      {/* Methodology notice */}
      <div style={styles.notice}>
        <span style={styles.noticeIcon}>ℹ</span>
        <span style={styles.noticeText}>
          Evaluation follows the CAFA protein-centric standard. Fmax is the maximum F1 across
          all thresholds, computed by averaging precision and recall across proteins, not terms.
          Smin is the minimum semantic distance, weighted by GO term information content. Both
          metrics are threshold-independent and directly comparable across methods. The frequency
          baseline predicts training-set annotation frequency for every protein regardless of
          sequence, it establishes the floor NeuralProt must beat.
        </span>
      </div>

      {/* Upload card */}
      <div style={styles.card}>
        <div style={styles.cardLabel}>Upload your dataset</div>
        <div style={styles.fileGrid}>
          <FileZone
            label="Test sequences (.fasta)"
            description="FASTA file of protein sequences to evaluate. Accession IDs must match the TSV."
            accept=".fasta,.fa"
            file={fastaFile}
            onChange={setFastaFile}
          />
          <FileZone
            label="Test annotations (.tsv)"
            description="UniProtKB-style TSV with a 'Gene Ontology IDs' column containing semicolon-separated GO term IDs."
            accept=".tsv,.txt"
            file={testTsv}
            onChange={setTestTsv}
          />
          <FileZone
            label="Training annotations (.tsv)"
            description="TSV of the training set annotations used to compute the frequency baseline and GO term information content for Smin."
            accept=".tsv,.txt"
            file={trainTsv}
            onChange={setTrainTsv}
          />
        </div>

        <div style={styles.uploadFooter}>
          <label style={styles.toggleWrap}>
            <input
              type="checkbox"
              checked={propagate}
              onChange={(e) => setPropagate(e.target.checked)}
              style={styles.checkbox}
            />
            <span style={styles.toggleLabel}>
              Apply annotation propagation (True Path Rule)
            </span>
          </label>
          <button
            onClick={handleEvaluate}
            disabled={!canRun}
            style={{ ...styles.runBtn, opacity: canRun ? 1 : 0.5 }}
          >
            {status === 'loading' ? 'Evaluating…' : 'Run evaluation →'}
          </button>
        </div>
        {error && <div style={styles.errorMsg}>{error}</div>}
      </div>

      {/* Loading */}
      {status === 'loading' && (
        <div style={styles.loadingCard}>
          <div style={styles.spinner} />
          <span style={styles.loadingText}>
            Running NeuralProt across all 22 groups and computing baseline…
          </span>
        </div>
      )}

      {/* Results */}
      {status === 'done' && results && (
        <>
          {groupEntries.length === 0 ? (
            <div style={styles.card}>
              <div style={styles.emptyMsg}>
                No groups were evaluated. This usually means no protein IDs in the FASTA
                matched the TSV. Check that both files use the same UniProt accession format.
              </div>
            </div>
          ) : (
            <>
              {/* Part A — Overall metrics */}
              <div style={styles.metricsGrid}>
                <MetricCard label="Overall Fmax"          value={results.overall_macro_fmax?.toFixed(4) ?? '—'} color="var(--teal-deep)" sub="CAFA protein-centric" />
                <MetricCard label="Overall Smin"          value={results.overall_macro_smin?.toFixed(4) ?? '—'} color="var(--amber)"     sub="lower is better" />
                <MetricCard label="Groups beating baseline" value={`${results.n_groups_beating_baseline} / ${results.n_groups_evaluated}`} color="var(--teal-deep)" sub="by Fmax" />
                <MetricCard label="Groups evaluated"      value={results.n_groups_evaluated} sub={`of 22 total`} />
              </div>

              {/* Part B — Fmax chart */}
              <div style={styles.card}>
                <div style={styles.sectionTitle}>Fmax — NeuralProt vs frequency baseline</div>
                <div style={styles.chartNote}>Higher is better</div>
                <div style={styles.legend}>
                  <span style={{ ...styles.dot, background: 'var(--teal)' }} /> NeuralProt
                  <span style={{ ...styles.dot, background: 'var(--surface-3)', border: '1px solid var(--border-2)', marginLeft: '16px' }} /> Frequency baseline
                </div>
                {fmaxSorted.map(([group, r]) => (
                  <ChartRow
                    key={group}
                    name={group}
                    valA={r.NeuralProt.fmax}
                    valB={r.baseline.fmax}
                    maxVal={maxFmax}
                    colorA="var(--teal)"
                    colorB="var(--border-2)"
                  />
                ))}
              </div>

              {/* Part C — Smin chart */}
              <div style={styles.card}>
                <div style={styles.sectionTitle}>Smin — NeuralProt vs frequency baseline</div>
                <div style={styles.chartNote}>Lower is better — semantic distance from true annotations weighted by GO term information content</div>
                <div style={styles.legend}>
                  <span style={{ ...styles.dot, background: 'var(--teal)' }} /> NeuralProt
                  <span style={{ ...styles.dot, background: 'var(--border-2)', marginLeft: '16px' }} /> Frequency baseline
                </div>
                {sminSorted.map(([group, r]) => (
                  <ChartRow
                    key={group}
                    name={group}
                    valA={r.NeuralProt.smin}
                    valB={r.baseline.smin}
                    maxVal={maxSmin}
                    colorA="var(--teal)"
                    colorB="var(--border-2)"
                  />
                ))}
              </div>

              {/* Part D — Full table */}
              <div style={styles.card}>
                <div style={styles.sectionTitle}>Per-group results</div>
                <div style={{ overflowX: 'auto' }}>
                  <GroupTable groups={results.group_results} />
                </div>
              </div>

              {/* Part E — Export */}
              <div style={styles.exportRow}>
                <button onClick={downloadResults} style={styles.exportBtn}>
                  Download results JSON
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

const styles = {
  page:    { maxWidth: '1000px', margin: '0 auto', padding: '0 24px 56px' },
  hero:    { textAlign: 'center', padding: '48px 0 28px' },
  h1:      { fontSize: '40px', fontWeight: '700', color: 'var(--text-1)', letterSpacing: '-0.03em', marginBottom: '12px' },
  sub:     { fontSize: '18px', fontWeight: '400', color: 'var(--text-2)', maxWidth: '520px', margin: '0 auto', lineHeight: '1.7' },
  notice: {
    display: 'flex', alignItems: 'flex-start', gap: '12px',
    background: '#FFFBEB', border: '1px solid #FDE68A',
    borderRadius: 'var(--radius-md)', padding: '14px 18px', marginBottom: '18px',
  },
  noticeIcon: { fontSize: '18px', color: '#92400E', flexShrink: 0, marginTop: '1px' },
  noticeText: { fontSize: '15px', fontWeight: '500', color: '#92400E', lineHeight: '1.6' },
  card: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)', padding: '24px 26px',
    marginBottom: '18px', boxShadow: 'var(--shadow-sm)',
  },
  cardLabel: {
    fontSize: '14px', fontWeight: '700', color: 'var(--text-3)',
    letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: '16px',
  },
  fileGrid:   { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '20px' },
  uploadFooter: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' },
  toggleWrap: { display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' },
  checkbox:   { width: '18px', height: '18px', accentColor: 'var(--teal)', cursor: 'pointer' },
  toggleLabel:{ fontSize: '15px', fontWeight: '500', color: 'var(--text-2)' },
  runBtn: {
    background: 'linear-gradient(135deg, #1D9E75, #0F6E56)', color: 'white',
    border: 'none', borderRadius: 'var(--radius-md)', padding: '12px 26px',
    fontSize: '16px', fontWeight: '600', cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(29,158,117,0.35)', whiteSpace: 'nowrap',
  },
  errorMsg: {
    marginTop: '12px', fontSize: '15px', fontWeight: '500', color: '#9B1C1C',
    background: '#FEF2F2', border: '1px solid #FCA5A5',
    borderRadius: 'var(--radius-md)', padding: '10px 14px',
  },
  loadingCard: {
    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px',
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)', padding: '40px', marginBottom: '20px',
    boxShadow: 'var(--shadow-sm)',
  },
  spinner: {
    width: '26px', height: '26px', borderRadius: '50%',
    border: '3px solid var(--border)', borderTopColor: 'var(--teal)',
    animation: 'spin 0.8s linear infinite',
  },
  loadingText: { fontSize: '17px', fontWeight: '500', color: 'var(--text-2)' },
  metricsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '18px' },
  sectionTitle:{ fontSize: '20px', fontWeight: '700', color: 'var(--text-1)', marginBottom: '6px' },
  chartNote:   { fontSize: '14px', fontWeight: '500', color: 'var(--text-3)', marginBottom: '14px' },
  legend:      { display: 'flex', alignItems: 'center', fontSize: '14px', fontWeight: '600', color: 'var(--text-2)', marginBottom: '16px' },
  dot:         { display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', marginRight: '6px' },
  emptyMsg:    { fontSize: '16px', color: 'var(--text-3)', lineHeight: '1.7', textAlign: 'center', padding: '16px' },
  exportRow:   { display: 'flex', justifyContent: 'center', marginTop: '4px' },
  exportBtn: {
    fontSize: '16px', fontWeight: '600', color: 'var(--blue)',
    background: 'var(--blue-dim)', border: '1px solid #BFDBFE',
    borderRadius: 'var(--radius-md)', padding: '12px 28px', cursor: 'pointer',
  },
};