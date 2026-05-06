"""
NeuralProt — Per-Term Fmax Analysis
===================================
Reads test_per_term_fmax.csv produced by NeuralProt_test_evaluation.py
and produces a detailed breakdown of which GO terms the models learn
well versus poorly.

Outputs (written to OUTPUT_DIR):
  per_term_summary.json        — statistics per group and overall
  learnable_terms.csv          — terms with Fmax >= 0.70
  weak_terms.csv               — terms with Fmax > 0 but < 0.50
  unlearnable_terms.csv        — terms with Fmax == 0.0 (support > 0)
  no_support_terms.csv         — terms absent from test set

Usage:
  python NeuralProt_per_term_analysis.py
"""

import os
import csv
import json
import numpy as np
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────────────────
TEST_EVAL_DIR = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/model/test_evaluation"
OUTPUT_DIR    = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/model/test_evaluation/per_term_analysis"
GO_DICT_PATH  = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_dict.json"

# Fmax thresholds for classification
STRONG_THRESHOLD = 0.70
WEAK_THRESHOLD   = 0.50
# ─────────────────────────────────────────────────────────────────────────────


def load_go_dict(path):
    if not os.path.exists(path):
        print(f"  Note: go_dict.json not found at {path}")
        print(f"  GO term names will not be included in output.")
        return {}
    with open(path) as f:
        return json.load(f)


def load_per_term_csv(path):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "go_term": row["go_term"],
                "group":   row["group"],
                "support": int(row["support"]),
                "fmax":    float(row["fmax"]) if row["fmax"] not in ("", "None") else None,
            })
    return rows


def get_go_name(go_term, go_dict):
    return go_dict.get(go_term, {}).get("name", "")


def get_namespace(go_term, go_dict):
    return go_dict.get(go_term, {}).get("namespace", "")


