"""
GO Term Group Assigner (v2 — with merges applied)
===================================================
Same logic as v1, but three small groups have been merged into
biologically related larger groups:

    viral_process              → interspecies_interaction
    growth                     → homeostatic_process
    molecular_adaptor_activity → mf_regulator_activity

Why merge instead of just dropping them?
    These groups had too few GO terms to train a reliable model on their own,
    but the terms are still biologically meaningful. Merging them into a related
    host group means we don't throw away real training signal — we just fold
    it into a group that can actually learn from it.

Usage:
    python go_group_assigner_v2.py
    Make sure go_dict.json is in the same directory.
"""

import json
from collections import defaultdict


# ── CONFIG ─────────────────────────────────────────────────────────────────────
GO_DICT_PATH = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_dict.json"
DATASET_PATH = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/raw/uniprotkb_AND_reviewed_true_AND_protein_2025_12_27.tsv"
GO_COL_IDX   = 5   # zero-based column index for GO terms in the TSV
# ───────────────────────────────────────────────────────────────────────────────


# ── GROUP DEFINITIONS ──────────────────────────────────────────────────────────
# This is the final set of target groups after removing the three small ones.
# viral_process, growth, and molecular_adaptor_activity no longer exist here —
# their terms will be caught during assignment and redirected via MERGE_MAP below.

TARGET_GROUPS = {
    # ── Still too large to train as-is — need splitting first ────────────────
    "biological_regulation":         "GO:0065007",
    "catalytic_activity":            "GO:0003824",
    "cellular_process":              "GO:0009987",
    "developmental_process":         "GO:0032502",
    "protein_containing_complex":    "GO:0032991",
    "localization":                  "GO:0051179",
    "cellular_anatomical_structure": "GO:0110165",
    "binding":                       "GO:0005488",
    "response_to_stimulus":          "GO:0050896",
    "transporter_activity":          "GO:0005215",
    "multicellular_organismal":      "GO:0032501",

    # ── Ready to train ────────────────────────────────────────────────────────
    "reproductive_process":          "GO:0022414",

    # viral_process (GO:0016032) was merged into this group.
    # Viruses are obligate interspecies pathogens — all viral processes are by
    # definition interspecies interactions. Biologically the most defensible merge.
    "interspecies_interaction":      "GO:0044419",

    "immune_system_process":         "GO:0002376",
    "molecular_transducer":          "GO:0060089",

    # molecular_adaptor_activity (GO:0060090) was merged into this group.
    # Molecular adaptors mediate interactions between proteins, which is a form
    # of molecular function regulation — they sit on the same branch of the hierarchy.
    "mf_regulator_activity":         "GO:0098772",

    "atp_dependent_activity":        "GO:0140657",

    # growth (GO:0040007) was merged into this group.
    # Growth is a primary mechanism of biological homeostasis — organisms grow
    # to maintain proper size and function. Solid biological justification.
    "homeostatic_process":           "GO:0042592",
}


# ── MERGE MAP ──────────────────────────────────────────────────────────────────
# After the tiebreaker picks a "best" group for a GO term, we check this map.
# If the winning group is one of the merged ones, we redirect to the host group.
# This is the actual mechanism that absorbs the small groups' terms.

MERGE_MAP = {
    "viral_process":               "interspecies_interaction",
    "growth":                      "homeostatic_process",
    "molecular_adaptor_activity":  "mf_regulator_activity",
}

# Root IDs for the merged groups — we still need these during assignment so the
# tiebreaker can "see" these groups and pick them as the most specific match
# before MERGE_MAP redirects them to their host.
MERGED_GROUP_ROOTS = {
    "viral_process":               "GO:0016032",
    "growth":                      "GO:0040007",
    "molecular_adaptor_activity":  "GO:0060090",
}

# Combined lookup used during assignment — includes both the real target groups
# and the temporary merged-group roots so nothing slips through
ALL_GROUPS = {**TARGET_GROUPS, **MERGED_GROUP_ROOTS}
# ───────────────────────────────────────────────────────────────────────────────


def load_go_dict(path):
    """
    Load the pre-parsed GO dictionary from go_parser.py's output.
    We rely on this file instead of re-parsing the OBO every time.
    """
    print(f"Loading go_dict from {path} ...")
    with open(path, "r") as f:
        go_dict = json.load(f)
    print(f"Loaded {len(go_dict):,} GO terms")
    return go_dict


def build_ancestor_cache(go_dict):
    """
    Rebuild the ancestor cache from go_dict.

    This isn't stored in go_dict.json (it'd be huge), so we recompute
    it in memory each run. The inner recursive function closes over `cache`
    so we don't have to pass it around as a parameter.
    """
    print("Rebuilding ancestor cache — takes about 10-30 seconds...")
    cache = {}

    def get_ancestors(go_id):
        if go_id in cache:
            return cache[go_id]   # already done, use cached result

        ancestors = set()
        term = go_dict.get(go_id)
        if term:
            for parent in term.get("parents", []):
                ancestors.add(parent)
                ancestors.update(get_ancestors(parent))   # walk up the tree

        cache[go_id] = ancestors
        return ancestors

    for go_id in go_dict:
        get_ancestors(go_id)

    print(f"Ancestor cache ready — {len(cache):,} terms covered")
    return cache


