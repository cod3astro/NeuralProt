"""
NeuralProt — FastAPI Backend
==============================
Exposes all NeuralProt inference capabilities as REST endpoints.

Endpoints:
  POST /predict/sequence   — single amino acid sequence → GO predictions
  POST /predict/fasta      — FASTA file upload → predictions for all sequences
  POST /evaluate           — annotated TSV + FASTA → per-term F1 evaluation
  POST /fmax               — annotated TSV + FASTA + train TSV → Fmax/Smin + baseline
  GET  /health             — server status and loaded model count
  GET  /groups             — list of all loaded model groups and their thresholds

All 22 models are loaded once at startup and kept in memory.
Temporary uploaded files are cleaned up after each request.

Usage:
  pip install fastapi uvicorn python-multipart
  uvicorn neuralprot_backend:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import uuid
import tempfile
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Import NeuralProt pipeline ────────────────────────────────────────────────
from neuralprot_inference import (
    FeatureExtractor,
    ModelRegistry,
    NeuralProtEvaluator,
    FmaxEngine,
    FrequencyBaseline,
    verify_feature_extractor,
    load_fasta,
    load_annotations_tsv,
    propagate_annotations,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
) 
logger = logging.getLogger(__name__) 


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

import os

MODELS_DIR   = os.environ.get("MODELS_DIR",   "./models")
GO_DICT_PATH = os.environ.get("GO_DICT_PATH", "./go_dict.json")

# Origins allowed to call this API — update with your frontend URL in production
ALLOWED_ORIGINS = [
    "https://neuralprot.vercel.app",
    "https://localhost:5173",
    "https://localhost:3000",
]


# ─────────────────────────────────────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NeuralProt API",
    description="GO term prediction from protein sequences using 22 biologically-grouped neural networks.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP — load models once
# ─────────────────────────────────────────────────────────────────────────────

import json

extractor = None
registry  = None
go_dict   = {}

@app.on_event("startup")
def startup():
    global extractor, registry, go_dict

    logger.info("Verifying feature extractor calibration...")
    verify_feature_extractor()

    logger.info("Loading models from %s ...", MODELS_DIR)
    extractor = FeatureExtractor()
    registry  = ModelRegistry(MODELS_DIR)

    if os.path.exists(GO_DICT_PATH):
        with open(GO_DICT_PATH) as f:
            go_dict = json.load(f)
        logger.info("GO dictionary loaded: %d terms.", len(go_dict))
    else:
        logger.warning("go_dict.json not found — GO term names will be absent from responses.")

    logger.info("Startup complete. %d group models ready.", len(registry.groups))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def save_upload(upload: UploadFile) -> str:
    """Save an uploaded file to a temp path. Caller must delete after use."""
    suffix = Path(upload.filename).suffix or ".tmp"
    tmp_path = os.path.join(tempfile.gettempdir(), f"neuralprot_{uuid.uuid4().hex}{suffix}")
    with open(tmp_path, "wb") as f:
        f.write(upload.file.read())
    return tmp_path


def cleanup(*paths):
    for p in paths:
        if p and os.path.exists(p):
            os.remove(p)


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class SequenceRequest(BaseModel):
    sequence: str
    top_n: Optional[int] = 20


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Check that the server is running and models are loaded."""
    return {
        "status":        "ok",
        "models_loaded": len(registry.groups) if registry else 0,
        "groups":        sorted(registry.groups.keys()) if registry else [],
    }


@app.get("/groups")
def get_groups():
    """Return all loaded model groups with their GO term counts and thresholds."""
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded yet.")
    return {
        group: {
            "n_terms":   meta["num_classes"],
            "threshold": meta["threshold"],
        }
        for group, meta in registry.groups.items()
    }


@app.post("/predict/sequence")
def predict_sequence(request: SequenceRequest):
    """
    Predict GO terms for a single amino acid sequence string.

    Returns all predictions above the tuned threshold for each group,
    sorted by confidence descending. Optionally limit to top_n results.
    """
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded.")

    sequence = request.sequence.strip()
    if not sequence:
        raise HTTPException(status_code=400, detail="Sequence cannot be empty.")

    try:
        features     = extractor.extract(sequence)
        predictions  = registry.predict_single(features)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    top = predictions[:request.top_n] if request.top_n else predictions

    # Enrich with GO term names if go_dict is available
    for pred in top:
        pred["go_name"]   = go_dict.get(pred["go_term"], {}).get("name", "")
        pred["namespace"] = go_dict.get(pred["go_term"], {}).get("namespace", "")

    return {
        "n_predictions": len(predictions),
        "showing":       len(top),
        "predictions":   top,
    }


