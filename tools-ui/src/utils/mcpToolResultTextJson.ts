/** First text block in an MCP tool result `content` array (shape used by our server tools). */
export type TextToolContentPart = Readonly<{ type: string; text?: string }>;

/** Minimal tool result shape from `@modelcontextprotocol/ext-apps` tool callbacks. */
export type ToolResultWithContent = Readonly<{ content: unknown }>;

/** Message passed to `setError` when JSON is missing, invalid, or `consume` throws. */
export const TOOL_RESULT_JSON_PARSE_ERROR =
  "Could not parse tool result." as const;

export type OnToolResult = (result: ToolResultWithContent) => Promise<void>;

/**
 * Returns a handler suitable for `app.ontoolresult`: first text block is parsed as JSON
 * and passed to `consume`; failures call `setError` with {@link TOOL_RESULT_JSON_PARSE_ERROR}.
 */
export function createOnToolResult<T>(
  onResult: (data: T) => void | Promise<void>,
  onError: (message: string) => void,
): OnToolResult {
  return async (result) => {
    try {
      const textBlock = (result.content as readonly TextToolContentPart[]).find(
        (c) => c.type === "text",
      );
      if (!textBlock?.text) return;
      const data = JSON.parse(textBlock.text) as T;
      await onResult(data);
    } catch {
      onError(TOOL_RESULT_JSON_PARSE_ERROR);
    }
  };
}
