"""
GO .obo File Parser
====================
Parses go-basic.obo, builds the GO hierarchy, propagates ancestors,
and reports group size distributions to guide model grouping decisions.

Usage:
    python parse_go.py

    Make sure go-basic.obo is in the same directory as your TSV Dataset
"""

import json
from collections import defaultdict


# ── CONFIG ─────────────────────────────────────────────────────────────────────
# Update these paths before running based on the location of your file, Everything downstream depends on these two files.
OBO_PATH     = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/raw/go-basic.obo"
DATASET_PATH = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/raw/uniprotkb_AND_reviewed_true_AND_protein_2025_12_27.tsv"
GO_COL_IDX   = 5   # zero-based column index for the GO terms in the TSV — double-check this matches your file


# ── PARSER ─────────────────────────────────────────────────────────────────────

def parse_obo(filepath):
    """
    Parse a GO .obo file into a dictionary of GO terms.

    The .obo format is basically a series of [Term] blocks separated by blank lines.
    We walk through line by line, collect fields for each block, then flush it into
    go_dict when we hit the next blank line or new block header.

    Returns
    -------
    go_dict    : dict  {go_id -> {"name", "namespace", "parents", "alt_ids", "is_obsolete"}}
    alt_id_map : dict  {old_alt_id -> canonical go_id}
                 Some proteins in Swiss-Prot still use retired GO IDs. This map
                 lets us silently reroute them to the current canonical term.
    """
    go_dict    = {}
    alt_id_map = {}   # keeps track of deprecated IDs that were folded into newer ones

    print(f"Opening OBO file: {filepath}")

    with open(filepath, "r") as f:
        current = None   # holds the term we're currently building up

        for line in f:
            line = line.strip()

            # Every [Term] block is the start of one GO entry
            if line == "[Term]":
                current = {
                    "name":        "",
                    "namespace":   "",
                    "parents":     [],
                    "alt_ids":     [],
                    "is_obsolete": False,
                }
                continue

            # A blank line or a new section header means the current term is done — save it
            if line == "" or line.startswith("["):
                if current and "id" in current:
                    go_id = current["id"]
                    go_dict[go_id] = current
                    # Register any alternate IDs so we can resolve them later
                    for alt in current["alt_ids"]:
                        alt_id_map[alt] = go_id
                current = None
                continue

            # If we're not inside a [Term] block, skip the line
            if current is None:
                continue

            # Pull out the fields we actually care about
            if line.startswith("id:"):
                current["id"] = line.split("id:")[1].strip()

            elif line.startswith("name:"):
                current["name"] = line.split("name:")[1].strip()

            elif line.startswith("namespace:"):
                current["namespace"] = line.split("namespace:")[1].strip()

            elif line.startswith("is_a:"):
                # is_a lines look like: is_a: GO:0000001 ! mitochondrial genome maintenance
                # We only want the GO ID part before the "!"
                parent_id = line.split("is_a:")[1].strip().split(" ")[0]
                current["parents"].append(parent_id)

            elif line.startswith("alt_id:"):
                alt = line.split("alt_id:")[1].strip()
                current["alt_ids"].append(alt)

            elif line.startswith("is_obsolete:"):
                val = line.split("is_obsolete:")[1].strip()
                current["is_obsolete"] = (val == "true")

        # The file might not end with a blank line, so flush whatever's still in current
        if current and "id" in current:
            go_id = current["id"]
            go_dict[go_id] = current
            for alt in current["alt_ids"]:
                alt_id_map[alt] = go_id

    # Toss out obsolete terms — we don't want to train on or predict retired concepts
    before_filter = len(go_dict)
    go_dict = {k: v for k, v in go_dict.items() if not v["is_obsolete"]}
    removed = before_filter - len(go_dict)

    print(f"Parsed {before_filter:,} total GO terms from the OBO file")
    print(f"Dropped {removed:,} obsolete terms — not useful for training")
    print(f"Keeping {len(go_dict):,} active GO terms")
    print(f"Registered {len(alt_id_map):,} alternate IDs that point to current canonical terms")

    return go_dict, alt_id_map


# ── ANCESTOR TRAVERSAL ─────────────────────────────────────────────────────────

def get_all_ancestors(go_id, go_dict, cache=None):
    """
    Recursively walk up the GO hierarchy and collect every ancestor of go_id.

    GO is a DAG (directed acyclic graph), so a term can have multiple parents,
    each of which can have multiple parents of their own. We recurse all the
    way up to the root terms.

    The cache is critical here — without it, shared ancestors get recomputed
    thousands of times. With it, each term is only traversed once.
    """
    if cache is None:
        cache = {}

    if go_id in cache:
        return cache[go_id]   # already done this one

    ancestors = set()
    term = go_dict.get(go_id)

    if term:
        for parent in term["parents"]:
            ancestors.add(parent)
            # Recurse up through this parent's ancestors too
            ancestors.update(get_all_ancestors(parent, go_dict, cache))

    cache[go_id] = ancestors
    return ancestors


