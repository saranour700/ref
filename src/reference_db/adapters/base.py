from abc import ABC, abstractmethod
from typing import Iterator


class RetailerAdapter(ABC):
    """Common interface for all retailer data sources."""

    @property
    @abstractmethod
    def retailer(self) -> str:
        """Return the retailer name."""
        pass

    @abstractmethod
    def products(self) -> Iterator[dict]:
        """Yield standardized product records."""
        pass

    @abstractmethod
    def nutrition(self) -> Iterator[dict]:
        """Yield standardized nutrition records."""
        pass