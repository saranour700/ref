from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import duckdb
import pandas as pd
from huggingface_hub import HfApi, hf_hub_download


HF_DATASET = "saraNour/compliments-reference-db"

INPUT_FILE = "phase_1/validated_products.parquet"

OUTPUT_FILE = "phase_2/standardized_products.parquet"
STATISTICS_FILE = "phase_2/statistics/identity_statistics.json"
VALIDATION_FILE = "phase_2/validation/validation_report.json"


REQUIRED_COLUMNS = [
    "external_id",
    "source_retailer",
    "brand",
    "title",
]

OPTIONAL_COLUMNS = [
    "barcode",
    "size_amount",
    "size_unit",
    "description",
    "ingredients_text",
    "nutrition_text",
    "image_url",
    "price",
    "currency",
]


IDENTITY_PATTERNS = {
    "organic": [r"\borganic\b"],
    "gluten_free": [r"\bgluten[- ]free\b"],
    "naturally_simple": [r"\bnaturally simple\b"],
    "sugar_free": [r"\bsugar[- ]free\b"],
    "unsalted": [r"\bunsalted\b"],
    "lactose_free": [r"\blactose[- ]free\b"],
    "peanut_free": [r"\bpeanut[- ]free\b"],
    "plant_based": [r"\bplant[- ]based\b"],
    "reduced_sodium": [r"\breduced sodium\b"],
}


FLAVOUR_PATTERNS = [
    "vanilla",
    "chocolate",
    "strawberry",
    "blueberry",
    "raspberry",
    "banana",
    "peach",
    "mango",
    "coffee",
    "caramel",
    "lemon",
    "lime",
    "original",
    "plain",
]


FORMULATION_PATTERNS = [
    "whole",
    "partly skimmed",
    "partially skimmed",
    "skim",
    "shredded",
    "sliced",
    "diced",
    "chopped",
    "powder",
    "liquid",
    "frozen",
    "fresh",
    "roasted",
]


def clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return re.sub(r"\s+", " ", value)


def normalize_text(value: Any) -> str | None:
    value = clean_text(value)

    if value is None:
        return None

    value = value.lower()
    value = value.replace("–", "-")
    value = value.replace("—", "-")

    return re.sub(r"\s+", " ", value).strip()


def normalize_brand(value: Any) -> str | None:
    return clean_text(value)


def extract_product_name(
    title: Any,
    brand: Any,
) -> str | None:
    title_clean = clean_text(title)
    brand_clean = clean_text(brand)

    if title_clean is None:
        return None

    if brand_clean is None:
        return title_clean

    if title_clean.lower().startswith(brand_clean.lower()):
        product_name = title_clean[len(brand_clean):].strip()
        product_name = re.sub(r"^[\s\-|:/]+", "", product_name)

        return product_name or title_clean

    return title_clean


def extract_identity_attributes(
    title: Any,
) -> dict[str, Any]:
    normalized = normalize_text(title)

    if normalized is None:
        return {}

    attributes = {}

    for attribute, patterns in IDENTITY_PATTERNS.items():
        attributes[attribute] = any(
            re.search(pattern, normalized)
            for pattern in patterns
        )

    return attributes


def extract_fat_attributes(
    title: Any,
) -> dict[str, Any]:
    normalized = normalize_text(title)

    result = {
        "fat_percentage": None,
        "fat_level": None,
    }

    if normalized is None:
        return result

    percentage_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*%",
        normalized,
    )

    if percentage_match:
        result["fat_percentage"] = float(
            percentage_match.group(1)
        )

    fat_levels = {
        "fat_free": [
            r"\bfat[- ]free\b",
            r"\bskim\b",
            r"\bskimmed\b",
        ],
        "low_fat": [
            r"\blow[- ]fat\b",
        ],
        "reduced_fat": [
            r"\breduced[- ]fat\b",
        ],
        "full_fat": [
            r"\bfull[- ]fat\b",
        ],
    }

    for level, patterns in fat_levels.items():
        if any(
            re.search(pattern, normalized)
            for pattern in patterns
        ):
            result["fat_level"] = level
            break

    return result


def extract_flavour(
    title: Any,
) -> str | None:
    normalized = normalize_text(title)

    if normalized is None:
        return None

    for flavour in FLAVOUR_PATTERNS:
        if re.search(
            rf"\b{re.escape(flavour)}\b",
            normalized,
        ):
            return flavour

    return None


def extract_formulation(
    title: Any,
) -> str | None:
    normalized = normalize_text(title)

    if normalized is None:
        return None

    for formulation in FORMULATION_PATTERNS:
        if re.search(
            rf"\b{re.escape(formulation)}\b",
            normalized,
        ):
            return formulation

    return None


def extract_variant_attributes(
    size_amount: Any,
    size_unit: Any,
) -> dict[str, Any]:
    attributes = {}

    amount = clean_text(size_amount)
    unit = clean_text(size_unit)

    if amount is not None:
        attributes["size_amount"] = amount

    if unit is not None:
        attributes["size_unit"] = unit

    return attributes


def build_identity_attributes(
    title: Any,
) -> dict[str, Any]:
    attributes = extract_identity_attributes(title)

    attributes.update(
        extract_fat_attributes(title)
    )

    flavour = extract_flavour(title)

    if flavour is not None:
        attributes["flavour"] = flavour

    formulation = extract_formulation(title)

    if formulation is not None:
        attributes["formulation"] = formulation

    return attributes


def build_identity_hash(
    source_retailer: Any,
    brand: Any,
    product_name: Any,
    identity_attributes: dict[str, Any],
) -> str:
    payload = {
        "source_retailer": normalize_text(
            source_retailer
        ),
        "brand": normalize_text(brand),
        "product_name": normalize_text(product_name),
        "identity_attributes": identity_attributes,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def validate_input_schema(
    df: pd.DataFrame,
) -> None:
    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )


