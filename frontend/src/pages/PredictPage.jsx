import { useState, useRef } from 'react';
import { predictSequence, predictFasta, EXAMPLE_SEQUENCES } from '../services/api';
import SequenceScanAnimation from '../components/SequenceScanAnimation';
import MetricsGrid           from '../components/MetricsGrid';
import GroupBars             from '../components/GroupBars';
import ResultsTable          from '../components/ResultsTable';

const CLEAN_REGEX = /[^ACDEFGHIKLMNPQRSTVWY]/gi;

// ── Batch results component ───────────────────────────────────────────────────

function BatchResults({ data }) {
  const [open, setOpen] = useState(null);

  const total = Object.values(data.results).reduce(
    (sum, r) => sum + r.n_predictions, 0
  );
  const withPreds = Object.values(data.results).filter(
    (r) => r.n_predictions > 0
  ).length;

  return (
    <div>
      {/* Summary card */}
      <div style={bStyles.summaryGrid}>
        {[
          { label: 'Sequences processed', value: data.n_sequences },
          { label: 'With predictions',    value: withPreds },
          { label: 'Total GO terms',      value: total },
          { label: 'Failed',              value: data.n_failed },
        ].map(({ label, value }) => (
          <div key={label} style={bStyles.summaryCard}>
            <div style={bStyles.summaryVal}>{value}</div>
            <div style={bStyles.summaryLabel}>{label}</div>
          </div>
        ))}
      </div>

      {/* Per-sequence rows */}
      <div style={bStyles.seqList}>
        {Object.entries(data.results).map(([pid, res]) => (
          <div key={pid} style={bStyles.seqItem}>
            <button
              style={bStyles.seqHeader}
              onClick={() => setOpen(open === pid ? null : pid)}
            >
              <span style={bStyles.seqId}>{pid}</span>
              <span style={bStyles.seqCount}>
                {res.n_predictions} GO term{res.n_predictions !== 1 ? 's' : ''}
              </span>
              <span style={bStyles.seqChevron}>
                {open === pid ? '▲' : '▼'}
              </span>
            </button>

            {open === pid && res.predictions.length > 0 && (
              <div style={bStyles.seqBody}>
                <ResultsTable predictions={res.predictions} />
              </div>
            )}
            {open === pid && res.predictions.length === 0 && (
              <div style={bStyles.seqEmpty}>
                No GO terms predicted above any group's threshold.
              </div>
            )}
          </div>
        ))}

        {Object.entries(data.errors).map(([pid, msg]) => (
          <div key={pid} style={{ ...bStyles.seqItem, ...bStyles.seqError }}>
            <span style={bStyles.seqId}>{pid}</span>
            <span style={bStyles.seqErrMsg}>{msg}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PredictPage() {
  const [mode,     setMode]     = useState('single');   // 'single' | 'batch'

  // Single sequence state
  const [sequence, setSequence] = useState('');
  const [status,   setStatus]   = useState('idle');
  const [progress, setProgress] = useState(0);
  const [result,   setResult]   = useState(null);
  const [error,    setError]    = useState('');

  // Batch FASTA state
  const [fastaFile,    setFastaFile]    = useState(null);
  const [fastaName,    setFastaName]    = useState('');
  const [fastaSeqCount, setFastaSeqCount] = useState(0);
  const [batchStatus,  setBatchStatus]  = useState('idle');
  const [batchResult,  setBatchResult]  = useState(null);
  const [batchError,   setBatchError]   = useState('');
  const fileRef = useRef();

  const cleanLen = sequence.replace(CLEAN_REGEX, '').length;

  // ── Single sequence ─────────────────────────────────────────────────────────

  function loadExample(name) {
    setSequence(EXAMPLE_SEQUENCES[name].sequence);
    setStatus('idle');
    setResult(null);
    setError('');
  }

  async function handlePredict() {
    const clean = sequence.replace(CLEAN_REGEX, '');
    if (clean.length < 10) {
      setError('Sequence is too short — minimum 10 amino acids.');
      return;
    }
    setError('');
    setStatus('loading');
    setProgress(0);
    setResult(null);

    let simulated = 0;
    const timer = setInterval(() => {
      simulated += 1;
      if (simulated <= 21) setProgress(simulated);
    }, 200);

    try {
      const res = await predictSequence(clean);
      clearInterval(timer);
      setProgress(22);
      setResult(res);
      setStatus('done');
    } catch (e) {
      clearInterval(timer);
      setError(e.message || 'Prediction failed. Is the backend running?');
      setStatus('error');
    }
  }

  // ── Batch FASTA ─────────────────────────────────────────────────────────────

  function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setFastaFile(file);
    setFastaName(file.name);
    setBatchResult(null);
    setBatchError('');

    // Count sequences by counting > lines
    const reader = new FileReader();
    reader.onload = (ev) => {
      const count = (ev.target.result.match(/^>/gm) || []).length;
      setFastaSeqCount(count);
    };
    reader.readAsText(file);
  }

  async function handleBatchPredict() {
    if (!fastaFile) return;
    setBatchError('');
    setBatchStatus('loading');
    setBatchResult(null);
    try {
      const res = await predictFasta(fastaFile);
      setBatchResult(res);
      setBatchStatus('done');
    } catch (e) {
      setBatchError(e.message || 'Batch prediction failed. Is the backend running?');
      setBatchStatus('error');
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.h1}>Protein Function Prediction</h1>
        <p style={styles.sub}>
          Predict Gene Ontology terms using 22 biologically-grouped neural
          networks trained on Swiss-Prot.
        </p>
      </div>

      {/* Mode toggle */}
      <div style={styles.modeToggle}>
        <button
          style={{ ...styles.modeBtn, ...(mode === 'single' ? styles.modeBtnActive : {}) }}
          onClick={() => setMode('single')}
        >
          Single sequence
        </button>
        <button
          style={{ ...styles.modeBtn, ...(mode === 'batch' ? styles.modeBtnActive : {}) }}
          onClick={() => setMode('batch')}
        >
          Batch FASTA
        </button>
      </div>

      {/* ── SINGLE MODE ── */}
      {mode === 'single' && (
        <>
          <div style={styles.card}>
            <div style={styles.cardLabel}>Amino acid sequence — FASTA or raw</div>
            <textarea
              style={styles.textarea}
              value={sequence}
              onChange={(e) => setSequence(e.target.value)}
              placeholder="Paste your protein sequence here, e.g. MKTAYIAKQRQISFVK..."
              spellCheck={false}
            />
            <div style={styles.cardFooter}>
              <div>
                <div style={styles.exLabel}>Try an example</div>
                <div style={styles.examples}>
                  {Object.keys(EXAMPLE_SEQUENCES).map((name) => (
                    <button key={name} onClick={() => loadExample(name)} style={styles.exBtn}>
                      {name}
                    </button>
                  ))}
                </div>
              </div>
              <div style={styles.rightControls}>
                {cleanLen > 0 && (
                  <span style={styles.seqStat}>{cleanLen} residues</span>
                )}
                <button
                  onClick={handlePredict}
                  disabled={status === 'loading' || cleanLen < 1}
                  style={{
                    ...styles.predictBtn,
                    opacity: status === 'loading' || cleanLen < 1 ? 0.6 : 1,
                  }}
                >
                  {status === 'loading' ? 'Predicting…' : 'Predict GO terms →'}
                </button>
              </div>
            </div>
            {error && <div style={styles.errorMsg}>{error}</div>}
          </div>

          {status === 'loading' && (
            <SequenceScanAnimation sequence={sequence} progress={progress} total={22} />
          )}

          {status === 'done' && result && (
            <>
              <MetricsGrid  result={result} />
              <GroupBars    result={result} />
              <ResultsTable predictions={result.predictions} />
            </>
          )}
        </>
      )}

      {/* ── BATCH MODE ── */}
      {mode === 'batch' && (
        <>
          <div style={styles.card}>
            <div style={styles.cardLabel}>FASTA file — one or more sequences</div>

            {/* Drop zone */}
            <div
              style={styles.dropZone}
              onClick={() => fileRef.current.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const file = e.dataTransfer.files[0];
                if (file) {
                  handleFileChange({ target: { files: [file] } });
                }
              }}
            >
              <input
                ref={fileRef}
                type="file"
                accept=".fasta,.fa,.faa,.txt"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              {fastaFile ? (
                <div style={styles.fileLoaded}>
                  <span style={styles.fileIcon}>📄</span>
                  <div>
                    <div style={styles.fileName}>{fastaName}</div>
                    <div style={styles.fileInfo}>
                      {fastaSeqCount} sequence{fastaSeqCount !== 1 ? 's' : ''} detected
                    </div>
                  </div>
                </div>
              ) : (
                <div style={styles.dropPrompt}>
                  <span style={styles.dropIcon}>⬆</span>
                  <div style={styles.dropText}>
                    Drop a FASTA file here or click to browse
                  </div>
                  <div style={styles.dropSub}>.fasta · .fa · .faa · .txt</div>
                </div>
              )}
            </div>

            <div style={styles.cardFooter}>
              <span style={styles.batchNote}>
                All sequences are processed in a single request.
                Results are expandable per sequence.
              </span>
              <button
                onClick={handleBatchPredict}
                disabled={!fastaFile || batchStatus === 'loading'}
                style={{
                  ...styles.predictBtn,
                  opacity: !fastaFile || batchStatus === 'loading' ? 0.6 : 1,
                }}
              >
                {batchStatus === 'loading'
                  ? `Processing ${fastaSeqCount} sequences…`
                  : 'Predict all →'}
              </button>
            </div>

            {batchError && <div style={styles.errorMsg}>{batchError}</div>}
          </div>

          {batchStatus === 'loading' && (
            <div style={styles.batchLoading}>
              <div style={styles.batchSpinner} />
              <span style={styles.batchLoadingText}>
                Processing {fastaSeqCount} sequences through 22 models…
              </span>
            </div>
          )}

          {batchStatus === 'done' && batchResult && (
            <BatchResults data={batchResult} />
          )}
        </>
      )}
    </div>
  );
}

// ── Batch sub-styles ──────────────────────────────────────────────────────────

const bStyles = {
  summaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
    marginBottom: '16px',
  },
  summaryCard: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 20px',
    boxShadow: 'var(--shadow-sm)',
  },
  summaryVal: {
    fontSize: '28px',
    fontWeight: '700',
    color: 'var(--text-1)',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '-0.02em',
    marginBottom: '4px',
  },
  summaryLabel: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
  },
  seqList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  seqItem: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-sm)',
  },
  seqHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    width: '100%',
    padding: '14px 18px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left',
  },
  seqId: {
    fontFamily: 'var(--font-mono)',
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    flex: 1,
  },
  seqCount: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  seqChevron: {
    fontSize: '12px',
    color: 'var(--text-3)',
  },
  seqBody: {
    borderTop: '1px solid var(--border)',
  },
  seqEmpty: {
    padding: '14px 18px',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    borderTop: '1px solid var(--border)',
  },
  seqError: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    padding: '14px 18px',
    background: '#FEF2F2',
    borderColor: '#FCA5A5',
  },
  seqErrMsg: {
    fontSize: '14px',
    fontWeight: '500',
    color: '#9B1C1C',
  },
};

