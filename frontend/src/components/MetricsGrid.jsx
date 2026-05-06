export default function MetricsGrid({ result }) {
  const { predictions, total_predictions, models_used, namespace_counts } = result;

  // Avg confidence across all predictions
  const avgConf = predictions.length > 0
    ? predictions.reduce((sum, p) => sum + p.confidence, 0) / predictions.length
    : 0;

  // Highest confidence prediction
  const topPred = predictions.length > 0
    ? predictions.reduce((best, p) => p.confidence > best.confidence ? p : best, predictions[0])
    : null;

  // Groups that fired (had at least one prediction)
  const groupsActivated = new Set(predictions.map((p) => p.group)).size;

  // Namespace breakdown string
  const nsParts = [
    namespace_counts.BP > 0 ? `${namespace_counts.BP} BP` : null,
    namespace_counts.MF > 0 ? `${namespace_counts.MF} MF` : null,
    namespace_counts.CC > 0 ? `${namespace_counts.CC} CC` : null,
  ].filter(Boolean).join(' · ');

  const CARDS = [
    {
      label:   'GO terms predicted',
      value:   total_predictions,
      sub:     nsParts || 'no predictions',
      color:   'var(--text-1)',
      tooltip: 'Total GO terms predicted across all 22 model groups',
    },
    {
      label:   'Avg confidence',
      value:   avgConf.toFixed(4),
      sub:     'mean sigmoid probability',
      color:   avgConf >= 0.85 ? 'var(--teal-deep)' : avgConf >= 0.70 ? 'var(--text-1)' : 'var(--amber)',
      tooltip: 'Average sigmoid probability across all predictions. Higher = more certain overall.',
    },
    {
      label:   'Highest confidence',
      value:   topPred ? topPred.confidence.toFixed(4) : '—',
      sub:     topPred ? topPred.go_term : 'no predictions',
      color:   'var(--teal-deep)',
      tooltip: 'The single GO term the model is most certain about for this sequence.',
    },
    {
      label:   'Groups activated',
      value:   `${groupsActivated} / ${models_used}`,
      sub:     'of 22 model groups fired',
      color:   'var(--text-1)',
      tooltip: 'How many of the 22 biological group models produced at least one prediction above their tuned threshold.',
    },
  ];

  return (
    <div style={styles.grid}>
      {CARDS.map(({ label, value, sub, color, tooltip }) => (
        <div key={label} style={styles.card} title={tooltip}>
          <div style={styles.label}>{label}</div>
          <div style={{ ...styles.value, color }}>{value}</div>
          <div style={styles.sub}>{sub}</div>
        </div>
      ))}
    </div>
  );
}

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '12px',
    marginBottom: '16px',
  },
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '20px 22px',
    boxShadow: 'var(--shadow-sm)',
    cursor: 'default',
  },
  label: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-3)',
    marginBottom: '8px',
    letterSpacing: '0.02em',
  },
  value: {
    fontSize: '28px',
    fontWeight: '700',
    letterSpacing: '-0.02em',
    lineHeight: 1,
    marginBottom: '6px',
    fontFamily: 'var(--font-mono)',
  },
  sub: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
    lineHeight: '1.4',
    wordBreak: 'break-word',
  },
};