def get_group_sizes(go_dict, ancestor_cache, groups):
    """
    Count how many terms in go_dict fall under each group's root.

    We compute this over the full ontology (not just the dataset) because
    it's used as a tiebreaker — we want the group with the smallest *total*
    footprint in the GO hierarchy, which is a stable, dataset-independent measure.
    """
    print("Computing full ontology size of each group (used as tiebreaker)...")
    sizes = {}

    for group_name, group_root in groups.items():
        count = sum(
            1 for go_id in go_dict
            if group_root in ancestor_cache.get(go_id, set())
        )
        sizes[group_name] = count

    # Quick sanity check — merged group roots should still show up with reasonable sizes
    print("Group sizes (including merged groups for reference):")
    for name, size in sorted(sizes.items(), key=lambda x: -x[1]):
        merged = " [will be merged]" if name in MERGE_MAP else ""
        print(f"  {name:<40} {size:>6,} terms{merged}")

    return sizes


def read_dataset_go_terms(dataset_path, go_col_idx, go_dict):
    """
    Pull every GO term from the dataset that also exists in go_dict.
    Terms not in go_dict are either obsolete or unresolved alternate IDs —
    either way we can't assign them to a group, so we skip them.
    """
    print(f"\nReading dataset GO annotations from {dataset_path} ...")
    dataset_go_terms = set()
    rows_read = 0
    rows_skipped = 0

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue

            parts = line.strip().split("\t")
            if len(parts) <= go_col_idx:
                rows_skipped += 1
                continue   # row doesn't reach the GO column

            rows_read += 1
            raw_ids = parts[go_col_idx].split(";")

            for raw in raw_ids:
                raw = raw.strip()
                if raw in go_dict:
                    dataset_go_terms.add(raw)

    print(f"Read {rows_read:,} protein rows ({rows_skipped} skipped)")
    print(f"Found {len(dataset_go_terms):,} unique GO terms present in go_dict")
    return dataset_go_terms


def assign_go_terms(dataset_go_terms, ancestor_cache, all_groups, group_sizes):
    """
    Assign each dataset GO term to exactly one final group.

    Three steps per term:
      1. Find all groups whose root appears in this term's ancestor set
      2. Pick the most specific match (smallest group by full ontology size)
      3. If that winner is a merged group, redirect to its host via MERGE_MAP

    The merge step is what makes v2 different from v1 — instead of leaving
    viral_process, growth, and molecular_adaptor_activity as separate groups,
    their terms quietly get folded into the host groups at this stage.
    """
    print("\nAssigning GO terms to groups (with merge redirection)...")

    assignment  = {}    # go_id → final group name
    unassigned  = set()
    merge_hits  = defaultdict(int)   # track how many terms got redirected by the merge
    multi_match = 0

    for go_id in dataset_go_terms:
        ancestors = ancestor_cache.get(go_id, set())

        # Step 1: which groups does this term belong to?
        matched_groups = [
            group_name
            for group_name, group_root in all_groups.items()
            if group_root in ancestors
        ]

        if not matched_groups:
            unassigned.add(go_id)
            continue

        # Step 2: pick the most specific (smallest) group
        if len(matched_groups) > 1:
            multi_match += 1
        best = min(matched_groups, key=lambda g: group_sizes.get(g, float("inf")))

        # Step 3: apply merge redirect if this group was absorbed into another
        final_group = MERGE_MAP.get(best, best)
        if best in MERGE_MAP:
            merge_hits[best] += 1   # count how many terms went through each merge

        assignment[go_id] = final_group

    print(f"Assignment complete:")
    print(f"  {len(assignment):,} terms assigned to a group")
    print(f"  {len(unassigned):,} terms left unassigned (root-level or above all groups)")
    print(f"  {multi_match:,} terms needed the tiebreaker (DAG overlap)")
    print(f"Merge redirects applied:")
    for source, count in merge_hits.items():
        target = MERGE_MAP[source]
        print(f"  {source} → {target} : {count:,} terms redirected")

    return assignment, unassigned


