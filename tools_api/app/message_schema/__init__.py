"""JSON Schema assets for structured LLM output."""

from pathlib import Path

MESSAGE_SCHEMA_DIR: Path = Path(__file__).resolve().parent
SWEEP_VERDICT_SCHEMA_PATH: Path = MESSAGE_SCHEMA_DIR / "sweep_verdict.json"


def schema_path_from_payload_value(stored: str) -> Path:
    """Resolve *stored* basename under ``MESSAGE_SCHEMA_DIR`` (e.g. ``sweep_verdict.json``)."""
    return MESSAGE_SCHEMA_DIR / Path(stored).name


__all__ = [
    "MESSAGE_SCHEMA_DIR",
    "SWEEP_VERDICT_SCHEMA_PATH",
    "schema_path_from_payload_value",
]
