NEON Taxonomy Similarity Index
===============================

This project provides a structured pipeline for comparing taxonomic data from the NEON HQ API with internal Biorepository (Biorepo) taxonomy reference files. The comparison is performed across multiple organismal groups using Jaccard similarity metrics.

Overview
--------

The pipeline executes the following steps:

1.  **Download taxonomies from NEON HQ** for each target group.

2.  **Generate corresponding Biorepo taxonomies** using internal reference files.

3.  **Filter to only accepted taxa** for a fair comparison.

4.  **Compute Jaccard similarity indexes** to assess concordance.

The pipeline is executed using a `Makefile` and Python scripts.

* * * * *

Prerequisites
-------------

-   Python 2+

-   Make (Linux/macOS) or GNU Make on Windows

### Directory Structure

```graphql
/
├── Makefile
├── scripts/
│   ├── download_neonhq_taxonomy.py
│   ├── generate_biorepo_taxonomy.py
│   ├── compare_taxonomies.py
│   ├── filter_neonhq_accepted.py
│   └── filter_biorepo_accepted.py
├── data/
│   ├── 00_uploaded_data/
│   ├── 01_downloaded_neonhq/
│   ├── 02_generated_neonbiorepo/
│   ├── 03_accepted_taxonomies/
│   └── 04_similiarity_index/
```

* * * * *

Usage
-----

### Step-by-Step

To run the entire pipeline:

```bash
make all
```

Or run step-by-step:

```bash
make dirs                   # Create necessary directories
make download_data          # Step 01: Download NEON HQ taxonomy data
make generate_data          # Step 02: Generate Biorepo taxonomies
make rework_taxonomies_accepted  # Step 03: Filter to accepted taxa
make similiarity_index      # Step 04: Compute Jaccard similarity index`
```

* * * * *

Inputs
------

Located in `data/00_uploaded_data/`:

-   `biorepo_neon_taxonomy.csv`

-   `biorepo_taxa.csv`

-   `biorepo_taxaenumtree.csv`

-   `biorepo_taxonunits.csv`

-   `biorepo_taxstatus.csv`

These are tables downloaded directly from the Biorepository database on 2025-06-10.

* * * * *

Outputs
-------

Each stage writes its results to subdirectories within `data/`:

-   **01_downloaded_neonhq/**: Raw NEON taxonomies per group

-   **02_generated_neonbiorepo/**: Generated Biorepo taxonomies

-   **03_accepted_taxonomies/**: Filtered (accepted-only) taxonomies

-   **04_similiarity_index/**:

    -   `jaccard_summary.csv`: Summary of similarity scores

    -   `<group>.comparison.txt`: Detailed comparison logs

* * * * *



Output Files
---------------

-   **`GROUP.comparison.txt`**
    A summary report of the comparison, including the Jaccard index score and counts of shared and unique taxa.

-   **`GROUP.comparison_biorepo_edges.txt`**
    Taxonomic relationships (e.g. parent-child edges) derived from the Biorepo dataset.

-   **`GROUP.comparison_neonhq_edges.txt`**
    Taxonomic relationships extracted from the NEON HQ dataset.

-   **`GROUP.comparison_union_edges.txt`**
    Combined set of all edges from both datasets---useful for visualizing the full taxonomic space.

-   **`GROUP.comparison_intersection_edges.txt`**
    Edges that are common to both NEON HQ and Biorepo datasets---these represent overlapping taxonomy structures.

-   **`GROUP.comparison_unique_to_biorepo_edges.txt`**
    Edges found only in the Biorepo dataset---indicating taxa or structures not present in NEON HQ.

-   **`GROUP.comparison_unique_to_neonhq_edges.txt`**
    Edges found only in the NEON HQ dataset---indicating taxa or structures not present in Biorepo.

Organism Groups
---------------

The pipeline processes the following groups:

-   ALGAE
-   BEETLE
-   BIRD
-   FISH
-   HERPETOLOGY
-   MACROINVERTEBRATE
-   MOSQUITO
-   MOSQUITO_PATHOGENS
-   SMALL_MAMMAL
-   PLANT
-   TICK

* * * * *

Notes
-----

### About the Jaccard Index

The **Jaccard Index** is a statistical measure used to compare the similarity and diversity between two sets. In the context of this pipeline, it quantifies the overlap between accepted taxonomies from NEON HQ and Biorepository datasets for a given organism group.

It is calculated as:

```
Jaccard Index = (Number of shared taxa) / (Total unique taxa across both datasets)
```

The resulting value ranges from **0** (no overlap) to **1** (perfect match). Higher values indicate greater consistency between the NEON and Biorepo taxonomies for that group, helping identify alignment or discrepancies in naming and classification.

### Underinflated Values

Some Jaccard index values may appear lower than expected due to inconsistencies in how taxonomic data is formatted or structured across different groups. While custom logic has been implemented to account for major group-specific formatting differences, there may still be unhandled edge cases where semantically equivalent taxa are represented differently (e.g., naming conventions, rank abbreviations, field usage). These mismatches can cause matching taxa to be treated as distinct, leading to underreporting in shared edges or overlapping taxa.