def build_ancestor_cache(go_dict):
    """
    Pre-compute the full ancestor set for every term in go_dict.

    This is the slow step — expect 10 to 30 seconds on a standard machine.
    We do it once here and reuse the result everywhere else. Without this,
    group assignment and annotation propagation would be extremely slow.
    """
    print("\nBuilding ancestor cache — this traverses the full GO hierarchy for every term.")
    print("It only runs once, so sit tight for ~10-30 seconds...")

    cache = {}
    for go_id in go_dict:
        get_all_ancestors(go_id, go_dict, cache)

    print(f"Done. Ancestor sets computed for {len(cache):,} terms.")
    return cache


# ── LABEL PROPAGATION ──────────────────────────────────────────────────────────

def propagate_labels(go_ids, go_dict, ancestor_cache):
    """
    Expand a protein's GO annotations to include all implied ancestor terms.

    This implements the True Path Rule: if a protein is annotated with GO:X,
    then it is also implicitly annotated with every term above GO:X in the
    hierarchy. Swiss-Prot only stores the most specific annotation, so we
    have to fill in the rest ourselves before building label vectors.

    Skipping this step is a common mistake — it causes the model to get
    penalized for correctly predicting ancestor terms that aren't in the labels.
    """
    propagated = set(go_ids)

    for go_id in go_ids:
        ancestors = ancestor_cache.get(go_id, set())
        propagated.update(ancestors)

    # Only keep terms we actually know about — filters out obsolete IDs that
    # might appear as ancestors from older annotations
    return propagated & go_dict.keys()


# ── REPORTING HELPERS ──────────────────────────────────────────────────────────

def get_namespace_distribution(go_dict):
    """
    Count how many GO terms live in each of the three namespaces
    (biological_process, molecular_function, cellular_component).

    Mostly a sanity check — if the numbers look wildly off from what
    the GO Consortium reports, something went wrong in parsing.
    """
    counts = defaultdict(int)
    for term in go_dict.values():
        counts[term["namespace"]] += 1

    print("\n── Namespace Distribution ──────────────────────────────────────")
    for ns, count in sorted(counts.items()):
        print(f"  {ns:<35} {count:>6,} terms")

    return counts


def get_top_level_groups(go_dict, ancestor_cache, min_size=100):
    """
    Find the direct children of the three GO root terms.
    These are the natural biological groupings we'll use as model boundaries.

    We only keep groups with at least `min_size` descendants — anything smaller
    is either too niche to be useful or should get merged into a related group.
    """
    # The three roots — every GO term is ultimately a descendant of one of these
    roots = {
        "GO:0008150": "biological_process",
        "GO:0003674": "molecular_function",
        "GO:0005575": "cellular_component",
    }

    print(f"\nFinding top-level groups with at least {min_size} descendant terms...")

    groups = {}
    for go_id, term in go_dict.items():
        # A "top-level group" means its parent is one of the three roots
        if any(root in term["parents"] for root in roots):
            descendants = [
                t for t in go_dict
                if go_id in ancestor_cache.get(t, set())
            ]
            size = len(descendants)
            if size >= min_size:
                groups[go_id] = {
                    "name":      term["name"],
                    "namespace": term["namespace"],
                    "size":      size,
                }

    print(f"Found {len(groups)} top-level groups that meet the size threshold.")
    print(f"\n── Top-Level Groups (≥{min_size} descendants) ──────────────────")
    print(f"  {'GO ID':<15} {'Size':>6}  {'Namespace':<30} Name")
    print(f"  {'-'*14} {'-'*6}  {'-'*29} {'-'*30}")
    for gid, info in sorted(groups.items(), key=lambda x: -x[1]["size"]):
        print(f"  {gid:<15} {info['size']:>6,}  {info['namespace']:<30} {info['name']}")

    return groups


