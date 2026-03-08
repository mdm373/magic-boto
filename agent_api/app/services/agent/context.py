from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
)

AGENT_SYSTEM_PROMPT = (
    "You are a helpful assistant for building Magic: The Gathering decks. "
    "You have access to tools to look up cards (e.g. by Scryfall ID). Use them when needed."
)


def ensure_agent_system_context(
    messages: list[ChatCompletionMessageParam],
) -> list[ChatCompletionMessageParam]:
    """Prepend or merge system prompt so the model knows it can use tools."""
    system_msg: ChatCompletionSystemMessageParam = {
        "role": "system",
        "content": AGENT_SYSTEM_PROMPT,
    }
    if not messages:
        return [system_msg]
    first = messages[0]
    if first.get("role") == "system":
        raw = first.get("content")
        existing = raw.strip() if isinstance(raw, str) else ""
        merged: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": f"{existing}\n\n{AGENT_SYSTEM_PROMPT}" if existing else AGENT_SYSTEM_PROMPT,
        }
        return [merged, *messages[1:]]
    return [system_msg, *messages]