@app.post("/predict/fasta")
async def predict_fasta(
    fasta_file: UploadFile = File(...),
    top_n: int = Form(20),
):
    """
    Predict GO terms for all sequences in an uploaded FASTA file.

    Returns one prediction block per sequence, each containing
    all GO terms predicted above the tuned threshold.
    """
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded.")

    fasta_path = save_upload(fasta_file)
    try:
        sequences_map = load_fasta(fasta_path)
    except Exception as e:
        cleanup(fasta_path)
        raise HTTPException(status_code=400, detail=f"Failed to parse FASTA: {e}")

    results = {}
    errors  = {}

    for pid, seq in sequences_map.items():
        try:
            features    = extractor.extract(seq)
            predictions = registry.predict_single(features)
            top         = predictions[:top_n]
            for pred in top:
                pred["go_name"]   = go_dict.get(pred["go_term"], {}).get("name", "")
                pred["namespace"] = go_dict.get(pred["go_term"], {}).get("namespace", "")
            results[pid] = {
                "n_predictions": len(predictions),
                "predictions":   top,
            }
        except ValueError as e:
            errors[pid] = str(e)

    cleanup(fasta_path)

    return {
        "n_sequences": len(sequences_map),
        "n_succeeded": len(results),
        "n_failed":    len(errors),
        "results":     results,
        "errors":      errors,
    }


@app.post("/evaluate")
async def evaluate(
    fasta_file:  UploadFile = File(...),
    data_tsv:    UploadFile = File(...),
    propagate:   bool = Form(True),
    go_col:      str  = Form("Gene Ontology IDs"),
):
    """
    Per-term F1 evaluation on an annotated test set.

    Accepts a FASTA file of sequences and a UniProtKB-style TSV of
    GO annotations. Returns per-term F1, precision, recall, and support
    across all 22 groups, plus group-level macro F1 summary.

    Use only on a genuinely held-out test set — not on validation data.
    """
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded.")

    fasta_path = save_upload(fasta_file)
    tsv_path   = save_upload(data_tsv)

    try:
        sequences_map   = load_fasta(fasta_path)
        annotations_map = load_annotations_tsv(tsv_path, go_col=go_col)

        if propagate and go_dict:
            annotations_map = propagate_annotations(annotations_map, go_dict)

        matched_ids = [pid for pid in sequences_map if pid in annotations_map]
        if not matched_ids:
            raise HTTPException(
                status_code=400,
                detail="No protein IDs overlap between FASTA and TSV. Check ID format."
            )

        sequences   = [sequences_map[pid]   for pid in matched_ids]
        annotations = [annotations_map[pid] for pid in matched_ids]

        import numpy as np
        evaluator      = NeuralProtEvaluator(registry, go_dict=go_dict)
        feature_matrix = np.stack([extractor.extract(seq) for seq in sequences])
        group_probs    = registry.get_group_probs(feature_matrix)

        all_term_rows   = []
        group_summaries = {}
        from sklearn.metrics import f1_score, precision_score, recall_score

        for group, meta in registry.groups.items():
            probs     = group_probs[group]
            go_terms  = meta["go_terms"]
            threshold = meta["threshold"]
            y_pred    = (probs >= threshold).astype(int)
            y_true    = np.zeros_like(y_pred, dtype=int)

            for i, ann_set in enumerate(annotations):
                for j, go_term in enumerate(go_terms):
                    if go_term in ann_set:
                        y_true[i, j] = 1

            term_rows = []
            valid_f1s = []

            for j, go_term in enumerate(go_terms):
                support = int(y_true[:, j].sum())
                row = {
                    "go_term":   go_term,
                    "go_name":   go_dict.get(go_term, {}).get("name", ""),
                    "namespace": go_dict.get(go_term, {}).get("namespace", ""),
                    "group":     group,
                    "support":   support,
                    "f1":        None,
                    "precision": None,
                    "recall":    None,
                    "threshold": threshold,
                }
                if support > 0:
                    yt = y_true[:, j]
                    yp = y_pred[:, j]
                    row["f1"]        = round(float(f1_score(yt, yp, zero_division=0)), 4)
                    row["precision"] = round(float(precision_score(yt, yp, zero_division=0)), 4)
                    row["recall"]    = round(float(recall_score(yt, yp, zero_division=0)), 4)
                    valid_f1s.append(row["f1"])
                term_rows.append(row)

            macro_f1 = round(float(np.mean(valid_f1s)), 4) if valid_f1s else 0.0
            group_summaries[group] = {
                "macro_f1":             macro_f1,
                "n_terms_in_model":     len(go_terms),
                "n_terms_with_support": len(valid_f1s),
                "threshold":            threshold,
            }
            all_term_rows.extend(term_rows)

        valid_all     = [r for r in all_term_rows if r["f1"] is not None]
        overall_macro = round(float(np.mean([r["f1"] for r in valid_all])), 4) if valid_all else 0.0

        return {
            "n_proteins_evaluated":      len(sequences),
            "n_matched_ids":             len(matched_ids),
            "overall_macro_f1":          overall_macro,
            "n_terms_f1_above_0.7":      sum(1 for r in valid_all if r["f1"] >= 0.7),
            "n_terms_f1_above_0.5":      sum(1 for r in valid_all if r["f1"] >= 0.5),
            "group_summary":             group_summaries,
            "per_term_results":          all_term_rows,
        }

    finally:
        cleanup(fasta_path, tsv_path)


