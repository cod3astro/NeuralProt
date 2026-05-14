// src/services/api.js
// All communication with the NeuralProt FastAPI backend lives here.
// Import individual functions into your page components as needed.

const BASE_URL = import.meta.env.VITE_API_URL || "https://localhost:8000";

// ── Health ────────────────────────────────────────────────────────────────────

export const checkHealth = async () => {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
};

export const getGroups = async () => {
  const res = await fetch(`${BASE_URL}/groups`);
  if (!res.ok) throw new Error("Failed to fetch groups");
  return res.json();
};

// ── Prediction ────────────────────────────────────────────────────────────────

const NS_MAP = {
  biological_process: 'BP',
  molecular_function: 'MF',
  cellular_component: 'CC',
};

export const predictSequence = async (sequence, topN = 500) => {
  const res = await fetch(`${BASE_URL}/predict/sequence`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ sequence, top_n: topN }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Prediction failed");
  }
  const raw = await res.json();

  const predictions = raw.predictions.map((p) => ({
    ...p,
    name:      p.go_name || '',
    namespace: NS_MAP[p.namespace] || p.namespace,
  }));

  const namespace_counts = { BP: 0, MF: 0, CC: 0 };
  predictions.forEach((p) => {
    if (namespace_counts[p.namespace] !== undefined) {
      namespace_counts[p.namespace] += 1;
    }
  });

  const groupMap = {};
  predictions.forEach((p) => {
    if (!groupMap[p.group]) {
      groupMap[p.group] = { group: p.group, max_confidence: 0, n_terms: 0 };
    }
    groupMap[p.group].n_terms += 1;
    groupMap[p.group].max_confidence = Math.max(
      groupMap[p.group].max_confidence,
      p.confidence,
    );
  });
  const group_confidences = Object.values(groupMap).sort(
    (a, b) => b.max_confidence - a.max_confidence,
  );

  return {
    predictions,
    total_predictions: predictions.length,
    models_used:       22,
    namespace_counts,
    group_confidences,
  };
};

export const predictFasta = async (fastaFile, topN = 500) => {
  const form = new FormData();
  form.append("fasta_file", fastaFile);
  form.append("top_n", topN);
  const res = await fetch(`${BASE_URL}/predict/fasta`, {
    method: "POST",
    body:   form,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "FASTA prediction failed");
  }
  return res.json();
};

// ── Evaluation ────────────────────────────────────────────────────────────────

export const evaluateF1 = async (fastaFile, tsvFile, propagate = true) => {
  const form = new FormData();
  form.append("fasta_file", fastaFile);
  form.append("data_tsv",   tsvFile);
  form.append("propagate",  propagate);
  const res = await fetch(`${BASE_URL}/evaluate`, {
    method: "POST",
    body:   form,
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Evaluation failed");
  }
  return res.json();
};

export const evaluateFmax = async (fastaFile, testTsv, trainTsv, propagate = true) => {
  const form = new FormData();
  form.append('fasta_file', fastaFile);
  form.append('test_tsv',   testTsv);
  form.append('train_tsv',  trainTsv);
  form.append('propagate',  String(propagate));
  const res = await fetch(`${BASE_URL}/fmax`, {
    method: 'POST',
    body:   form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  return res.json();
};

export const EXAMPLE_SEQUENCES = {
  'PAX6 (transcription factor)': {
    id: 'P26367',
    description: 'Paired box protein Pax-6 · Homo sapiens',
    sequence: 'MQNSHSGVNQLGGVFVNGRPLPDSTRQKIVELAHSGARPCDISRILQVSNGCVSKILGRYYETGSIRPRAIGGSKPRVATPEVVSKIAQYKRECPSIFAWEIRDRLLSEGVCTNDNIPSVSSINRVLRNLASEKQQMGADGMYDKLRMLNGQTGSWGTRPGWYPGTSVPGQPTQDGCQQQEGGGENTNSISSNGEDSDEAQMRLQLKRKLQRNRTSFTQEQIEALEKEFERTHYPDVFARERLAAKIDLPEARIQVWFSNRRAKWRREEKLRNQRRQASNTPSHIPISSSFSTSVYQPIPQPTTPVSSFTSGSMLGRTDTALTNTYSALPPMPSFTMANNLPMQPPVPSQTSSYSCMLPTSPSVNGRSYDTYTPPHMQTHMNSQPMGTSGTTSTGLISPGVSVPVQVPGSEPDMSQYWPRLQ',
  },
  'Insulin': {
    id: 'P01308',
    description: 'Insulin · Homo sapiens',
    sequence: 'MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN',
  },
  'p53 (tumour suppressor)': {
    id: 'P04637',
    description: 'Cellular tumour antigen p53 · Homo sapiens',
    sequence: 'MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLDESGRLSFEV',
  },
};

// ── Utility helpers ───────────────────────────────────────────────────────────

export const uniprotTermUrl = (goTerm) => {
  return `https://www.ebi.ac.uk/QuickGO/term/${goTerm}`;
};