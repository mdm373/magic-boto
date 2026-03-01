"""Agent loop: chat with LM Studio and execute tools (e.g. get_card) in-process."""

import json
from typing import Any, cast

import httpx
from loguru import logger

from app.db import get_async_session_factory
from app.services import query_card

# OpenAI-format tool definitions for the model. Name matches execution dispatch.
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_card",
            "description": (
                "Look up a Magic: The Gathering card by its Scryfall ID (UUID with dashes)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scryfall_id": {
                        "type": "string",
                        "description": "Scryfall UUID of the card (e.g. 7dx-xxxx-xxxx-xxxx).",
                    },
                },
                "required": ["scryfall_id"],
            },
        },
    },
]

MAX_TOOL_ROUNDS = 10

# Injected so the model knows it can use tools. Prepended or merged with the first system message.
AGENT_SYSTEM_PROMPT = (
    "You are a helpful assistant for building Magic: The Gathering decks. "
    "You have access to a get_card tool to look up cards by Scryfall ID when the user "
    "asks about a card or provides an ID. Use it when you need card details to answer."
)


def _ensure_agent_system_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepend or merge our system prompt so the model knows it can use tools."""
    if not messages:
        return [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
    first = messages[0]
    if first.get("role") == "system":
        existing = (first.get("content") or "").strip()
        if existing:
            first = {
                **first,
                "content": f"{existing}\n\n{AGENT_SYSTEM_PROMPT}",
            }
        else:
            first = {"role": "system", "content": AGENT_SYSTEM_PROMPT}
        return [first, *messages[1:]]
    return [{"role": "system", "content": AGENT_SYSTEM_PROMPT}, *messages]


async def _execute_tool(name: str, arguments: str) -> str:
    """Run one tool by name with JSON arguments. Returns JSON string for tool content."""
    if name != "get_card":
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        args = json.loads(arguments)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid arguments JSON: {e!s}"})
    scryfall_id = args.get("scryfall_id")
    if not scryfall_id or not isinstance(scryfall_id, str):
        return json.dumps({"error": "Missing or invalid scryfall_id"})
    logger.debug("Tool request: get_card(scryfall_id={})", scryfall_id)
    factory = get_async_session_factory()
    async with factory() as session:
        card = await query_card(session, scryfall_id.strip())
    if card is None:
        return json.dumps({"error": "Card not found", "scryfall_id": scryfall_id})
    return card.model_dump_json()


async def run_chat_loop(
    *,
    url: str,
    timeout: float,
    messages: list[dict[str, Any]],
    model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """
    Run the agent loop: send messages + tools to LM Studio; on tool_calls,
    execute tools, append results, repeat. Return the final completion JSON.
    """
    current_messages = list(_ensure_agent_system_context(messages))
    payload: dict[str, Any] = {
        "model": model,
        "messages": current_messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "stream": False,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    for _ in range(MAX_TOOL_ROUNDS):
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        choice = (data.get("choices") or [None])[0]
        if not choice:
            return cast(dict[str, Any], data)
        msg = choice.get("message") or {}
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return cast(dict[str, Any], data)
        current_messages.append(msg)
        for tc in tool_calls:
            tid = tc.get("id") or ""
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            arguments = fn.get("arguments") or "{}"
            content = await _execute_tool(name, arguments)
            current_messages.append({"role": "tool", "tool_call_id": tid, "content": content})
        payload["messages"] = current_messages
    return cast(dict[str, Any], data)