@app.post("/fmax")
async def fmax_evaluation(
    fasta_file:    UploadFile = File(...),
    test_tsv:      UploadFile = File(...),
    train_tsv:     UploadFile = File(...),
    propagate:     bool = Form(True),
    go_col:        str  = Form("Gene Ontology IDs"),
):
    """
    Fmax and Smin evaluation following the CAFA protein-centric standard.

    Accepts a FASTA file, a test annotation TSV, and a training annotation TSV.
    Runs NeuralProt and a frequency baseline on identical data so the comparison
    is methodologically sound. Returns Fmax, Smin, and baseline gain per group.
    """
    if not registry:
        raise HTTPException(status_code=503, detail="Models not loaded.")

    fasta_path = save_upload(fasta_file)
    test_path  = save_upload(test_tsv)
    train_path = save_upload(train_tsv)

    try:
        import numpy as np

        sequences_map     = load_fasta(fasta_path)
        test_annotations  = load_annotations_tsv(test_path,  go_col=go_col)
        train_annotations = load_annotations_tsv(train_path, go_col=go_col)

        if propagate and go_dict:
            test_annotations  = propagate_annotations(test_annotations,  go_dict)
            train_annotations = propagate_annotations(train_annotations, go_dict)

        matched_ids = [pid for pid in sequences_map if pid in test_annotations]
        logger.info("Matched IDs: %s", matched_ids)
        if not matched_ids:
            raise HTTPException(
                status_code=400,
                detail="No protein IDs overlap between FASTA and test TSV."
            )

        sequences      = [sequences_map[pid]    for pid in matched_ids]
        test_ann_list  = [test_annotations[pid] for pid in matched_ids]
        train_ann_list = list(train_annotations.values())

        engine         = FmaxEngine()
        feature_matrix = np.stack([extractor.extract(seq) for seq in sequences])
        group_probs    = registry.get_group_probs(feature_matrix)

        group_results = {}

        for group, meta in registry.groups.items():
            probs    = group_probs[group]
            go_terms = meta["go_terms"]

            y_true = np.zeros((len(sequences), len(go_terms)), dtype=int)
            for i, ann_set in enumerate(test_ann_list):
                for j, t in enumerate(go_terms):
                    if t in ann_set:
                        y_true[i, j] = 1

            ic_table = engine.build_ic_table(train_ann_list, go_terms)

            dp_results = engine.sweep(
                prob_matrix=probs,
                y_true_matrix=y_true,
                go_terms=go_terms,
                ic_table=ic_table,
            )

            baseline = FrequencyBaseline(
                train_annotations=train_ann_list,
                go_terms=go_terms,
            )
            baseline.fit()
            bl_results = baseline.evaluate(
                test_annotations=test_ann_list,
                go_terms=go_terms,
                engine=engine,
                ic_table=ic_table,
            )

            group_results[group] = {
                "NeuralProt": {
                    "fmax":           dp_results["fmax"],
                    "fmax_threshold": dp_results["fmax_threshold"],
                    "fmax_precision": dp_results["fmax_precision"],
                    "fmax_recall":    dp_results["fmax_recall"],
                    "smin":           dp_results["smin"],
                },
                "baseline": {
                    "fmax": bl_results["fmax"],
                    "smin": bl_results["smin"],
                },
                "fmax_gain_over_baseline": round(
                    dp_results["fmax"] - bl_results["fmax"], 4
                ),
                "smin_improvement": round(
                    bl_results["smin"] - dp_results["smin"], 4
                ),
                "n_test_proteins": len(matched_ids),
                "n_go_terms":      len(go_terms),
            }

        all_fmax     = [r["NeuralProt"]["fmax"] for r in group_results.values()]
        all_smin     = [r["NeuralProt"]["smin"] for r in group_results.values()]
        overall_fmax = round(float(np.mean(all_fmax)), 4)
        overall_smin = round(float(np.mean(all_smin)), 4)

        return {
            "overall_macro_fmax":        overall_fmax,
            "overall_macro_smin":        overall_smin,
            "n_groups_evaluated":        len(group_results),
            "n_groups_beating_baseline": sum(
                1 for r in group_results.values() if r["fmax_gain_over_baseline"] > 0
            ),
            "group_results": group_results,
        }

    finally:
        cleanup(fasta_path, test_path, train_path)