# scripts/generate_second_taxonomy.py

import argparse
import csv
import json
import os
import sys
import datetime 

def load_csv_to_dict(filepath, key_column_or_list, encoding='utf-8'):
    """
    Loads a CSV file into a dictionary.
    Keys can be from a single column (string) or a compound key (list of strings).
    """
    data = {}
    if not os.path.exists(filepath):
        print(f"Error: Reference file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(filepath, 'r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames 

        if isinstance(key_column_or_list, str):
            if key_column_or_list not in fieldnames:
                print(f"Error: Key column '{key_column_or_list}' not found in {filepath}. Found fields: {fieldnames}", file=sys.stderr)
                sys.exit(1)
            for row in reader:
                data[row[key_column_or_list]] = row
        elif isinstance(key_column_or_list, list):
            missing_cols = [col for col in key_column_or_list if col not in fieldnames]
            if missing_cols:
                print(f"Error: Compound key columns {missing_cols} not found in {filepath}. Found fields: {fieldnames}", file=sys.stderr)
                sys.exit(1)
            for row in reader:
                key = tuple(row[col] for col in key_column_or_list)
                data[key] = row
        else:
            print("Error: key_column_or_list must be a string or a list of strings.", file=sys.stderr)
            sys.exit(1)
    return data

def load_taxa_enum_tree(filepath, encoding='utf-8'):
    """
    Loads biorepo_taxaenumtree.csv. Stores ALL parenttids for each tid,
    as the direct parent resolution will happen in build_lineage based on rankID.
    """
    data = {} # {child_tid: [parent_tid1, parent_tid2, ...]}
    if not os.path.exists(filepath):
        print(f"Error: Reference file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    
    with open(filepath, 'r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f)
        required_cols = ['tid', 'parenttid'] 
        if not all(col in reader.fieldnames for col in required_cols):
            print(f"Error: Missing required columns ({', '.join(required_cols)}) in {filepath}. Found fields: {reader.fieldnames}", file=sys.stderr)
            sys.exit(1)

        for row in reader:
            current_tid = row.get('tid')
            parent_tid = row.get('parenttid')

            if current_tid and parent_tid:
                if current_tid not in data:
                    data[current_tid] = []
                data[current_tid].append(parent_tid)
    return data


def build_lineage(tid, taxa_data, taxa_enum_tree, taxon_units_data):
    """
    Builds the full lineage (Kingdom, Phylum, Class, etc.) for a given tid
    by traversing up the parent tree. The direct parent is determined by
    finding the ancestor with the highest rankID that is strictly less than
    the current tid's rankID.
    Returns a dictionary of ranks.
    """
    lineage = {}
    current_tid = tid

    # Map rankid to rankname from biorepo_taxonunits for quick lookup
    # FIXED: Keyed by 'rankid', not 'taxonunitid' (still relevant and correct)
    rankid_to_rankname = {
        row['rankid']: row['rankname'].lower() 
        for row in taxon_units_data.values()
        if 'rankid' in row and 'rankname' in row and row.get('kingdomName') == 'Organism'
    }

    visited_tids = set() 

    while current_tid and current_tid not in visited_tids:
        visited_tids.add(current_tid)
        
        taxon_info = taxa_data.get(current_tid)
        if not taxon_info:
            break 

        rank_id_str = taxon_info.get('rankID')
        sci_name = taxon_info.get('sciName')

        # Add current taxon to lineage if valid rank
        if rank_id_str and sci_name:
            mapped_rank_name = rankid_to_rankname.get(str(rank_id_str)) 
            if mapped_rank_name:
                lineage[mapped_rank_name] = sci_name  

        # Determine the direct parent based on rankID
        child_rank_id = None
        if rank_id_str:
            try:
                child_rank_id = int(rank_id_str)
            except ValueError:
                print(f"Warning: Invalid rankID '{rank_id_str}' for tid {current_tid}. Cannot determine direct parent based on rank. Stopping traversal.", file=sys.stderr)
                break
        else:
            print(f"Warning: No rankID found for tid {current_tid}. Cannot determine direct parent based on rank. Stopping traversal.", file=sys.stderr)
            break


        potential_parents_list = taxa_enum_tree.get(current_tid, [])

        best_parent_tid = None
        # Initialize with a value lower than any valid parent rankID would be,
        # ensuring the first valid parent is picked.
        closest_parent_rank_id = -1 

        for p_tid in potential_parents_list:
            # Skip self-loops if present in enumtree
            if p_tid == current_tid:
                continue

            parent_taxon_info = taxa_data.get(p_tid)
            if not parent_taxon_info:
                continue

            parent_rank_id_str = parent_taxon_info.get('rankID')
            if not parent_rank_id_str:
                continue

            try:
                parent_rank_id = int(parent_rank_id_str)
            except ValueError:
                continue

            # Rule: Parent rankID must be strictly less than child's rankID (meaning it's a higher rank)
            # We want the one with the largest rankID among valid parents (closest to child's rank numerically, but higher rank)
            if parent_rank_id < child_rank_id and parent_rank_id > closest_parent_rank_id:
                closest_parent_rank_id = parent_rank_id
                best_parent_tid = p_tid

        if best_parent_tid:
            current_tid = best_parent_tid
        else:
            break 

    return lineage


def generate_second_taxonomy(group_code: str,
                              neonhq_taxonomy_path: str,
                              biorepo_neon_taxonomy_path: str,
                              biorepo_taxa_path: str,
                              biorepo_enum_tree_path: str,
                              biorepo_taxon_units_path: str,
                              output_path: str):
    """
    Generates the second taxonomy CSV containing only biorepo-derived data,
    linked by neon_taxonID and neon_lookup_group (from --group argument).
    """
    print(f"--- Step 02: Generating second taxonomy for {group_code} ---")

    # 1. Load reference data
    print(f"Loading biorepo_taxa from: {biorepo_taxa_path}")
    taxa_data = load_csv_to_dict(biorepo_taxa_path, 'tid')

    print(f"Loading biorepo_neon_taxonomy from: {biorepo_neon_taxonomy_path}")
    neon_biorepo_map = load_csv_to_dict(biorepo_neon_taxonomy_path, ['taxonGroup', 'taxonCode'])

    print(f"Loading biorepo_taxaenumtree from: {biorepo_enum_tree_path} (loading all parent-child associations for rank-based resolution)")
    taxa_enum_tree = load_taxa_enum_tree(biorepo_enum_tree_path)

    print(f"Loading biorepo_taxonunits from: {biorepo_taxon_units_path}")
    taxon_units_data = load_csv_to_dict(biorepo_taxon_units_path, 'taxonunitid')

    second_taxonomy_records = []
    all_fieldnames = set() 

    # Dynamically generate biorepo_lineage_fields_ordered using 'rankid' for sorting
    dynamic_ranks = []
    organism_kingdom_rows_found = 0 
    for row in taxon_units_data.values():
        if (row.get('kingdomName') == 'Organism' and
            'rankname' in row and 'rankid' in row): 
            organism_kingdom_rows_found += 1 
            try:
                rank_identifier = int(row['rankid']) 
                dynamic_ranks.append((rank_identifier, "biorepo_" + row['rankname'].lower()))
            except ValueError:
                print(f"Warning: Could not parse rankid '{row.get('rankid')}' for rank '{row.get('rankname')}'. Skipping this rank unit due to invalid rankid format.", file=sys.stderr)
                continue
    
    print(f"Info: Found {organism_kingdom_rows_found} rows with 'kingdomName' as 'Organism' and valid 'rankname'/'rankid' in biorepo_taxonunits.csv.")

    dynamic_ranks.sort(key=lambda x: x[0])
    
    biorepo_lineage_fields_ordered = [rank_name for level, rank_name in dynamic_ranks]
    
    if "biorepo_organism" not in biorepo_lineage_fields_ordered:
        biorepo_lineage_fields_ordered.insert(0, "biorepo_organism")
    
    if not biorepo_lineage_fields_ordered:
        print("Warning: No taxonomic lineage fields could be generated from biorepo_taxonunits.csv after filtering. This might indicate an issue with the file content, column names, or the 'Organism' filter value.", file=sys.stderr)


    core_output_fields_ordered = [
        "neon_taxonID",
        "neon_lookup_group",
        "is_biorepo_mapped",
        "biorepo_tid",
        "scientificName_biorepo",
        "taxonRank_biorepo",
        "verbatimScientificName_biorepo_map",
    ]
    core_output_fields_ordered.extend(biorepo_lineage_fields_ordered)


    print(f"Processing NEON HQ data from: {neonhq_taxonomy_path}")
    if not os.path.exists(neonhq_taxonomy_path):
        print(f"Error: NEON HQ CSV not found for group {group_code}: {neonhq_taxonomy_path}", file=sys.stderr)
        sys.exit(1)

    processed_neon_records = 0 
    processed_mapped_biorepo_records = 0 

    with open(neonhq_taxonomy_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        if 'taxonID' not in reader.fieldnames:
            print(f"Error: NEON HQ file '{neonhq_taxonomy_path}' missing 'taxonID' column. Found fields: {reader.fieldnames}", file=sys.stderr)
            sys.exit(1)

        for neon_record in reader:
            processed_neon_records += 1 
            output_record = {}

            neon_taxon_id = neon_record.get('taxonID')
            lookup_taxon_group = group_code

            output_record['neon_taxonID'] = neon_taxon_id
            output_record['neon_lookup_group'] = lookup_taxon_group

            output_record['is_biorepo_mapped'] = False
            output_record['biorepo_tid'] = None
            output_record['scientificName_biorepo'] = None
            output_record['taxonRank_biorepo'] = None
            output_record['verbatimScientificName_biorepo_map'] = None

            for field in biorepo_lineage_fields_ordered:
                output_record[field] = None

            compound_key_for_map = (lookup_taxon_group, neon_taxon_id)

            if neon_taxon_id and compound_key_for_map in neon_biorepo_map:
                biorepo_map_entry = neon_biorepo_map[compound_key_for_map]
                biorepo_tid = biorepo_map_entry.get('tid')

                if biorepo_tid and biorepo_tid in taxa_data:
                    processed_mapped_biorepo_records += 1 
                    taxa_entry = taxa_data[biorepo_tid]
                    
                    lineage_info = build_lineage(biorepo_tid, taxa_data, taxa_enum_tree, taxon_units_data)

                    output_record['is_biorepo_mapped'] = True
                    output_record['biorepo_tid'] = biorepo_tid
                    output_record['scientificName_biorepo'] = taxa_entry.get('sciName')

                    if taxa_entry.get('rankID'):
                        output_record['taxonRank_biorepo'] = taxon_units_data.get(taxa_entry['rankID'], {}).get('rankname')

                    for rank_key, sci_name in lineage_info.items():
                        formatted_rank_field = f'biorepo_{rank_key}'
                        if formatted_rank_field in biorepo_lineage_fields_ordered:
                             output_record[formatted_rank_field] = sci_name

                    output_record['verbatimScientificName_biorepo_map'] = biorepo_map_entry.get('verbatimScientificName')
                else:
                    print(f"Warning: NEON record (group '{lookup_taxon_group}', ID '{neon_taxon_id}') mapped to biorepo_tid '{biorepo_tid}' but biorepo_tid not found in biorepo_taxa. Only basic map data included for this entry.", file=sys.stderr)
                    output_record['biorepo_tid'] = biorepo_tid
                    output_record['verbatimScientificName_biorepo_map'] = biorepo_map_entry.get('verbatimScientificName')
            else:
                print(f"Info: NEON record (group '{lookup_taxon_group}', ID '{neon_taxon_id}') not found in biorepo_neon_taxonomy mapping. No biorepo data will be included for this entry.", file=sys.stderr)
            
            second_taxonomy_records.append(output_record)
            all_fieldnames.update(output_record.keys())

    if not second_taxonomy_records:
        print(f"No records processed for group '{group_code}'. Output file will be empty.", file=sys.stderr)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        open(output_path, 'w').close()
        return

    final_fieldnames = []
    for field in core_output_fields_ordered:
        if field in all_fieldnames:
            final_fieldnames.append(field)

    remaining_fields = sorted(list(all_fieldnames - set(final_fieldnames)))
    final_fieldnames.extend(remaining_fields)

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        writer.writeheader()
        writer.writerows(second_taxonomy_records)

    print(f"Successfully generated {len(second_taxonomy_records)} second taxonomy records for '{group_code}' to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate second taxonomy CSV by combining NEON HQ data with biorepo data."
    )
    parser.add_argument(
        "--group",
        required=True,
        help="Taxon group code (e.g., ALGAE, MACROINVERTEBRATE). This is used as the 'taxonGroup' part of the compound key for mapping to biorepo data."
    )
    parser.add_argument(
        "--neonhq-taxonomy",
        required=True,
        help="Path to the NEON HQ CSV file (e.g., data/01_downloaded_neonhq/ALGAE.neonhq.csv). "
             "This file must contain a 'taxonID' column."
    )
    parser.add_argument(
        "--biorepo-neon-taxonomy",
        required=True,
        help="Path to biorepo_neon_taxonomy.csv (master mapping from NEON (taxonGroup, taxonCode) to biorepo tid). "
             "This file must contain 'taxonGroup' and 'taxonCode' columns."
    )
    parser.add_argument(
        "--biorepo-taxa",
        required=True,
        help="Path to biorepo_taxa.csv (details for each biorepo tid)."
    )
    parser.add_argument(
        "--biorepo-enum-tree",
        required=True,
        help="Path to biorepo_taxaenumtree.csv (parent-child relationships for biorepo tids)."
    )
    parser.add_argument(
        "--biorepo-taxon-units",
        required=True,
        help="Path to biorepo_taxonunits.csv (maps rankID to rankname)."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output CSV file (e.g., data/02_generated_neonbiorepo/ALGAE.biorepo.csv)."
    )
    args = parser.parse_args()

    generate_second_taxonomy(
        args.group,
        args.neonhq_taxonomy,
        args.biorepo_neon_taxonomy,
        args.biorepo_taxa,
        args.biorepo_enum_tree,
        args.biorepo_taxon_units,
        args.output
    )