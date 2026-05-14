"""
NeuralProt — Test Set Evaluation
================================
Evaluates all 22 trained group models on the held-out test set.
Computes Fmax and Smin (CAFA protein-centric standard) and compares
against a frequency baseline trained on the training split.

This script must only be run ONCE for final paper results.
The test set (test_idx.json) was never used during training or
threshold tuning — it is genuinely held out.

Outputs (written to OUTPUT_DIR):
  test_fmax_summary.json     — Fmax and Smin per group + overall
  test_per_term_fmax.csv     — per-term Fmax across all groups
  test_fmax_comparison.json  — NeuralProt vs baseline per group

Usage:
  python NeuralProt_test_evaluation.py
"""

import os
import sys
import json
import math
import csv
import logging
import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — update these paths to match your machine
# ─────────────────────────────────────────────────────────────────────────────

PROCESSED_DIR = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/processed_data"
MODEL_DIR     = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/backend/models"
OUTPUT_DIR    = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/model/test_evaluation"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

GROUPS = [
    "reproductive_process",
    "interspecies_interaction",
    "immune_system_process",
    "molecular_transducer",
    "mf_regulator_activity",
    "homeostatic_process",
    "atp_dependent_activity",
    "oxidoreductase_activity",
    "transferase_activity",
    "hydrolase_activity",
    "lyase_activity",
    "ion_transport",
    "vesicle_mediated_transport",
    "protein_transport",
    "lipid_transport",
    "nuclear_transport",
    "protein_binding",
    "dna_binding",
    "rna_binding",
    "lipid_binding",
    "metal_ion_binding",
    "small_molecule_binding",
]

# ─────────────────────────────────────────────────────────────────────────────
# MODEL DEFINITION — must match training architecture exactly
# ─────────────────────────────────────────────────────────────────────────────

class ProteinMLP(nn.Module):
    def __init__(self, input_dim=428, num_classes=128, dropout=0.3):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 1024),
            nn.BatchNorm1d(1024),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(dropout),

            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        return self.network(x)


# ─────────────────────────────────────────────────────────────────────────────
# SPLIT HELPER — must exactly match build_dataloaders() in train_model.ipynb
# ─────────────────────────────────────────────────────────────────────────────

def get_split_indices(n_total):
    """
    Reproduce the exact 80/10/10 split used during training.
    Returns train_idx, val_idx, test_idx.
    random_state=42 must never change.
    """
    indices = list(range(n_total))
    train_val_idx, test_idx = train_test_split(
        indices, test_size=0.1, random_state=42
    )
    train_idx, val_idx = train_test_split(
        train_val_idx, test_size=0.111, random_state=42
    )
    return train_idx, val_idx, test_idx


def verify_test_idx(group_name, computed_test_idx, group_dir):
    """
    Cross-check computed test indices against saved test_idx.json.
    Raises RuntimeError if they do not match — prevents silent data leakage.
    """
    test_idx_path = os.path.join(group_dir, "test_idx.json")
    if not os.path.exists(test_idx_path):
        raise FileNotFoundError(
            f"{group_name}: test_idx.json not found at {test_idx_path}. "
            "Run the training notebook with the updated build_dataloaders() first."
        )
    with open(test_idx_path) as f:
        saved = set(json.load(f))
    if set(computed_test_idx) != saved:
        raise RuntimeError(
            f"{group_name}: computed test indices do not match test_idx.json. "
            "The split logic here does not match build_dataloaders(). "
            "Both must use test_size=0.1, random_state=42 as the first split."
        )


