"""
NeuralProt Inference Pipeline
============================
Three operating modes:

  predict   — accepts a protein sequence (or FASTA), returns predicted GO terms
              with confidence scores from all trained group models.

  evaluate  — accepts an annotated test set, computes per-term F1, precision,
              recall, and support across all groups.

  fmax      — accepts an annotated test set and training annotations, computes
              Fmax and Smin (CAFA standard) with frequency baseline comparison.

Usage:
  # Single sequence prediction
  python neuralprot_inference.py predict \\
      --sequence MKTAYIAKQRQISFVKSHFSRQ... \\
      --models_dir ./models

  # FASTA file prediction
  python neuralprot_inference.py predict \\
      --fasta ./test_proteins.fasta \\
      --models_dir ./models \\
      --output_json ./predictions.json

  # Per-term F1 evaluation
  python neuralprot_inference.py evaluate \\
      --fasta ./test_proteins.fasta \\
      --data_tsv ./test_annotations.tsv \\
      --models_dir ./models \\
      --go_dict ./go_dict.json \\
      --propagate \\
      --output_dir ./evaluation_results

  # Fmax/Smin evaluation with baseline
  python neuralprot_inference.py fmax \\
      --fasta ./test_proteins.fasta \\
      --data_tsv ./test_annotations.tsv \\
      --train_tsv ./train_annotations.tsv \\
      --models_dir ./models \\
      --go_dict ./go_dict.json \\
      --propagate \\
      --output_dir ./fmax_results
"""

import sys
import json
import math
import logging
import argparse
import csv
from itertools import product
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

# ── Optional dependencies ──────────────────────────────────────────────────
try:
    from sklearn.metrics import f1_score, precision_score, recall_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

AMINO_ACIDS = list("ACDEFGHIKLMNPQRSTVWY")
VALID_AA_SET = set(AMINO_ACIDS)

_CALIB_SEQ = "ACDEFGHIKLMNPQRSTVWY"

_CALIB_EXPECTED = np.array([
    0.2909762,    # norm_length
    0.0023956,    # norm_mw
   -0.49,         # gravy
    0.15,         # aromaticity
    0.0475,       # norm_instability
    0.49312523,   # norm_pI
   -0.00093326,   # norm_charge_ph7
    0.195,        # norm_aliphatic
], dtype=np.float32)

_CALIB_TOLERANCE = 1e-4


def verify_feature_extractor() -> None:
    extractor = FeatureExtractor()
    computed = extractor.extract(_CALIB_SEQ)[420:428]
    delta = np.abs(computed - _CALIB_EXPECTED)

    if delta.max() > _CALIB_TOLERANCE:
        labels = [
            "norm_length", "norm_mw", "gravy", "aromaticity",
            "norm_instability", "norm_pI", "norm_charge_ph7", "norm_aliphatic",
        ]
        mismatches = [
            f"  {labels[i]}: got {computed[i]:.6f}, expected {_CALIB_EXPECTED[i]:.6f} "
            f"(delta={delta[i]:.2e})"
            for i in range(8) if delta[i] > _CALIB_TOLERANCE
        ]
        raise RuntimeError(
            "FeatureExtractor does not match data_processor.ipynb.\n"
            "Mismatched features:\n" + "\n".join(mismatches)
        )

    logger.info("Feature extractor calibration passed (max delta: %.2e).", delta.max())


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

