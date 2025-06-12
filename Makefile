# Define variables
GROUPS = ALGAE BEETLE BIRD FISH HERPETOLOGY MACROINVERTEBRATE MOSQUITO MOSQUITO_PATHOGENS SMALL_MAMMAL PLANT TICK
NEON_API_BASE_URL = https://data.neonscience.org/api/v0/taxonomy

# Main directory for all pipeline data
DATA_DIR = data

# Step-specific directories for outputs
UPLOADED_DATA_DIR = $(DATA_DIR)/00_uploaded_data
DOWNLOAD_DIR = $(DATA_DIR)/01_downloaded_neonhq
GENERATED_DIR = $(DATA_DIR)/02_generated_neonbiorepo
ACCEPTED_TAXONOMY_DIR = $(DATA_DIR)/03_accepted_taxonomies
SIMILARITY_INDEX_DIR = $(DATA_DIR)/04_similiarity_index

# Paths to the biorepo reference files
BIOREPO_NEON_TAXONOMY_FILE = $(UPLOADED_DATA_DIR)/biorepo_neon_taxonomy.csv
BIOREPO_TAXA_FILE = $(UPLOADED_DATA_DIR)/biorepo_taxa.csv
BIOREPO_ENUM_TREE_FILE = $(UPLOADED_DATA_DIR)/biorepo_taxaenumtree.csv
BIOREPO_TAXON_UNITS_FILE = $(UPLOADED_DATA_DIR)/biorepo_taxonunits.csv
BIOREPO_TAXSTATUS_FILE = $(UPLOADED_DATA_DIR)/biorepo_taxstatus.csv

# Python Scripts
DOWNLOAD_SCRIPT = scripts/download_neonhq_taxonomy.py
GENERATE_SCRIPT = scripts/generate_biorepo_taxonomy.py
COMPARE_SCRIPT = scripts/compare_taxonomies.py
ACCEPTED_NEONHQ_SCRIPT = scripts/filter_neonhq_accepted.py
ACCEPTED_BIOREPO_SCRIPT = scripts/filter_biorepo_accepted.py
COMPARE_SCRIPT = scripts/compare_taxonomies.py

# --- Main Target ---
all: similiarity_index

# --- Create all necessary directories ---
dirs:
	@echo "Creating pipeline directories..."
	@mkdir -p $(UPLOADED_DATA_DIR) $(DOWNLOAD_DIR) $(GENERATED_DIR) $(ACCEPTED_TAXONOMY_DIR) $(SIMILARITY_INDEX_DIR)

# --- Step 01: Download NEONHQ Taxonomies for each group ---
download_data: dirs
	@echo "--- Step 01: Downloading NEON HQ taxonomies ---"
	@for group in $(GROUPS); do \
		echo "Downloading $$group..."; \
		python $(DOWNLOAD_SCRIPT) \
			--group $$group \
			--output $(DOWNLOAD_DIR)/$$group.neonhq.csv \
			--api-url $(NEON_API_BASE_URL); \
	done

# --- Step 02: Generate Biorepo Taxonomies for each group ---
generate_data: download_data $(BIOREPO_NEON_TAXONOMY_FILE) $(BIOREPO_TAXA_FILE) $(BIOREPO_ENUM_TREE_FILE) $(BIOREPO_TAXON_UNITS_FILE)
	@echo "--- Step 02: Generating Biorepository taxonomies ---"
	@for group in $(GROUPS); do \
		echo "Generating for $$group..."; \
		python $(GENERATE_SCRIPT) \
			--group $$group \
			--neonhq-taxonomy $(DOWNLOAD_DIR)/$$group.neonhq.csv \
			--biorepo-neon-taxonomy $(BIOREPO_NEON_TAXONOMY_FILE) \
			--biorepo-taxa $(BIOREPO_TAXA_FILE) \
			--biorepo-enum-tree $(BIOREPO_ENUM_TREE_FILE) \
			--biorepo-taxon-units $(BIOREPO_TAXON_UNITS_FILE) \
			--output $(GENERATED_DIR)/$$group.biorepo.csv; \
	done

# --- Step 03: Rework Taxonomies to Accepted taxa ---
rework_taxonomies_accepted: generate_data $(BIOREPO_TAXSTATUS_FILE)
	@echo "--- Step 03: Reworking Taxonomies to Accepted taxa ---"
	@for group in $(GROUPS); do \
		echo "Reworking $$group..."; \
		python $(ACCEPTED_NEONHQ_SCRIPT) \
			--input $(DOWNLOAD_DIR)/$$group.neonhq.csv \
			--output $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.csv; \
		{ \
		  head -n 1 $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.csv; \
		  tail -n +2 $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.csv | sort -t ',' -k 1,1; \
		} > $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.sorted.csv; \
		mv $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.sorted.csv $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.csv; \
		python $(ACCEPTED_BIOREPO_SCRIPT) \
			--input $(GENERATED_DIR)/$$group.biorepo.csv \
			--taxstatus $(BIOREPO_TAXSTATUS_FILE) \
			--output $(ACCEPTED_TAXONOMY_DIR)/$$group.biorepo.accepted.csv; \
	done


# --- Step 04: Create Jaccard similarity index ---
similiarity_index: rework_taxonomies_accepted
	@echo "--- Step 04: Creating Jaccard Similarity Index ---"
	rm $(SIMILARITY_INDEX_DIR)/jaccard_summary.csv;
	@for group in $(GROUPS); do \
		echo "Calculating Similarity Index for $$group..."; \
		python $(COMPARE_SCRIPT) \
			--group $$group \
			--summary-output $(SIMILARITY_INDEX_DIR)/jaccard_summary.csv \
			--neonhq $(ACCEPTED_TAXONOMY_DIR)/$$group.neonhq.accepted.csv \
			--biorepo $(ACCEPTED_TAXONOMY_DIR)/$$group.biorepo.accepted.csv \
			--output $(SIMILARITY_INDEX_DIR)/$$group.comparison.txt; \
	done