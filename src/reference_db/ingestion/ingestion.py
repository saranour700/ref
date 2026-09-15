import dlt
import duckdb

from reference_db.adapters.base import RetailerAdapter


DB_PATH = "compliments_reference_db.duckdb"


def get_existing_product_ids() -> set[tuple[str, str]]:
    """Return product identities already stored in the raw layer."""
    connection = duckdb.connect(DB_PATH)

    try:
        rows = connection.sql(
            """
            SELECT retailer, retailer_product_id
            FROM raw.raw_products
            """
        ).fetchall()

        return set(rows)

    except duckdb.CatalogException:
        return set()

    finally:
        connection.close()


def get_existing_nutrition_ids() -> set[str]:
    """Return nutrition product IDs already stored."""
    connection = duckdb.connect(DB_PATH)

    try:
        rows = connection.sql(
            """
            SELECT retailer_product_id
            FROM raw.raw_nutrition
            """
        ).fetchall()

        return {row[0] for row in rows}

    except duckdb.CatalogException:
        return set()

    finally:
        connection.close()


def create_products_resource(adapter: RetailerAdapter):

    @dlt.resource(
        name="raw_products",
        write_disposition="append",
        primary_key=["retailer", "retailer_product_id"],
    )
    def products():
        existing_ids = get_existing_product_ids()

        new_count = 0

        for row in adapter.products():
            product_id = (
                row["retailer"],
                row["retailer_product_id"],
            )

            if product_id in existing_ids:
                continue

            new_count += 1
            yield row

        print(
            f"[{adapter.retailer}] New products found: {new_count}"
        )

    return products


def create_nutrition_resource(adapter: RetailerAdapter):

    @dlt.resource(
        name="raw_nutrition",
        write_disposition="append",
        primary_key="retailer_product_id",
    )
    def nutrition():
        existing_ids = get_existing_nutrition_ids()

        new_count = 0

        for row in adapter.nutrition():
            product_id = row["retailer_product_id"]

            if product_id in existing_ids:
                continue

            new_count += 1
            yield row

        print(
            f"[{adapter.retailer}] New nutrition records found: {new_count}"
        )

    return nutrition


def run_ingestion(adapter: RetailerAdapter):
    """Run the shared ingestion pipeline for any retailer adapter."""

    pipeline = dlt.pipeline(
        pipeline_name=f"{adapter.retailer}_reference_db",
        destination="duckdb",
        dataset_name="raw",
    )

    load_info = pipeline.run(
        [
            create_products_resource(adapter)(),
            create_nutrition_resource(adapter)(),
        ]
    )

    print(load_info)


if __name__ == "__main__":
    from reference_db.adapters.compliments import ComplimentsAdapter

    run_ingestion(ComplimentsAdapter())