# Reference DB system

A reusable data pipeline for building retailer-level reference datasets for Open Food Facts Canada.

## Overview

Reference DB transforms raw retailer product data into standardized, validated, classified, grouped, and enriched product datasets.

The pipeline is designed to support multiple retailers while keeping retailer-specific extraction logic isolated from the generic processing pipeline.

## Architecture

```text
Retailer Source
      ↓
Retailer Adapter
      ↓
Ingestion
      ↓
Phase 1 — Validation
      ↓
Phase 2 — Identity
      ↓
Phase 3 — Classification + Taxonomy + Grouping
      ↓
Phase 4 — Variants
      ↓
Phase 5 — Nutrition
      ↓
Phase 6 — Scores & Enrichment
      ↓
Retailer Reference Dataset
```

## Project Structure

```text
reference-db/
│
├── contracts/
│   ├── ingestion/
│   ├── phase_1/
│   ├── phase_2/
│   ├── phase_3/
│   ├── phase_4/
│   ├── phase_5/
│   └── phase_6/
│
├── reference_data/
│   └── taxonomy/
│
├── src/
│   └── reference_db/
│       ├── adapters/
│       ├── ingestion/
│       ├── phase_1/
│       ├── phase_2/
│       ├── phase_3/
│       ├── phase_4/
│       ├── phase_5/
│       ├── phase_6/
│       └── orchestration/
│
├── tests/
├── data/
├── README.md
├── pyproject.toml
└── .gitignore
```

## Supported Retailers

The architecture is designed to support:

* Walmart
* Costco
* Metro
* Voilà / Sobeys

Additional retailers can be added through new adapters without changing the generic pipeline phases.

## Technology Stack

* Python
* dlt — data ingestion
* DuckDB — analytical storage
* dbt — SQL transformations and data quality tests
* Prefect — workflow orchestration
* pytest — testing

## Design Principles

* Keep retailer-specific logic inside adapters.
* Keep processing phases retailer-agnostic.
* Preserve source identifiers and provenance.
* Never invent missing source values.
* Keep identity separate from variants.
* Keep classification, taxonomy, and product grouping as separate concerns.
* Preserve traceability from processed records back to source data.
* Validate data at phase boundaries using executable data contracts.
* Prefer simple implementations before introducing additional infrastructure.

## Pipeline Phases

### Phase 1 — Validation

Validates the ingested product dataset against the ingestion contract and checks required fields, data types, identifiers, and duplicate records.

### Phase 2 — Identity

Builds a standardized product identity representation and separates identity attributes from variant attributes.

### Phase 3 — Classification, Taxonomy & Grouping

Classifies products, assigns the Reference DB taxonomy, and creates product groups based on product identity.

### Phase 4 — Variants

Models variants within existing product groups.

### Phase 5 — Nutrition

Standardizes and validates nutrition data and links it to products.

### Phase 6 — Scores & Enrichment

Calculates available product scores and assigns enrichment references such as Nutri-Score and Agribalyse references where possible.

## Data Contracts

Each pipeline stage has a versioned contract defining:

* Expected input schema
* Expected output schema
* Required and optional fields
* Processing responsibilities
* Quality expectations
* Primary identifiers
* Lineage

Contracts are stored under `contracts/`.

## Data

Raw and generated datasets are not committed to this repository by default.

The `data/` directory is intended for local or generated pipeline data.

## Development

Create and activate the virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the project in editable mode:

```bash
pip install -e .
```

Run tests:

```bash
pytest
```

## Status

The repository currently contains the project architecture, contracts, and implementation skeleton.

Pipeline phases are being implemented incrementally and tested independently before being integrated into the complete workflow.
