from dataclasses import dataclass
from typing import Literal


QualityStatus = Literal[
    "PASS",
    "WARNING",
    "AMBIGUOUS",
    "FAIL",
]

ReviewStatus = Literal[
    "AMBIGUOUS",
    "RESOLVED",
    "REJECTED",
]


@dataclass
class ReviewRecord:
    record_id: str
    retailer: str
    phase: str
    ambiguity_type: str
    reason: str
    confidence: float | None
    resume_from: str
