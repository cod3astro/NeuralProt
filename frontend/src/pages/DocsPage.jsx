const SECTIONS = [
  {
    number: '01',
    title: 'Download the data',
    steps: [
      {
        label: 'UniProtKB Swiss-Prot TSV',
        body: 'Go to UniProtKB and search "Reviewed:true, Group:Gene Ontology, Proteins With:Function, Protein Existence:Protein Level" to filter Swiss-Prot only. Click Download, select TSV format, and include these columns: Entry, Sequence, Gene Ontology IDs, Protein names, Organism.',
        link: { href: 'https://www.uniprot.org/uniprotkb?query=reviewed:true', label: 'Open UniProtKB →' },
      },
      {
        label: 'Swiss-Prot FASTA file',
        body: 'From the same search results page, download again in FASTA format. This gives you the amino acid sequences matched to the accessions in the TSV.',
      },
      {
        label: 'Gene Ontology OBO file',
        body: 'Download go-basic.obo from the Gene Ontology Consortium. Use go-basic specifically, not the full go.obo, to keep hierarchy relationships unambiguous.',
        link: { href: 'https://geneontology.org/docs/download-ontology/', label: 'Download go-basic.obo →' },
      },
    ],
  },
  {
    number: '02',
    title: 'Environment setup',
    steps: [
      {
        label: 'Python dependencies',
        code: 'pip install torch numpy biopython scikit-learn fastapi uvicorn',
        body: 'No GPU required. All training and inference runs on standard CPU hardware.',
      },
      {
        label: 'Frontend dependencies',
        code: 'cd frontend && npm install',
        body: 'Requires Node.js 18+. The frontend runs on React + Vite.',
      },
      {
        label: 'Hardware requirements',
        body: 'Training all 22 groups takes approximately 4–5 hours on a modern CPU. Each group trains independently and checkpoints after every epoch, so training can be safely interrupted and resumed.',
      },
    ],
  },
  {
    number: '03',
    title: 'Training pipeline',
    steps: [
     {
        label: 'Step 1 — Parse the GO hierarchy',
        code: 'python go_parser.py',
        body: 'Reads go-basic.obo and produces go_dict.json with all active GO terms, their namespaces, parent links, alternate IDs, and pre-computed ancestor sets.',
      },
      {
        label: 'Step 2 — Assign GO terms to groups',
        code: 'python go_group_assigner_v2.py',
        body: 'Uses the GO hierarchy to assign each dataset GO term to exactly one biological group. Small groups are merged into biologically related larger ones. Produces go_group_assignment_v2.json.',
      },
      {
        label: 'Step 3 — Split large groups, process data and extract features',
        code: 'data_processor.ipynb',
        body: 'Splits large GO groups into biologically defined sub-groups, applies annotation propagation (True Path Rule), and computes 428-dimensional physicochemical feature vectors per protein. Saves features.npy, labels.npy, and go_terms.json per group.',
      },
      {
        label: 'Step 4 — Train models',
        code: 'train_model.ipynb',
        body: 'Trains one MLP per group with BCEWithLogitsLoss + pos_weight for class imbalance, Adam optimizer, and ReduceLROnPlateau scheduler. Uses an 80/10/10 train/val/test split. Saves {group}_best.pt after every improvement.',
      },
      {
        label: 'Step 5 — Tune prediction thresholds',
        code: 'threshold_tuning.ipynb',
        body: 'Sweeps 100 threshold values per group on the validation set and selects the threshold with highest macro F1. Saves optimal thresholds to models/threshold_results.json. Average gain: +0.11 F1 per group.',
      },
    ],
  },
  {
    number: '04',
    title: 'Running inference',
    steps: [
      {
        label: 'Single sequence or Batch prediction from FASTA',
        code: 'neuralprot_inference.py predict',
        body: "Extracts 428-dimensional features and runs all 22 group models. Returns GO terms predicted above each group's tuned threshold, sorted by confidence.",
      },
      {
        label: 'Per-term F1 evaluation',
        code: 'neuralprot_inference.py evaluate',
        body: 'Computes per-term F1, precision, and recall at the tuned threshold across all groups. Outputs per_term_f1.csv and evaluation_summary.json. Use only on a held-out test set.',
      },
      {
        label: 'Fmax / Smin evaluation',
        code: 'neuralprot_inference.py fmax',
        body: 'Computes protein-centric Fmax and Smin following the CAFA standard, sweeping all thresholds. Runs a frequency baseline on identical data for comparison. Outputs fmax_comparison.json and per-group threshold curves.',
      },
    ],
  },
  {
    number: '05',
    title: 'Starting the web app',
    steps: [
      {
        label: 'Start the FastAPI backend',
        code: 'uvicorn backend.main:app --reload --port 8000',
        body: 'The backend loads all 22 models at startup. Subsequent predictions are fast since models stay in memory.',
      },
      {
        label: 'Start the frontend',
        code: 'cd frontend && npm run dev',
        body: 'Runs the React dev server at https://localhost:5173. Set VITE_API_URL=https://localhost:8000 in a .env file to connect to the backend.',
      },
      {
        label: 'Production build',
        code: 'cd frontend && npm run build',
        body: 'Outputs a static build to frontend/dist/ that can be served by any static file host or the FastAPI backend directly.',
      },
    ],
  },
];

