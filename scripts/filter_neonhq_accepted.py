import argparse
import csv
import os
import sys

def select_neonhq_accepted(input_filepath, output_filepath, id_col='taxonID', accepted_id_col='acceptedTaxonID'):
    """
    Selects rows from the NEON HQ taxonomy where taxonID matches acceptedTaxonID,
    and then collapses 'SPP' forms to 'SP' forms if both exist for the same base name.
    """
    print(f"--- Selecting accepted taxa from NEON HQ: {os.path.basename(input_filepath)} ---")

    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        sys.exit(1)

    initial_accepted_rows = {} # Store rows where taxonID == acceptedTaxonID, keyed by taxonID
    fieldnames = []
    processed_count = 0

    try:
        with open(input_filepath, 'r', encoding='utf-8', newline='') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames

            if id_col not in fieldnames:
                print(f"Error: Required column '{id_col}' not found in '{input_filepath}'. Found: {fieldnames}", file=sys.stderr)
                sys.exit(1)
            if accepted_id_col not in fieldnames:
                print(f"Error: Required column '{accepted_id_col}' not found in '{input_filepath}'. Found: {fieldnames}", file=sys.stderr)
                sys.exit(1)

            for row in reader:
                processed_count += 1
                taxon_id = row.get(id_col)
                accepted_taxon_id = row.get(accepted_id_col)

                if taxon_id and accepted_taxon_id and taxon_id == accepted_taxon_id:
                    initial_accepted_rows[taxon_id] = row

        if not fieldnames:
            print(f"Warning: Input file '{input_filepath}' was empty or had no headers.", file=sys.stderr)
            # Proceed to create an empty output file.

        print(f"Initial pass: Identified {len(initial_accepted_rows)} self-accepted taxa.")

        final_selected_rows = []
        # This set will track base_name -> {'SP': row, 'SPP': row}
        # to handle the collapse logic
        sp_spp_resolver = {}
        processed_taxon_ids = set() # To prevent adding the same taxonID twice in final selection

        # Second pass: Apply SP/SPP collapse logic
        for taxon_id, row_data in initial_accepted_rows.items():
            if taxon_id in processed_taxon_ids:
                continue # Already handled as part of a collapse group or directly added

            # Check for SP/SPP pattern
            if taxon_id.endswith('SPP'):
                base_name = taxon_id[:-3]
                sp_key = base_name + 'SP'
                
                # Check if the SP version exists and is also self-accepted
                if sp_key in initial_accepted_rows:
                    # Both SPP and SP versions exist and are self-accepted
                    # Prioritize SP, add SP to resolver, mark SPP as processed
                    sp_spp_resolver.setdefault(base_name, {})['SP'] = initial_accepted_rows[sp_key]
                    sp_spp_resolver.setdefault(base_name, {})['SPP'] = row_data # Store SPP for completeness but will prefer SP
                    processed_taxon_ids.add(taxon_id) # Mark SPP as processed
                    processed_taxon_ids.add(sp_key) # Mark SP as processed
                else:
                    # Only SPP version exists or SP version is not self-accepted, keep SPP
                    final_selected_rows.append(row_data)
                    processed_taxon_ids.add(taxon_id)

            elif taxon_id.endswith('SP'):
                base_name = taxon_id[:-2]
                spp_key = base_name + 'SPP'
                
                # If the SPP version exists and is also self-accepted, this SP will be handled by the SPP block
                # Otherwise, it's just a standalone SP, so we add it.
                if spp_key not in initial_accepted_rows:
                    final_selected_rows.append(row_data)
                    processed_taxon_ids.add(taxon_id)
                # If spp_key IS in initial_accepted_rows, it means the SPP block above
                # already handled this base_name, including both SP and SPP via sp_spp_resolver.
                # So we just mark SP as processed and move on.
                else:
                    processed_taxon_ids.add(taxon_id)
            else:
                # Not an SP/SPP variant, just add it if not already processed
                if taxon_id not in processed_taxon_ids:
                    final_selected_rows.append(row_data)
                    processed_taxon_ids.add(taxon_id)
        
        # Finally, add the resolved SP/SPP groups
        for base_name, variants in sp_spp_resolver.items():
            if 'SP' in variants:
                final_selected_rows.append(variants['SP'])
            elif 'SPP' in variants: # Fallback if only SPP was found for some reason
                final_selected_rows.append(variants['SPP'])
            # No need for else, if it got into sp_spp_resolver, it must have at least one variant.

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_filepath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_filepath, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(final_selected_rows)

        print(f"Processed {processed_count} rows from input. Selected {len(final_selected_rows)} unique accepted taxa after SP/SPP collapse.")
        print(f"Accepted taxa saved to: {output_filepath}")

    except Exception as e:
        print(f"An error occurred during processing: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Selects accepted taxa from NEON HQ taxonomy CSV files and collapses SPP to SP variants."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the input NEON HQ taxonomy CSV file (e.g., ALGAE.neonhq.csv)."
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to the output CSV file for accepted taxa (e.g., ALGAE.accepted.csv)."
    )
    args = parser.parse_args()

    select_neonhq_accepted(args.input, args.output)