class FeatureExtractor:
    """
    Converts a raw protein sequence into a 428-dimensional feature vector.
    Normalization matches data_processor.ipynb exactly — no external norm_stats needed.

    Layout:
      [0:20]    Amino acid composition          (20 features)
      [20:420]  Dipeptide composition           (400 features)
      [420:428] Physicochemical properties      (8 features)
    """

    # Molecular weight of each amino acid residue (Da)
    AA_MW = {
        'A': 89.09,  'C': 121.16, 'D': 133.10, 'E': 147.13, 'F': 165.19,
        'G': 75.03,  'H': 155.16, 'I': 131.17, 'K': 146.19, 'L': 131.17,
        'M': 149.21, 'N': 132.12, 'P': 115.13, 'Q': 146.15, 'R': 174.20,
        'S': 105.09, 'T': 119.12, 'V': 117.15, 'W': 204.23, 'Y': 181.19,
    }

    # Kyte-Doolittle hydropathy values
    AA_HYDRO = {
        'A':  1.8, 'C':  2.5, 'D': -3.5, 'E': -3.5, 'F':  2.8,
        'G': -0.4, 'H': -3.2, 'I':  4.5, 'K': -3.9, 'L':  3.8,
        'M':  1.9, 'N': -3.5, 'P': -1.6, 'Q': -3.5, 'R': -4.5,
        'S': -0.8, 'T': -0.7, 'V':  4.2, 'W': -0.9, 'Y': -1.3,
    }

    # Instability index dipeptide weights (Guruprasad et al., 1990)
    INSTABILITY_WEIGHTS = {
        ('G','G'):13.34, ('G','D'):1.0,  ('G','E'):1.0,  ('G','H'):1.0,
        ('G','N'):1.0,   ('G','Q'):1.0,  ('G','R'):1.0,  ('G','S'):1.0,
        ('G','T'):1.0,   ('A','A'):1.0,  ('A','D'):1.0,  ('A','E'):1.0,
        ('A','H'):1.0,   ('A','K'):1.0,  ('A','N'):1.0,  ('A','Q'):1.0,
        ('A','R'):1.0,   ('A','S'):1.0,  ('A','T'):1.0,  ('C','K'):1.0,
        ('D','G'):1.0,   ('E','E'):1.0,  ('E','K'):1.0,  ('E','N'):1.0,
        ('E','Q'):1.0,   ('E','R'):1.0,  ('E','S'):1.0,  ('F','K'):1.0,
        ('H','H'):1.0,   ('H','K'):1.0,  ('H','N'):1.0,  ('H','Q'):1.0,
        ('H','R'):1.0,   ('H','S'):1.0,  ('I','F'):1.0,  ('I','K'):1.0,
        ('I','L'):1.0,   ('I','N'):1.0,  ('I','Q'):1.0,  ('I','R'):1.0,
        ('I','S'):1.0,   ('K','E'):1.0,  ('K','K'):1.0,  ('K','N'):1.0,
        ('K','P'):1.0,   ('K','Q'):1.0,  ('K','R'):1.0,  ('K','S'):1.0,
        ('L','F'):1.0,   ('L','K'):1.0,  ('L','N'):1.0,  ('L','Q'):1.0,
        ('L','R'):1.0,   ('L','S'):1.0,  ('M','K'):1.0,  ('N','D'):1.0,
        ('N','G'):1.0,   ('N','N'):1.0,  ('P','K'):1.0,  ('Q','D'):1.0,
        ('Q','E'):1.0,   ('Q','H'):1.0,  ('Q','K'):1.0,  ('Q','N'):1.0,
        ('Q','Q'):1.0,   ('Q','R'):1.0,  ('Q','S'):1.0,  ('R','H'):1.0,
        ('R','K'):1.0,   ('R','N'):1.0,  ('R','Q'):1.0,  ('R','R'):1.0,
        ('R','S'):1.0,   ('S','D'):1.0,  ('S','E'):1.0,  ('S','N'):1.0,
        ('S','S'):1.0,   ('T','K'):1.0,  ('V','K'):1.0,  ('W','K'):1.0,
        ('Y','K'):1.0,
    }

    def __init__(self):
        self._dipeptides = ["".join(p) for p in product(AMINO_ACIDS, repeat=2)]
        self._dipeptide_index = {dp: i for i, dp in enumerate(self._dipeptides)}


    def extract(self, sequence: str) -> np.ndarray:
        """Return a 428-dimensional float32 feature vector."""
        seq = self._clean(sequence)
        if not seq:
            raise ValueError("Sequence is empty after removing non-standard amino acids.")

        aa_comp = self._amino_acid_composition(seq)   # 20
        dp_comp = self._dipeptide_composition(seq)    # 400
        physico = self._physicochemical(seq)          # 8

        vec = np.concatenate([aa_comp, dp_comp, physico]).astype(np.float32)
        assert vec.shape == (428,), f"Feature dimension mismatch: {vec.shape}"
        return vec

    @staticmethod
    def _clean(seq: str) -> str:
        return "".join(c for c in seq.upper().strip() if c in VALID_AA_SET)

    def _amino_acid_composition(self, seq: str) -> np.ndarray:
        n = len(seq)
        counts = {aa: 0 for aa in AMINO_ACIDS}
        for aa in seq:
            counts[aa] += 1
        return np.array([counts[aa] / n for aa in AMINO_ACIDS], dtype=np.float32)

    def _dipeptide_composition(self, seq: str) -> np.ndarray:
        n_pairs = len(seq) - 1
        counts = np.zeros(400, dtype=np.float32)
        if n_pairs <= 0:
            return counts
        for i in range(n_pairs):
            dp = seq[i:i+2]
            idx = self._dipeptide_index.get(dp)
            if idx is not None:
                counts[idx] += 1
        return counts / n_pairs

    def _physicochemical(self, seq: str) -> np.ndarray:
        """
        Exactly matches data_processor.ipynb compute_features() normalization.
        No BioPython needed — all formulas are self-contained.
        """
        n = len(seq)
        aa_counts = {aa: seq.count(aa) for aa in AMINO_ACIDS}

        # 1. Normalized length
        norm_length = math.log1p(n) / math.log1p(35000)

        # 2. Molecular weight
        mw = sum(self.AA_MW.get(aa, 110.0) for aa in seq) - (n - 1) * 18.02
        norm_mw = mw / 1e6

        # 3. GRAVY score — raw, no scaling
        gravy = sum(self.AA_HYDRO.get(aa, 0.0) for aa in seq) / n

        # 4. Aromaticity — fraction of F, W, Y
        aromaticity = sum(1 for aa in seq if aa in ('F', 'W', 'Y')) / n

        # 5. Instability index
        instability = 0.0
        if n > 1:
            for i in range(n - 1):
                instability += self.INSTABILITY_WEIGHTS.get((seq[i], seq[i+1]), 1.0)
            instability = (10.0 / n) * instability
        norm_instability = instability / 200.0

        # 6. Isoelectric point via binary search
        lo, hi = 0.0, 14.0
        for _ in range(100):
            mid = (lo + hi) / 2.0
            if self._charge_at_ph(seq, mid) > 0:
                lo = mid
            else:
                hi = mid
        norm_pI = ((lo + hi) / 2.0) / 14.0

        # 7. Net charge at pH 7.0 — tanh-scaled
        norm_charge_ph7 = float(np.tanh(self._charge_at_ph(seq, 7.0) / 50.0))

        # 8. Aliphatic index
        aliphatic = (
            aa_counts.get('A', 0) * 1.0 +
            aa_counts.get('V', 0) * 2.9 +
            aa_counts.get('I', 0) * 3.9 +
            aa_counts.get('L', 0) * 3.9
        ) / n * 100
        norm_aliphatic = aliphatic / 300.0

        return np.array([
            norm_length, norm_mw, gravy, aromaticity,
            norm_instability, norm_pI, norm_charge_ph7, norm_aliphatic,
        ], dtype=np.float32)

    @staticmethod
    def _charge_at_ph(seq: str, ph: float) -> float:
        """Net charge of a protein at a given pH. Matches data_processor.ipynb exactly."""
        charge = 0.0
        charge += 1.0 / (1.0 + 10 ** (ph - 8.0))   # N-terminus
        charge -= 1.0 / (1.0 + 10 ** (3.1 - ph))    # C-terminus
        for aa in seq:
            if   aa == 'K': charge += 1.0 / (1.0 + 10 ** (ph - 10.5))
            elif aa == 'R': charge += 1.0 / (1.0 + 10 ** (ph - 12.5))
            elif aa == 'H': charge += 1.0 / (1.0 + 10 ** (ph - 6.0))
            elif aa == 'D': charge -= 1.0 / (1.0 + 10 ** (3.9 - ph))
            elif aa == 'E': charge -= 1.0 / (1.0 + 10 ** (4.1 - ph))
            elif aa == 'C': charge -= 1.0 / (1.0 + 10 ** (8.3 - ph))
            elif aa == 'Y': charge -= 1.0 / (1.0 + 10 ** (10.1 - ph))
        return charge


