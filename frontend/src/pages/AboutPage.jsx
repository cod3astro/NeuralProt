import { useState } from 'react';

const AUTHORS = [
  {
    initials: 'AT',
    name:     'Abdullateef Tijani',
    role:     'Lead developer · University of Ilorin',
    color:    { bg: '#E1F5EE', text: '#0F6E56' },
    links: [
      { label: 'GitHub',     href: 'https://github.com/cod3astro'      },
      { label: 'LinkedIn',   href: 'https://linkedin.com/in/abdullateef-tijani'    },
      { label: 'Email',      href: 'mailto:molabosipolateef@gmail.com' },
    ],
  },
  {
    initials: 'AA',
    name:     'Aisha Alimi',
    role:     'Researcher · University of Lagos',
    color:    { bg: '#E6F1FB', text: '#185FA5' },
    links: [
      { label: 'GitHub',       href: 'https://github.com/abolaji2188'        },
      { label: 'LinkedIn',   href: 'https:/linkedin.com/in/alimi-aisha-2a7024334'    },
      { label: 'Email',        href: 'mailto:alimiaisha2008@gmail.com' },
    ],
  },
];

const PROJECT_STATS = [
  { label: 'Models trained',        value: '22'        },
  { label: 'GO terms covered',      value: '1,539'     },
  { label: 'Total dataset proteins',value: '105,425'   },
  { label: 'Training proteins',     value: '~84,000'   },
  { label: 'Overall test Fmax',     value: '0.6635'    },
  { label: 'Best group Fmax',       value: '0.8789'    },
  { label: 'Feature dimensions',    value: '428'       },
  { label: 'Avg threshold gain',    value: '+0.11 F1'  },
  { label: 'Groups beat baseline',  value: '21 / 22'   },
  { label: 'Training time',         value: '~4–5 hrs'  },
];

const TECH_STACK = [
  {
    category: 'Machine learning',
    color: { bg: '#E1F5EE', text: '#0F6E56', border: '#5DCAA5' },
    items: [
      { name: 'PyTorch',      desc: 'MLP model training and inference' },
      { name: 'NumPy',        desc: 'Feature matrix operations'        },
      { name: 'scikit-learn', desc: 'F1, precision, recall evaluation' },
      { name: 'SciPy',        desc: 'Isoelectric point binary search'  },
    ],
  },
  {
    category: 'Backend',
    color: { bg: '#E6F1FB', text: '#185FA5', border: '#93C5FD' },
    items: [
      { name: 'FastAPI',  desc: 'REST API for model inference'     },
      { name: 'Uvicorn',  desc: 'ASGI server for FastAPI'          },
      { name: 'Pydantic', desc: 'Request and response validation'  },
      { name: 'Python',   desc: 'Core language — 3.10+'            },
    ],
  },
  {
    category: 'Frontend',
    color: { bg: '#FAEEDA', text: '#854F0B', border: '#FCD34D' },
    items: [
      { name: 'React',          desc: 'UI component framework'           },
      { name: 'Vite',           desc: 'Dev server and build tool'        },
      { name: 'React Router',   desc: 'Client-side page routing'         },
      { name: 'DM Sans / Mono', desc: 'Typography — Google Fonts'        },
    ],
  },
  {
    category: 'Data',
    color: { bg: '#F3E8FF', text: '#6B21A8', border: '#C084FC' },
    items: [
      { name: 'UniProtKB Swiss-Prot', desc: 'Gold-standard protein database'  },
      { name: 'Gene Ontology',        desc: 'go-basic.obo hierarchy file'     },
      { name: 'FASTA format',         desc: 'Protein sequence input/output'   },
      { name: 'TSV format',           desc: 'Annotation and metadata storage' },
    ],
  },
];

const CITATION = `@article{neuralprot2026,
  title   = {NeuralProt: A Modular, CPU-Efficient Protein
             Function Annotation System},
  author  = {Abdullateef and Aisha},
  journal = {Journal Name},
  year    = {2026},
  doi     = {10.xxxx/neuralprot.2026}
}`;

