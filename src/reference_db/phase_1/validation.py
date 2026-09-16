
from pathlib import Path
import json

import duckdb
import pandas as pd


# Configuration

DB_PATH = "compliments_reference_db.duckdb"

OUTPUT_DIR = Path("data/phase_1")
VALIDATION_DIR = OUTPUT_DIR / "validation"
STATISTICS_DIR = OUTPUT_DIR / "statistics"

VERSION = "1.0.0"
RULES_VERSION = "1.0.0"


# Input / output schema

INPUT_COLUMNS = [
    "retailer_product_id",
    "product_name",
    "brand",
    "retailer",
    "upc",
    "size",
    "price",
    "price_currency",
    "is_available",
    "source",
    "source_url",
    "scraped_at",
    "product_id",
    "private_label",
    "image_url",
    "product_url",
    "category",
]


# Technical columns added by dlt.
# They are not part of the retailer business schema.

DLT_METADATA_COLUMNS = [
    "_dlt_load_id",
    "_dlt_id",
]


OUTPUT_COLUMNS = [
    "external_id",
    "source_retailer",
    "title",
    "brand",
    "barcode",
    "description",
    "ingredients_text",
    "nutrition_text",
    "image_url",
    "size_amount",
    "size_unit",
    "price",
    "currency",
    "scraped_at",
]


REQUIRED_COLUMNS = [
    "external_id",
    "source_retailer",
    "title",
]


OPTIONAL_OUTPUT_COLUMNS = [
    "brand",
    "barcode",
    "description",
    "ingredients_text",
    "nutrition_text",
    "image_url",
    "size_amount",
    "size_unit",
    "price",
    "currency",
    "scraped_at",
]


# Reading

def load_raw_products() -> pd.DataFrame:
    """Load raw product data from DuckDB."""

    connection = duckdb.connect(DB_PATH)

    try:
        df = connection.sql(
            "SELECT * FROM raw.raw_products"
        ).df()
    finally:
        connection.close()

    return df


# Schema validation

def validate_input_schema(df: pd.DataFrame) -> dict:
    """
    Validate the schema received from the ingestion layer.

    dlt technical metadata columns are ignored because they are not
    part of the retailer business schema.
    """

    actual_columns = set(df.columns)

    missing_columns = [
        column
        for column in INPUT_COLUMNS
        if column not in actual_columns
    ]

    new_columns = [
        column
        for column in df.columns
        if column not in INPUT_COLUMNS
        and column not in DLT_METADATA_COLUMNS
    ]

    return {
        "expected_columns": INPUT_COLUMNS,
        "actual_columns": list(df.columns),
        "missing_columns": missing_columns,
        "new_columns": new_columns,
        "schema_valid": len(missing_columns) == 0,
    }


# Generic boundary mapping

