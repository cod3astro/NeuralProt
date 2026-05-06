import { useEffect, useState } from 'react';

export default function SequenceScanAnimation({ sequence, progress, total }) {
  const [highlightIndex, setHighlightIndex] = useState(0);
  const clean = sequence.replace(/[^ACDEFGHIKLMNPQRSTVWY]/gi, '').toUpperCase();
  const display = clean.slice(0, 40);

  const AA_COLORS = {
    A: '#1D9E75', V: '#1D9E75', I: '#1D9E75', L: '#1D9E75',
    M: '#1D9E75', F: '#1D9E75', W: '#1D9E75', P: '#1D9E75',
    S: '#185FA5', T: '#185FA5', C: '#185FA5', Y: '#185FA5',
    N: '#185FA5', Q: '#185FA5',
    K: '#854F0B', R: '#854F0B', H: '#854F0B',
    D: '#9B1C1C', E: '#9B1C1C',
    G: '#9CA3AF',
  };

  useEffect(() => {
    const interval = setInterval(() => {
      setHighlightIndex((i) => (i + 1) % display.length);
    }, 80);
    return () => clearInterval(interval);
  }, [display.length]);

  const pct = total > 0 ? Math.round((progress / total) * 100) : 0;

  return (
    <div style={styles.wrap}>
      <div style={styles.label}>Scanning sequence through 22 models</div>

      <div style={styles.seqWrap}>
        {display.split('').map((aa, i) => {
          const isActive = i === highlightIndex;
          const isPast   = i < highlightIndex;
          return (
            <span
              key={i}
              style={{
                ...styles.aa,
                color: isActive
                  ? (AA_COLORS[aa] || 'var(--text-2)')
                  : isPast ? 'var(--text-3)' : 'var(--border-2)',
                fontWeight: isActive ? '700' : '400',
                transform: isActive ? 'translateY(-3px)' : 'none',
                transition: 'all 0.1s ease',
              }}
            >
              {aa}
            </span>
          );
        })}
        <span style={styles.ellipsis}>···</span>
      </div>

      <div style={styles.progressWrap}>
        <div style={styles.progressTrack}>
          <div style={{ ...styles.progressBar, width: `${pct}%` }} />
        </div>
        <span style={styles.progressText}>
          {progress} / {total} models complete
        </span>
      </div>

      <div style={styles.statsRow}>
        {['428 features extracted', 'Annotation propagation ✓', 'Tuned thresholds applied'].map((s, i) => (
          <span
            key={i}
            style={{
              ...styles.stat,
              opacity: progress > i * 7 ? 1 : 0.25,
              transition: 'opacity 0.4s ease',
            }}
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '36px 32px',
    marginBottom: '20px',
    textAlign: 'center',
    boxShadow: 'var(--shadow-sm)',
  },
  label: {
    fontSize: '16px',
    fontWeight: '600',
    color: 'var(--text-3)',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    marginBottom: '24px',
  },
  seqWrap: {
    display: 'flex',
    justifyContent: 'center',
    flexWrap: 'nowrap',
    gap: '4px',
    marginBottom: '28px',
    overflow: 'hidden',
  },
  aa: {
    fontFamily: 'var(--font-mono)',
    fontSize: '18px',
    display: 'inline-block',
    lineHeight: 1,
  },
  ellipsis: {
    fontFamily: 'var(--font-mono)',
    fontSize: '18px',
    color: 'var(--border-2)',
    marginLeft: '6px',
    letterSpacing: '4px',
  },
  progressWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '20px',
  },
  progressTrack: {
    flex: 1,
    height: '6px',
    background: 'var(--surface-3)',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  progressBar: {
    height: '100%',
    background: 'linear-gradient(90deg, var(--teal), var(--teal-light))',
    borderRadius: '3px',
    transition: 'width 0.2s ease',
  },
  progressText: {
    fontSize: '15px',
    fontWeight: '500',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-mono)',
    minWidth: '180px',
    textAlign: 'right',
  },
  statsRow: {
    display: 'flex',
    justifyContent: 'center',
    gap: '16px',
    flexWrap: 'wrap',
  },
  stat: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--teal-deep)',
    background: 'var(--teal-dim)',
    padding: '5px 14px',
    borderRadius: '20px',
  },
};