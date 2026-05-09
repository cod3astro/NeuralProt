"""
NeuralProt — Data Preparation Pipeline
======================================
Loads GO ontology, parses UniProtKB TSV + FASTA, applies True Path Rule
annotation propagation, and saves per-group intermediate data.

⚠ This script produces INTERMEDIATE files only.
Run data_processor.ipynb after this script to produce the final
training-ready files (features.npy, labels.npy, go_terms.json).

What this script produces for each group:
    labels.npz      — binary label matrix (intermediate — converted by data_processor.ipynb)
    pos_weights.npy — per-term class imbalance correction weights
    accessions.json — ordered list of protein accessions
    terms.json      — ordered list of GO term IDs (intermediate — renamed by data_processor.ipynb)
    metadata.json   — quick stats: protein count, term count, label density

What data_processor.ipynb produces (required for training):
    features.npy    — 428-dimensional feature vectors per protein
    labels.npy      — binary label matrix (converted from labels.npz)
    go_terms.json   — GO term list (renamed from terms.json)

Usage:
    python data_pipeline.py
    # then run data_processor.ipynb
"""

import os
import json
import pickle
import numpy as np

# The GO hierarchy can get pretty deep — bump this up so recursive ancestor
# lookups don't blow the stack. The iterative cache builder below handles most
# of it, but this is a safety net for edge cases.


# ── CONFIG ────────────────────────────────────────────────────────────────────
TSV_PATH        = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/raw/uniprotkb_AND_reviewed_true_AND_protein_2025_12_27.tsv"
FASTA_PATH      = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/raw/uniprotkb_AND_reviewed_true_AND_protein_2025_12_27.fasta"
GO_DICT_PATH    = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_dict.json"
ASSIGNMENT_PATH = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/go_group_assignment_v2.json"
OUTPUT_DIR      = "C:/Users/USER/Documents/cod3astro/ML_AI/NeuralProt/data/processed/processed_data"

GO_COL_IDX    = 5   # zero-based column index for GO terms in the TSV
ACCESSION_COL = 0   # zero-based column index for the protein accession

# These are the 7 base groups processed by data_pipeline.py.
# The remaining 15 groups were produced by large_group_splitter_v2.py
# and processed directly by data_processor.ipynb.
TRAIN_GROUPS = [
    "reproductive_process",
    "interspecies_interaction",
    "immune_system_process",
    "molecular_transducer",
    "mf_regulator_activity",
    "homeostatic_process",
    "atp_dependent_activity",
]
# ─────────────────────────────────────────────────────────────────────────────


def load_go_dict(path):
    """
    Load the parsed GO dictionary from go_parser.py's output.
    This is the backbone of everything downstream — term lookups,
    ancestor traversal, and label filtering all depend on it.
    """
    print(f"Loading GO dictionary from {path} ...")
    with open(path, "r") as f:
        go_dict = json.load(f)
    print(f"Loaded {len(go_dict):,} active GO terms")
    return go_dict


def load_group_assignment(path):
    """
    Load the group → [GO term IDs] mapping from go_group_assigner_v2.py.
    We only pull out the 'groups' key — the unassigned list and merge log
    are bookkeeping we don't need here.
    """
    print(f"Loading group assignments from {path} ...")
    with open(path, "r") as f:
        data = json.load(f)
    groups = data["groups"]
    print(f"Found {len(groups)} groups in assignment file")
    for name, terms in groups.items():
        print(f"  {name:<35} {len(terms):>5,} GO terms assigned")
    return groups