def map_to_phase1_schema(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Map the common ingestion schema to the Phase 1 contract schema.

    This mapping is generic and does not contain retailer-specific logic.
    """

    result = pd.DataFrame(index=df.index)

    result["external_id"] = df["retailer_product_id"]

    result["source_retailer"] = df["retailer"]

    result["title"] = df["product_name"]

    result["brand"] = df["brand"]

    result["barcode"] = df["upc"]

    # These fields are not available in the current ingestion schema.
    result["description"] = None
    result["ingredients_text"] = None
    result["nutrition_text"] = None

    result["image_url"] = df["image_url"]

    # Size remains preserved in the ingestion layer as one source value.
    # Parsing it into amount/unit is intentionally not done here.
    result["size_amount"] = None
    result["size_unit"] = None

    result["price"] = df["price"]

    result["currency"] = df["price_currency"]

    result["scraped_at"] = df["scraped_at"]

    return result


# Validation

def validate_required_columns(
    df: pd.DataFrame,
) -> dict:
    """Check that all required Phase 1 columns exist."""

    return {
        column: column in df.columns
        for column in REQUIRED_COLUMNS
    }


def validate_missing_required_values(
    df: pd.DataFrame,
) -> dict:
    """Check required fields for missing values."""

    result = {}

    for column in REQUIRED_COLUMNS:
        result[column] = int(
            df[column].isna().sum()
        )

    return result


def validate_duplicates(
    df: pd.DataFrame,
) -> dict:
    """
    Detect duplicate product identifiers within a retailer.
    """

    duplicate_mask = df.duplicated(
        subset=[
            "source_retailer",
            "external_id",
        ],
        keep=False,
    )

    duplicate_rows = int(
        duplicate_mask.sum()
    )

    if duplicate_rows == 0:
        duplicate_groups = 0
    else:
        duplicate_groups = int(
            df.loc[duplicate_mask]
            .groupby(
                [
                    "source_retailer",
                    "external_id",
                ]
            )
            .ngroups
        )

    return {
        "duplicate_rows": duplicate_rows,
        "duplicate_groups": duplicate_groups,
    }


def validate_data_types(
    df: pd.DataFrame,
) -> dict:
    """
    Validate the important data types required by the contract.
    """

    return {
        "external_id_is_string_like": (
            pd.api.types.is_string_dtype(
                df["external_id"]
            )
        ),
        "source_retailer_is_string_like": (
            pd.api.types.is_string_dtype(
                df["source_retailer"]
            )
        ),
        "title_is_string_like": (
            pd.api.types.is_string_dtype(
                df["title"]
            )
        ),
        "price_is_numeric": (
            pd.api.types.is_numeric_dtype(
                df["price"]
            )
        ),
    }


# Statistics

def calculate_null_statistics(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate null count and null percentage for every column.
    """

    total_rows = len(df)

    statistics = []

    for column in df.columns:
        null_count = int(
            df[column].isna().sum()
        )

        null_percentage = (
            (null_count / total_rows) * 100
            if total_rows > 0
            else 0.0
        )

        statistics.append(
            {
                "column": column,
                "total_rows": total_rows,
                "null_count": null_count,
                "null_percentage": round(
                    null_percentage,
                    2,
                ),
            }
        )

    return pd.DataFrame(statistics)


# Quality status

def determine_quality_status(
    report: dict,
    null_statistics: pd.DataFrame,
) -> str:
    """
    Determine the overall Phase 1 quality status.

    FAIL:
        A critical validation issue exists.

    WARNING:
        Required data is valid, but optional data is missing
        or a non-technical schema change was detected.

    PASS:
        No critical or warning conditions were detected.
    """

    missing_required = report[
        "missing_required_values"
    ]

    if any(
        count > 0
        for count in missing_required.values()
    ):
        return "FAIL"

    duplicates = report["duplicates"]

    if duplicates["duplicate_rows"] > 0:
        return "FAIL"

    data_types = report["data_types"]

    if not all(data_types.values()):
        return "FAIL"

    schema = report["input_schema"]

    if not schema["schema_valid"]:
        return "FAIL"

    warning_columns = []

    for _, row in null_statistics.iterrows():
        if (
            row["column"] in OPTIONAL_OUTPUT_COLUMNS
            and row["null_count"] > 0
        ):
            warning_columns.append(
                row["column"]
            )

    if warning_columns:
        return "WARNING"

    if schema["new_columns"]:
        return "WARNING"

    return "PASS"


# Report

def build_validation_report(
    df: pd.DataFrame,
    raw_df: pd.DataFrame,
    null_statistics: pd.DataFrame,
) -> dict:
    """Build the complete Phase 1 validation report."""

    input_schema = validate_input_schema(
        raw_df
    )

    required_columns = (
        validate_required_columns(df)
    )

    missing_required = (
        validate_missing_required_values(df)
    )

    duplicates = validate_duplicates(df)

    data_types = validate_data_types(df)

    report = {
        "phase": "phase_1_validation",
        "version": VERSION,
        "rules_version": RULES_VERSION,
        "row_count": len(df),
        "column_count": len(df.columns),
        "input_schema": input_schema,
        "required_columns": required_columns,
        "missing_required_values": missing_required,
        "duplicates": duplicates,
        "data_types": data_types,
        "null_statistics": null_statistics.to_dict(
            orient="records"
        ),
    }

    report["quality_status"] = (
        determine_quality_status(
            report,
            null_statistics,
        )
    )

    return report


# Main

def run_phase1() -> None:
    """Execute Phase 1 validation."""

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    VALIDATION_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATISTICS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading raw products...")

    raw_df = load_raw_products()

    print(f"Raw rows: {len(raw_df)}")

    print("Validating input schema...")

    input_schema = validate_input_schema(
        raw_df
    )

    if not input_schema["schema_valid"]:
        print(
            "Phase 1 failed: input schema is invalid."
        )

        print(
            "Missing columns:",
            input_schema["missing_columns"],
        )

        return

    print(
        "Mapping ingestion schema to Phase 1 schema..."
    )

    validated_df = map_to_phase1_schema(
        raw_df
    )

    print("Running validation...")

    null_statistics = (
        calculate_null_statistics(
            validated_df
        )
    )

    report = build_validation_report(
        validated_df,
        raw_df,
        null_statistics,
    )

    print(
        f"Quality status: "
        f"{report['quality_status']}"
    )

    output_path = (
        OUTPUT_DIR
        / "validated_products.parquet"
    )

    statistics_path = (
        STATISTICS_DIR
        / "null_statistics.csv"
    )

    report_path = (
        VALIDATION_DIR
        / "validation_report.json"
    )

    print(
        "Saving validated products..."
    )

    validated_df.to_parquet(
        output_path,
        index=False,
    )

    print(
        "Saving null statistics..."
    )

    null_statistics.to_csv(
        statistics_path,
        index=False,
    )

    print(
        "Saving validation report..."
    )

    with open(
        report_path,
        "w",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    print()
    print("Phase 1 completed.")
    print(
        f"Validated rows: {len(validated_df)}"
    )
    print(
        f"Quality status: "
        f"{report['quality_status']}"
    )
    print(
        f"Output: {output_path}"
    )
    print(
        f"Null statistics: "
        f"{statistics_path}"
    )
    print(
        f"Validation report: "
        f"{report_path}"
    )


if __name__ == "__main__":
    run_phase1()