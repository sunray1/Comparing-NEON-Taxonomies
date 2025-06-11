import argparse
import csv
import os
import sys

# --- Define standard taxonomic rank order and mapping ---
# This list defines the order in which we'll try to build lineages.
# It should cover the most common ranks present in your data.
STANDARD_RANK_ORDER = [
    'kingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species',
    'subspecies', 'variety', 'form'
    # Add more ranks here if they are consistently present in your data (e.g., 'subfamily', 'tribe')
]

# This maps our canonical lowercase rank names to the expected column names
# in the NEON HQ taxonomy file.
# Note: 'species', 'subspecies', 'variety', and 'form' here are placeholders. Logic in extract_lineage_edges handles their construction.
NEONHQ_COLUMN_MAP = {
    'kingdom': 'dwc:kingdom',
    'phylum': 'dwc:phylum', # We will add special logic in extract_lineage_edges to also check 'dwc:division' for this canonical rank
    'class': 'dwc:class',
    'order': 'dwc:order',
    'family': 'dwc:family',
    'genus': 'dwc:genus',
    'species': 'dwc:scientificName', # Placeholder. Logic below overrides it.
    'subspecies': 'dwc:subspecies', # Placeholder. Logic below overrides it.
    'variety': 'gbif:variety', # Placeholder. Logic below overrides it.
    'form': 'gbif:form' # Placeholder. Logic below overrides it.
}

# This maps our canonical lowercase rank names to the expected column names
# in the Biorepo taxonomy file.
BIOREPO_COLUMN_MAP = {
    'kingdom': 'biorepo_kingdom',
    'phylum': 'biorepo_division', # Biorepo's 'division' field serves as phylum/division
    'class': 'biorepo_class',
    'class': 'biorepo_class',
    'order': 'biorepo_order',
    'family': 'biorepo_family',
    'genus': 'biorepo_genus',
    'species': 'biorepo_species',
    'subspecies': 'biorepo_subspecies',
    'variety': 'biorepo_variety',
    'form': 'biorepo_form'
}

def load_taxonomy(filepath, group_code, id_col):
    """
    Loads a taxonomy CSV file into a dictionary, keyed by the specified ID column.
    Returns the data dictionary and the list of fieldnames.
    """
    data = {}
    fieldnames = []
    if not os.path.exists(filepath):
        print(f"Error: Taxonomy file for group '{group_code}' not found: {filepath}", file=sys.stderr)
        return None, None
    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            if id_col not in fieldnames:
                print(f"Error: Required ID column '{id_col}' not found in '{filepath}'. Found fields: {fieldnames}", file=sys.stderr)
                return None, None
            for row in reader:
                data[row[id_col]] = row
    except Exception as e:
        print(f"An error occurred loading {filepath}: {e}", file=sys.stderr)
        return None, None
    return data, fieldnames

