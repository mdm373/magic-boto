"""Sweep system prompt template (shared by kickoff and outbox payload builders)."""

from __future__ import annotations

from app.prompts import SWEEP_PROMPTS_DIR

_SYSTEM_PROMPT_TEMPLATE = (
    (SWEEP_PROMPTS_DIR / "system_prompt.md").read_text(encoding="utf-8").strip()
)


def format_sweep_system_prompt(tag_description: str) -> str:
    """Format the sweep system prompt for a tag's description."""
    return _SYSTEM_PROMPT_TEMPLATE.format(tag_description=tag_description)
