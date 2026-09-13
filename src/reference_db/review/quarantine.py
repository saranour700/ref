from pathlib import Path
import json

from .models import ReviewRecord


def quarantine_record(
    record: ReviewRecord,
    output_dir: str = "data/review",
) -> Path:
    """
    Save an ambiguous record for later review.
    """

    phase_dir = Path(output_dir) / record.retailer / record.phase
    phase_dir.mkdir(parents=True, exist_ok=True)

    output_file = phase_dir / "ambiguous.jsonl"

    with output_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.__dict__) + "\n")

    return output_file
