# NeuralProt

**Modular, CPU-Efficient Protein Function Prediction Guided by the Gene Ontology Hierarchy**

NeuralProt predicts Gene Ontology (GO) terms from protein sequences using 22 biologically-grouped neural networks trained on UniProtKB Swiss-Prot. It runs entirely on standard CPU hardware — no GPU required.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Visit-1D9E75?style=for-the-badge)](https://your-app.vercel.app)
[![Backend](https://img.shields.io/badge/Backend-Render-4F46E5?style=for-the-badge)](https://neuralprot-backend.onrender.com/health)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge)](https://python.org)
[![React](https://img.shields.io/badge/React-Vite-61DAFB?style=for-the-badge)](https://vitejs.dev)

---

## What It Does

Given an amino acid sequence, NeuralProt:

- Computes a 428-dimensional physicochemical feature vector from the sequence
- Runs the vector through all 22 group-specific MLP models
- Returns predicted GO terms above each group's tuned threshold, sorted by confidence
- Covers 1,539 GO terms across Biological Process, Molecular Function, and Cellular Component

---

## Results

| Metric | Value |
|---|---|
| Overall test Fmax (CAFA standard) | 0.6635 |
| Best group Fmax (nuclear_transport) | 0.8789 |
| Groups beating frequency baseline | 21 / 22 |
| GO terms with Fmax ≥ 0.70 | 42.6% of 1,539 terms |
| Training proteins | 105,425 (UniProtKB Swiss-Prot) |
| Feature dimensions | 428 |
| Hardware requirement | CPU only |

---

## Project Structure

```
neuralprot/
├── backend/
│   ├── neuralprot_backend.py      # FastAPI REST API
│   ├── neuralprot_inference.py    # Inference pipeline (predict, evaluate, fmax)
│   ├── requirements.txt
│   └── models/                    # 22 trained group models
│       ├── {group}_best.pt        # Model weights
│       ├── {group}_terms.json     # GO term list per group
│       └── threshold_results.json # Tuned thresholds per group
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── PredictPage.jsx    # Single sequence + batch FASTA prediction
│   │   │   ├── ComparePage.jsx    # Benchmark comparison
│   │   │   ├── EvaluatePage.jsx   # Custom dataset evaluation
│   │   │   ├── DocsPage.jsx       # Pipeline documentation
│   │   │   └── AboutPage.jsx      # Project overview
│   │   ├── components/
│   │   │   ├── SequenceScanAnimation.jsx
│   │   │   ├── MetricsGrid.jsx
│   │   │   ├── GroupBars.jsx
│   │   │   └── ResultsTable.jsx
│   │   └── services/
│   │       └── api.js             # All backend communication
│   └── .env                       # VITE_API_URL=https://neuralprot-backend.onrender.com
│
└── scripts/                       # Training and evaluation pipeline
    ├── go_parser.py               # Parses go-basic.obo → go_dict.json
    ├── go_group_assigner_v2.py    # Assigns GO terms to biological groups
    ├── data_pipeline.py           # Builds per-group label matrices
    ├── data_processor.ipynb       # Feature extraction + large group splitting
    ├── train_model.ipynb          # Trains one MLP per group
    ├── threshold_tuning.ipynb     # Finds optimal threshold per group
    ├── neuralprot_test_evaluation.py  # Fmax/Smin on held-out test set
    └── neuralprot_per_term_analysis.py # Per-term Fmax breakdown
```

---

## Pipeline Overview

The full training pipeline runs in six steps:

```
Step 1  python go_parser.py
        Reads go-basic.obo → go_dict.json (38,560 active GO terms, ancestor cache)

Step 2  python go_group_assigner_v2.py
        Assigns each dataset GO term to exactly one biological group
        → go_group_assignment_v2.json

Step 3  data_processor.ipynb
        Splits large groups into sub-groups, applies True Path Rule propagation,
        computes 428-dimensional feature vectors per protein
        → processed_data/{group}/features.npy, labels.npy, go_terms.json

Step 4  train_model.ipynb
        Trains one MLP per group (80/10/10 split, BCEWithLogitsLoss + pos_weight)
        → models/{group}_best.pt

Step 5  threshold_tuning.ipynb
        Sweeps 100 thresholds per group on validation set, selects best macro F1
        → models/threshold_results.json

Step 6  neuralprot_test_evaluation.py
        Evaluates all groups on held-out test set using Fmax and Smin
        → test_evaluation/test_fmax_summary.json
```

---

## Feature Vector

Each protein sequence is converted to a fixed 428-dimensional vector:

| Range | Feature | Dimensions |
|---|---|---|
| [0:20] | Amino acid composition | 20 |
| [20:420] | Dipeptide composition | 400 |
| [420] | Normalised length | 1 |
| [421] | Molecular weight | 1 |
| [422] | GRAVY score | 1 |
| [423] | Aromaticity | 1 |
| [424] | Instability index | 1 |
| [425] | Isoelectric point | 1 |
| [426] | Net charge at pH 7 | 1 |
| [427] | Aliphatic index | 1 |

All features computed from sequence only — no structural data, no language model embeddings.

---

## The 22 Biological Groups

| Group | GO Terms | Test Fmax |
|---|---|---|
| nuclear_transport | 13 | 0.8789 |
| molecular_transducer | 50 | 0.8613 |
| lipid_transport | 25 | 0.8492 |
| atp_dependent_activity | 54 | 0.8048 |
| metal_ion_binding | 16 | 0.8017 |
| ion_transport | 49 | 0.7928 |
| lipid_binding | 38 | 0.7759 |
| dna_binding | 34 | 0.7359 |
| small_molecule_binding | 57 | 0.7252 |
| protein_transport | 36 | 0.7128 |
| lyase_activity | 75 | 0.6947 |
| rna_binding | 38 | 0.6394 |
| oxidoreductase_activity | 159 | 0.6293 |
| vesicle_mediated_transport | 38 | 0.6161 |
| mf_regulator_activity | 98 | 0.6143 |
| hydrolase_activity | 131 | 0.6035 |
| homeostatic_process | 88 | 0.5558 |
| transferase_activity | 154 | 0.5350 |
| immune_system_process | 106 | 0.5149 |
| interspecies_interaction | 111 | 0.5123 |
| protein_binding | 97 | 0.3753 |
| reproductive_process | 72 | 0.3686 |

---

## Running Locally

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn neuralprot_backend:app --host 0.0.0.0 --port 8000 --reload
```

Visit `http://localhost:8000/health` to confirm all 22 models are loaded.

### Frontend

```bash
cd frontend
npm install
```

Create `.env` in the frontend folder:

```
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
```

Open `http://localhost:5173`.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Server status and loaded model count |
| GET | `/groups` | All 22 groups with GO term counts and thresholds |
| POST | `/predict/sequence` | Single sequence → GO term predictions |
| POST | `/predict/fasta` | FASTA file → batch predictions |
| POST | `/evaluate` | Labelled dataset → per-term F1 evaluation |
| POST | `/fmax` | Labelled dataset → Fmax/Smin with baseline comparison |

### Example: Single Sequence Prediction

```bash
curl -X POST https://neuralprot-backend.onrender.com/predict/sequence \
  -H "Content-Type: application/json" \
  -d '{"sequence": "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPK", "top_n": 20}'
```

Response:
```json
{
  "n_predictions": 12,
  "showing": 12,
  "predictions": [
    {
      "go_term": "GO:0005179",
      "group": "molecular_transducer",
      "confidence": 0.9412,
      "threshold": 0.92,
      "go_name": "hormone activity",
      "namespace": "molecular_function"
    }
  ]
}
```

---

## Inference CLI

```bash
# Single sequence
python neuralprot_inference.py predict \
  --sequence MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPK \
  --models_dir ./models

# FASTA file
python neuralprot_inference.py predict \
  --fasta ./proteins.fasta \
  --models_dir ./models \
  --output_json ./predictions.json

# Per-term F1 evaluation
python neuralprot_inference.py evaluate \
  --fasta ./test.fasta \
  --data_tsv ./test_annotations.tsv \
  --models_dir ./models \
  --go_dict ./go_dict.json \
  --propagate \
  --output_dir ./evaluation_results

# Fmax / Smin evaluation with baseline
python neuralprot_inference.py fmax \
  --fasta ./test.fasta \
  --data_tsv ./test_annotations.tsv \
  --train_tsv ./train_annotations.tsv \
  --models_dir ./models \
  --go_dict ./go_dict.json \
  --propagate \
  --output_dir ./fmax_results
```

---

## Model Architecture

Each group model is a 4-layer MLP:

```
428 → Linear(1024) → BatchNorm → ReLU → Dropout(30%)
    → Linear(512)  → BatchNorm → ReLU → Dropout(30%)
    → Linear(256)  → BatchNorm → ReLU → Dropout(20%)
    → Linear(num_classes)  [raw logits]
```

Sigmoid converts logits to probabilities during inference. Tuned thresholds (0.38–0.95) convert probabilities to binary predictions.

---

## Training Details

| Setting | Value |
|---|---|
| Loss function | BCEWithLogitsLoss + pos_weight |
| Optimiser | Adam (lr=0.001, weight_decay=1e-4) |
| Scheduler | ReduceLROnPlateau (factor=0.5, patience=2) |
| Data split | 80% train / 10% val / 10% test |
| Random seed | 42 (fixed throughout) |
| Epochs | Up to 100 with early stopping |
| MIN_TERM_FREQ | 50 (GO terms in fewer proteins excluded) |
| Pos_weight clip | 10,000 |

---

## Data

- **Source:** UniProtKB Swiss-Prot (downloaded January 2025)
- **Proteins:** 105,425 manually reviewed entries
- **GO ontology:** go-basic.obo from Gene Ontology Consortium
- **Annotation propagation:** True Path Rule applied — all ancestor terms added to each protein's label set before training

---

## Tech Stack

| Layer | Technology |
|---|---|
| Model training | PyTorch, NumPy, scikit-learn |
| Backend API | FastAPI, Uvicorn |
| Frontend | React, Vite, React Router |
| Data | UniProtKB Swiss-Prot, Gene Ontology |
| Frontend hosting | Vercel |
| Backend hosting | Render |

---

## Limitations

- Covers 1,539 of 27,160 unique GO terms in the dataset (~5.7%)
- Eleven additional large groups remain to be trained
- Reproductive process is the only group below the frequency baseline (Fmax 0.3686)
- No head-to-head comparison against DeepGOPlus on identical data has been conducted
- Optimal thresholds were identified on the validation set — confirmed on held-out test set

---

## Citation

If you use NeuralProt in your work, please cite:

```
NeuralProt: Modular, CPU-Efficient Protein Function Prediction
Guided by the Gene Ontology Hierarchy
Faculty of Life Sciences, 2026
```

---

## Acknowledgements

- [UniProt Consortium](https://www.uniprot.org) for the Swiss-Prot database
- [Gene Ontology Consortium](https://geneontology.org) for the GO ontology and go-basic.obo file
- [CAFA](https://www.biofunctionprediction.org/cafa/) for the Fmax and Smin evaluation standard