def extract_lineage_edges(taxonomy_data, taxonomy_fieldnames, taxonomy_type, group_code=None):
    """
    Extracts a set of unique (parent_rank, parent_name, child_rank, child_name) tuples (edges)
    from the provided taxonomy data, using hardcoded rank order and specific column mappings.
    `taxonomy_type` can be 'neonhq' or 'biorepo'.
    `group_code` is used for group-specific parsing rules.
    """
    all_edges = set()

    for taxon_record in taxonomy_data.values():
        current_lineage = [] # List of (canonical_rank, name.lower()) tuples for this record
        
        # Determine which column map to use
        column_map = {}
        if taxonomy_type == 'neonhq':
            column_map = NEONHQ_COLUMN_MAP
        elif taxonomy_type == 'biorepo':
            column_map = BIOREPO_COLUMN_MAP
        else:
            raise ValueError(f"Unknown taxonomy_type: {taxonomy_type}. Expected 'neonhq' or 'biorepo'.")
        
        # Helper to get cleaned specificEpithet for NEON HQ
        def get_neonhq_species_epithet(record):
            epithet = record.get('dwc:specificEpithet', '').strip()
            if epithet.lower() in ['sp.', 'spp.']:
                return '' # Treat "sp."/"spp." as empty
            return epithet

        # Build the lineage for the current taxon_record based on STANDARD_RANK_ORDER
        for rank_name in STANDARD_RANK_ORDER:
            value = None
            col_name_in_map = column_map.get(rank_name) # This is the preferred column name for the rank

            # --- Special Handling for NEON HQ ranks ---
            if taxonomy_type == 'neonhq':
                if rank_name == 'phylum':
                    # Try dwc:phylum first, then dwc:division
                    value = taxon_record.get('dwc:phylum', '').strip()
                    if not value:
                        value = taxon_record.get('dwc:division', '').strip()
                elif rank_name == 'species':
                    genus = taxon_record.get('dwc:genus', '').strip()
                    epithet = get_neonhq_species_epithet(taxon_record)
                    scientific_name = taxon_record.get('dwc:scientificName', '').strip()

                    if genus and epithet:
                        # Default species name (no cross assumed initially)
                        value = f"{genus} {epithet}"

                        # Special handling for PLANT group to include hybrid cross
                        if group_code and group_code.upper() == 'PLANT' and '×' in scientific_name:
                            # Case 1: Intergeneric hybrid, e.g., "×Triticosecale L."
                            # Check if scientific_name starts with '×' followed immediately by genus (case-insensitive)
                            if scientific_name.lower().startswith(f"×{genus.lower()}"):
                                # If genus is found, and epithet is also present, combine them with the leading cross
                                if epithet:
                                    value = f"×{genus} {epithet}"
                                else: # If no specific epithet, it's just the hybrid genus itself
                                    value = f"×{genus}"
                            else:
                                # Case 2: Interspecific hybrid, e.g., "Quercus ×rosacea L."
                                # Check if "Genus ×Epithet" pattern (with or without space after cross) exists in scientific_name
                                # and always format the output value with a space after the cross.
                                search_pattern_no_space = f"{genus} ×{epithet}"
                                search_pattern_with_space = f"{genus} × {epithet}"
                                
                                if search_pattern_no_space.lower() in scientific_name.lower() or \
                                   search_pattern_with_space.lower() in scientific_name.lower():
                                    value = search_pattern_with_space # Assigns "Genus × Epithet"
                                # Else, keep default value (no cross found in expected pattern)
                
                elif rank_name == 'subspecies':
                    genus = taxon_record.get('dwc:genus', '').strip()
                    specific_epithet = get_neonhq_species_epithet(taxon_record)
                    subspecies_epithet_from_field = taxon_record.get('dwc:subspecies', '').strip()
                    scientific_name = taxon_record.get('dwc:scientificName', '').strip()
                    
                    subspecies_final_value = None

                    if genus and specific_epithet: # We need a valid species base first
                        # Case 1: dwc:subspecies field is filled
                        if subspecies_epithet_from_field:
                            base_subspecies_name = f"{genus} {specific_epithet} {subspecies_epithet_from_field}"
                            
                            # Special handling for PLANT group if dwc:subspecies has a cross or scientific_name indicates one
                            if group_code and group_code.upper() == 'PLANT' and '×' in scientific_name:
                                # Check for pattern "Genus species ×subspecies" (with or without space after cross)
                                # and always format the output value with a space after the cross.
                                search_pattern_no_space = f"{genus} {specific_epithet} ×{subspecies_epithet_from_field}"
                                search_pattern_with_space = f"{genus} {specific_epithet} × {subspecies_epithet_from_field}"
                                
                                if search_pattern_no_space.lower() in scientific_name.lower() or \
                                   search_pattern_with_space.lower() in scientific_name.lower():
                                    subspecies_final_value = search_pattern_with_space
                                else:
                                    subspecies_final_value = base_subspecies_name
                            else:
                                subspecies_final_value = base_subspecies_name

                        # Case 2: dwc:subspecies field is empty, but for HERPETOLOGY or SMALL_MAMMAL, check dwc:scientificName for trinomial
                        elif group_code and (group_code.upper() == 'HERPETOLOGY' or group_code.upper() == 'SMALL_MAMMAL'):
                            parts = scientific_name.split()
                            # Check if it's a trinomial AND the first two parts match our derived genus and species
                            # This heuristic assumes scientific_name for these specific cases is strictly
                            # "Genus species subspecies" without an author.
                            if len(parts) == 3 and \
                               parts[0].lower() == genus.lower() and \
                               parts[1].lower() == specific_epithet.lower():
                                
                                subspecies_epithet_from_sciname = parts[2]
                                subspecies_final_value = f"{genus} {specific_epithet} {subspecies_epithet_from_sciname}"
                                
                    value = subspecies_final_value # Set the value for the 'subspecies' rank
                elif rank_name == 'variety':
                    genus = taxon_record.get('dwc:genus', '').strip()
                    specific_epithet = get_neonhq_species_epithet(taxon_record)
                    variety_epithet = taxon_record.get('gbif:variety', '').strip()

                    # Only proceed if we can form a base species name AND have a variety epithet
                    if genus and specific_epithet and variety_epithet:
                        base_species_name = f"{genus} {specific_epithet}"
                        value = f"{base_species_name} var. {variety_epithet}"
                elif rank_name == 'form':
                    genus = taxon_record.get('dwc:genus', '').strip()
                    specific_epithet = get_neonhq_species_epithet(taxon_record)
                    form_epithet = taxon_record.get('gbif:form', '').strip()

                    # Only proceed if we can form a base species name AND have a form epithet
                    if genus and specific_epithet and form_epithet:
                        base_species_name = f"{genus} {specific_epithet}"
                        value = f"{base_species_name} f. {form_epithet}"
                else: # Standard handling for other NEON HQ ranks not covered by special cases
                    if col_name_in_map and col_name_in_map in taxonomy_fieldnames:
                        value = taxon_record.get(col_name_in_map, '').strip()
            # --- End Special Handling for NEON HQ ranks ---

            # --- Standard handling for Biorepo ranks ---
            elif taxonomy_type == 'biorepo':
                if col_name_in_map and col_name_in_map in taxonomy_fieldnames:
                    value = taxon_record.get(col_name_in_map, '').strip()
            # --- End Standard handling for Biorepo ranks ---
            
            if value: # Only add if a non-empty value exists for this rank in this record
                current_lineage.append((rank_name, value.lower()))
        
        # Now, extract edges from the built lineage
        for i in range(len(current_lineage) - 1):
            parent_rank, parent_name = current_lineage[i]
            child_rank, child_name = current_lineage[i+1]
            if parent_name and child_name: # Ensure valid names exists for the edge
                edge_tuple = (parent_rank, parent_name, child_rank, child_name)
                all_edges.add(edge_tuple)
                
    return all_edges

