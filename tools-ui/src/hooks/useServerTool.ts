import { useCallback } from "react";
import type { App } from "@modelcontextprotocol/ext-apps";
import type { ReadonlyRecord } from "../types/utils";
import type { TextToolContentPart } from "../utils/mcpToolResultTextJson";

/**
 * Returns a typed async caller that invokes an MCP server tool and extracts
 * the JSON payload from the first text content block in the result.
 */
export function useServerTool(app: App | null) {
  return useCallback(
    async <T>(name: string, args: ReadonlyRecord<string, unknown>): Promise<T> => {
      if (!app) throw new Error("App not connected.");

      const result = await app.callServerTool({ name, arguments: args });
      const textBlock = (result.content as readonly TextToolContentPart[]).find(
        (c) => c.type === "text",
      );
      if (!textBlock?.text) throw new Error(`No text content in response from '${name}'.`);
      return JSON.parse(textBlock.text) as T;
    },
    [app],
  );
}
