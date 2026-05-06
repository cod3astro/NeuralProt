export default function GroupBars({ result }) {
  const { group_confidences, namespace_counts, total_predictions } = result;
  const maxConf = Math.max(...group_confidences.map((g) => g.max_confidence));

  return (
    <div style={styles.grid}>
      {/* Left — confidence by group */}
      <div style={styles.card}>
        <div style={styles.title}>Confidence by model group</div>
        {group_confidences.map(({ group, max_confidence, n_terms }) => (
          <div key={group} style={styles.row}>
            <div style={styles.groupLabel} title={group}>
              {group.replace(/_/g, ' ')}
            </div>
            <div style={styles.barTrack}>
              <div
                style={{
                  ...styles.bar,
                  width: `${(max_confidence / maxConf) * 100}%`,
                }}
              />
            </div>
            <div style={styles.rowRight}>
              <span style={styles.confVal}>{max_confidence.toFixed(4)}</span>
              <span style={styles.termCount}>{n_terms}t</span>
            </div>
          </div>
        ))}
      </div>

      {/* Right — namespace breakdown */}
      <div style={styles.card}>
        <div style={styles.title}>Terms by namespace</div>
        {[
          { key: 'BP', label: 'Biological Process', color: '#1D9E75', bg: '#E1F5EE' },
          { key: 'MF', label: 'Molecular Function',  color: '#185FA5', bg: '#E6F1FB' },
          { key: 'CC', label: 'Cellular Component',  color: '#854F0B', bg: '#FAEEDA' },
        ].map(({ key, label, color, bg }) => {
          const count = namespace_counts[key] || 0;
          const pct   = total_predictions > 0 ? (count / total_predictions) * 100 : 0;
          return (
            <div key={key} style={styles.row}>
              <div style={styles.groupLabel}>{label}</div>
              <div style={styles.barTrack}>
                <div style={{ ...styles.bar, width: `${pct}%`, background: color }} />
              </div>
              <div style={styles.rowRight}>
                <span style={{ fontSize: '14px', fontWeight: '700', color, background: bg, padding: '3px 10px', borderRadius: '12px' }}>
                  {count}
                </span>
              </div>
            </div>
          );
        })}

        <div style={styles.nsSummary}>
          {[
            { key: 'BP', color: '#1D9E75' },
            { key: 'MF', color: '#185FA5' },
            { key: 'CC', color: '#854F0B' },
          ].map(({ key, color }) => (
            <div key={key} style={styles.nsChip}>
              <div style={{ ...styles.nsDot, background: color }} />
              <span style={styles.nsKey}>{key}</span>
              <span style={styles.nsCount}>{namespace_counts[key] || 0}</span>
            </div>
          ))}
          <span style={styles.nsTotal}>/ {total_predictions} total</span>
        </div>
      </div>
    </div>
  );
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    marginBottom: '16px',
  },
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 22px',
    boxShadow: 'var(--shadow-sm)',
  },
  title: {
    fontSize: '14px',
    fontWeight: '700',
    color: 'var(--text-2)',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    marginBottom: '16px',
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '12px',
  },
  groupLabel: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-2)',
    width: '150px',
    flexShrink: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  barTrack: {
    flex: 1,
    background: 'var(--surface-3)',
    borderRadius: '3px',
    height: '7px',
    overflow: 'hidden',
  },
  bar: {
    height: '100%',
    background: 'var(--teal)',
    borderRadius: '3px',
    transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
  },
  rowRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    minWidth: '90px',
    justifyContent: 'flex-end',
  },
  confVal: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-2)',
    fontFamily: 'var(--font-mono)',
  },
  termCount: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  nsSummary: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
    marginTop: '18px',
    paddingTop: '14px',
    borderTop: '1px solid var(--border)',
  },
  nsChip: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  nsDot: {
    width: '9px',
    height: '9px',
    borderRadius: '50%',
  },
  nsKey: {
    fontSize: '14px',
    fontWeight: '700',
    color: 'var(--text-2)',
  },
  nsCount: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
  },
  nsTotal: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    marginLeft: 'auto',
  },
};