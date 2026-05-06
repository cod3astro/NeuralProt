import { useState } from 'react';
import { predictSequence, EXAMPLE_SEQUENCES } from '../services/api';

const CLEAN_REGEX = /[^ACDEFGHIKLMNPQRSTVWY]/gi;

const NS_ABBREV = {
  biological_process: 'BP',
  molecular_function: 'MF',
  cellular_component: 'CC',
};
const NS_COLOR = {
  BP: '#2D6A4F',
  MF: '#1B4965',
  CC: '#8B5A2B',
};

export default function ComparePage() {
  const [seqA, setSeqA] = useState('');
  const [seqB, setSeqB] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [resultsA, setResultsA] = useState(null);
  const [resultsB, setResultsB] = useState(null);

  const cleanLenA = seqA.replace(CLEAN_REGEX, '').length;
  const cleanLenB = seqB.replace(CLEAN_REGEX, '').length;

  function loadExample(name, target) {
    const example = EXAMPLE_SEQUENCES[name].sequence;
    if (target === 'A') setSeqA(example);
    else setSeqB(example);
  }

  async function handleCompare() {
    const cleanA = seqA.replace(CLEAN_REGEX, '');
    const cleanB = seqB.replace(CLEAN_REGEX, '');
    if (cleanA.length < 10 || cleanB.length < 10) {
      setError('Both sequences must be at least 10 amino acids.');
      return;
    }
    setError('');
    setLoading(true);
    setResultsA(null);
    setResultsB(null);
    try {
      const [resA, resB] = await Promise.all([
        predictSequence(cleanA),
        predictSequence(cleanB),
      ]);
      setResultsA(resA);
      setResultsB(resB);
    } catch (e) {
      setError(e.message || 'Comparison failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }

  // Derived shared / unique lists
  const shared =
    resultsA && resultsB
      ? resultsA.predictions.filter((p) =>
          resultsB.predictions.some((q) => q.go_term === p.go_term)
        )
      : [];
  const uniqueA = resultsA
    ? resultsA.predictions.filter(
        (p) => !resultsB?.predictions.some((q) => q.go_term === p.go_term)
      )
    : [];
  const uniqueB = resultsB
    ? resultsB.predictions.filter(
        (p) => !resultsA?.predictions.some((q) => q.go_term === p.go_term)
      )
    : [];

  // Group confidence comparison – build lookup maps from the array structure
  const confMapA = {};
  const confMapB = {};
  if (resultsA) {
    resultsA.group_confidences.forEach((item) => {
      confMapA[item.group] = item.max_confidence;
    });
  }
  if (resultsB) {
    resultsB.group_confidences.forEach((item) => {
      confMapB[item.group] = item.max_confidence;
    });
  }
  const allGroups = new Set([...Object.keys(confMapA), ...Object.keys(confMapB)]);
  const groups = Array.from(allGroups).sort((a, b) => {
    const maxA = Math.max(confMapA[a] || 0, confMapB[a] || 0);
    const maxB = Math.max(confMapA[b] || 0, confMapB[b] || 0);
    return maxB - maxA;
  });

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.h1}>Compare two proteins</h1>
        <p style={styles.sub}>
          Predict GO terms for two sequences in parallel and see shared
          functions, unique terms, and group confidence side by side.
        </p>
      </div>

      {/* Input grid */}
      <div style={styles.inputGrid}>
        {/* Protein A */}
        <div style={styles.card}>
          <div style={styles.cardLabel}>Protein A</div>
          <textarea
            style={styles.textarea}
            value={seqA}
            onChange={(e) => setSeqA(e.target.value)}
            placeholder="Paste sequence for Protein A…"
            spellCheck={false}
          />
          <div style={styles.cardFooter}>
            <div style={styles.examples}>
              {Object.keys(EXAMPLE_SEQUENCES).map((name) => (
                <button
                  key={name + 'A'}
                  onClick={() => loadExample(name, 'A')}
                  style={styles.exBtn}
                >
                  {name}
                </button>
              ))}
            </div>
            {cleanLenA > 0 && (
              <span style={styles.seqStat}>{cleanLenA} residues</span>
            )}
          </div>
        </div>

        {/* Protein B */}
        <div style={styles.card}>
          <div style={styles.cardLabel}>Protein B</div>
          <textarea
            style={styles.textarea}
            value={seqB}
            onChange={(e) => setSeqB(e.target.value)}
            placeholder="Paste sequence for Protein B…"
            spellCheck={false}
          />
          <div style={styles.cardFooter}>
            <div style={styles.examples}>
              {Object.keys(EXAMPLE_SEQUENCES).map((name) => (
                <button
                  key={name + 'B'}
                  onClick={() => loadExample(name, 'B')}
                  style={styles.exBtn}
                >
                  {name}
                </button>
              ))}
            </div>
            {cleanLenB > 0 && (
              <span style={styles.seqStat}>{cleanLenB} residues</span>
            )}
          </div>
        </div>
      </div>

      {/* Compare button */}
      <div style={styles.compareRow}>
        <button
          onClick={handleCompare}
          disabled={loading || cleanLenA < 10 || cleanLenB < 10}
          style={{
            ...styles.predictBtn,
            opacity:
              loading || cleanLenA < 10 || cleanLenB < 10 ? 0.6 : 1,
          }}
        >
          {loading ? 'Predicting…' : 'Compare →'}
        </button>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}

      {/* Loading state */}
      {loading && (
        <div style={styles.loadingCard}>
          <div style={styles.spinner} />
          <span>Running 22 models on both sequences…</span>
        </div>
      )}

      {/* Results */}
      {resultsA && resultsB && (
        <>
          {/* Part 1 – Metrics summary */}
          <div style={styles.metricsRow}>
            {[
              { label: 'Protein A', res: resultsA },
              { label: 'Protein B', res: resultsB },
            ].map(({ label, res }) => (
              <div key={label} style={styles.metricCard}>
                <div style={styles.metricTitle}>{label}</div>
                <div style={styles.metricGrid}>
                  {[
                    ['GO terms', res.total_predictions],
                    [
                      'Avg confidence',
                      res.predictions.length
                        ? (
                            res.predictions.reduce(
                              (s, p) => s + p.confidence,
                              0
                            ) / res.predictions.length
                          ).toFixed(2)
                        : '—',
                    ],
                    ['Groups activated', res.models_used],
                    [
                      'Top GO term',
                      res.predictions.length
                        ? res.predictions[0].go_term
                        : '—',
                    ],
                  ].map(([k, v]) => (
                    <div key={k} style={styles.metricItem}>
                      <div style={styles.metricVal}>{v}</div>
                      <div style={styles.metricLabel}>{k}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Part 2 – Shared GO terms */}
          {shared.length > 0 && (
            <div style={styles.card}>
              <div style={styles.sectionTitle}>
                Shared GO terms ({shared.length})
              </div>
              <div style={styles.table}>
                <div style={styles.tableHeader}>
                  <div style={styles.goCol}>GO term</div>
                  <div style={styles.nameCol}>Name</div>
                  <div style={styles.nsCol}>NS</div>
                  <div style={styles.confCol}>Conf. A</div>
                  <div style={styles.confCol}>Conf. B</div>
                  <div style={styles.indicatorCol}></div>
                </div>
                {shared
                  .sort((a, b) => {
                    const matchB_a = resultsB.predictions.find(
                      (q) => q.go_term === a.go_term
                    );
                    const matchB_b = resultsB.predictions.find(
                      (q) => q.go_term === b.go_term
                    );
                    const avgA =
                      (a.confidence + (matchB_a?.confidence || 0)) / 2;
                    const avgB =
                      (b.confidence + (matchB_b?.confidence || 0)) / 2;
                    return avgB - avgA;
                  })
                  .map((p) => {
                    const matchB = resultsB.predictions.find(
                      (q) => q.go_term === p.go_term
                    );
                    const confA = p.confidence;
                    const confB = matchB?.confidence || 0;
                    const higher =
                      confA > confB ? 'A' : confB > confA ? 'B' : null;
                    return (
                      <div key={p.go_term} style={styles.tableRow}>
                        <div style={styles.goCol}>{p.go_term}</div>
                        <div style={styles.nameCol}>
                          {p.go_name || p.name}
                        </div>
                        <div style={styles.nsCol}>
                          <span
                            style={{
                              ...styles.nsBadge,
                              background:
                                NS_COLOR[NS_ABBREV[p.namespace]] || '#999',
                            }}
                          >
                            {NS_ABBREV[p.namespace] || p.namespace}
                          </span>
                        </div>
                        <div style={styles.confCol}>{confA.toFixed(2)}</div>
                        <div style={styles.confCol}>{confB.toFixed(2)}</div>
                        <div style={styles.indicatorCol}>
                          {higher === 'A' && (
                            <span style={styles.arrowA}>▲</span>
                          )}
                          {higher === 'B' && (
                            <span style={styles.arrowB}>▼</span>
                          )}
                          {!higher && (
                            <span style={styles.equal}>—</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* Part 3 – Unique terms */}
          <div style={styles.uniqueGrid}>
            {[
              { title: 'Only in Protein A', data: uniqueA },
              { title: 'Only in Protein B', data: uniqueB },
            ].map(({ title, data }) => (
              <div key={title} style={styles.card}>
                <div style={styles.sectionTitle}>
                  {title} ({data.length})
                </div>
                <div style={styles.uniqueList}>
                  {data.map((p) => (
                    <div key={p.go_term} style={styles.uniqueItem}>
                      <span style={styles.uniqueTerm}>{p.go_term}</span>
                      <span
                        style={{
                          ...styles.nsBadge,
                          background:
                            NS_COLOR[NS_ABBREV[p.namespace]] || '#999',
                          marginLeft: 8,
                        }}
                      >
                        {NS_ABBREV[p.namespace] || p.namespace}
                      </span>
                      <span style={styles.uniqueConf}>
                        {(p.confidence * 100).toFixed(0)}%
                      </span>
                      <div style={styles.uniqueName}>
                        {p.go_name || p.name}
                      </div>
                    </div>
                  ))}
                  {data.length === 0 && (
                    <div style={styles.emptyText}>No unique terms</div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Part 4 – Group confidence comparison */}
          <div style={styles.card}>
            <div style={styles.sectionTitle}>
              Group confidence comparison
            </div>
            <div style={styles.groupChart}>
              {groups.map((group) => {
                const aVal = Number(confMapA[group] ?? 0);
                const bVal = Number(confMapB[group] ?? 0);
                return (
                  <div key={group} style={styles.groupRow}>
                    <div style={styles.groupLabel}>{group}</div>
                    <div style={styles.barContainer}>
                      <div style={styles.barTrack}>
                        <div
                          style={{
                            ...styles.barA,
                            width: `${(aVal / 1) * 100}%`,
                          }}
                        />
                      </div>
                      <span style={styles.barVal}>{aVal.toFixed(2)}</span>
                    </div>
                    <div style={styles.barContainer}>
                      <div style={styles.barTrack}>
                        <div
                          style={{
                            ...styles.barB,
                            width: `${(bVal / 1) * 100}%`,
                          }}
                        />
                      </div>
                      <span style={styles.barVal}>{bVal.toFixed(2)}</span>
                    </div>
                  </div>
                );
              })}
              {groups.length === 0 && (
                <div style={styles.emptyText}>No groups activated</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Styles (matching PredictPage design system) ─────────────
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
  inputGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginBottom: '8px',
  },
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '22px',
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
  cardFooter: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: '12px',
    gap: '12px',
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
  },
  seqStat: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  compareRow: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '18px',
  },
  predictBtn: {
    background: 'linear-gradient(135deg, #1D9E75, #0F6E56)',
    color: 'white',
    border: 'none',
    borderRadius: 'var(--radius-md)',
    padding: '14px 32px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(29,158,117,0.35)',
    transition: 'opacity 0.15s',
    whiteSpace: 'nowrap',
  },
  errorBox: {
    marginTop: '12px',
    fontSize: '15px',
    fontWeight: '500',
    color: '#9B1C1C',
    background: '#FEF2F2',
    border: '1px solid #FCA5A5',
    borderRadius: 'var(--radius-md)',
    padding: '10px 14px',
  },
  loadingCard: {
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
  spinner: {
    width: '24px',
    height: '24px',
    border: '3px solid var(--border)',
    borderTopColor: 'var(--teal)',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  metricsRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginBottom: '18px',
  },
  metricCard: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '22px',
    boxShadow: 'var(--shadow-sm)',
  },
  metricTitle: {
    fontSize: '18px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '16px',
  },
  metricGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  metricItem: {
    background: 'var(--surface-2)',
    borderRadius: 'var(--radius-sm)',
    padding: '12px',
  },
  metricVal: {
    fontSize: '18px',
    fontWeight: '700',
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-1)',
    marginBottom: '4px',
  },
  metricLabel: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
  },
  sectionTitle: {
    fontSize: '17px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '12px',
  },
  table: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  },
  tableHeader: {
    display: 'grid',
    gridTemplateColumns: '180px 1fr 60px 70px 70px 40px',
    background: 'var(--surface-2)',
    borderBottom: '1px solid var(--border)',
    padding: '12px 16px',
    fontSize: '14px',
    fontWeight: '700',
    color: 'var(--text-2)',
    gap: '8px',
  },
  tableRow: {
    display: 'grid',
    gridTemplateColumns: '180px 1fr 60px 70px 70px 40px',
    padding: '10px 16px',
    borderBottom: '1px solid var(--border)',
    gap: '8px',
    fontSize: '15px',
    alignItems: 'center',
  },
  goCol: {
    fontFamily: 'var(--font-mono)',
    fontWeight: '600',
    color: 'var(--blue)',
  },
  nameCol: {
    fontWeight: '500',
    color: 'var(--text-2)',
  },
  nsCol: {},
  confCol: {
    fontFamily: 'var(--font-mono)',
    fontWeight: '600',
    textAlign: 'center',
  },
  indicatorCol: {
    textAlign: 'center',
    fontWeight: '700',
  },
  arrowA: { color: 'var(--teal)' },
  arrowB: { color: 'var(--blue)' },
  equal: { color: 'var(--text-3)' },
  nsBadge: {
    display: 'inline-block',
    fontSize: '12px',
    fontWeight: '600',
    color: '#fff',
    padding: '2px 8px',
    borderRadius: '12px',
  },
  uniqueGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginBottom: '18px',
  },
  uniqueList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  uniqueItem: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-2)',
    padding: '8px 0',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: '6px',
  },
  uniqueTerm: {
    fontFamily: 'var(--font-mono)',
    fontWeight: '600',
    color: 'var(--blue)',
  },
  uniqueConf: {
    fontFamily: 'var(--font-mono)',
    fontSize: '13px',
    color: 'var(--text-3)',
    marginLeft: 'auto',
  },
  uniqueName: {
    width: '100%',
    fontSize: '13px',
    color: 'var(--text-3)',
    marginTop: '4px',
  },
  emptyText: {
    fontSize: '15px',
    fontWeight: '500',
    color: 'var(--text-3)',
    padding: '16px',
    textAlign: 'center',
  },
  groupChart: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  groupRow: {
    display: 'grid',
    gridTemplateColumns: '140px 1fr 1fr',
    alignItems: 'center',
    gap: '16px',
    padding: '6px 0',
  },
  groupLabel: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--text-2)',
  },
barContainer: {
  display: 'grid',
  gridTemplateColumns: '1fr 48px',
  alignItems: 'center',
  gap: '8px',
},
barTrack: {
  flex: 1,
  marginLeft: '60px' ,
  maxWidth: '250px',
  height: '20px',
  background: 'var(--surface-2)',
  borderRadius: 'var(--radius-sm)',
  overflow: 'hidden',
  border: '1px solid var(--border)',
},
 barVal: {
   fontSize: '14px',
   fontFamily: 'var(--font-mono)',
   fontWeight: '600',
   color: 'var(--text-2)',
   textAlign: 'right',
   flexShrink: 0,
 },
  barA: {
    height: '100%',
    background: 'var(--teal)',
    borderRadius: 'var(--radius-sm)',
    transition: 'width 0.4s',
  },
  barB: {
    height: '100%',
    background: 'var(--blue)',
    borderRadius: 'var(--radius-sm)',
    transition: 'width 0.4s',
  },
};