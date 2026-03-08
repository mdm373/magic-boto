from collections.abc import Sequence

from openai.types.chat import ChatCompletionFunctionToolParam

from .tool_client import OpenAPIToolClient


class OpenAPITooling:
    def __init__(
        self, tools: Sequence[ChatCompletionFunctionToolParam], client: OpenAPIToolClient
    ) -> None:
        self._tools = tools
        self._client = client

    def get_tools(self) -> Sequence[ChatCompletionFunctionToolParam]:
        return self._tools

    async def request_tool(self, operation_id: str, arguments: str) -> str:
        return await self._client.request_tool(operation_id, arguments)
