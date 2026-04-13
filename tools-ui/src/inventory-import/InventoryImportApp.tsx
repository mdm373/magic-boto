import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useRef, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";

import { createOnToolResult } from "../utils/mcpToolResultTextJson";
import type { TextToolContentPart } from "../utils/mcpToolResultTextJson";

// ── Types ─────────────────────────────────────────────────────────────────────

type OpenInventoryImportResult = Readonly<{
  inventory_name: string;
  existing_names: readonly string[];
}>;

type ImportInventoryCsvResult = Readonly<{
  status: "ok";
  unknown_scryfall_ids: readonly string[];
}>;

type ViewState =
  | Readonly<{ kind: "ready" }>
  | Readonly<{ kind: "importing" }>
  | Readonly<{ kind: "done"; inventoryName: string; unknownScryfallIds: readonly string[] }>
  | Readonly<{ kind: "error"; message: string }>;

// ── Styles ────────────────────────────────────────────────────────────────────

const PAGE_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100%",
  padding: "1.5rem",
  gap: "1.25rem",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-tertiary)",
  boxSizing: "border-box",
};

const LABEL_STYLE: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
};

const LABEL_TEXT_STYLE: React.CSSProperties = {
  fontSize: "0.875rem",
  opacity: 0.8,
};

const INPUT_STYLE: React.CSSProperties = {
  padding: "0.5rem 0.625rem",
  borderRadius: "var(--border-radius-md, 6px)",
  border: "1px solid var(--color-border, #444)",
  backgroundColor: "var(--color-background-secondary, #1e1e1e)",
  color: "inherit",
  fontSize: "1rem",
};

// ── Component ─────────────────────────────────────────────────────────────────

export function InventoryImportApp() {
  const [view, setView] = useState<ViewState>({ kind: "ready" });
  const [existingNames, setExistingNames] = useState<readonly string[]>([]);
  const [inventoryName, setInventoryName] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "InventoryImportApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (createdApp) => {
      createdApp.ontoolinput = async () => {
        setView({ kind: "ready" });
        setExistingNames([]);
        setInventoryName("");
        setCsvFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      };

      // open_inventory_import provides existing names and optional pre-fill.
      // Errors are silently ignored — the form is already usable without them.
      createdApp.ontoolresult = createOnToolResult<OpenInventoryImportResult>(
        (data) => {
          setExistingNames(data.existing_names ?? []);
          if (data.inventory_name) setInventoryName(data.inventory_name);
        },
        () => {},
      );

      createdApp.onteardown = async () => ({});
      createdApp.onerror = console.error;
    },
  });

  useHostStyles(app, app?.getHostContext() as McpUiHostContext | undefined);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCsvFile(e.target.files?.[0] ?? null);
  };

  const handleImport = async () => {
    if (!app || !csvFile || !inventoryName.trim()) return;
    setView({ kind: "importing" });
    try {
      const csvContent = await csvFile.text();
      const result = await app.callServerTool({
        name: "import_inventory_csv_content",
        arguments: {
          csv_content: csvContent,
          inventory_name: inventoryName.trim(),
        },
      });
      const textBlock = (result.content as readonly TextToolContentPart[]).find(
        (c) => c.type === "text",
      );
      if (!textBlock?.text) {
        setView({ kind: "error", message: "No text content in import result." });
        return;
      }
      const data = JSON.parse(textBlock.text) as ImportInventoryCsvResult;
      setView({
        kind: "done",
        inventoryName: inventoryName.trim(),
        unknownScryfallIds: data.unknown_scryfall_ids ?? [],
      });
    } catch (e) {
      setView({ kind: "error", message: String(e) });
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  if (error) {
    return (
      <div style={PAGE_STYLE}>
        <strong style={{ color: "var(--color-error, #ef4444)" }}>Connection error:</strong>{" "}
        {error.message}
      </div>
    );
  }

  if (view.kind === "done") {
    return (
      <div style={PAGE_STYLE}>
        <h2 style={{ margin: 0, fontSize: "1.125rem" }}>Import complete</h2>
        <p style={{ margin: 0 }}>
          Cards imported into <strong>{view.inventoryName}</strong>.
        </p>
        {view.unknownScryfallIds.length > 0 && (
          <div
            style={{
              padding: "0.625rem 0.75rem",
              borderRadius: "var(--border-radius-md, 6px)",
              backgroundColor: "color-mix(in srgb, var(--color-warning, #f59e0b) 12%, transparent)",
              border: "1px solid var(--color-warning, #f59e0b)",
              fontSize: "0.8125rem",
            }}
          >
            <strong>{view.unknownScryfallIds.length}</strong> Scryfall id(s) were not in the
            catalog and were skipped. Check the MCP server logs for details.
          </div>
        )}
      </div>
    );
  }

  const isImporting = view.kind === "importing";
  const canSubmit = isConnected && !isImporting && csvFile !== null && inventoryName.trim().length > 0;

  return (
    <div style={PAGE_STYLE}>
      <h2 style={{ margin: 0, fontSize: "1.125rem" }}>Import Inventory CSV</h2>

      {view.kind === "error" && (
        <div
          style={{
            padding: "0.625rem 0.75rem",
            borderRadius: "var(--border-radius-md, 6px)",
            backgroundColor: "color-mix(in srgb, var(--color-error, #ef4444) 15%, transparent)",
            border: "1px solid var(--color-error, #ef4444)",
            fontSize: "0.875rem",
          }}
        >
          {view.message}
        </div>
      )}

      <label style={LABEL_STYLE}>
        <span style={LABEL_TEXT_STYLE}>Inventory name</span>
        <input
          type="text"
          value={inventoryName}
          onChange={(e) => setInventoryName(e.target.value)}
          placeholder="e.g. my-deck"
          list="existing-inventory-names"
          disabled={isImporting}
          style={INPUT_STYLE}
        />
        {existingNames.length > 0 && (
          <datalist id="existing-inventory-names">
            {existingNames.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
        )}
      </label>

      <label style={LABEL_STYLE}>
        <span style={LABEL_TEXT_STYLE}>CSV file</span>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={handleFileChange}
          disabled={isImporting}
          style={{ ...INPUT_STYLE, padding: "0.375rem 0.625rem", cursor: "pointer" }}
        />
        {csvFile && (
          <span style={{ fontSize: "0.75rem", opacity: 0.6, wordBreak: "break-all" }}>
            {csvFile.name}
          </span>
        )}
      </label>

      <button
        onClick={() => void handleImport()}
        disabled={!canSubmit}
        style={{
          padding: "0.625rem 1.5rem",
          borderRadius: "var(--border-radius-md, 6px)",
          border: "none",
          backgroundColor: canSubmit
            ? "var(--color-accent, #3b82f6)"
            : "var(--color-background-secondary, #374151)",
          color: canSubmit ? "#fff" : "var(--color-text-tertiary)",
          fontSize: "1rem",
          cursor: canSubmit ? "pointer" : "default",
          alignSelf: "flex-start",
          opacity: isImporting ? 0.6 : 1,
          transition: "opacity 150ms",
        }}
      >
        {isImporting ? "Importing…" : "Import"}
      </button>
    </div>
  );
}
