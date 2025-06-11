import argparse
import csv
import os
import sys

def select_biorepo_accepted(input_filepath, taxstatus_filepath, output_filepath,
                            biorepo_tid_col='biorepo_tid', taxstatus_tid_col='tid',
                            taxstatus_accepted_tid_col='tidaccepted'):
    """
    Selects rows from the biorepo-generated taxonomy where the biorepo_tid
    is an accepted tid according to biorepo_taxstatus.csv, ensuring uniqueness
    of accepted tids in the output.
    """
    print(f"--- Selecting accepted taxa from Biorepo-generated: {os.path.basename(input_filepath)} ---")

    if not os.path.exists(input_filepath):
        print(f"Error: Input file not found: {input_filepath}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(taxstatus_filepath):
        print(f"Error: Biorepo tax status file not found: {taxstatus_filepath}", file=sys.stderr)
        sys.exit(1)

    # 1. Load accepted tids from biorepo_taxstatus.csv
    accepted_tids = set()
    try:
        with open(taxstatus_filepath, 'r', encoding='utf-8', newline='') as ts_file:
            reader = csv.DictReader(ts_file)
            if taxstatus_tid_col not in reader.fieldnames or taxstatus_accepted_tid_col not in reader.fieldnames:
                print(f"Error: Biorepo tax status file '{taxstatus_filepath}' missing '{taxstatus_tid_col}' or '{taxstatus_accepted_tid_col}' column.", file=sys.stderr)
                sys.exit(1)
            for row in reader:
                tid = row.get(taxstatus_tid_col)
                tid_accepted = row.get(taxstatus_accepted_tid_col)
                if tid and tid_accepted and tid == tid_accepted:
                    accepted_tids.add(tid)
        if not accepted_tids:
            print("Warning: No accepted tids found in biorepo_taxstatus.csv. Output will be empty.", file=sys.stderr)

    except Exception as e:
        print(f"An error occurred reading biorepo_taxstatus.csv: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Process the main biorepo-generated taxonomy file
    selected_rows = []
    fieldnames = []
    processed_count = 0
    selected_count = 0
    seen_output_tids = set() # To ensure uniqueness in the output based on biorepo_tid

    try:
        with open(input_filepath, 'r', encoding='utf-8', newline='') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames

            if biorepo_tid_col not in fieldnames:
                print(f"Error: Required column '{biorepo_tid_col}' not found in '{input_filepath}'. Found: {fieldnames}", file=sys.stderr)
                sys.exit(1)

            for row in reader:
                processed_count += 1
                current_biorepo_tid = row.get(biorepo_tid_col)

                if current_biorepo_tid and \
                   current_biorepo_tid in accepted_tids and \
                   current_biorepo_tid not in seen_output_tids: # Ensure unique accepted tids in output
                    selected_rows.append(row)
                    seen_output_tids.add(current_biorepo_tid)
                    selected_count += 1

        if not fieldnames:
            print(f"Warning: Input file '{input_filepath}' was empty or had no headers.", file=sys.stderr)
            # Proceed to create an empty output file.

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_filepath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_filepath, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(selected_rows)

        print(f"Processed {processed_count} rows from input. Selected {selected_count} unique accepted taxa.")
        print(f"Accepted Biorepo taxa saved to: {output_filepath}")

    except Exception as e:
        print(f"An error occurred during processing: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Selects accepted taxa from biorepo-generated taxonomy CSV files."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the input biorepo-generated taxonomy CSV file (e.g., ALGAE.biorepo.csv)."
    )
    parser.add_argument(
        "--taxstatus",
        type=str,
        required=True,
        help="Path to the biorepo_taxstatus.csv file."
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to the output CSV file for accepted taxa (e.g., ALGAE.biorepo.accepted.csv)."
    )
    args = parser.parse_args()

    select_biorepo_accepted(args.input, args.taxstatus, args.output)