# ─────────────────────────────────────────────────────────────────────────────
# MODEL DEFINITION  (must exactly match training architecture)
# ─────────────────────────────────────────────────────────────────────────────

class NeuralProtMLP(nn.Module):
    """
    428 → 1024 (BN, ReLU, Drop 30%)
        → 512  (BN, ReLU, Drop 30%)
        → 256  (BN, ReLU, Drop 20%)
        → num_classes  (raw logits)
    """

    def __init__(self, num_classes: int, input_dim: int = 428):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 1024),
            nn.BatchNorm1d(1024),
            nn.ReLU(),
            nn.Dropout(0.30),

            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.30),

            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.20),

            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


# ─────────────────────────────────────────────────────────────────────────────
# MODEL REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ModelRegistry:
    """
    Discovers and loads all NeuralProt group models from a directory.

    Expected layout in models_dir:
      {group}_best.pt          PyTorch model weights
      {group}_terms.json       Ordered list of GO term IDs for this group
      threshold_results.json   {"group": {"best_threshold": 0.87, ...}, ...}

    Threshold key resolution order:
      1. "best_threshold"
      2. "threshold"
      3. "optimal_threshold"
      4. Falls back to 0.5 with a warning

    If threshold_results.json is absent entirely, all groups use 0.5
    and a prominent warning is printed.
    """

    # Keys to check in threshold_results.json per group entry
    THRESHOLD_KEYS = ("best_threshold", "threshold", "optimal_threshold")

    def __init__(self, models_dir: str, device: str = "cpu"):
        self.models_dir = Path(models_dir)
        self.device = torch.device(device)
        self.groups: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        thresholds = self._load_thresholds()

        pt_files = sorted(self.models_dir.glob("*_best.pt"))
        if not pt_files:
            raise FileNotFoundError(
                f"No *_best.pt files found in {self.models_dir}. "
                "Check that --models_dir points to the correct folder."
            )

        n_loaded = 0
        for pt_path in pt_files:
            group = pt_path.stem.replace("_best", "")
            terms_path = self.models_dir / f"{group}_terms.json"

            if not terms_path.exists():
                logger.warning(
                    f"Skipping group '{group}': {terms_path.name} not found."
                )
                continue

            with open(terms_path) as f:
                go_terms = json.load(f)

            num_classes = len(go_terms)
            model = NeuralProtMLP(num_classes=num_classes)
            checkpoint = torch.load(pt_path, map_location=self.device, weights_only=False)

            # Handle both raw state_dict and wrapped checkpoint dicts
            if isinstance(checkpoint, dict):
                state_dict = (
                    checkpoint.get("model_state_dict")
                    or checkpoint.get("state_dict")
                    or checkpoint.get("model_state")
                    or checkpoint
                )
            else:
                state_dict = checkpoint

            try:
                model.load_state_dict(state_dict)
            except RuntimeError as e:
                logger.error(
                    f"Failed to load weights for '{group}'. "
                    f"The checkpoint structure may differ from the model definition.\n"
                    f"Error: {e}"
                )
                continue

            model.to(self.device)
            model.eval()

            threshold = self._resolve_threshold(group, thresholds)

            self.groups[group] = {
                "model":      model,
                "go_terms":   go_terms,
                "threshold":  threshold,
                "num_classes": num_classes,
            }
            n_loaded += 1

        logger.info(
            f"Loaded {n_loaded} group models from {self.models_dir}: "
            f"{sorted(self.groups.keys())}"
        )

    def _load_thresholds(self) -> dict:
        path = self.models_dir / "threshold_results.json"
        if not path.exists():
            logger.warning(
                "threshold_results.json not found. All groups will use threshold=0.5. "
                "This will significantly underperform tuned thresholds — "
                "ensure this file is present for real predictions."
            )
            return {}
        with open(path) as f:
            data = json.load(f)
        logger.info(f"Threshold file loaded: {len(data)} group entries.")
        return data

    def _resolve_threshold(self, group: str, thresholds: dict) -> float:
        entry = thresholds.get(group, {})
        if not entry:
            return 0.5

        # Handle nested structure: {"optimal_threshold": {"threshold": 0.87, ...}}
        for key in ("optimal_threshold", "default_threshold"):
            if key in entry:
                val = entry[key]
                if isinstance(val, dict):
                    return float(val["threshold"])
                return float(val)

        # Handle flat structure: {"best_threshold": 0.87}
        for key in self.THRESHOLD_KEYS:
            if key in entry:
                val = entry[key]
                if isinstance(val, dict):
                    return float(val.get("threshold", 0.5))
                return float(val)

        logger.warning(
            f"Group '{group}': could not resolve threshold from entry. Using 0.5."
        )
        return 0.5

    # ── Inference ────────────────────────────────────────────────────────────

    def predict_single(self, features: np.ndarray) -> list[dict]:
        """
        Run one feature vector through all group models.
        Returns a flat list of positive predictions, sorted by confidence.
        """
        x = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)
        results = []
        with torch.no_grad():
            for group, meta in self.groups.items():
                logits = meta["model"](x)
                probs  = torch.sigmoid(logits).squeeze(0).cpu().numpy()
                thresh = meta["threshold"]
                for go_term, prob in zip(meta["go_terms"], probs):
                    if prob >= thresh:
                        results.append({
                            "go_term":    go_term,
                            "group":      group,
                            "confidence": round(float(prob), 4),
                            "threshold":  thresh,
                        })
        return sorted(results, key=lambda r: r["confidence"], reverse=True)

    def get_group_probs(self, feature_matrix: np.ndarray) -> dict[str, np.ndarray]:
        """
        Returns raw sigmoid probability arrays per group.
        Shape: (n_proteins, num_classes_in_group)
        Used by NeuralProtEvaluator for per-term F1.
        """
        x = torch.tensor(feature_matrix, dtype=torch.float32).to(self.device)
        group_probs = {}
        with torch.no_grad():
            for group, meta in self.groups.items():
                logits = meta["model"](x)
                group_probs[group] = torch.sigmoid(logits).cpu().numpy()
        return group_probs