const FEATURE_ROWS = [
  { range: '[0 : 20]',   type: 'Amino acid composition', dims: '20',  desc: 'Fraction of each of the 20 standard amino acids in the sequence.' },
  { range: '[20 : 420]', type: 'Dipeptide composition',  dims: '400', desc: 'Fraction of each possible adjacent amino acid pair (20×20).' },
  { range: '[420]',      type: 'Normalised length',       dims: '1',   desc: 'log1p(n) / log1p(35000) — log-scaled sequence length.' },
  { range: '[421]',      type: 'Molecular weight',        dims: '1',   desc: 'Sum of residue masses minus water lost at peptide bonds, scaled to MDa.' },
  { range: '[422]',      type: 'GRAVY score',             dims: '1',   desc: 'Grand Average of Hydropathy — raw Kyte-Doolittle sum / length.' },
  { range: '[423]',      type: 'Aromaticity',             dims: '1',   desc: 'Fraction of aromatic residues (F, W, Y).' },
  { range: '[424]',      type: 'Instability index',       dims: '1',   desc: 'Guruprasad dipeptide instability score, normalised by / 200.' },
  { range: '[425]',      type: 'Isoelectric point',       dims: '1',   desc: 'pH at zero net charge via binary search, normalised by / 14.' },
  { range: '[426]',      type: 'Charge at pH 7',          dims: '1',   desc: 'Net charge under physiological conditions, tanh-scaled by / 50.' },
  { range: '[427]',      type: 'Aliphatic index',         dims: '1',   desc: 'Ikai 1980 aliphatic index (A + 2.9V + 3.9(I+L)) / n × 100, normalised by / 300.' },
];

