from dataclasses import dataclass
from typing import Literal


QualityStatus = Literal[
    "PASS",
    "WARNING",
    "AMBIGUOUS",
    "FAIL",
]


@dataclass
class QualityResult:
    status: QualityStatus
    message: str = ""


def is_allowed_to_continue(result: QualityResult) -> bool:
    """
    Return whether the pipeline can continue to the next phase.
    """

    return result.status in {"PASS", "WARNING"}
