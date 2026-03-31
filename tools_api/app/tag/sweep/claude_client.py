"""Claude API client for the tag sweep task."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import anthropic
from anthropic.types import MessageParam
from loguru import logger

from app.models.magic_boto_card import MagicBotoCardModel
from app.services.tag_service import CardTagEntry
from app.tag.card_payload import card_to_dict
from settings import get_settings

_PROMPTS_DIR = Path(__file__).parent
SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.md").read_text().strip()
_USER_PROMPT_TEMPLATE = (_PROMPTS_DIR / "user_prompt.md").read_text()


def _build_user_message(tag_description: str, cards: list[Mapping[str, object]]) -> str:
    cards_json = json.dumps(cards, indent=2)
    return _USER_PROMPT_TEMPLATE.format(tag_description=tag_description, cards_json=cards_json)


def _extract_entries(raw_entries: list[object]) -> list[CardTagEntry]:
    """Parse a list of {id, reason} objects or plain strings into CardTagEntry values.

    Accepts both the new object format and the legacy string format so
    old-format responses (e.g. during retries) don't hard-fail.
    """
    entries: list[CardTagEntry] = []
    for item in raw_entries:
        if isinstance(item, dict):
            raw_id = item.get("id")
            if isinstance(raw_id, str) and raw_id:
                raw_reason = item.get("reason")
                reason = raw_reason if isinstance(raw_reason, str) and raw_reason else None
                entries.append(CardTagEntry(oracle_id=raw_id, reason=reason))
        elif isinstance(item, str) and item:
            entries.append(CardTagEntry(oracle_id=item))
    return entries


def _parse_response(
    raw: str,
) -> tuple[list[CardTagEntry], list[CardTagEntry], set[str]]:
    """Parse raw JSON, strip fences, and return (tag_entries, unsure_entries, returned_ids).

    ``returned_ids`` is the union of all oracle_ids for hallucination detection.
    Raises ValueError on invalid JSON so the caller can reprompt.
    """
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    tag_entries = _extract_entries(parsed.get("tag", []))
    unsure_entries = _extract_entries(parsed.get("unsure", []))
    returned_ids = {e.oracle_id for e in tag_entries} | {e.oracle_id for e in unsure_entries}
    return tag_entries, unsure_entries, returned_ids


class SweepClaudeClient:
    """Holds the fixed per-sweep Claude call state; call() varies only by page."""

    def __init__(
        self,
        client: anthropic.Anthropic,
        model: str,
        max_tokens: int,
        max_hallucination_retries: int,
        log_path: Path,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._max_hallucination_retries = max_hallucination_retries
        self._log_path = log_path

    def call(
        self,
        tag_description: str,
        cards: Sequence[MagicBotoCardModel],
    ) -> tuple[list[CardTagEntry], list[CardTagEntry]]:
        """Return (tag_entries, unsure_entries), retrying on hallucinated oracle IDs."""
        card_dicts = [card_to_dict(c) for c in cards]
        input_ids = {str(c.oracle_id) for c in cards}
        user_message = _build_user_message(tag_description, card_dicts)
        messages: list[MessageParam] = [{"role": "user", "content": user_message}]

        for attempt in range(1 + self._max_hallucination_retries):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            raw = text_blocks[0].text.strip() if text_blocks else ""

            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "attempt": attempt,
                            "user_message": messages[-1]["content"],
                            "raw_response": raw,
                            "stop_reason": response.stop_reason,
                            "model": response.model,
                        }
                    )
                    + "\n"
                )

            stop_reason = response.stop_reason
            if stop_reason == "max_tokens":
                logger.warning(
                    "Truncated at {} tokens — raise tag_sweep_max_tokens.", self._max_tokens
                )
            if not text_blocks:
                logger.warning("No text blocks, stop_reason={}; skipping page.", stop_reason)
                return [], []
            if not raw:
                logger.warning("Empty text stop_reason={}; skipping page.", stop_reason)
                return [], []

            try:
                tag_entries, unsure_entries, returned_ids = _parse_response(raw)
            except ValueError as exc:
                suffix = (
                    " — retrying." if attempt < self._max_hallucination_retries else " — giving up."
                )
                logger.warning(
                    "Attempt {}/{}: Claude returned unparseable JSON: {}{}",
                    attempt + 1,
                    1 + self._max_hallucination_retries,
                    exc,
                    suffix,
                )
                if attempt >= self._max_hallucination_retries:
                    return [], []
                correction = (
                    "Your previous response was not valid JSON. "
                    "Reply with only a raw JSON object — no markdown, no explanation — "
                    'with keys "tag" and "unsure", each an array of '
                    '{"id": "<oracle_id>", "reason": "<brief reason>"} objects.'
                )
                messages = [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": correction},
                ]
                continue

            hallucinated = returned_ids - input_ids
            if not hallucinated:
                return tag_entries, unsure_entries

            bad = ", ".join(sorted(hallucinated))
            logger.warning(
                "Attempt {}/{}: Claude hallucinated {} oracle ID(s) not in input: {}{}",
                attempt + 1,
                1 + self._max_hallucination_retries,
                len(hallucinated),
                bad,
                " — retrying." if attempt < self._max_hallucination_retries else " — giving up.",
            )
            if attempt >= self._max_hallucination_retries:
                return [], []

            # Extend the conversation: show Claude its bad response and correct it.
            correction = (
                f"Your previous response included oracle ID(s) that were not in the input: {bad}. "
                "You must only use oracle_ids that appear verbatim in the card list provided. "
                "Please respond again with a corrected JSON object using only valid oracle_ids."
            )
            messages = [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": raw},
                {"role": "user", "content": correction},
            ]
        return [], []


_settings = get_settings()


def create_sweep_claude_client() -> SweepClaudeClient:
    api_key = _settings.anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set — required for the tag sweep client.")
    debug_dir = Path(_settings.debug_output_dir)
    debug_dir.mkdir(parents=True, exist_ok=True)
    claude_log_path = debug_dir / "claude.jsonl"
    return SweepClaudeClient(
        anthropic.Anthropic(api_key=api_key),
        _settings.tag_sweep_model,
        _settings.tag_sweep_max_tokens,
        _settings.tag_sweep_max_hallucination_retries,
        claude_log_path,
    )