def build_ancestor_cache_iterative(go_dict):
    """
    Build the full ancestor set for every GO term without recursion.

    We use an explicit stack-based DFS instead of the recursive version
    because the GO hierarchy can be deep enough to hit Python's default
    recursion limit on some terms. Same result, no stack overflow risk.

    How it works: for each term, we start a stack with its direct parents,
    then keep popping parents off the stack and adding *their* parents until
    the stack is empty. Everything we visited is an ancestor.
    """
    print("Building ancestor cache (iterative DFS — avoids recursion limits)...")

    cache = {}

    for go_id in go_dict:
        if go_id in cache:
            continue   # already computed as part of another term's traversal

        ancestors = set()
        # Seed the stack with this term's direct parents
        stack = list(go_dict.get(go_id, {}).get("parents", []))

        while stack:
            parent = stack.pop()
            if parent in ancestors:
                continue   # already visited this node, skip to avoid cycles

            ancestors.add(parent)

            # Push this parent's parents onto the stack so we keep climbing
            parent_info = go_dict.get(parent, {})
            stack.extend(parent_info.get("parents", []))

        cache[go_id] = ancestors

    print(f"Ancestor cache ready — {len(cache):,} terms covered")
    return cache


def propagate_labels(go_ids, go_dict, ancestor_cache):
    """
    Expand a protein's raw GO annotations to include all ancestor terms.

    This implements the True Path Rule: if a protein performs a specific
    function (e.g. zinc ion transport), it also implicitly performs every
    broader function above it in the hierarchy (ion transport, transport, etc.).

    Swiss-Prot only stores the most specific annotation. Without this step,
    the model gets penalized for correctly predicting ancestor terms that
    aren't in the raw label — a silent but serious training error.

    We filter the result against go_dict at the end to drop any obsolete
    terms that might appear as ancestors from older annotations.
    """
    propagated = set(go_ids)

    for go_id in go_ids:
        ancestors = ancestor_cache.get(go_id, set())
        propagated.update(ancestors)

    # Only keep terms we actually know about — tosses obsolete ancestor IDs
    return propagated & go_dict.keys()