// ── Page styles ───────────────────────────────────────────────────────────────

const styles = {
  page: {
    maxWidth: '1000px',
    margin: '0 auto',
    padding: '0 24px 56px',
  },
  hero: {
    textAlign: 'center',
    padding: '48px 0 28px',
  },
  h1: {
    fontSize: '40px',
    fontWeight: '700',
    color: 'var(--text-1)',
    letterSpacing: '-0.03em',
    marginBottom: '12px',
  },
  sub: {
    fontSize: '18px',
    fontWeight: '400',
    color: 'var(--text-2)',
    maxWidth: '520px',
    margin: '0 auto',
    lineHeight: '1.7',
  },
  modeToggle: {
    display: 'flex',
    gap: '4px',
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '4px',
    marginBottom: '18px',
    width: 'fit-content',
  },
  modeBtn: {
    fontSize: '15px',
    fontWeight: '500',
    padding: '8px 20px',
    borderRadius: 'calc(var(--radius-md) - 2px)',
    border: 'none',
    background: 'none',
    color: 'var(--text-2)',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  modeBtnActive: {
    background: 'var(--surface)',
    color: 'var(--text-1)',
    fontWeight: '600',
    boxShadow: 'var(--shadow-sm)',
    border: '1px solid var(--border)',
  },
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '22px',
    marginBottom: '18px',
    boxShadow: 'var(--shadow-sm)',
  },
  cardLabel: {
    fontSize: '14px',
    fontWeight: '700',
    color: 'var(--text-3)',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    marginBottom: '10px',
  },
  textarea: {
    width: '100%',
    height: '100px',
    fontFamily: 'var(--font-mono)',
    fontSize: '14px',
    fontWeight: '500',
    lineHeight: '1.8',
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '12px 14px',
    color: 'var(--text-1)',
    resize: 'none',
    outline: 'none',
    wordBreak: 'break-all',
  },
  dropZone: {
    border: '2px dashed var(--border)',
    borderRadius: 'var(--radius-md)',
    background: 'var(--surface-2)',
    padding: '32px',
    textAlign: 'center',
    cursor: 'pointer',
    transition: 'border-color 0.15s',
    marginBottom: '14px',
  },
  fileLoaded: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
  },
  fileIcon: {
    fontSize: '32px',
  },
  fileName: {
    fontSize: '16px',
    fontWeight: '600',
    color: 'var(--text-1)',
    fontFamily: 'var(--font-mono)',
  },
  fileInfo: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    marginTop: '4px',
  },
  dropPrompt: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
  },
  dropIcon: {
    fontSize: '28px',
    color: 'var(--text-3)',
  },
  dropText: {
    fontSize: '16px',
    fontWeight: '500',
    color: 'var(--text-2)',
  },
  dropSub: {
    fontSize: '13px',
    fontWeight: '400',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  cardFooter: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: '14px',
    gap: '16px',
  },
  exLabel: {
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--text-3)',
    marginBottom: '8px',
    letterSpacing: '0.02em',
  },
  examples: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap',
  },
  exBtn: {
    fontSize: '14px',
    fontWeight: '500',
    padding: '6px 14px',
    borderRadius: '20px',
    border: '1px solid var(--border)',
    background: 'var(--surface-2)',
    color: 'var(--text-2)',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  rightControls: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    flexShrink: 0,
  },
  seqStat: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  batchNote: {
    fontSize: '14px',
    fontWeight: '400',
    color: 'var(--text-3)',
    lineHeight: '1.5',
    maxWidth: '380px',
  },
  predictBtn: {
    background: 'linear-gradient(135deg, #1D9E75, #0F6E56)',
    color: 'white',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    padding: '12px 26px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(29,158,117,0.35)',
    transition: 'opacity 0.15s',
    whiteSpace: 'nowrap',
    flexShrink: 0,
  },
  errorMsg: {
    marginTop: '12px',
    fontSize: '15px',
    fontWeight: '500',
    color: '#9B1C1C',
    background: '#FEF2F2',
    border: '1px solid #FCA5A5',
    borderRadius: 'var(--radius-md)',
    padding: '10px 14px',
  },
  batchLoading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '40px',
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    marginBottom: '18px',
  },
  batchSpinner: {
    width: '24px',
    height: '24px',
    border: '3px solid var(--border)',
    borderTopColor: 'var(--teal)',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  batchLoadingText: {
    fontSize: '16px',
    fontWeight: '500',
    color: 'var(--text-2)',
  },
};