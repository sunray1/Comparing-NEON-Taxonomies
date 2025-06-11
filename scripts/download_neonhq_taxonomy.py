# scripts/download_taxonomy.py

import requests
import json
import csv
import argparse
import sys
import os

def download_taxonomy(group_code: str, output_path: str, api_base_url: str):
    """
    Downloads all taxonomy data for a specific group from the NEON API,
    handling pagination, and saves it as a CSV file.

    Args:
        group_code (str): The taxon type code (e.g., 'ALGAE', 'FISH').
        output_path (str): The file path where the CSV data will be saved.
                           Expected to be like 'data/01_downloaded_neonhq/GROUP.csv'.
        api_base_url (str): The base URL for the NEON taxonomy API.
    """
    all_records = []
    next_page_url = f"{api_base_url}?taxonTypeCode={group_code}&verbose=true&limit=1000" # Start with limit=100

    print(f"Starting download for group '{group_code}'...")

    try:
        while next_page_url:
            print(f"Fetching page from: {next_page_url}")
            response = requests.get(next_page_url, timeout=60) # Increased timeout to 60 seconds
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

            page_data = response.json()

            # Extend the list with records from the current page
            if 'data' in page_data and isinstance(page_data['data'], list):
                all_records.extend(page_data['data'])
            else:
                print(f"Warning: 'data' key not found or not a list in response for {group_code} from {next_page_url}", file=sys.stderr)
                break # Stop if data format is unexpected

            # Check for the next page
            next_page_url = page_data.get('next')
            if next_page_url == "": # API might return empty string instead of null for last page
                next_page_url = None

        if not all_records:
            print(f"No records found for group '{group_code}'. Output file will be empty.", file=sys.stderr)
            # Create an empty file to satisfy Makefile dependency
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                pass # Create empty file
            return

        # Prepare for CSV writing
        # Get all unique field names from all records to use as CSV headers
        fieldnames = set()
        for record in all_records:
            fieldnames.update(record.keys())
        # Convert set to list for consistent order, could sort if desired
        fieldnames = sorted(list(fieldnames))

        # Ensure the output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)

        print(f"Successfully downloaded and saved {len(all_records)} records for '{group_code}' to: {output_path}")

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error downloading for group '{group_code}': {e}", file=sys.stderr)
        print(f"Response content: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error downloading for group '{group_code}': {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        print(f"Timeout error downloading for group '{group_code}': {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"An unexpected request error occurred for group '{group_code}': {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON from response for group '{group_code}': {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"File I/O error when writing to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unhandled error occurred during download for group '{group_code}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download paginated taxonomy data from the NEON API and save it as CSV."
    )
    parser.add_argument(
        "--group",
        required=True,
        help="Taxon type code to download (e.g., ALGAE, FISH)."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output CSV file (e.g., data/01_downloaded_neonhq/ALGAE.csv)."
    )
    parser.add_argument(
        "--api-url",
        required=True,
        help="Base URL for the NEON taxonomy API (e.g., https://data.neonscience.org/api/v0/taxonomy)."
    )
    args = parser.parse_args()

    download_taxonomy(args.group, args.output, args.api_url)