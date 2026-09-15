import duckdb

from .base import RetailerAdapter


PRODUCTS_SOURCE = (
    "hf://datasets/saraNour/compliments-brand/"
    "raw_data/products.parquet"
)

NUTRITION_SOURCE = (
    "hf://datasets/saraNour/compliments-brand/"
    "raw_data/nutrition.parquet"
)


class ComplimentsAdapter(RetailerAdapter):

    @property
    def retailer(self) -> str:
        return "sobeys"

    def _read_parquet(self, source: str):
        connection = duckdb.connect()

        connection.execute(
            "CREATE SECRET hf_token "
            "(TYPE huggingface, PROVIDER credential_chain)"
        )

        reader = connection.sql(
            f"SELECT * FROM '{source}'"
        ).to_arrow_reader()

        return reader, connection

    def products(self):
        reader, connection = self._read_parquet(PRODUCTS_SOURCE)

        try:
            for batch in reader:
                yield from batch.to_pylist()
        finally:
            connection.close()

    def nutrition(self):
        reader, connection = self._read_parquet(NUTRITION_SOURCE)

        try:
            for batch in reader:
                yield from batch.to_pylist()
        finally:
            connection.close()