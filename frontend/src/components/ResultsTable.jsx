import { useState } from 'react';
import { uniprotTermUrl } from '../services/api';

const NS_ABBREV = {
  biological_process: 'BP',
  molecular_function: 'MF',
  cellular_component: 'CC',
};

const NS_STYLE = {
  BP: { background: '#E1F5EE', color: '#0F6E56' },
  MF: { background: '#E6F1FB', color: '#185FA5' },
  CC: { background: '#FAEEDA', color: '#854F0B' },
};

function exportJSON(predictions) {
  const blob = new Blob([JSON.stringify(predictions, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'neuralprot_predictions.json'; a.click();
  URL.revokeObjectURL(url);
}

function exportCSV(predictions) {
  const header = 'go_term,name,group,confidence,threshold,margin,namespace\n';
  const rows   = predictions.map((p) => {
    const margin = (p.confidence - p.threshold).toFixed(4);
    return `${p.go_term},"${p.name}",${p.group},${p.confidence},${p.threshold},${margin},${p.namespace}`;
  });
  const blob = new Blob([header + rows.join('\n')], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'neuralprot_predictions.csv'; a.click();
  URL.revokeObjectURL(url);
}

function MarginBadge({ confidence, threshold }) {
  const margin = confidence - threshold;
  const pct    = Math.min((margin / (1 - threshold)) * 100, 100);
  const color  = margin >= 0.15 ? '#0F6E56'
               : margin >= 0.07 ? '#854F0B'
               : '#9B1C1C';
  const bg     = margin >= 0.15 ? '#E1F5EE'
               : margin >= 0.07 ? '#FAEEDA'
               : '#FEF2F2';
  return (
    <div style={styles.marginWrap} title={`Threshold: ${threshold.toFixed(2)} · Margin: +${margin.toFixed(4)}`}>
      <div style={styles.marginTrack}>
        <div style={{ ...styles.marginBar, width: `${pct}%`, background: color }} />
      </div>
      <span style={{ ...styles.marginNum, color, background: bg }}>
        +{margin.toFixed(3)}
      </span>
    </div>
  );
}

export default function ResultsTable({ predictions }) {
  const [filter,  setFilter]  = useState('All');
  const [showAll, setShowAll] = useState(false);

  const filtered = filter === 'All'
    ? predictions
    : predictions.filter((p) => p.namespace === filter);

  const visible = showAll ? filtered : filtered.slice(0, 10);

  return (
    <div style={styles.card}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerTitle}>
          {filtered.length} prediction{filtered.length !== 1 ? 's' : ''}
          {filter !== 'All' ? ` · ${filter}` : ''}
        </span>
        <div style={styles.headerRight}>
          <div style={styles.pills}>
            {['All', 'BP', 'MF', 'CC'].map((ns) => (
              <button
                key={ns}
                onClick={() => { setFilter(ns); setShowAll(false); }}
                style={{ ...styles.pill, ...(filter === ns ? styles.pillActive : {}) }}
              >
                {ns}
              </button>
            ))}
          </div>
          <button onClick={() => exportJSON(predictions)} style={styles.exportBtn}>JSON</button>
          <button onClick={() => exportCSV(predictions)}  style={styles.exportBtn}>CSV</button>
        </div>
      </div>

      {/* Legend for margin */}
      <div style={styles.legend}>
        <span style={styles.legendTitle}>Threshold margin</span>
        <span style={{ ...styles.legendChip, color: '#0F6E56', background: '#E1F5EE' }}>≥ +0.15 solid</span>
        <span style={{ ...styles.legendChip, color: '#854F0B', background: '#FAEEDA' }}>+0.07 moderate</span>
        <span style={{ ...styles.legendChip, color: '#9B1C1C', background: '#FEF2F2' }}>{'< +0.07 marginal'}</span>
        <span style={styles.legendNote}>How far above the tuned threshold each prediction sits</span>
      </div>

    <div className="results-table-scroll">
      {/* Column headers */}
      <div style={styles.colHead}>
        <span>GO term</span>
        <span>Name</span>
        <span>Group</span>
        <span>Confidence</span>
        <span>Margin</span>
        <span>NS</span>
        <span></span>
      </div>


      {/* Rows */}
      {visible.map((pred, i) => (
        <div key={pred.go_term} style={{ ...styles.row, opacity: i >= 8 ? 0.75 : 1 }}>
          <span style={styles.goId}>{pred.go_term}</span>
          <span style={styles.goName}>{pred.name}</span>
          <span style={styles.goGroup}>{pred.group.replace(/_/g, ' ')}</span>

          {/* Confidence */}
          <div style={styles.confWrap}>
            <div style={styles.confTrack}>
              <div style={{ ...styles.confBar, width: `${pred.confidence * 100}%` }} />
            </div>
            <span style={styles.confNum}>{pred.confidence.toFixed(4)}</span>
          </div>

          {/* Threshold margin */}
          <MarginBadge confidence={pred.confidence} threshold={pred.threshold} />

          <span style={{ ...styles.nsBadge, ...(NS_STYLE[NS_ABBREV[pred.namespace] || pred.namespace] || {}) }}>
            {NS_ABBREV[pred.namespace] || pred.namespace}
          </span>
          <a
            href={uniprotTermUrl(pred.go_term)}
            target="_blank"
            rel="noreferrer"
            style={styles.extLink}
            title="View on QuickGO"
          >
            ↗
          </a>
        </div>
      ))}
            </div>

      {/* Footer */}
      {filtered.length > 10 && (
        <div style={styles.footer}>
          <button onClick={() => setShowAll((s) => !s)} style={styles.showMoreBtn}>
            {showAll ? 'Show fewer' : `+ ${filtered.length - 10} more predictions`}
          </button>
        </div>
      )}
    </div>
  );
}

const styles = {
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-sm)',
    marginBottom: '20px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px 20px',
    borderBottom: '1px solid var(--border)',
    flexWrap: 'wrap',
    gap: '10px',
  },
  headerTitle: {
    fontSize: '17px',
    fontWeight: '600',
    color: 'var(--text-1)',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  pills: {
    display: 'flex',
    gap: '4px',
  },
  pill: {
    fontSize: '14px',
    fontWeight: '500',
    padding: '5px 13px',
    borderRadius: '20px',
    border: '1px solid var(--border)',
    background: 'none',
    color: 'var(--text-2)',
    cursor: 'pointer',
  },
  pillActive: {
    background: 'var(--teal-dim)',
    color: 'var(--teal-deep)',
    borderColor: 'var(--teal-light)',
    fontWeight: '700',
  },
  exportBtn: {
    fontSize: '14px',
    fontWeight: '500',
    padding: '6px 14px',
    borderRadius: 'var(--radius-sm)',
    border: '1px solid var(--border)',
    background: 'none',
    color: 'var(--text-2)',
    cursor: 'pointer',
  },
  legend: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 20px',
    background: 'var(--surface-2)',
    borderBottom: '1px solid var(--border)',
    flexWrap: 'wrap',
  },
  legendTitle: {
    fontSize: '13px',
    fontWeight: '700',
    color: 'var(--text-2)',
    marginRight: '4px',
  },
  legendChip: {
    fontSize: '12px',
    fontWeight: '600',
    padding: '2px 9px',
    borderRadius: '20px',
  },
  legendNote: {
    fontSize: '12px',
    fontWeight: '400',
    color: 'var(--text-3)',
    marginLeft: '4px',
    fontStyle: 'italic',
  },
  colHead: {
    display: 'grid',
    gridTemplateColumns: '110px 1fr 130px 130px 120px 46px 30px',
    gap: '10px',
    padding: '10px 20px',
    background: 'var(--surface-2)',
    fontSize: '13px',
    fontWeight: '700',
    color: 'var(--text-3)',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    borderBottom: '1px solid var(--border)',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '110px 1fr 130px 130px 120px 46px 30px',
    gap: '10px',
    alignItems: 'center',
    padding: '12px 20px',
    borderBottom: '1px solid var(--border)',
    transition: 'background 0.1s',
  },
  goId: {
    fontFamily: 'var(--font-mono)',
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--blue)',
  },
  goName: {
    color: 'var(--text-1)',
    fontWeight: '500',
    fontSize: '14px',
    lineHeight: '1.3',
    wordBreak: 'break-word',
  },
  goGroup: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
    wordBreak: 'break-word',
  },
  confWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
  },
  confTrack: {
    flex: 1,
    height: '5px',
    background: 'var(--surface-3)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  confBar: {
    height: '100%',
    background: 'linear-gradient(90deg, var(--teal), var(--teal-light))',
    borderRadius: '3px',
  },
  confNum: {
    fontFamily: 'var(--font-mono)',
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--text-2)',
    minWidth: '50px',
  },
  marginWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    cursor: 'help',
  },
  marginTrack: {
    flex: 1,
    height: '5px',
    background: 'var(--surface-3)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  marginBar: {
    height: '100%',
    borderRadius: '3px',
    transition: 'width 0.4s ease',
  },
  marginNum: {
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    fontWeight: '700',
    padding: '2px 6px',
    borderRadius: '5px',
    whiteSpace: 'nowrap',
  },
  nsBadge: {
    fontSize: '13px',
    fontWeight: '700',
    padding: '3px 8px',
    borderRadius: '5px',
    textAlign: 'center',
  },
  extLink: {
    fontSize: '16px',
    color: 'var(--text-3)',
    textDecoration: 'none',
    textAlign: 'center',
  },
  footer: {
    padding: '14px 20px',
    borderTop: '1px solid var(--border)',
    background: 'var(--surface-2)',
  },
  showMoreBtn: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
  },
};