export default function DocsPage() {
  return (
    <div style={styles.page}>
      <div style={styles.hero}>
        <h1 style={styles.h1}>Documentation</h1>
        <p style={styles.sub}>
          Everything needed to reproduce the dataset, retrain the models,
          and extend NeuralProt to new GO term groups.
        </p>
      </div>

      {/* Quick stats bar */}
      <div style={styles.statsBar}>
        {[
          { label: 'Training proteins', value: '~105,000' },
          { label: 'GO terms covered',  value: '~1,500'   },
          { label: 'Models trained',    value: '22'        },
          { label: 'Training time',     value: '~5 hours'  },
          { label: 'Hardware',          value: 'CPU only'  },
        ].map(({ label, value }) => (
          <div key={label} style={styles.statItem}>
            <div style={styles.statValue}>{value}</div>
            <div style={styles.statLabel}>{label}</div>
          </div>
        ))}
      </div>

      {/* Main sections */}
      {SECTIONS.map((section) => (
        <div key={section.number} style={styles.section}>
          <div style={styles.sectionHeader}>
            <span style={styles.sectionNumber}>{section.number}</span>
            <h2 style={styles.sectionTitle}>{section.title}</h2>
          </div>
          <div style={styles.steps}>
            {section.steps.map((step, i) => (
              <div key={i} style={styles.step}>
                <div style={styles.stepDot} />
                <div style={styles.stepContent}>
                  <div style={styles.stepLabel}>{step.label}</div>
                  {step.code && (
                    <div className="docs-code-block" style={styles.codeBlock}>
                      <code style={styles.code}>{step.code}</code>
                    </div>
                  )}
                  <div style={styles.stepBody}>{step.body}</div>
                  {step.link && (
                    <a href={step.link.href} target="_blank" rel="noreferrer" style={styles.stepLink}>
                      {step.link.label}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Feature vector reference */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <span style={styles.sectionNumber}>06</span>
          <h2 style={styles.sectionTitle}>Feature vector reference</h2>
        </div>
        <div className="docs-feature-table-note" style={{ display: 'none', padding: '12px', color: 'var(--text-3)', fontSize: '14px' }}>
             Feature vector reference hidden on small screens.
            </div>
        <div className="docs-feature-table" style={styles.featureTable}>
          <div style={styles.featureHeader}>
            <span>Index</span>
            <span>Feature</span>
            <span>Dims</span>
            <span>Description</span>
          </div>
          {FEATURE_ROWS.map((row, i) => (
            <div
              key={i}
              style={{
                ...styles.featureRow,
                background: i % 2 === 0 ? 'var(--surface)' : 'var(--surface-2)',
              }}
            >
              <span style={styles.featureRange}>{row.range}</span>
              <span style={styles.featureType}>{row.type}</span>
              <span style={styles.featureDims}>{row.dims}</span>
              <span style={styles.featureDesc}>{row.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

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
  statsBar: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: '1px',
    background: 'var(--border)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    overflow: 'hidden',
    marginBottom: '28px',
    boxShadow: 'var(--shadow-sm)',
  },
  statItem: {
    background: 'var(--surface)',
    padding: '18px 20px',
    textAlign: 'center',
  },
  statValue: {
    fontSize: '22px',
    fontWeight: '700',
    color: 'var(--teal-deep)',
    marginBottom: '4px',
    fontFamily: 'var(--font-mono)',
  },
  statLabel: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
  },
  section: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '28px',
    marginBottom: '18px',
    boxShadow: 'var(--shadow-sm)',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid var(--border)',
  },
  sectionNumber: {
    fontSize: '13px',
    fontWeight: '700',
    color: 'var(--teal-deep)',
    background: 'var(--teal-dim)',
    padding: '4px 10px',
    borderRadius: '6px',
    fontFamily: 'var(--font-mono)',
    letterSpacing: '0.04em',
  },
  sectionTitle: {
    fontSize: '22px',
    fontWeight: '700',
    color: 'var(--text-1)',
    letterSpacing: '-0.01em',
  },
  steps: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  step: {
    display: 'flex',
    gap: '18px',
    alignItems: 'flex-start',
  },
  stepDot: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    background: 'var(--teal)',
    flexShrink: 0,
    marginTop: '6px',
  },
  stepContent: {
    flex: 1,
  },
  stepLabel: {
    fontSize: '17px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '8px',
  },
  codeBlock: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '12px 16px',
    marginBottom: '10px',
    overflowX: 'auto',
  },
  code: {
    fontFamily: 'var(--font-mono)',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-1)',
    whiteSpace: 'pre',
  },
  stepBody: {
    fontSize: '16px',
    fontWeight: '400',
    color: 'var(--text-2)',
    lineHeight: '1.7',
  },
  stepLink: {
    display: 'inline-block',
    marginTop: '8px',
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    textDecoration: 'none',
  },
  featureTable: {
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  },
  featureHeader: {
    display: 'grid',
    gridTemplateColumns: '110px 200px 70px 1fr',
    gap: '12px',
    padding: '12px 18px',
    background: 'var(--surface-2)',
    borderBottom: '1px solid var(--border)',
    fontSize: '13px',
    fontWeight: '700',
    color: 'var(--text-3)',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  featureRow: {
    display: 'grid',
    gridTemplateColumns: '110px 200px 70px 1fr',
    gap: '12px',
    padding: '13px 18px',
    borderBottom: '1px solid var(--border)',
    alignItems: 'start',
  },
  featureRange: {
    fontFamily: 'var(--font-mono)',
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--blue)',
  },
  featureType: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--text-1)',
  },
  featureDims: {
    fontFamily: 'var(--font-mono)',
    fontSize: '15px',
    fontWeight: '700',
    color: 'var(--teal-deep)',
    textAlign: 'center',
  },
  featureDesc: {
    fontSize: '14px',
    fontWeight: '400',
    color: 'var(--text-2)',
    lineHeight: '1.6',
  },
};