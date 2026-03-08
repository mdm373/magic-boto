"""Agent service: chat loop with LLM proxy, tools from tools_api OpenAPI, execute via HTTP."""

from openai import AsyncOpenAI, omit
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionToolMessageParam,
)
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.completion_create_params import CompletionCreateParams

from app.services.openapi_tooling import OpenAPITooling

from .context import ensure_agent_system_context
from .message_to_param import assistant_message_to_param


class Agent:
    def __init__(
        self, tooling: OpenAPITooling, max_tool_rounds: int, open_api_client: AsyncOpenAI
    ) -> None:
        self._tooling = tooling
        self._max_tool_rounds = max_tool_rounds
        self._open_api_client = open_api_client

    async def run_chat_loop(self, body: CompletionCreateParams) -> ChatCompletion:
        """
        Run the agent loop: send messages + tools to LLM; on tool_calls,
        invoke tools_api over HTTP, append results, repeat. Return final completion.
        """
        raw_messages = body.get("messages") or []
        messages = list(raw_messages)
        model = body.get("model") or ""
        temperature = body.get("temperature")
        max_tokens = body.get("max_tokens")
        current_messages = ensure_agent_system_context(messages)
        for _ in range(self._max_tool_rounds):
            data = await self._open_api_client.chat.completions.create(
                model=model,
                messages=current_messages,
                tools=self._tooling.get_tools(),
                tool_choice="auto",
                stream=False,
                temperature=temperature if temperature is not None else omit,
                max_tokens=max_tokens if max_tokens is not None else omit,
            )
            choice = data.choices[0] if data.choices else None
            if not choice:
                return data
            msg = choice.message
            tool_calls = msg.tool_calls
            if not tool_calls:
                return data
            current_messages.append(assistant_message_to_param(msg))
            for tc in tool_calls:
                if not isinstance(tc, ChatCompletionMessageFunctionToolCall):
                    continue
                content = await self._tooling.request_tool(tc.function.name, tc.function.arguments)
                tool_msg: ChatCompletionToolMessageParam = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": content,
                }
                current_messages.append(tool_msg)
        return data