def calculate_jaccard_index(set1, set2):
    """Calculates the Jaccard index between two sets."""
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    if union == 0:
        return 1.0 # Both sets are empty, considered perfectly similar
    return intersection / union

def write_edges_to_file(edges_set, filename):
    """Writes a set of lineage edges to a specified file, one edge per line."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            for edge in sorted(list(edges_set)): # Sort for consistent output
                f.write(f"{edge}\n")
        print(f"Edges written to: {filename}")
    except Exception as e:
        print(f"Error writing edges to {filename}: {e}", file=sys.stderr)

def compare_taxonomies(group_code, neonhq_path, biorepo_path, output_path):
    """
    Compares two taxonomy CSV files for a given group, generates a detailed report
    and various edge set files, and returns a dictionary of calculated metrics.
    Returns None if there's a critical error preventing comparison.
    """
    report_lines = []
    report_lines.append(f"Comparison Report for Group: {group_code}\n")
    report_lines.append("--- Overview ---\n")

    report_lines.append(f"Canonical Ranks used for lineage: {', '.join(STANDARD_RANK_ORDER)}\n")
    
    # Load Taxonomy 1 (NEON HQ raw data)
    report_lines.append(f"Loading NEON HQ Taxonomy from: {neonhq_path}\n")
    t1_data, t1_fieldnames = load_taxonomy(neonhq_path, group_code, 'taxonID')
    if t1_data is None:
        report_lines.append("Failed to load NEON HQ Taxonomy. Aborting comparison.\n")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report_lines)
        return None # Indicate failure
    report_lines.append(f"Total records in NEON HQ Taxonomy: {len(t1_data)}\n")

    # Load Taxonomy 2 (Biorepo-derived raw data)
    report_lines.append(f"Loading Biorepo Taxonomy from: {biorepo_path}\n")
    t2_data, t2_fieldnames = load_taxonomy(biorepo_path, group_code, 'biorepo_tid')
    if t2_data is None:
        report_lines.append("Failed to load Biorepo Taxonomy. Aborting comparison.\n")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report_lines)
        return None # Indicate failure
    report_lines.append(f"Total records in Biorepo Taxonomy: {len(t2_data)}\n")

    report_lines.append("\n--- Lineage Edge Comparison (Jaccard Index) ---\n")

    # Extract edges for both taxonomies, passing group_code to neonhq extraction
    t1_edges = extract_lineage_edges(t1_data, t1_fieldnames, 'neonhq', group_code)
    report_lines.append(f"Unique edges found in NEON HQ Taxonomy: {len(t1_edges)}\n")

    t2_edges = extract_lineage_edges(t2_data, t2_fieldnames, 'biorepo') # Biorepo does not need group_code special handling
    report_lines.append(f"Unique edges found in Biorepo Taxonomy: {len(t2_edges)}\n")

    # Calculate Jaccard Index
    jaccard_index = calculate_jaccard_index(t1_edges, t2_edges)
    report_lines.append(f"\nOverall Jaccard Index for Lineage Edges: {jaccard_index:.4f}\n")

    intersection_len = len(t1_edges.intersection(t2_edges))
    t1_edges_len = len(t1_edges)
    t2_edges_len = len(t2_edges)

    report_lines.append(f"Number of common edges (intersection): {intersection_len}\n")
    report_lines.append(f"Total unique edges (union): {len(t1_edges.union(t2_edges))}\n")

    # Calculate new metrics (NEON HQ matched and Biorepo matched percentages)
    neonhq_match_rate = intersection_len / t1_edges_len if t1_edges_len > 0 else 0.0
    biorepo_match_rate = intersection_len / t2_edges_len if t2_edges_len > 0 else 0.0

    report_lines.append(f"NEON HQ Edges Matched Rate: {neonhq_match_rate:.4f} ({intersection_len}/{t1_edges_len})\n")
    report_lines.append(f"Biorepo Edges Matched Rate: {biorepo_match_rate:.4f} ({intersection_len}/{t2_edges_len})\n")


    # Determine base filename for edge outputs - based on output_path
    output_dir = os.path.dirname(output_path)
    output_basename = os.path.splitext(os.path.basename(output_path))[0]
    
    # Calculate difference sets
    unique_to_neonhq = t1_edges - t2_edges
    unique_to_biorepo = t2_edges - t1_edges

    # Write each set of edges to a file
    write_edges_to_file(t1_edges.union(t2_edges), os.path.join(output_dir, f"{output_basename}_union_edges.txt"))
    write_edges_to_file(t1_edges.intersection(t2_edges), os.path.join(output_dir, f"{output_basename}_intersection_edges.txt"))
    write_edges_to_file(t1_edges, os.path.join(output_dir, f"{output_basename}_neonhq_edges.txt"))
    write_edges_to_file(t2_edges, os.path.join(output_dir, f"{output_basename}_biorepo_edges.txt"))
    write_edges_to_file(unique_to_neonhq, os.path.join(output_dir, f"{output_basename}_unique_to_neonhq_edges.txt"))
    write_edges_to_file(unique_to_biorepo, os.path.join(output_dir, f"{output_basename}_unique_to_biorepo_edges.txt"))

    # Optionally, list some unique edges for insight (useful for debugging)
    MAX_EDGE_EXAMPLES = 10
    
    if unique_to_neonhq:
        report_lines.append(f"\n--- Examples of Edges Unique to NEON HQ Taxonomy (Top {min(MAX_EDGE_EXAMPLES, len(unique_to_neonhq))}) ---\n")
        for i, edge in enumerate(list(sorted(unique_to_neonhq))[:MAX_EDGE_EXAMPLES]):
            report_lines.append(f"  {i+1}. {edge}\n")
    else:
        report_lines.append("\nNo edges found unique to NEON HQ Taxonomy.\n")

    if unique_to_biorepo:
        report_lines.append(f"\n--- Examples of Edges Unique to Biorepo Taxonomy (Top {min(MAX_EDGE_EXAMPLES, len(unique_to_biorepo))}) ---\n")
        for i, edge in enumerate(list(sorted(unique_to_biorepo))[:MAX_EDGE_EXAMPLES]):
            report_lines.append(f"  {i+1}. {edge}\n")
    else:
        report_lines.append("\nNo edges found unique to Biorepo Taxonomy.\n")

    # Write the main report to the output file
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(report_lines)

    print(f"Comparison report saved to: {output_path}")

    # Return a dictionary of all calculated metrics
    return {
        'jaccard_index': jaccard_index,
        'neonhq_match_rate': neonhq_match_rate,
        'biorepo_match_rate': biorepo_match_rate
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compares two taxonomy CSV files (NEON HQ raw vs. biorepo-generated raw) "
                    "by calculating a Jaccard Index on their unique lineage edges based on CSV headers."
    )
    parser.add_argument(
        "--group",
        type=str,
        required=True,
        help="Taxon group code (e.g., ALGAE, HERPS) for reporting purposes and group-specific parsing rules."
    )
    parser.add_argument(
        "--neonhq",
        type=str,
        required=True,
        help="Path to the NEON HQ raw taxonomy CSV file."
    )
    parser.add_argument(
        "--biorepo",
        type=str,
        required=True,
        help="Path to the biorepo raw taxonomy CSV file."
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to the output comparison report (.txt) file. Additional files for edge sets will be created alongside this."
    )
    parser.add_argument(
        "--summary-output",
        type=str,
        help="Optional: Path to a CSV file to append Jaccard indices and other metrics for each group. "
             "If the file does not exist, it will be created with headers."
    )
    args = parser.parse_args()

    # Perform the comparison for the current group
    # The function now returns a dictionary of results
    comparison_results = compare_taxonomies(
        args.group,
        args.neonhq,
        args.biorepo,
        args.output
    )

    # If a summary output file is specified and comparison was successful, append the result
    if args.summary_output and comparison_results is not None:
        summary_filepath = args.summary_output
        file_exists = os.path.exists(summary_filepath)
        
        # Define the header for the summary CSV
        summary_fieldnames = ['group_code', 'jaccard_index', 'neonhq_match_rate', 'biorepo_match_rate']

        try:
            with open(summary_filepath, 'a', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=summary_fieldnames)
                
                # Check if the file is empty to write header
                # Use os.stat and .st_size to check if file is truly empty
                if not file_exists or os.stat(summary_filepath).st_size == 0:
                    writer.writeheader()
                
                writer.writerow({
                    'group_code': args.group,
                    'jaccard_index': f"{comparison_results['jaccard_index']:.4f}",
                    'neonhq_match_rate': f"{comparison_results['neonhq_match_rate']:.4f}",
                    'biorepo_match_rate': f"{comparison_results['biorepo_match_rate']:.4f}"
                })
            print(f"Metrics for {args.group} appended to summary file: {summary_filepath}")
        except Exception as e:
            print(f"Error appending to summary file {summary_filepath}: {e}", file=sys.stderr)
    elif args.summary_output and comparison_results is None:
        # If comparison failed, append a row indicating failure for all metrics
        summary_filepath = args.summary_output
        file_exists = os.path.exists(summary_filepath)
        summary_fieldnames = ['group_code', 'jaccard_index', 'neonhq_match_rate', 'biorepo_match_rate']
        try:
            with open(summary_filepath, 'a', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=summary_fieldnames)
                if not file_exists or os.stat(summary_filepath).st_size == 0:
                    writer.writeheader()
                writer.writerow({
                    'group_code': args.group,
                    'jaccard_index': 'N/A (Error)',
                    'neonhq_match_rate': 'N/A (Error)',
                    'biorepo_match_rate': 'N/A (Error)'
                })
            print(f"Metrics for {args.group} (failed) appended to summary file: {summary_filepath}")
        except Exception as e:
            print(f"Error appending (failed) metrics to summary file {summary_filepath}: {e}", file=sys.stderr)