def write_csv(rows, path, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved: {path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_path = os.path.join(TEST_EVAL_DIR, "test_per_term_fmax.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found.")
        print("Run NeuralProt_test_evaluation.py first.")
        return

    print("Loading per-term Fmax data...")
    rows    = load_per_term_csv(csv_path)
    go_dict = load_go_dict(GO_DICT_PATH)

    print(f"  Total GO terms in models : {len(rows):,}")

    # ── Categorise every term ─────────────────────────────────────────────────
    no_support   = [r for r in rows if r["support"] == 0]
    with_support = [r for r in rows if r["support"] > 0]

    strong       = [r for r in with_support if r["fmax"] is not None and r["fmax"] >= STRONG_THRESHOLD]
    moderate     = [r for r in with_support if r["fmax"] is not None and WEAK_THRESHOLD <= r["fmax"] < STRONG_THRESHOLD]
    weak         = [r for r in with_support if r["fmax"] is not None and 0 < r["fmax"] < WEAK_THRESHOLD]
    unlearnable  = [r for r in with_support if r["fmax"] is not None and r["fmax"] == 0.0]

    print(f"\n  Terms with test support    : {len(with_support):,}")
    print(f"  Terms without test support : {len(no_support):,}")
    print(f"\n  Of {len(with_support):,} supported terms:")
    print(f"    Fmax ≥ 0.70  (strong)      : {len(strong):,}  ({100*len(strong)/max(len(with_support),1):.1f}%)")
    print(f"    Fmax 0.50–0.69 (moderate)  : {len(moderate):,}  ({100*len(moderate)/max(len(with_support),1):.1f}%)")
    print(f"    Fmax 0.01–0.49 (weak)      : {len(weak):,}  ({100*len(weak)/max(len(with_support),1):.1f}%)")
    print(f"    Fmax = 0.0   (unlearnable) : {len(unlearnable):,}  ({100*len(unlearnable)/max(len(with_support),1):.1f}%)")

    # ── Per-group breakdown ───────────────────────────────────────────────────
    print("\n  Per-group breakdown:")
    print(f"  {'GROUP':<35} {'TERMS':>6} {'SUPPORT':>8} {'STRONG':>7} "
          f"{'MOD':>5} {'WEAK':>5} {'ZERO':>5} {'MEAN Fmax':>10}")
    print("  " + "-" * 85)

    group_stats = defaultdict(dict)
    by_group    = defaultdict(list)
    for r in rows:
        by_group[r["group"]].append(r)

    for group in sorted(by_group.keys()):
        grp_rows   = by_group[group]
        grp_supp   = [r for r in grp_rows if r["support"] > 0]
        grp_fmax   = [r["fmax"] for r in grp_supp if r["fmax"] is not None]

        n_strong      = sum(1 for f in grp_fmax if f >= STRONG_THRESHOLD)
        n_moderate    = sum(1 for f in grp_fmax if WEAK_THRESHOLD <= f < STRONG_THRESHOLD)
        n_weak        = sum(1 for f in grp_fmax if 0 < f < WEAK_THRESHOLD)
        n_zero        = sum(1 for f in grp_fmax if f == 0.0)
        mean_fmax     = float(np.mean(grp_fmax)) if grp_fmax else 0.0

        group_stats[group] = {
            "n_terms_total":    len(grp_rows),
            "n_terms_support":  len(grp_supp),
            "n_terms_strong":   n_strong,
            "n_terms_moderate": n_moderate,
            "n_terms_weak":     n_weak,
            "n_terms_zero":     n_zero,
            "mean_term_fmax":   round(mean_fmax, 4),
            "best_term_fmax":   round(max(grp_fmax), 4) if grp_fmax else None,
            "worst_term_fmax":  round(min(grp_fmax), 4) if grp_fmax else None,
        }

        print(
            f"  {group:<35} {len(grp_rows):>6} {len(grp_supp):>8} "
            f"{n_strong:>7} {n_moderate:>5} {n_weak:>5} {n_zero:>5} "
            f"{mean_fmax:>10.4f}"
        )

    # ── Overall statistics ────────────────────────────────────────────────────
    all_fmax = [r["fmax"] for r in with_support if r["fmax"] is not None]
    overall_mean = float(np.mean(all_fmax)) if all_fmax else 0.0
    overall_med  = float(np.median(all_fmax)) if all_fmax else 0.0

    print(f"\n  Overall mean per-term Fmax  : {overall_mean:.4f}")
    print(f"  Overall median per-term Fmax: {overall_med:.4f}")

    # ── Top 20 best terms ─────────────────────────────────────────────────────
    print("\n  Top 20 best-learned GO terms:")
    print(f"  {'GO Term':<15} {'Fmax':>6}  {'Support':>8}  {'Group':<30}  Name")
    print("  " + "-" * 95)
    top20 = sorted(with_support, key=lambda r: -(r["fmax"] or 0.0))[:20]
    for r in top20:
        name = get_go_name(r["go_term"], go_dict)[:35]
        print(
            f"  {r['go_term']:<15} {r['fmax']:>6.4f}  {r['support']:>8,}  "
            f"{r['group']:<30}  {name}"
        )

    # ── Bottom 20 worst supported terms ──────────────────────────────────────
    print("\n  20 worst-learned GO terms (with support > 5):")
    print(f"  {'GO Term':<15} {'Fmax':>6}  {'Support':>8}  {'Group':<30}  Name")
    print("  " + "-" * 95)
    bottom = sorted(
        [r for r in with_support if r["support"] > 5 and r["fmax"] is not None],
        key=lambda r: r["fmax"] or 0.0
    )[:20]
    for r in bottom:
        name = get_go_name(r["go_term"], go_dict)[:35]
        print(
            f"  {r['go_term']:<15} {r['fmax']:>6.4f}  {r['support']:>8,}  "
            f"{r['group']:<30}  {name}"
        )

    # ── Write output CSV files ────────────────────────────────────────────────
    print("\n  Writing output files...")
    fields = ["go_term", "go_name", "namespace", "group", "support", "fmax"]

    def enrich(rows_list):
        return [
            {
                "go_term":   r["go_term"],
                "go_name":   get_go_name(r["go_term"], go_dict),
                "namespace": get_namespace(r["go_term"], go_dict),
                "group":     r["group"],
                "support":   r["support"],
                "fmax":      r["fmax"],
            }
            for r in rows_list
        ]

    write_csv(
        sorted(enrich(strong), key=lambda r: -(r["fmax"] or 0)),
        os.path.join(OUTPUT_DIR, "learnable_terms.csv"),
        fields,
    )
    write_csv(
        sorted(enrich(weak), key=lambda r: -(r["fmax"] or 0)),
        os.path.join(OUTPUT_DIR, "weak_terms.csv"),
        fields,
    )
    write_csv(
        enrich(unlearnable),
        os.path.join(OUTPUT_DIR, "unlearnable_terms.csv"),
        fields,
    )
    write_csv(
        enrich(no_support),
        os.path.join(OUTPUT_DIR, "no_support_terms.csv"),
        fields,
    )

    # ── Save summary JSON ─────────────────────────────────────────────────────
    summary = {
        "total_go_terms_in_models":    len(rows),
        "terms_with_test_support":     len(with_support),
        "terms_without_test_support":  len(no_support),
        "terms_strong_fmax_gte_0.70":  len(strong),
        "terms_moderate_fmax_0.50_0.69": len(moderate),
        "terms_weak_fmax_0.01_0.49":   len(weak),
        "terms_unlearnable_fmax_0.0":  len(unlearnable),
        "overall_mean_term_fmax":      round(overall_mean, 4),
        "overall_median_term_fmax":    round(overall_med, 4),
        "group_breakdown":             dict(group_stats),
    }

    summary_path = os.path.join(OUTPUT_DIR, "per_term_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved: {summary_path}")

    print(f"\n  All files written to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()