export default function AboutPage() {
  const [copied, setCopied] = useState(false);

  function copyCitation() {
    navigator.clipboard.writeText(CITATION).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.h1}>About NeuralProt</h1>
        <p style={styles.sub}>
          A modular, CPU-efficient protein function annotation system
          using biologically-grounded Gene Ontology term grouping.
        </p>
      </div>

      {/* Abstract */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <div style={styles.cardTitle}>Abstract</div>
          <a href="#" style={styles.paperLink}>View paper →</a>
        </div>
        <p style={styles.abstract}>
          NeuralProt: A Modular, CPU-Efficient Protein Function Prediction Guided by the Gene Ontology Hierarchy
          </p>
                  <p style={styles.abstract}>
          Computational prediction of protein function from sequence remains a central challenge in bioinformatics. 
          Existing deep learning approaches treat Gene Ontology (GO) prediction as a single large multi-label classification problem,
           demanding GPU infrastructure and producing models poorly calibrated for rare terms. This study aims to develop a modular, 
           CPU-accessible protein function annotation system that uses the GO hierarchy as an architectural prior to improve both predictive 
           performance and biological interpretability.
           </p>
             <p style={styles.abstract}>
          NeuralProt trains a separate Multilayer Perceptron for each of 22 biologically defined GO term groups determined by the 
          top-level structure of the GO ontology. Large groups are decomposed into biologically coherent sub-groups based on enzyme 
          commission classification and binding partner type. All models operate on 428-dimensional physicochemical feature vectors 
          comprising amino acid composition, dipeptide composition, and eight normalised physicochemical properties computed directly 
          from amino acid sequence. Annotation propagation implementing the GO True Path Rule was applied consistently throughout training 
          and evaluation to ensure label completeness. Models were trained and evaluated on 105,425 UniProtKB Swiss-Prot proteins using a 
          strict 80/10/10 train/validation/test split with the test set held out completely until final evaluation.
          </p>
          <p style={styles.abstract}>
          NeuralProt achieves an overall macro Fmax of 0.6635 on the held-out test set following the CAFA protein-centric standard, 
          with individual group Fmax ranging from 0.369 to 0.879. The system outperforms a frequency baseline in 21 of 22 groups, 
          and per-term analysis across 1,539 GO terms shows 42.6% achieving Fmax ≥ 0.70. These results demonstrate that biologically 
          motivated modular decomposition of the GO prediction problem, combined with physicochemical sequence features, produces competitive 
          functional annotations on standard CPU hardware without requiring GPU infrastructure or protein language model embeddings.
        </p>
        <div style={styles.doiRow}>
          <div style={styles.doiBox}>
            doi: 10.xxxx/neuralprot.2026 · pending publication
          </div>
          <div style={styles.doiBtns}>
            <a href="#" style={styles.doiBtn}>View paper →</a>
            <a href="#" style={styles.doiBtn}>bioRxiv →</a>
          </div>
        </div>
      </div>

      {/* Citation */}
      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <div style={styles.cardTitle}>Cite this work</div>
          <button onClick={copyCitation} style={styles.copyBtn}>
            {copied ? '✓ Copied!' : 'Copy BibTeX'}
          </button>
        </div>
        <div style={styles.codeBlock}>
          <pre style={styles.citationCode}>{CITATION}</pre>
        </div>
      </div>

      {/* Authors */}
      <div style={styles.sectionLabel}>Authors</div>
      <div style={styles.authorsGrid}>
        {AUTHORS.map((author) => (
          <div key={author.name} style={styles.authorCard}>
            <div style={{ ...styles.avatar, background: author.color.bg, color: author.color.text }}>
              {author.initials}
            </div>
            <div style={styles.authorInfo}>
              <div style={styles.authorName}>{author.name}</div>
              <div style={styles.authorRole}>{author.role}</div>
              <div style={styles.authorLinks}>
                {author.links.map(({ label, href }) => (
                  <a key={label} href={href} target="_blank" rel="noreferrer" style={styles.authorLink}>
                    {label} →
                  </a>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Tech stack */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Technology stack</div>
        <div style={styles.techGrid}>
          {TECH_STACK.map(({ category, color, items }) => (
            <div
              key={category}
              style={{
                ...styles.techCard,
                borderTop: `3px solid ${color.border}`,
              }}
            >
              <div style={{ ...styles.techCategory, color: color.text, background: color.bg }}>
                {category}
              </div>
              <div style={styles.techItems}>
                {items.map(({ name, desc }) => (
                  <div key={name} style={styles.techItem}>
                    <div style={styles.techName}>{name}</div>
                    <div style={styles.techDesc}>{desc}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Project stats */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Project statistics</div>
        <div style={styles.statsGrid}>
          {PROJECT_STATS.map(({ label, value }) => (
            <div key={label} style={styles.statCard}>
              <div style={styles.statValue}>{value}</div>
              <div style={styles.statLabel}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Key findings */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Key findings</div>
        <div style={styles.findingsGrid}>
          {[
            {
              num: '1',
              title: 'Label space size drives performance',
              body: 'Groups with 13–25 GO terms achieve test Fmax of 0.77-0.88. Groups with 100+ terms typically score 0.38-0.63. Splitting large groups into biologically defined sub-groups is the single most effective improvement strategy.',
            },
            {
              num: '2',
              title: 'Threshold tuning is mandatory',
              body: 'The default threshold of 0.5 was suboptimal for every group. Average gain from tuning: +0.11 F1. Nineteen of 22 groups converged to optimal thresholds between 0.80 and 0.95, indicating models are well-calibrated but conservative.',
            },
            {
              num: '3',
              title: 'Physicochemical features are sufficient',
              body: '428-dimensional features: Amino acid composition, dipeptide composition, and 8 physicochemical properties, produce models achieving Fmax up to 0.88 with no GPU, no protein language model, and no structural data.',
            },
            {
              num: '4',
              title: 'Annotation propagation is non-negotiable',
              body: 'Without propagation, training labels are systematically incomplete, models are penalised for predicting biologically correct ancestor terms. Every serious GO prediction publication implements propagation.',
            },
          ].map(({ num, title, body }) => (
            <div key={num} style={styles.findingCard}>
              <div style={styles.findingNum}>{num}</div>
              <div style={styles.findingContent}>
                <div style={styles.findingTitle}>{title}</div>
                <div style={styles.findingBody}>{body}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Open source */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Open source</div>
        <p style={styles.openSourceText}>
          NeuralProt is released under the MIT License. All code, trained model
          weights, and threshold configurations are freely available for academic
          and commercial use.
        </p>
        <div style={styles.openSourceLinks}>
          <a href="https://github.com" target="_blank" rel="noreferrer" style={styles.osBtn}>
            GitHub repository →
          </a>
          <a href="#" style={styles.osBtn}>
            Download models →
          </a>
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
  card: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '28px',
    marginBottom: '18px',
    boxShadow: 'var(--shadow-sm)',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '16px',
    flexWrap: 'wrap',
    gap: '10px',
  },
  cardTitle: {
    fontSize: '20px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '18px',
  },
  sectionLabel: {
    fontSize: '20px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '14px',
  },
  paperLink: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  },
  abstract: {
    fontSize: '16px',
    fontWeight: '400',
    color: 'var(--text-2)',
    lineHeight: '1.8',
    marginBottom: '20px',
    wordBreak: 'break-word',
  },
  doiRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    paddingTop: '16px',
    borderTop: '1px solid var(--border)',
  },
  doiBox: {
    fontFamily: 'var(--font-mono)',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-3)',
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '10px 14px',
    wordBreak: 'break-all',
  },
  doiBtns: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  doiBtn: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    background: 'var(--blue-dim)',
    border: '1px solid #BFDBFE',
    borderRadius: 'var(--radius-md)',
    padding: '9px 16px',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  },
  copyBtn: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--teal-deep)',
    background: 'var(--teal-dim)',
    border: '1px solid var(--teal-light)',
    borderRadius: 'var(--radius-md)',
    padding: '8px 16px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  codeBlock: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 20px',
    overflowX: 'auto',
  },
  citationCode: {
    fontFamily: 'var(--font-mono)',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-1)',
    lineHeight: '1.8',
    margin: 0,
    whiteSpace: 'pre',
  },
  authorsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '14px',
    marginBottom: '18px',
  },
  authorCard: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-lg)',
    padding: '22px',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '16px',
    boxShadow: 'var(--shadow-sm)',
  },
  avatar: {
    width: '52px',
    height: '52px',
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '18px',
    fontWeight: '700',
    flexShrink: 0,
  },
  authorInfo: {
    flex: 1,
    minWidth: 0,
  },
  authorName: {
    fontSize: '18px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '4px',
    wordBreak: 'break-word',
  },
  authorRole: {
    fontSize: '14px',
    fontWeight: '400',
    color: 'var(--text-2)',
    marginBottom: '12px',
    lineHeight: '1.5',
    wordBreak: 'break-word',
  },
  authorLinks: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  authorLink: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--blue)',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  },
  techGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '14px',
  },
  techCard: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    overflow: 'hidden',
  },
  techCategory: {
    fontSize: '13px',
    fontWeight: '700',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    padding: '10px 14px',
  },
  techItems: {
    padding: '10px 14px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  techItem: {
    borderBottom: '1px solid var(--border)',
    paddingBottom: '10px',
  },
  techName: {
    fontSize: '15px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '2px',
    wordBreak: 'break-word',
  },
  techDesc: {
    fontSize: '13px',
    fontWeight: '400',
    color: 'var(--text-3)',
    lineHeight: '1.5',
    wordBreak: 'break-word',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: '12px',
  },
  statCard: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-md)',
    padding: '18px 16px',
    textAlign: 'center',
  },
  statValue: {
    fontSize: '26px',
    fontWeight: '700',
    color: 'var(--teal-deep)',
    fontFamily: 'var(--font-mono)',
    marginBottom: '6px',
    wordBreak: 'break-word',
  },
  statLabel: {
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--text-3)',
    lineHeight: '1.4',
  },
  findingsGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  findingCard: {
    display: 'flex',
    gap: '18px',
    alignItems: 'flex-start',
    paddingBottom: '20px',
    borderBottom: '1px solid var(--border)',
  },
  findingNum: {
    width: '34px',
    height: '34px',
    borderRadius: '50%',
    background: 'var(--teal-dim)',
    color: 'var(--teal-deep)',
    fontSize: '16px',
    fontWeight: '700',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  findingContent: {
    flex: 1,
    minWidth: 0,
  },
  findingTitle: {
    fontSize: '17px',
    fontWeight: '700',
    color: 'var(--text-1)',
    marginBottom: '6px',
    wordBreak: 'break-word',
  },
  findingBody: {
    fontSize: '15px',
    fontWeight: '400',
    color: 'var(--text-2)',
    lineHeight: '1.7',
    wordBreak: 'break-word',
  },
  openSourceText: {
    fontSize: '16px',
    fontWeight: '400',
    color: 'var(--text-2)',
    lineHeight: '1.7',
    marginBottom: '16px',
    wordBreak: 'break-word',
  },
  openSourceLinks: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  osBtn: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--blue)',
    background: 'var(--blue-dim)',
    border: '1px solid #BFDBFE',
    borderRadius: 'var(--radius-md)',
    padding: '10px 18px',
    textDecoration: 'none',
    whiteSpace: 'nowrap',
  },
};