def filter_by_dataset(go_dict, alt_id_map, dataset_path, go_col_idx):
    """
    Read the TSV dataset and figure out which GO terms actually show up in it.

    Not every term in the GO ontology appears in Swiss-Prot, so this gives us
    the realistic working set — the terms we'd actually be training on.
    Also resolves any alternate IDs in the dataset to their canonical forms.
    """
    print(f"\nReading GO annotations from dataset: {dataset_path}")
    dataset_go_terms = set()
    rows_read = 0

    with open(dataset_path, "r") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue   # skip header lines and blanks

            parts = line.strip().split("\t")
            if len(parts) <= go_col_idx:
                continue   # row doesn't have enough columns — skip it

            rows_read += 1
            raw_ids = parts[go_col_idx].split(";")

            for raw in raw_ids:
                raw = raw.strip()
                if not raw:
                    continue
                # If it's an old alternate ID, swap it for the current canonical one
                canonical = alt_id_map.get(raw, raw)
                if canonical in go_dict:
                    dataset_go_terms.add(canonical)

    total_active = len(go_dict)
    covered = len(dataset_go_terms)

    print(f"Read {rows_read:,} protein rows from the dataset")
    print(f"Found {covered:,} unique GO terms across all proteins")
    print(f"That's {covered / total_active * 100:.1f}% of the {total_active:,} active GO terms in the ontology")

    if covered < 1000:
        print("WARNING: fewer than 1,000 GO terms found — double-check GO_COL_IDX is set correctly")

    return dataset_go_terms


def report_group_coverage(groups, dataset_go_terms, go_dict, ancestor_cache):
    """
    For each top-level group, show how many of its descendant terms
    actually appear in our dataset.

    This tells us which groups are worth training — a group where 70%+ of
    its terms appear in the dataset is a much better candidate than one with 10%.
    """
    print("\n── Dataset Coverage per Top-Level Group ────────────────────────")
    print(f"  {'GO ID':<15} {'Total':>6}  {'In Dataset':>10}  {'Coverage':>8}  Name")
    print(f"  {'-'*14} {'-'*6}  {'-'*10}  {'-'*8}  {'-'*30}")

    results = []
    for gid, info in groups.items():
        descendants = {
            t for t in go_dict
            if gid in ancestor_cache.get(t, set())
        }
        in_dataset = descendants & dataset_go_terms
        coverage = len(in_dataset) / len(descendants) * 100 if descendants else 0

        results.append({
            "go_id":      gid,
            "name":       info["name"],
            "namespace":  info["namespace"],
            "total":      len(descendants),
            "in_dataset": len(in_dataset),
            "coverage":   coverage,
        })

    for r in sorted(results, key=lambda x: -x["in_dataset"]):
        print(
            f"  {r['go_id']:<15} {r['total']:>6,}  "
            f"{r['in_dataset']:>10,}  {r['coverage']:>7.1f}%  {r['name']}"
        )

    # Flag anything with suspiciously low coverage so it doesn't slip through unnoticed
    low_coverage = [r for r in results if r["coverage"] < 30]
    if low_coverage:
        print(f"\nHeads up: {len(low_coverage)} group(s) have less than 30% dataset coverage")
        print("These might not be worth training a dedicated model for:")
        for r in low_coverage:
            print(f"  {r['name']} ({r['go_id']}) — {r['coverage']:.1f}%")

    return results


# ── SAVE ───────────────────────────────────────────────────────────────────────

def save_go_dict(go_dict, path="C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_dict.json"):
    """
    Serialize go_dict to JSON so we don't have to re-parse the OBO file
    every time we run downstream scripts. Sets and lists need explicit
    conversion since JSON doesn't know what a Python set is.
    """
    print(f"\nSaving go_dict to {path} ...")

    # JSON can't handle sets, so convert parents and alt_ids to lists
    serializable = {
        k: {**v, "parents": list(v["parents"]), "alt_ids": list(v["alt_ids"])}
        for k, v in go_dict.items()
    }

    with open(path, "w") as f:
        json.dump(serializable, f)

    print(f"Saved {len(go_dict):,} GO terms to {path}")
    print("This file gets loaded by the group assigner and data processor — don't move it.")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("NeuralProt — GO Ontology Parser")
    print("=" * 60)

    # Step 1: Parse the OBO file and get every active GO term + alt ID map
    go_dict, alt_id_map = parse_obo(OBO_PATH)

    # Step 2: Quick sanity check on how terms are distributed across namespaces
    get_namespace_distribution(go_dict)

    # Step 3: Build ancestor cache — the slow step, but we need it for everything else
    ancestor_cache = build_ancestor_cache(go_dict)

    # Step 4: Figure out which top-level groups exist and how big they are
    groups = get_top_level_groups(go_dict, ancestor_cache, min_size=100)

    # Step 5: Cross-reference against the actual dataset to see what we're working with
    if DATASET_PATH:
        dataset_go_terms = filter_by_dataset(go_dict, alt_id_map, DATASET_PATH, GO_COL_IDX)
        report_group_coverage(groups, dataset_go_terms, go_dict, ancestor_cache)
    else:
        print("\nNo DATASET_PATH set — skipping dataset coverage check.")

    # Step 6: Save go_dict so downstream scripts can load it without re-parsing
    save_go_dict(go_dict)

    print("\n" + "=" * 60)
    print("Parser finished. Check the coverage table above to decide which")
    print("groups to train models on — higher coverage = more reliable training.")
    print("=" * 60)


if __name__ == "__main__":
    main()