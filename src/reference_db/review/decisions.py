from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class ReviewDecision:
    record_id: str
    retailer: str
    phase: str
    decision: str
    resume_from: str
    reviewer: str


def save_decision(
    decision: ReviewDecision,
    output_dir: str = "data/review",
) -> Path:
    """
    Save a review decision.
    """

    phase_dir = Path(output_dir) / decision.retailer / decision.phase
    phase_dir.mkdir(parents=True, exist_ok=True)

    output_file = phase_dir / "decisions.jsonl"

    with output_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision.__dict__) + "\n")

    return output_file