# ─────────────────────────────────────────────────────────────────────────────
# FMAX / SMIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class FmaxEngine:
    """
    Computes Fmax and Smin following the CAFA protein-centric standard.
    Identical implementation to neuralprot_inference.py.
    """
    THRESHOLD_STEPS = 101

    def build_ic_table(self, label_matrix, go_terms):
        """IC(t) = -log2(freq(t)) from training annotation frequencies."""
        n = label_matrix.shape[0]
        if n == 0:
            return {}
        counts = label_matrix.sum(axis=0)
        ic = {}
        for j, t in enumerate(go_terms):
            c = counts[j]
            ic[t] = -math.log2(c / n) if c > 0 else 0.0
        return ic

    def sweep(self, prob_matrix, y_true_matrix, go_terms, ic_table=None):
        thresholds  = np.linspace(0.0, 1.0, self.THRESHOLD_STEPS)
        n_proteins, n_terms = prob_matrix.shape
        true_counts = y_true_matrix.sum(axis=1).astype(float)

        ic_array = np.zeros(n_terms, dtype=float)
        if ic_table:
            for j, t in enumerate(go_terms):
                ic_array[j] = ic_table.get(t, 0.0)

        curve = {"threshold": [], "f": [], "s": [],
                 "precision": [], "recall": [], "ru": [], "mi": []}

        for thresh in thresholds:
            pred = (prob_matrix >= thresh).astype(float)
            tp   = (pred * y_true_matrix).sum(axis=1)
            n_pred = pred.sum(axis=1)

            has_pred = n_pred > 0
            avg_prec = (tp[has_pred] / n_pred[has_pred]).mean() if has_pred.sum() > 0 else 0.0

            has_true = true_counts > 0
            rec_vals = np.where(has_true, tp / np.where(has_true, true_counts, 1.0), 0.0)
            avg_rec  = rec_vals.mean() if has_true.sum() > 0 else 0.0

            f = (2 * avg_prec * avg_rec / (avg_prec + avg_rec)
                 if avg_prec + avg_rec > 0 else 0.0)

            missed = y_true_matrix * (1 - pred)
            wrong  = pred * (1 - y_true_matrix)
            ru = (missed * ic_array).sum(axis=1).mean()
            mi = (wrong  * ic_array).sum(axis=1).mean()
            s  = math.sqrt(ru ** 2 + mi ** 2)

            curve["threshold"].append(round(float(thresh), 4))
            curve["precision"].append(round(float(avg_prec), 6))
            curve["recall"].append(round(float(avg_rec), 6))
            curve["f"].append(round(float(f), 6))
            curve["ru"].append(round(float(ru), 6))
            curve["mi"].append(round(float(mi), 6))
            curve["s"].append(round(float(s), 6))

        fmax_idx = int(np.argmax(curve["f"]))
        smin_idx = int(np.argmin(curve["s"]))

        return {
            "fmax":           curve["f"][fmax_idx],
            "fmax_threshold": curve["threshold"][fmax_idx],
            "fmax_precision": curve["precision"][fmax_idx],
            "fmax_recall":    curve["recall"][fmax_idx],
            "smin":           curve["s"][smin_idx],
            "smin_threshold": curve["threshold"][smin_idx],
            "curve":          curve,
        }

    def per_term_fmax(self, prob_col, y_true_col):
        if y_true_col.sum() == 0:
            return None
        thresholds = np.linspace(0.0, 1.0, self.THRESHOLD_STEPS)
        best_f = 0.0
        for thresh in thresholds:
            pred = (prob_col >= thresh).astype(int)
            tp = int((pred * y_true_col).sum())
            fp = int((pred * (1 - y_true_col)).sum())
            fn = int(((1 - pred) * y_true_col).sum())
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f    = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            best_f = max(best_f, f)
        return round(best_f, 4)


# ─────────────────────────────────────────────────────────────────────────────
# FREQUENCY BASELINE
# ─────────────────────────────────────────────────────────────────────────────

class FrequencyBaseline:
    """
    Predicts the training-set frequency of each GO term for every protein.
    Evaluated identically to NeuralProt using FmaxEngine.sweep().
    """

    def __init__(self, train_label_matrix, go_terms):
        n = train_label_matrix.shape[0]
        counts = train_label_matrix.sum(axis=0)
        self.freq_scores = counts / n if n > 0 else counts
        self.go_terms    = go_terms

    def predict_matrix(self, n_proteins):
        return np.tile(self.freq_scores, (n_proteins, 1))

    def evaluate(self, test_label_matrix, engine, ic_table=None):
        prob_matrix = self.predict_matrix(test_label_matrix.shape[0])
        return engine.sweep(
            prob_matrix=prob_matrix,
            y_true_matrix=test_label_matrix.astype(float),
            go_terms=self.go_terms,
            ic_table=ic_table,
        )


