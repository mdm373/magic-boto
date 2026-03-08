from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageToolCallUnionParam,
)


def assistant_message_to_param(msg: ChatCompletionMessage) -> ChatCompletionAssistantMessageParam:
    """Convert completion assistant message (response model) to param for next request."""
    tool_calls: list[ChatCompletionMessageToolCallUnionParam] = []
    for tc in msg.tool_calls or []:
        if isinstance(tc, ChatCompletionMessageFunctionToolCall):
            tool_calls.append(
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
            )
            continue
        if isinstance(tc, ChatCompletionMessageCustomToolCall):
            tool_calls.append(
                {
                    "id": tc.id,
                    "type": "custom",
                    "custom": {"name": tc.custom.name, "input": tc.custom.input},
                }
            )
            continue
    return {
        "role": "assistant",
        "content": msg.content,
        "tool_calls": tool_calls,
    }
