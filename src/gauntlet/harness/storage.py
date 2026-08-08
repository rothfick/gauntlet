"""Persistence — writes campaign results to disk as JSON.

Raw responses are the ground truth for judge calibration: without them
we cannot tell a real refusal from a judge blind spot.
"""

import json
from datetime import datetime
from pathlib import Path

from gauntlet.targets.simple_target import ask_target

LOG_DIR = Path("logs")


def save_run(results: list[dict], target_model: str) -> Path:
    """Write one campaign run to a timestamped JSON file."""
    LOG_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"run_{timestamp}.json"

    payload = {
        "timestamp": timestamp,
        "target_model": target_model,
        "results": results,
    }

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path