# ─────────────────────────────────────────────────────────────────────────────
# INFERENCE ON TEST SET
# ─────────────────────────────────────────────────────────────────────────────

def run_inference(model_path, feature_matrix_test, n_classes):
    """Load best model and return sigmoid probabilities for test proteins."""
    checkpoint = torch.load(model_path, map_location=DEVICE, weights_only=False)
    model = ProteinMLP(num_classes=n_classes).to(DEVICE)

    state = (checkpoint.get("model_state")
             or checkpoint.get("model_state_dict")
             or checkpoint)
    model.load_state_dict(state)
    model.eval()

    x = torch.tensor(feature_matrix_test, dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        logits = model(x)
        probs  = torch.sigmoid(logits).cpu().numpy()
    return probs


# ─────────────────────────────────────────────────────────────────────────────
# PRINT TABLE
# ─────────────────────────────────────────────────────────────────────────────

def print_results_table(group_results, overall_fmax, overall_smin):
    col_w = 30
    print("\n" + "=" * 85)
    print(f"  TEST SET EVALUATION RESULTS  (Fmax / Smin — CAFA protein-centric)")
    print("=" * 85)
    print(
        f"  {'GROUP':<{col_w}} {'NP Fmax':>8} {'BL Fmax':>8} "
        f"{'GAIN':>8} {'NP Smin':>8} {'BL Smin':>8} {'N Test':>7}"
    )
    print("  " + "-" * 83)
    for group, r in sorted(group_results.items(),
                            key=lambda x: -x[1]["NeuralProt"]["fmax"]):
        dp   = r["NeuralProt"]
        bl   = r["baseline"]
        gain = r["fmax_gain_over_baseline"]
        gain_str = f"+{gain:.4f}" if gain >= 0 else f"{gain:.4f}"
        print(
            f"  {group:<{col_w}} {dp['fmax']:>8.4f} {bl['fmax']:>8.4f} "
            f"{gain_str:>8} {dp['smin']:>8.4f} {bl['smin']:>8.4f} "
            f"{r['n_test_proteins']:>7,}"
        )
    print("  " + "=" * 83)
    print(f"  {'OVERALL (macro across groups)':<{col_w}} {overall_fmax:>8.4f}")
    print(f"  {'OVERALL Smin (macro)':<{col_w}} {overall_smin:>8.4f}")
    print("=" * 85 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    engine = FmaxEngine()

    group_results    = {}
    all_term_rows    = []
    failed_groups    = []

    for group_name in GROUPS:
        logger.info("Processing: %s", group_name)
        group_dir  = os.path.join(PROCESSED_DIR, group_name)
        model_path = os.path.join(MODEL_DIR, f"{group_name}_best.pt")

        # ── Verify files exist ────────────────────────────────────────────────
        missing = [f for f in [
            os.path.join(group_dir, "features.npy"),
            os.path.join(group_dir, "labels.npy"),
            os.path.join(group_dir, "go_terms.json"),
            os.path.join(group_dir, "test_idx.json"),
            model_path,
        ] if not os.path.exists(f)]

        if missing:
            logger.error("Skipping %s — missing files: %s", group_name, missing)
            failed_groups.append(group_name)
            continue

        # ── Load data ─────────────────────────────────────────────────────────
        feature_matrix = np.load(os.path.join(group_dir, "features.npy"))
        label_matrix   = np.load(os.path.join(group_dir, "labels.npy"))

        with open(os.path.join(group_dir, "go_terms.json")) as f:
            go_terms = json.load(f)

        n_total   = len(label_matrix)
        n_classes = len(go_terms)

        # ── Reproduce split and verify ────────────────────────────────────────
        train_idx, val_idx, test_idx = get_split_indices(n_total)

        try:
            verify_test_idx(group_name, test_idx, group_dir)
        except RuntimeError as e:
            logger.error(str(e))
            failed_groups.append(group_name)
            continue

        # ── Slice to splits ───────────────────────────────────────────────────
        feature_test  = feature_matrix[test_idx]
        label_test    = label_matrix[test_idx].astype(float)
        label_train   = label_matrix[train_idx].astype(float)

        logger.info(
            "  Split — Train: %d  Val: %d  Test: %d",
            len(train_idx), len(val_idx), len(test_idx)
        )

        # ── Build IC table from training labels ───────────────────────────────
        ic_table = engine.build_ic_table(label_train, go_terms)

        # ── Run NeuralProt inference on test set ────────────────────────────────
        probs = run_inference(model_path, feature_test, n_classes)

        # ── NeuralProt Fmax / Smin ──────────────────────────────────────────────
        dp_results = engine.sweep(
            prob_matrix=probs,
            y_true_matrix=label_test,
            go_terms=go_terms,
            ic_table=ic_table,
        )

        # ── Frequency baseline ────────────────────────────────────────────────
        baseline    = FrequencyBaseline(label_train, go_terms)
        bl_results  = baseline.evaluate(label_test, engine, ic_table=ic_table)

        # ── Per-term Fmax ─────────────────────────────────────────────────────
        for j, go_term in enumerate(go_terms):
            support   = int(label_test[:, j].sum())
            term_fmax = engine.per_term_fmax(probs[:, j], label_test[:, j])
            all_term_rows.append({
                "go_term":   go_term,
                "group":     group_name,
                "support":   support,
                "fmax":      term_fmax,
            })

        group_results[group_name] = {
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
            "n_test_proteins": len(test_idx),
            "n_go_terms":      n_classes,
        }

        logger.info(
            "  Fmax: %.4f (baseline: %.4f, gain: %+.4f)  Smin: %.4f",
            dp_results["fmax"], bl_results["fmax"],
            group_results[group_name]["fmax_gain_over_baseline"],
            dp_results["smin"],
        )

    # ── Overall metrics ───────────────────────────────────────────────────────
    if not group_results:
        logger.error("No groups evaluated successfully. Check paths and files.")
        sys.exit(1)

    all_fmax = [r["NeuralProt"]["fmax"] for r in group_results.values()]
    all_smin = [r["NeuralProt"]["smin"] for r in group_results.values()]
    overall_fmax = round(float(np.mean(all_fmax)), 4)
    overall_smin = round(float(np.mean(all_smin)), 4)

    n_above_07 = sum(1 for f in all_fmax if f >= 0.7)
    n_above_05 = sum(1 for f in all_fmax if f >= 0.5)
    n_beats_baseline = sum(
        1 for r in group_results.values()
        if r["fmax_gain_over_baseline"] > 0
    )

    # ── Write outputs ─────────────────────────────────────────────────────────
    summary = {
        "overall_macro_fmax":        overall_fmax,
        "overall_macro_smin":        overall_smin,
        "n_groups_evaluated":        len(group_results),
        "n_groups_fmax_above_0.7":   n_above_07,
        "n_groups_fmax_above_0.5":   n_above_05,
        "n_groups_beating_baseline": n_beats_baseline,
        "failed_groups":             failed_groups,
        "group_results":             group_results,
    }

    summary_path = os.path.join(OUTPUT_DIR, "test_fmax_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    comparison_path = os.path.join(OUTPUT_DIR, "test_fmax_comparison.json")
    with open(comparison_path, "w") as f:
        json.dump(group_results, f, indent=2)

    per_term_path = os.path.join(OUTPUT_DIR, "test_per_term_fmax.csv")
    with open(per_term_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["go_term", "group", "support", "fmax"])
        writer.writeheader()
        rows_sorted = sorted(
            all_term_rows,
            key=lambda r: (r["fmax"] is None, -(r["fmax"] or 0.0)),
        )
        writer.writerows(rows_sorted)

    # ── Print summary table ───────────────────────────────────────────────────
    print_results_table(group_results, overall_fmax, overall_smin)

    print(f"  Groups beating frequency baseline : {n_beats_baseline} / {len(group_results)}")
    print(f"  Groups with Fmax ≥ 0.70           : {n_above_07}")
    print(f"  Groups with Fmax ≥ 0.50           : {n_above_05}")
    if failed_groups:
        print(f"\n  Failed groups: {failed_groups}")

    print(f"\n  Output files written to: {OUTPUT_DIR}/")
    print(f"    test_fmax_summary.json")
    print(f"    test_fmax_comparison.json")
    print(f"    test_per_term_fmax.csv")


if __name__ == "__main__":
    main()