def report(assignment, unassigned, group_sizes, target_groups):
    """
    Print a full breakdown of how many terms landed in each final group
    and what we recommend doing with each based on size.
    """
    group_counts = defaultdict(int)
    for go_id, group in assignment.items():
        group_counts[group] += 1

    print("\n── Group Assignment Results (v2 — merges applied) ───────────────")
    print(f"  {'Group':<35} {'GO Root':<15} {'Assigned':>8}  Status")
    print(f"  {'-'*34} {'-'*14} {'-'*8}  {'-'*25}")

    trainable   = []
    needs_split = []

    for group_name, group_root in sorted(
        target_groups.items(), key=lambda x: -group_counts.get(x[0], 0)
    ):
        assigned = group_counts.get(group_name, 0)

        if assigned >= 500:
            status = "SPLIT FURTHER"
            needs_split.append((group_name, assigned))
        elif assigned >= 150:
            status = "READY TO TRAIN"
            trainable.append((group_name, assigned))
        elif assigned > 0:
            status = "SMALL — review before training"
            trainable.append((group_name, assigned))
        else:
            status = "empty — check if merge worked"

        print(f"  {group_name:<35} {group_root:<15} {assigned:>8,}  {status}")

    print(f"\n  Total assigned : {len(assignment):,} GO terms")
    print(f"  Unassigned     : {len(unassigned):,} GO terms (documented for paper)")

    # Show exactly what the three merges contributed to their host groups
    print(f"\n── Merge Summary ────────────────────────────────────────────────")
    print(f"  viral_process            → interspecies_interaction : "
          f"{group_counts.get('interspecies_interaction', 0):,} total terms in host group")
    print(f"  growth                   → homeostatic_process      : "
          f"{group_counts.get('homeostatic_process', 0):,} total terms in host group")
    print(f"  molecular_adaptor_activity → mf_regulator_activity  : "
          f"{group_counts.get('mf_regulator_activity', 0):,} total terms in host group")

    # The 7 groups we're actually going to train first
    print(f"\n── The 7 Groups Ready to Train First ────────────────────────────")
    first_batch = [
        "reproductive_process",
        "interspecies_interaction",
        "immune_system_process",
        "molecular_transducer",
        "mf_regulator_activity",
        "homeostatic_process",
        "atp_dependent_activity",
    ]
    for name in sorted(first_batch, key=lambda n: -group_counts.get(n, 0)):
        count = group_counts.get(name, 0)
        print(f"  {name:<40} {count:>5,} GO terms")

    if needs_split:
        print(f"\n── Groups Still Needing a Split Script ──────────────────────────")
        for name, count in sorted(needs_split, key=lambda x: -x[1]):
            print(f"  {name:<40} {count:>5,} GO terms — too many, split first")


def save_assignment(assignment, unassigned, path="C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_group_assignment_v2.json"):
    """
    Save the final assignment to JSON.

    Output structure: { "groups": {group_name: [go_id, ...]}, "unassigned": [...], "merge_log": {...} }

    The merge_log is included so the paper can cite the biological justification
    for each merge decision — this is the kind of thing reviewers ask about.
    """
    print(f"\nSaving assignment to {path} ...")

    # Flip go_id → group into group → [go_ids]
    group_to_terms = defaultdict(list)
    for go_id, group in assignment.items():
        group_to_terms[group].append(go_id)

    output = {
        "groups": dict(group_to_terms),
        "unassigned": list(unassigned),
        "merge_log": {
            "viral_process → interspecies_interaction":
                "viral processes are a subset of interspecies interactions — viruses are obligate interspecies pathogens",
            "growth → homeostatic_process":
                "growth is a primary mechanism of biological homeostasis",
            "molecular_adaptor_activity → mf_regulator_activity":
                "molecular adaptors mediate protein-protein interactions, a form of molecular function regulation",
        }
    }

    with open(path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved {len(group_to_terms)} groups and {len(unassigned)} unassigned terms to {path}")
    print("The merge_log in this file documents the biological justification for each merge.")
    print("Keep this file — the splitting script and data processor both depend on it.")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("NeuralProt — GO Term Group Assigner v2 (with merges)")
    print("=" * 60)

    # Step 1: Load the parsed GO dictionary
    go_dict = load_go_dict(GO_DICT_PATH)

    # Step 2: Rebuild the ancestor cache — needed to check group membership
    ancestor_cache = build_ancestor_cache(go_dict)

    # Step 3: Compute ontology-wide sizes for all groups, including the merged ones
    #         We need the merged group sizes too so the tiebreaker can still use them
    group_sizes = get_group_sizes(go_dict, ancestor_cache, ALL_GROUPS)

    # Step 4: Collect the GO terms that actually appear in our dataset
    dataset_go_terms = read_dataset_go_terms(DATASET_PATH, GO_COL_IDX, go_dict)

    # Step 5: Assign — pick best group, then apply merge redirects
    assignment, unassigned = assign_go_terms(
        dataset_go_terms, ancestor_cache, ALL_GROUPS, group_sizes
    )

    # Step 6: Print the full summary — check the merge numbers look right here
    report(assignment, unassigned, group_sizes, TARGET_GROUPS)

    # Step 7: Save to disk for the splitting script and data processor
    save_assignment(assignment, unassigned)

    print("\n" + "=" * 60)
    print("Done. Next step: run the data_processor notebook which contains the large_group_splitter on the groups")
    print("flagged 'SPLIT FURTHER' before you start data processing.")
    print("=" * 60)


if __name__ == "__main__":
    main()