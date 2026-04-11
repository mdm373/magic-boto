"""Markdown prompt templates shipped with the application."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent

SWEEP_PROMPTS_DIR: Path = _ROOT / "sweep"
AUDIT_PROMPTS_DIR: Path = _ROOT / "audit"

__all__ = ["AUDIT_PROMPTS_DIR", "SWEEP_PROMPTS_DIR"]