# ─────────────────────────────────────────────────────────────────────────────
# EVALUATOR — per-term F1, precision, recall, support
# ─────────────────────────────────────────────────────────────────────────────

class NeuralProtEvaluator:
    """
    Full evaluation pipeline for an annotated test set.

    Produces three output files in output_dir:
      per_term_f1.csv          One row per GO term: F1, precision, recall, support
      group_summary.json       Macro F1 per group + metadata
      evaluation_summary.json  Overall system metrics for the paper

    ⚠ IMPORTANT: Only call this on a held-out test set that was NOT used for
    threshold tuning. The thresholds in threshold_results.json were identified
    on the validation split. Evaluating on the same split produces optimistic F1.
    If you haven't created a separate test split, do so before calling evaluate.
    """

    def __init__(self, registry: ModelRegistry, go_dict: dict = None):
        self.registry = registry
        self.go_dict  = go_dict or {}

    def evaluate(
        self,
        protein_ids: list[str],
        sequences:   list[str],
        annotations: list[set],
        extractor:   FeatureExtractor,
        output_dir:  str = "./evaluation_results",
    ) -> dict:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Feature extraction
        logger.info(f"Extracting features for {len(sequences)} proteins...")
        try:
            feature_matrix = np.stack([extractor.extract(seq) for seq in sequences])
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            raise

        # Inference
        logger.info("Running inference across all group models...")
        group_probs = self.registry.get_group_probs(feature_matrix)

        all_term_rows   = []
        group_summaries = {}

        for group, meta in self.registry.groups.items():
            probs     = group_probs[group]          # (N, C)
            go_terms  = meta["go_terms"]
            threshold = meta["threshold"]
            y_pred    = (probs >= threshold).astype(int)

            # Build ground-truth matrix
            y_true = np.zeros_like(y_pred, dtype=int)
            for i, ann_set in enumerate(annotations):
                for j, go_term in enumerate(go_terms):
                    if go_term in ann_set:
                        y_true[i, j] = 1

            # Per-term metrics
            term_rows  = []
            valid_f1s  = []

            for j, go_term in enumerate(go_terms):
                support = int(y_true[:, j].sum())
                row = {
                    "go_term":   go_term,
                    "go_name":   self._name(go_term),
                    "namespace": self._namespace(go_term),
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
                "n_terms_zero_f1":      sum(1 for f in valid_f1s if f == 0.0),
                "threshold":            threshold,
            }
            all_term_rows.extend(term_rows)

        # Write outputs
        csv_path = output_path / "per_term_f1.csv"
        self._write_csv(all_term_rows, csv_path)

        summary_path = output_path / "group_summary.json"
        with open(summary_path, "w") as f:
            json.dump(group_summaries, f, indent=2)

        # Overall metrics
        valid_all     = [r for r in all_term_rows if r["f1"] is not None]
        overall_macro = round(float(np.mean([r["f1"] for r in valid_all])), 4) if valid_all else 0.0

        overview = {
            "n_proteins_evaluated":    len(sequences),
            "n_go_terms_in_models":    len(all_term_rows),
            "n_terms_with_test_support": len(valid_all),
            "overall_macro_f1":        overall_macro,
            "n_terms_f1_above_0.7":    sum(1 for r in valid_all if r["f1"] >= 0.7),
            "n_terms_f1_above_0.5":    sum(1 for r in valid_all if r["f1"] >= 0.5),
            "n_terms_f1_zero":         sum(1 for r in valid_all if r["f1"] == 0.0),
            "group_summary":           group_summaries,
        }
        with open(output_path / "evaluation_summary.json", "w") as f:
            json.dump(overview, f, indent=2)

        self._print_table(group_summaries, overall_macro)
        logger.info(f"All evaluation files written to {output_path}/")
        return overview


    def evaluate_with_fmax(
        self,
        protein_ids: list[str],
        sequences: list[str],
        annotations: list[set],
        train_annotations: list[set],
        extractor: FeatureExtractor,
        output_dir: str = "./evaluation_results",
    ) -> dict:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        engine = FmaxEngine()

        logger.info("Extracting features for %d proteins...", len(sequences))
        feature_matrix = np.stack([extractor.extract(seq) for seq in sequences])
        group_probs = self.registry.get_group_probs(feature_matrix)

        group_results = {}
        all_per_term_rows = []

        for group, meta in self.registry.groups.items():
            probs    = group_probs[group]
            go_terms = meta["go_terms"]

            # Ground truth matrix
            y_true = np.zeros((len(sequences), len(go_terms)), dtype=int)
            for i, ann_set in enumerate(annotations):
                for j, t in enumerate(go_terms):
                    if t in ann_set:
                        y_true[i, j] = 1

            # IC table from training annotations
            ic_table = engine.build_ic_table(train_annotations, go_terms)

            # NeuralProt Fmax/Smin
            NeuralProt_results = engine.sweep(
                prob_matrix=probs,
                y_true_matrix=y_true,
                go_terms=go_terms,
                ic_table=ic_table,
            )

            # Frequency baseline
            baseline = FrequencyBaseline(
                train_annotations=train_annotations,
                go_terms=go_terms,
            )
            baseline.fit()
            baseline_results = baseline.evaluate(
                test_annotations=annotations,
                go_terms=go_terms,
                engine=engine,
                ic_table=ic_table,
            )

            # Per-term Fmax
            for j, go_term in enumerate(go_terms):
                support = int(y_true[:, j].sum())
                term_fmax = engine.per_term_fmax(probs[:, j], y_true[:, j])
                all_per_term_rows.append({
                    "go_term":   go_term,
                    "go_name":   self._name(go_term),
                    "namespace": self._namespace(go_term),
                    "group":     group,
                    "support":   support,
                    "fmax":      term_fmax,
                })

            group_results[group] = {
                "NeuralProt": {
                    "fmax":           NeuralProt_results["fmax"],
                    "fmax_threshold": NeuralProt_results["fmax_threshold"],
                    "fmax_precision": NeuralProt_results["fmax_precision"],
                    "fmax_recall":    NeuralProt_results["fmax_recall"],
                    "smin":           NeuralProt_results["smin"],
                },
                "baseline": {
                    "fmax":           baseline_results["fmax"],
                    "fmax_threshold": baseline_results["fmax_threshold"],
                    "smin":           baseline_results["smin"],
                },
                "fmax_gain_over_baseline": round(
                    NeuralProt_results["fmax"] - baseline_results["fmax"], 4
                ),
                "smin_improvement": round(
                    baseline_results["smin"] - NeuralProt_results["smin"], 4
                ),
                "n_terms": len(go_terms),
            }

            # Save threshold curves for plotting
            curve_path = output_path / f"{group}_fmax_curve.json"
            with open(curve_path, "w") as f:
                json.dump({
                    "NeuralProt_curve": NeuralProt_results["curve"],
                    "baseline_curve": baseline_results["curve"],
                }, f, indent=2)

        # Write outputs
        per_term_path = output_path / "per_term_fmax.csv"
        fieldnames = ["go_term", "go_name", "namespace", "group", "support", "fmax"]
        with open(per_term_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            rows_sorted = sorted(
                all_per_term_rows,
                key=lambda r: (r["fmax"] is None, -(r["fmax"] or 0.0)),
            )
            writer.writerows(rows_sorted)

        comparison_path = output_path / "fmax_comparison.json"
        with open(comparison_path, "w") as f:
            json.dump(group_results, f, indent=2)

        self._print_fmax_table(group_results)
        logger.info("Fmax evaluation files written to %s/", output_path)
        return group_results

    @staticmethod
    def _print_fmax_table(group_results: dict):
        col_w = 30
        print("\n" + "=" * 80)
        print(
            f"{'GROUP':<{col_w}} {'DP Fmax':>8} {'BL Fmax':>8} "
            f"{'GAIN':>8} {'DP Smin':>8} {'BL Smin':>8}"
        )
        print("=" * 80)
        for group, r in sorted(
            group_results.items(),
            key=lambda x: -x[1]["NeuralProt"]["fmax"]
        ):
            dp = r["NeuralProt"]
            bl = r["baseline"]
            gain = r["fmax_gain_over_baseline"]
            gain_str = f"+{gain:.4f}" if gain >= 0 else f"{gain:.4f}"
            print(
                f"{group:<{col_w}} {dp['fmax']:>8.4f} {bl['fmax']:>8.4f} "
                f"{gain_str:>8} {dp['smin']:>8.4f} {bl['smin']:>8.4f}"
            )
        print("=" * 80 + "\n")


    def _name(self, go_term: str) -> str:
        return self.go_dict.get(go_term, {}).get("name", "")

    def _namespace(self, go_term: str) -> str:
        return self.go_dict.get(go_term, {}).get("namespace", "")

    @staticmethod
    def _write_csv(rows: list[dict], path: Path):
        fieldnames = [
            "go_term", "go_name", "namespace", "group",
            "support", "f1", "precision", "recall", "threshold",
        ]
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            # Sort: supported terms first (by F1 desc), then unsupported
            rows_sorted = sorted(
                rows,
                key=lambda r: (r["f1"] is None, -(r["f1"] or 0.0)),
            )
            writer.writerows(rows_sorted)

    @staticmethod
    def _print_table(group_summaries: dict, overall_macro: float):
        col_w = 35
        print("\n" + "=" * 75)
        print(
            f"{'GROUP':<{col_w}} {'MACRO F1':>10} "
            f"{'TERMS':>7} {'W/SUPPORT':>10} {'ZERO F1':>8}"
        )
        print("=" * 75)
        for group, s in sorted(group_summaries.items(), key=lambda x: -x[1]["macro_f1"]):
            print(
                f"{group:<{col_w}} {s['macro_f1']:>10.4f} "
                f"{s['n_terms_in_model']:>7} {s['n_terms_with_support']:>10} "
                f"{s['n_terms_zero_f1']:>8}"
            )
        print("=" * 75)
        print(f"{'OVERALL MACRO F1':<{col_w}} {overall_macro:>10.4f}")
        print("=" * 75 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# FMAX / SMIN ENGINE  (CAFA protein-centric standard)
# ─────────────────────────────────────────────────────────────────────────────

class FmaxEngine:
    """
    Computes Fmax and Smin following the CAFA protein-centric standard.

    Fmax: maximum F1 over all thresholds, where F1 is computed by averaging
          precision and recall across proteins rather than across terms.

    Smin: minimum semantic distance over all thresholds, weighted by GO term
          information content. Captures how wrong predictions are in biological
          terms, not just binary right/wrong.

    Both metrics are threshold-independent and directly comparable across
    NeuralProt and any baseline evaluated on the same proteins.
    """

    THRESHOLD_STEPS = 101  # 0.00, 0.01, 0.02, ... 1.00

    def __init__(self):
        pass

    # ── Information Content ───────────────────────────────────────────────────

    def build_ic_table(
        self,
        annotations: list[set],
        go_terms: list[str],
    ) -> dict[str, float]:
        """
        Compute information content for each GO term from annotation frequencies.

        IC(t) = -log2( freq(t) )
        where freq(t) = proteins annotated with t / total proteins.

        Terms that never appear in annotations get IC = 0 (no information).
        The maximum IC across all terms is stored for Smin normalisation.
        """
        n = len(annotations)
        if n == 0:
            return {}

        counts = {t: 0 for t in go_terms}
        for ann_set in annotations:
            for t in ann_set:
                if t in counts:
                    counts[t] += 1

        ic = {}
        for t, count in counts.items():
            if count > 0:
                ic[t] = -math.log2(count / n)
            else:
                ic[t] = 0.0

        return ic

    # ── Core Sweep ────────────────────────────────────────────────────────────

    def sweep(
        self,
        prob_matrix: np.ndarray,       # (n_proteins, n_terms)
        y_true_matrix: np.ndarray,     # (n_proteins, n_terms)  binary
        go_terms: list[str],
        ic_table: dict[str, float] = None,
    ) -> dict:
        """
        Sweep thresholds from 0 to 1. At each step compute:
          - protein-centric precision, recall, F
          - ru (remaining uncertainty) and mi (misinformation) for Smin

        Returns a dict of lists, one value per threshold step, plus
        Fmax and Smin extracted from the curves.
        """
        thresholds = np.linspace(0.0, 1.0, self.THRESHOLD_STEPS)
        n_proteins, n_terms = prob_matrix.shape

        # Pre-compute per-protein true counts (constant across thresholds)
        true_counts = y_true_matrix.sum(axis=1).astype(float)  # (n_proteins,)

        # Per-term IC array for Smin (zeros if ic_table not provided)
        ic_array = np.zeros(n_terms, dtype=float)
        if ic_table:
            for j, t in enumerate(go_terms):
                ic_array[j] = ic_table.get(t, 0.0)

        curve = {
            "threshold":  [],
            "precision":  [],
            "recall":     [],
            "f":          [],
            "ru":         [],  # remaining uncertainty
            "mi":         [],  # misinformation
            "s":          [],  # semantic distance = sqrt(ru^2 + mi^2)
        }

        for thresh in thresholds:
            pred_matrix = (prob_matrix >= thresh).astype(float)  # (n, c)

            # ── Protein-centric precision and recall ──────────────────────────
            tp_per_protein  = (pred_matrix * y_true_matrix).sum(axis=1)  # (n,)
            pred_per_protein = pred_matrix.sum(axis=1)                   # (n,)

            # Precision: only proteins that predicted at least one term
            has_pred = pred_per_protein > 0
            if has_pred.sum() > 0:
                prec_vals = tp_per_protein[has_pred] / pred_per_protein[has_pred]
                avg_precision = prec_vals.mean()
            else:
                avg_precision = 0.0

            # Recall: all proteins (proteins with no true annotations
            # contribute 0 recall and are included in the average)
            has_true = true_counts > 0
            if has_true.sum() > 0:
                rec_vals = np.where(
                    has_true,
                    tp_per_protein / np.where(has_true, true_counts, 1.0),
                    0.0,
                )
                avg_recall = rec_vals.mean()
            else:
                avg_recall = 0.0

            if avg_precision + avg_recall > 0:
                f = 2 * avg_precision * avg_recall / (avg_precision + avg_recall)
            else:
                f = 0.0

            # ── Smin: remaining uncertainty and misinformation ────────────────
            # ru_i = sum of IC for true terms the model missed
            # mi_i = sum of IC for predicted terms that were wrong
            missed  = y_true_matrix * (1 - pred_matrix)  # true but not predicted
            wrong   = pred_matrix * (1 - y_true_matrix)  # predicted but not true

            ru_per_protein = (missed * ic_array).sum(axis=1).mean()
            mi_per_protein = (wrong  * ic_array).sum(axis=1).mean()
            s = math.sqrt(ru_per_protein ** 2 + mi_per_protein ** 2)

            curve["threshold"].append(round(float(thresh), 4))
            curve["precision"].append(round(float(avg_precision), 6))
            curve["recall"].append(round(float(avg_recall), 6))
            curve["f"].append(round(float(f), 6))
            curve["ru"].append(round(float(ru_per_protein), 6))
            curve["mi"].append(round(float(mi_per_protein), 6))
            curve["s"].append(round(float(s), 6))

        # ── Extract Fmax and Smin from curves ─────────────────────────────────
        fmax_idx = int(np.argmax(curve["f"]))
        smin_idx = int(np.argmin(curve["s"]))

        return {
            "fmax":            curve["f"][fmax_idx],
            "fmax_threshold":  curve["threshold"][fmax_idx],
            "fmax_precision":  curve["precision"][fmax_idx],
            "fmax_recall":     curve["recall"][fmax_idx],
            "smin":            curve["s"][smin_idx],
            "smin_threshold":  curve["threshold"][smin_idx],
            "smin_ru":         curve["ru"][smin_idx],
            "smin_mi":         curve["mi"][smin_idx],
            "curve":           curve,  # full curve for plotting
        }

    # ── Per-Term Fmax ─────────────────────────────────────────────────────────

    def per_term_fmax(
        self,
        prob_col: np.ndarray,    # (n_proteins,)
        y_true_col: np.ndarray,  # (n_proteins,)  binary
    ) -> float:
        """
        Fmax for a single GO term — term-centric, not protein-centric.
        Used in per-term analysis to identify which terms are learnable.
        """
        if y_true_col.sum() == 0:
            return None  # no support, cannot evaluate

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
    Naive baseline: for every protein, predict the training-set annotation
    frequency of each GO term, regardless of sequence content.

    This establishes the floor NeuralProt must beat. If NeuralProt cannot
    outperform a model that ignores the sequence entirely, the features
    carry no useful signal.

    The baseline is evaluated using the same FmaxEngine as NeuralProt,
    ensuring the comparison is methodologically identical.

    Usage:
        baseline = FrequencyBaseline(train_annotations, go_terms)
        baseline.fit()
        results = baseline.evaluate(test_annotations, engine)
    """

    def __init__(
        self,
        train_annotations: list[set],
        go_terms: list[str],
    ):
        self.train_annotations = train_annotations
        self.go_terms = go_terms
        self.go_term_index = {t: i for i, t in enumerate(go_terms)}
        self._freq_scores = None   # filled by fit()

    def fit(self):
        """
        Compute per-term frequency from training annotations.
        Frequency = fraction of training proteins annotated with the term.
        """
        n = len(self.train_annotations)
        counts = np.zeros(len(self.go_terms), dtype=float)

        for ann_set in self.train_annotations:
            for t in ann_set:
                idx = self.go_term_index.get(t)
                if idx is not None:
                    counts[idx] += 1

        self._freq_scores = counts / n if n > 0 else counts
        logger.info(
            "Frequency baseline fitted on %d proteins, %d terms. "
            "Top frequency: %.4f",
            n, len(self.go_terms), self._freq_scores.max(),
        )

    def predict_matrix(self, n_proteins: int) -> np.ndarray:
        """
        Return a probability matrix where every protein gets the same
        frequency score for every term. Shape: (n_proteins, n_terms).
        This is what the FmaxEngine sweep expects.
        """
        if self._freq_scores is None:
            raise RuntimeError("Call fit() before predict_matrix().")
        return np.tile(self._freq_scores, (n_proteins, 1))

    def evaluate(
        self,
        test_annotations: list[set],
        go_terms: list[str],
        engine: FmaxEngine,
        ic_table: dict[str, float] = None,
    ) -> dict:
        """
        Build ground truth matrix, generate frequency predictions,
        and run the same FmaxEngine sweep used for NeuralProt.
        """
        if self._freq_scores is None:
            raise RuntimeError("Call fit() before evaluate().")

        n_proteins = len(test_annotations)
        n_terms = len(go_terms)

        # Ground truth matrix
        y_true = np.zeros((n_proteins, n_terms), dtype=int)
        go_term_index = {t: i for i, t in enumerate(go_terms)}
        for i, ann_set in enumerate(test_annotations):
            for t in ann_set:
                j = go_term_index.get(t)
                if j is not None:
                    y_true[i, j] = 1

        prob_matrix = self.predict_matrix(n_proteins)

        results = engine.sweep(
            prob_matrix=prob_matrix,
            y_true_matrix=y_true,
            go_terms=go_terms,
            ic_table=ic_table,
        )
        results["method"] = "frequency_baseline"
        return results

# ─────────────────────────────────────────────────────────────────────────────
# DATA I/O UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def load_fasta(path: str) -> dict[str, str]:
    """Parse a FASTA file. Returns {protein_id: sequence}."""
    seqs = {}
    pid, buf = None, []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if pid:
                    seqs[pid] = "".join(buf)
                pid = line[1:].split()[0]
                buf = []
            elif line:
                buf.append(line)
    if pid:
        seqs[pid] = "".join(buf)
    logger.info(f"FASTA: loaded {len(seqs)} sequences from {path}")
    return seqs


def load_annotations_tsv(path: str, go_col: str = "Gene Ontology IDs") -> dict[str, set]:
    """
    Load GO annotations from a UniProtKB-style TSV.
    Protein ID column is tried in order: Entry, protein_id, ID.
    GO terms expected as semicolon-separated values.
    """
    annotations = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            pid = row.get("Entry") or row.get("protein_id") or row.get("ID", "")
            if not pid:
                continue
            go_set = {
                t.strip() for t in row.get(go_col, "").split(";")
                if t.strip().startswith("GO:")
            }
            annotations[pid] = go_set
    logger.info(f"TSV: loaded annotations for {len(annotations)} proteins from {path}")
    return annotations


def propagate_annotations(
    annotations: dict[str, set],
    go_dict: dict,
) -> dict[str, set]:
    """
    Expand each protein's GO term set with all ancestors (True Path Rule).
    Requires go_dict entries to contain an "ancestors" key (list or set).
    Obsolete terms are filtered out.
    """
    logger.info("Applying annotation propagation...")
    active = {tid for tid, entry in go_dict.items() if not entry.get("is_obsolete", False)}
    propagated = {}
    for pid, go_set in annotations.items():
        expanded = set(go_set)
        for go_term in go_set:
            if go_term in go_dict:
                ancestors = go_dict[go_term].get("ancestors", [])
                if isinstance(ancestors, list):
                    ancestors = set(ancestors)
                expanded.update(ancestors)
        propagated[pid] = expanded & active  # filter to active terms only
    logger.info("Propagation complete.")
    return propagated


# ─────────────────────────────────────────────────────────────────────────────
# CLI COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

def cmd_predict(args):
    verify_feature_extractor()
    extractor = FeatureExtractor()
    registry  = ModelRegistry(args.models_dir, device=args.device)

    all_results = {}

    if args.fasta:
        sequences_map = load_fasta(args.fasta)
        for pid, seq in sequences_map.items():
            try:
                features = extractor.extract(seq)
                preds    = registry.predict_single(features)
                all_results[pid] = preds
                _print_predictions(pid, preds, args.top_n)
            except ValueError as e:
                logger.warning(f"Skipping '{pid}': {e}")

    elif args.sequence:
        try:
            features = extractor.extract(args.sequence)
            preds    = registry.predict_single(features)
            all_results["input_sequence"] = preds
            _print_predictions("Input sequence", preds, args.top_n)
        except ValueError as e:
            logger.error(f"Feature extraction failed: {e}")
            sys.exit(1)

    else:
        logger.error("Provide either --sequence or --fasta.")
        sys.exit(1)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(all_results, f, indent=2)
        logger.info(f"Predictions saved to {args.output_json}")


def cmd_evaluate(args):
    if not SKLEARN_AVAILABLE:
        logger.error(
            "scikit-learn is required for evaluation.\n"
            "Install with: pip install scikit-learn"
        )
        sys.exit(1)

    verify_feature_extractor()
    extractor = FeatureExtractor()
    registry  = ModelRegistry(args.models_dir, device=args.device)

    go_dict = {}
    if args.go_dict:
        with open(args.go_dict) as f:
            go_dict = json.load(f)
        logger.info(f"GO dictionary: {len(go_dict)} terms loaded.")

    sequences_map  = load_fasta(args.fasta)
    annotations_map = load_annotations_tsv(args.data_tsv, go_col=args.go_col)

    if args.propagate:
        if not go_dict:
            logger.warning("--propagate requires --go_dict. Skipping propagation.")
        else:
            annotations_map = propagate_annotations(annotations_map, go_dict)

    # Match IDs across FASTA and TSV
    matched_ids = [pid for pid in sequences_map if pid in annotations_map]
    if not matched_ids:
        logger.error(
            "No protein IDs overlap between FASTA and TSV. "
            "Check that both files use the same ID format (e.g., UniProt accession)."
        )
        sys.exit(1)

    logger.info(
        f"{len(matched_ids)} proteins matched between FASTA and TSV "
        f"(FASTA: {len(sequences_map)}, TSV: {len(annotations_map)})."
    )

    sequences   = [sequences_map[pid]   for pid in matched_ids]
    annotations = [annotations_map[pid] for pid in matched_ids]

    evaluator = NeuralProtEvaluator(registry, go_dict=go_dict)
    evaluator.evaluate(
        protein_ids=matched_ids,
        sequences=sequences,
        annotations=annotations,
        extractor=extractor,
        output_dir=args.output_dir,
    )


def cmd_fmax(args):
    verify_feature_extractor()

    extractor = FeatureExtractor()
    registry = ModelRegistry(args.models_dir, device=args.device)

    go_dict = {}
    if args.go_dict:
        with open(args.go_dict) as f:
            go_dict = json.load(f)

    sequences_map       = load_fasta(args.fasta)
    test_annotations    = load_annotations_tsv(args.data_tsv,  go_col=args.go_col)
    train_annotations   = load_annotations_tsv(args.train_tsv, go_col=args.go_col)

    if args.propagate and go_dict:
        test_annotations  = propagate_annotations(test_annotations,  go_dict)
        train_annotations = propagate_annotations(train_annotations, go_dict)

    matched_ids = [pid for pid in sequences_map if pid in test_annotations]
    if not matched_ids:
        logger.error("No overlapping IDs between FASTA and test TSV.")
        sys.exit(1)

    sequences        = [sequences_map[pid]    for pid in matched_ids]
    test_ann_list    = [test_annotations[pid] for pid in matched_ids]
    train_ann_list   = list(train_annotations.values())

    evaluator = NeuralProtEvaluator(registry, go_dict=go_dict)
    evaluator.evaluate_with_fmax(
        protein_ids=matched_ids,
        sequences=sequences,
        annotations=test_ann_list,
        train_annotations=train_ann_list,
        extractor=extractor,
        output_dir=args.output_dir,
    )


def _print_predictions(label: str, predictions: list[dict], top_n: int):
    print(f"\n{'='*65}")
    print(f"Protein:          {label}")
    print(f"GO terms predicted: {len(predictions)}")
    print(f"{'─'*65}")
    print(f"{'GO Term':<16} {'Confidence':>11}  {'Group'}")
    print(f"{'─'*65}")
    for pred in predictions[:top_n]:
        print(
            f"{pred['go_term']:<16} {pred['confidence']:>11.4f}  {pred['group']}"
        )
    if len(predictions) > top_n:
        print(f"  ... and {len(predictions) - top_n} more (use --top_n to see more).")
    print(f"{'='*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# ARGUMENT PARSER
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="NeuralProt_inference.py",
        description="NeuralProt: GO term prediction and per-term F1 evaluation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--device", default="cpu", choices=["cpu", "cuda"],
        help="Compute device (default: cpu)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── predict ──────────────────────────────────────────────────────────────
    pred = subparsers.add_parser("predict", help="Predict GO terms for one or more sequences")
    pred.add_argument("--sequence",   type=str, help="Raw amino acid sequence string")
    pred.add_argument("--fasta",      type=str, help="FASTA file with one or more sequences")
    pred.add_argument("--models_dir", required=True, help="Directory containing trained model files")
    pred.add_argument("--top_n",      type=int, default=20, help="Max predictions to display")
    pred.add_argument("--output_json", type=str, help="Save all predictions to a JSON file")
    pred.set_defaults(func=cmd_predict)

    # ── evaluate ─────────────────────────────────────────────────────────────
    evl = subparsers.add_parser(
        "evaluate",
        help="Per-term F1 evaluation on a labeled test set",
    )
    evl.add_argument("--fasta",      required=True, help="FASTA file of test sequences")
    evl.add_argument("--data_tsv",   required=True, help="TSV with protein IDs and GO annotations")
    evl.add_argument("--models_dir", required=True, help="Directory containing trained model files")
    evl.add_argument("--go_dict",    type=str, default=None, help="go_dict.json from go_parser.py")
    evl.add_argument(
        "--propagate", action="store_true",
        help="Apply annotation propagation before evaluation (strongly recommended)",
    )
    evl.add_argument(
        "--go_col", type=str, default="Gene Ontology IDs",
        help="TSV column name containing GO terms (default: 'Gene Ontology IDs')",
    )
    evl.add_argument(
        "--output_dir", default="./evaluation_results",
        help="Directory for output files (default: ./evaluation_results)",
    )
    evl.set_defaults(func=cmd_evaluate)


    # ── fmax ─────────────────────────────────────────────────────────────────
    fmx = subparsers.add_parser(
        "fmax",
        help="Fmax/Smin evaluation with frequency baseline comparison",
    )
    fmx.add_argument("--fasta",            required=True)
    fmx.add_argument("--data_tsv",         required=True,
                     help="Test set annotations (TSV)")
    fmx.add_argument("--train_tsv",        required=True,
                     help="Training set annotations (TSV) — needed for baseline and IC")
    fmx.add_argument("--models_dir",       required=True)
    fmx.add_argument("--go_dict",          type=str, default=None)
    fmx.add_argument("--propagate",        action="store_true")
    fmx.add_argument("--go_col",           default="Gene Ontology IDs")
    fmx.add_argument("--output_dir",       default="./fmax_results")
    fmx.set_defaults(func=cmd_fmax)

    return parser


def main():
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()