def transform_products(
    df: pd.DataFrame,
) -> pd.DataFrame:
    validate_input_schema(df)

    records = []

    for _, row in df.iterrows():
        external_id = clean_text(
            row["external_id"]
        )

        source_retailer = clean_text(
            row["source_retailer"]
        )

        brand = normalize_brand(
            row["brand"]
        )

        title = clean_text(
            row["title"]
        )

        product_name = extract_product_name(
            title,
            brand,
        )

        identity_attributes = (
            build_identity_attributes(title)
        )

        variant_attributes = (
            extract_variant_attributes(
                row.get("size_amount"),
                row.get("size_unit"),
            )
        )

        identity_hash = build_identity_hash(
            source_retailer,
            brand,
            product_name,
            identity_attributes,
        )

        records.append(
            {
                "external_id": external_id,
                "source_retailer": source_retailer,
                "barcode": clean_text(
                    row.get("barcode")
                ),
                "brand": brand,
                "title": title,
                "product_name": product_name,
                "identity_attributes": json.dumps(
                    identity_attributes,
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "variant_attributes": json.dumps(
                    variant_attributes,
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "size_amount": clean_text(
                    row.get("size_amount")
                ),
                "size_unit": clean_text(
                    row.get("size_unit")
                ),
                "identity_hash": identity_hash,
            }
        )

    return pd.DataFrame(records)


def load_from_huggingface() -> pd.DataFrame:
    print(
        f"Reading Phase 1 output from HF: "
        f"{INPUT_FILE}"
    )

    local_file = hf_hub_download(
        repo_id=HF_DATASET,
        filename=INPUT_FILE,
        repo_type="dataset",
    )

    return pd.read_parquet(local_file)


def build_statistics(
    df: pd.DataFrame,
) -> dict[str, Any]:
    duplicate_count = int(
        df.duplicated(
            subset=[
                "source_retailer",
                "external_id",
            ],
            keep=False,
        ).sum()
    )

    return {
        "input_rows": int(len(df)),
        "output_rows": int(len(df)),
        "duplicate_product_keys": duplicate_count,
        "missing_product_name": int(
            df["product_name"].isna().sum()
        ),
        "missing_brand": int(
            df["brand"].isna().sum()
        ),
        "missing_barcode": int(
            df["barcode"].isna().sum()
        ),
        "missing_identity_hash": int(
            df["identity_hash"].isna().sum()
        ),
        "unique_identity_hashes": int(
            df["identity_hash"].nunique()
        ),
    }


def build_validation_report(
    df: pd.DataFrame,
    statistics: dict[str, Any],
) -> dict[str, Any]:
    critical_errors = []
    warnings = []

    if statistics["missing_product_name"] > 0:
        critical_errors.append(
            "missing_product_identity"
        )

    if statistics["duplicate_product_keys"] > 0:
        critical_errors.append(
            "duplicate_external_id_within_retailer"
        )

    if statistics["missing_identity_hash"] > 0:
        critical_errors.append(
            "missing_identity_hash"
        )

    if statistics["missing_brand"] > 0:
        warnings.append("missing_brand")

    if statistics["missing_barcode"] > 0:
        warnings.append("missing_barcode")

    if critical_errors:
        status = "FAIL"
    elif warnings:
        status = "WARNING"
    else:
        status = "PASS"

    return {
        "phase": "phase_2_identity",
        "status": status,
        "input_rows": int(len(df)),
        "output_rows": int(len(df)),
        "critical_errors": critical_errors,
        "warnings": warnings,
        "statistics": statistics,
        "decision": (
            "continue"
            if status in {"PASS", "WARNING"}
            else "stop"
        ),
    }


def upload_to_huggingface(
    df: pd.DataFrame,
    statistics: dict[str, Any],
    report: dict[str, Any],
) -> None:
    api = HfApi()

    parquet_path = "/tmp/standardized_products.parquet"
    statistics_path = "/tmp/identity_statistics.json"
    validation_path = "/tmp/validation_report.json"

    df.to_parquet(
        parquet_path,
        index=False,
    )

    with open(
        statistics_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            statistics,
            file,
            indent=2,
            ensure_ascii=False,
        )

    with open(
        validation_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    api.upload_file(
        path_or_fileobj=parquet_path,
        path_in_repo=OUTPUT_FILE,
        repo_id=HF_DATASET,
        repo_type="dataset",
    )

    api.upload_file(
        path_or_fileobj=statistics_path,
        path_in_repo=STATISTICS_FILE,
        repo_id=HF_DATASET,
        repo_type="dataset",
    )

    api.upload_file(
        path_or_fileobj=validation_path,
        path_in_repo=VALIDATION_FILE,
        repo_id=HF_DATASET,
        repo_type="dataset",
    )


def run_phase_2() -> pd.DataFrame:
    print(
        "Starting Phase 2 — "
        "Identity / Semantic Normalization"
    )

    input_df = load_from_huggingface()

    print(
        f"Phase 1 rows received: {len(input_df)}"
    )

    output_df = transform_products(input_df)

    statistics = build_statistics(
        output_df
    )

    report = build_validation_report(
        output_df,
        statistics,
    )

    upload_to_huggingface(
        output_df,
        statistics,
        report,
    )

    print()
    print("Phase 2 completed.")
    print(
        f"Output rows: {len(output_df)}"
    )
    print(
        f"Status: {report['status']}"
    )
    print(
        f"Uploaded: {OUTPUT_FILE}"
    )

    return output_df


if __name__ == "__main__":
    run_phase_2()