def parse_tsv(tsv_path, go_col_idx, accession_col):
    """
    Parse the UniProtKB TSV file and build a map of accession → raw GO term set.

    The first row is the header — we skip it. We also skip blank lines and
    any rows that don't reach the GO column (shouldn't happen in a clean export,
    but Swiss-Prot downloads can occasionally have odd formatting).

    Note: these are raw, un-propagated GO IDs. Propagation happens later in
    build_and_save_group so we can do it per group efficiently.
    """
    print(f"\nParsing TSV from {tsv_path} ...")
    protein_go  = {}
    rows_read   = 0
    rows_empty  = 0   # rows where accession or GO column was blank

    with open(tsv_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0 or line.startswith("#") or not line.strip():
                continue   # skip header and blank lines

            parts = line.strip().split("\t")
            if len(parts) <= max(go_col_idx, accession_col):
                continue   # row doesn't reach the columns we need

            accession = parts[accession_col].strip()
            raw_go    = parts[go_col_idx].strip()

            if not accession or not raw_go:
                rows_empty += 1
                continue   # both fields must be present to be useful

            go_ids = {g.strip() for g in raw_go.split(";") if g.strip()}
            protein_go[accession] = go_ids
            rows_read += 1

    print(f"Parsed {rows_read:,} proteins with GO annotations")
    if rows_empty > 0:
        print(f"Skipped {rows_empty:,} rows with missing accession or GO column")

    # A rough sanity check — if this number is wildly low, something's off
    if len(protein_go) < 1000:
        print("WARNING: fewer than 1,000 proteins loaded — check TSV_PATH and column indices")

    return protein_go


def parse_fasta(fasta_path):
    """
    Parse the UniProtKB FASTA file and extract accession → sequence.

    UniProtKB FASTA headers look like:
        >sp|P12345|GENE_HUMAN Some description of the protein...
    We grab the second pipe-delimited field as the accession (P12345),
    which matches what the TSV uses. For any non-standard header, we fall
    back to the first word after the '>'.

    The sequences dict is also saved to sequences.pkl so other scripts
    can load it without re-parsing this file, which takes a while.
    """
    print(f"\nParsing FASTA from {fasta_path} ...")

    sequences   = {}
    current_id  = None
    current_seq = []

    with open(fasta_path, "r") as f:
        for line in f:
            line = line.strip()

            if line.startswith(">"):
                # Save the sequence we just finished building
                if current_id:
                    sequences[current_id] = "".join(current_seq)

                header = line[1:]
                parts  = header.split("|")

                if len(parts) >= 2:
                    current_id = parts[1]   # standard UniProtKB format: sp|ACCESSION|...
                else:
                    current_id = parts[0].split()[0]   # fallback for non-standard headers

                current_seq = []
            else:
                current_seq.append(line)   # sequence lines just get concatenated

        # Don't forget the last sequence — the loop ends without a final ">" to flush it
        if current_id:
            sequences[current_id] = "".join(current_seq)

    print(f"Loaded {len(sequences):,} protein sequences")

    # Save to disk so downstream scripts (e.g. the feature extractor) don't
    # need to re-parse this whole file from scratch
    sequences_pkl = os.path.join(OUTPUT_DIR, "sequences.pkl")
    with open(sequences_pkl, "wb") as f:
        pickle.dump(sequences, f)
    print(f"Saved sequences to {sequences_pkl} for reuse by other scripts")

    return sequences


def build_and_save_group(group_name, group_go_terms, protein_go, sequences,
                         go_dict, ancestor_cache, output_dir):
    """
    Build the training data for one group and save all output files.

    For each protein that has at least one GO term from this group:
      1. Propagate its raw annotations to include all ancestor terms
      2. Find the intersection with this group's term list
      3. Build a binary label vector (1 = term present, 0 = absent)

    Then compute pos_weights — the per-term class imbalance correction factor.
    pos_weight[i] = (number of negatives for term i) / (number of positives for term i)
    This tells the loss function to upweight rare positive predictions so the
    model doesn't just learn to always predict negative for rare GO terms.

    Proteins are skipped if their accession doesn't appear in the FASTA —
    we need the sequence for feature extraction, so no sequence = no training row.
    """
    group_go_set = set(group_go_terms)
    go_term_list = sorted(group_go_terms)   # sorted for reproducible column order
    term_to_idx  = {t: i for i, t in enumerate(go_term_list)}
    n_terms      = len(go_term_list)

    accessions   = []
    label_matrix = []
    skipped      = 0   # proteins present in TSV but missing from FASTA

    print(f"  Building label matrix for {group_name} ({n_terms} terms)...")

    for accession, raw_go_ids in protein_go.items():
        # Quick pre-filter: does this protein have any terms in this group at all?
        if not (raw_go_ids & group_go_set):
            continue   # not relevant to this group — skip cheaply before propagation

        if accession not in sequences:
            skipped += 1
            continue   # no sequence available — can't use this protein

        # Propagate labels — adds all ancestor terms the raw annotations imply
        propagated     = propagate_labels(raw_go_ids, go_dict, ancestor_cache)
        relevant_terms = propagated & group_go_set

        if not relevant_terms:
            # After propagation, nothing landed in this group — unusual but possible
            continue

        # Build the label vector for this protein
        vec = np.zeros(n_terms, dtype=np.float32)
        for term in relevant_terms:
            vec[term_to_idx[term]] = 1.0

        accessions.append(accession)
        label_matrix.append(vec)

    if len(accessions) < 50:
        # Too few proteins to train anything meaningful — don't even save the files
        print(f"  Only {len(accessions)} proteins found for {group_name} — skipping this group")
        print(f"  (Need at least 50. Consider lowering frequency filters or merging with another group.)")
        return None

    label_matrix = np.array(label_matrix, dtype=np.float32)
    n_proteins   = label_matrix.shape[0]

    print(f"  {n_proteins:,} proteins included, {skipped:,} skipped (no FASTA sequence)")

    # Compute pos_weights — small epsilon added to pos_counts to avoid divide-by-zero
    # for terms that appear in every single protein (all positive = weight of ~1)
    pos_counts  = label_matrix.sum(axis=0) + 1e-6
    neg_counts  = n_proteins - pos_counts
    pos_weights = np.clip(neg_counts / pos_counts, 1.0, 10000.0)

    # Log some label density info — useful for spotting degenerate groups
    label_density = float(label_matrix.mean())
    max_weight    = float(pos_weights.max())
    print(f"  Label density: {label_density:.4f} (fraction of term-protein pairs that are positive)")
    print(f"  Max pos_weight: {max_weight:.1f} (highest class imbalance ratio in this group)")
    if max_weight >= 9000:
        print(f"  Note: max pos_weight is near the clip ceiling — some terms are very rare here")

    # Create the group's output folder
    group_dir = os.path.join(output_dir, group_name)
    os.makedirs(group_dir, exist_ok=True)

    # Save intermediate files — data_processor.ipynb converts these
    # into the final training-ready formats (labels.npy, go_terms.json)
    np.savez_compressed(os.path.join(group_dir, "labels.npz"), labels=label_matrix)
    np.save(os.path.join(group_dir, "pos_weights.npy"), pos_weights)

    with open(os.path.join(group_dir, "terms.json"), "w") as f:
        json.dump(go_term_list, f)
        # Renamed to go_terms.json by data_processor.ipynb

    with open(os.path.join(group_dir, "terms.json"), "w") as f:
        json.dump(go_term_list, f)
        # Column j in labels.npz corresponds to terms[j]

    with open(os.path.join(group_dir, "metadata.json"), "w") as f:
        json.dump({
            "n_proteins":           n_proteins,
            "n_terms":              n_terms,
            "label_density":        label_density,
            "skipped_no_sequence":  skipped,
            "max_pos_weight":       max_weight,
        }, f, indent=2)

    print(f"  Saved to {group_dir}/")
    return group_dir


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("NeuralProt — Data Preparation Pipeline")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

    # Step 1: Load the GO dictionary and group assignments
    go_dict    = load_go_dict(GO_DICT_PATH)
    group_data = load_group_assignment(ASSIGNMENT_PATH)

    # Step 2: Build the ancestor cache — needed for label propagation
    ancestor_cache = build_ancestor_cache_iterative(go_dict)

    # Step 3: Load protein annotations from TSV and sequences from FASTA
    protein_go = parse_tsv(TSV_PATH, GO_COL_IDX, ACCESSION_COL)
    sequences  = parse_fasta(FASTA_PATH)

    # Step 4: Check that the TSV and FASTA overlap well enough to be useful
    matched = sum(1 for acc in protein_go if acc in sequences)
    print(f"\nTSV/FASTA overlap: {matched:,} of {len(protein_go):,} proteins have both annotations and sequence")
    if matched / len(protein_go) < 0.8:
        print("WARNING: less than 80% of annotated proteins have a matching FASTA sequence")
        print("         Check that TSV_PATH and FASTA_PATH refer to the same Swiss-Prot release")

    # Step 5: Build and save per-group data
    print(f"\nProcessing {len(TRAIN_GROUPS)} groups...")
    results = {}

    for group_name in TRAIN_GROUPS:
        if group_name not in group_data:
            print(f"\nGroup '{group_name}' not found in assignment file — skipping")
            print(f"  Check that go_group_assigner_v2.py ran successfully for this group")
            continue

        n_terms = len(group_data[group_name])
        print(f"\n{'─'*50}")
        print(f"Group: {group_name}  ({n_terms} GO terms assigned)")

        group_dir = build_and_save_group(
            group_name,
            group_data[group_name],
            protein_go,
            sequences,
            go_dict,
            ancestor_cache,
            OUTPUT_DIR,
        )

        if group_dir:
            results[group_name] = "saved"
        else:
            results[group_name] = "skipped (too few proteins)"

    # Step 6: Final summary
    print(f"\n{'='*60}")
    print("Data preparation complete. Summary:")
    for group_name, status in results.items():
        print(f"  {group_name:<35} {status}")

    saved  = sum(1 for s in results.values() if s == "saved")
    skipped = len(results) - saved
    print(f"\n  {saved} groups saved, {skipped} skipped")
    print("  Next step: run the feature extractor on each saved group folder,")
    print("  then start training with train_model.ipynb")
    print("=" * 60)


if __name__ == "__main__":
    main()