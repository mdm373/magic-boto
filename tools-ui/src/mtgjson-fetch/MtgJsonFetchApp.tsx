import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import {
  useEnqueueMtgjsonFetch,
  useGetMtgjsonFetchJob,
  type MtgjsonFetchEditionState,
  type MtgjsonFetchJobStatus,
} from "../hooks/useMcpTools";
import { usePoll } from "../hooks/usePoll";
import type { ReadonlyRecord } from "../types/utils";
import { createOnToolResult } from "../utils/mcpToolResultTextJson";

type EnqueuePayload = Readonly<{ job_id: string; status: string }>;

/** Extra top/left so content does not hug the MCP panel edges */
const PAGE_STYLE: React.CSSProperties = {
  padding: "2rem 1.5rem 1.5rem 2rem",
  minHeight: "100%",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-family-sans, sans-serif)",
  boxSizing: "border-box",
};

const STATE_COLORS: ReadonlyRecord<MtgjsonFetchEditionState, string> = {
  requested: "#6b7280",
  inprogress: "#f59e0b",
  done: "#22c55e",
};

const STATE_LABELS: ReadonlyRecord<MtgjsonFetchEditionState, string> = {
  requested: "Pending",
  inprogress: "In progress",
  done: "Done",
};

/** ~10 table body rows (0.8rem text + vertical padding) plus room for sticky header */
const EDITIONS_TABLE_MAX_HEIGHT = "min(22rem, 50vh)" as const;

export function MtgJsonFetchApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [codesInput, setCodesInput] = useState("SLD");
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<MtgjsonFetchJobStatus | null>(null);
  const [appError, setAppError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "MtgJsonFetchApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (app) => {
      app.ontoolresult = createOnToolResult<EnqueuePayload>(
        (data) => {
          if (data.job_id) setJobId(data.job_id);
        },
        setAppError,
      );
      app.onteardown = async () => ({});
      app.onerror = (e) => setAppError(String(e));
      app.onhostcontextchanged = (ctx) => setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) setHostContext(app.getHostContext());
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const enqueueFetch = useEnqueueMtgjsonFetch(app);
  const getJob = useGetMtgjsonFetchJob(app);

  const pollJob = useCallback(async (): Promise<boolean> => {
    if (!jobId) return false;
    try {
      const data = await getJob(jobId);
      setStatus(data);
      return data.ended_at === null;
    } catch (e) {
      setAppError(`Poll failed: ${String(e)}`);
      return false;
    }
  }, [jobId, getJob]);

  usePoll({
    enabled: Boolean(app && jobId),
    intervalMs: 3000,
    tick: pollJob,
  });

  const handleStart = useCallback(async () => {
    if (!app) return;
    setStarting(true);
    setAppError(null);
    try {
      const result = await enqueueFetch(codesInput.trim());
      setJobId(result.job_id);
      const initial = await getJob(result.job_id);
      setStatus(initial);
    } catch (e) {
      setAppError(String(e));
    } finally {
      setStarting(false);
    }
  }, [app, codesInput, enqueueFetch, getJob]);

  const insets = hostContext?.safeAreaInsets;
  const pageStyle: React.CSSProperties = insets
    ? {
        ...PAGE_STYLE,
        // Host insets are often 0; still keep at least PAGE_STYLE padding (esp. top/left).
        paddingTop: `max(2rem, ${insets.top}px)`,
        paddingRight: `max(1.5rem, ${insets.right}px)`,
        paddingBottom: `max(1.5rem, ${insets.bottom}px)`,
        paddingLeft: `max(2rem, ${insets.left}px)`,
      }
    : PAGE_STYLE;

  if (error || appError) {
    return (
      <div style={pageStyle}>
        <strong>Error:</strong> {error?.message ?? appError}
      </div>
    );
  }

  if (!isConnected) {
    return <div style={pageStyle}>Connecting…</div>;
  }

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: 2 }}>
          MTGJSON catalog fetch
        </div>
        <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>Async fetch</div>
      </div>

      <label style={{ display: "block", fontSize: "0.8rem", marginBottom: 6 }}>
        Comma-separated set codes to force a re-import. Empty defaults to SLD.
      </label>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
          marginBottom: "1rem",
        }}
      >
        <input
          type="text"
          value={codesInput}
          onChange={(e) => setCodesInput(e.target.value)}
          style={{
            flex: "1 1 12rem",
            minWidth: 0,
            maxWidth: 420,
            padding: "0.5rem 0.6rem",
            borderRadius: 6,
            border: "1px solid var(--color-border-subtle, #d1d5db)",
            fontSize: "0.9rem",
            boxSizing: "border-box",
          }}
        />
        <button
          type="button"
          onClick={() => void handleStart()}
          disabled={starting}
          style={{
            flex: "0 0 auto",
            padding: "0.5rem 1rem",
            borderRadius: 6,
            border: "none",
            backgroundColor: "var(--color-accent, #2563eb)",
            color: "#fff",
            fontWeight: 600,
            cursor: starting ? "wait" : "pointer",
          }}
        >
          {starting ? "Starting…" : "Start fetch"}
        </button>
      </div>

      {jobId && (
        <div style={{ fontSize: "0.7rem", color: "var(--color-text-tertiary)", marginBottom: "0.75rem" }}>
          Job: {jobId}
        </div>
      )}

      {status?.error_message && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.6rem 0.75rem",
            borderRadius: 6,
            backgroundColor: "rgba(239, 68, 68, 0.12)",
            color: "#b91c1c",
            fontSize: "0.85rem",
            whiteSpace: "pre-wrap",
          }}
        >
          {status.error_message}
        </div>
      )}

      {status && status.editions.length > 0 && (
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: 8 }}>Editions</div>
          <div
            style={{
              maxHeight: EDITIONS_TABLE_MAX_HEIGHT,
              overflowY: "auto",
              overflowX: "auto",
              borderRadius: 6,
              border: "1px solid var(--color-border-subtle, #e5e7eb)",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
              <thead
                style={{
                  position: "sticky",
                  top: 0,
                  zIndex: 1,
                  backgroundColor: "var(--color-background-tertiary)",
                  boxShadow: "0 1px 0 var(--color-border-subtle, #e5e7eb)",
                }}
              >
                <tr style={{ textAlign: "left", color: "var(--color-text-secondary)" }}>
                  <th style={{ padding: "4px 8px 4px 0" }}>Set</th>
                  <th style={{ padding: "4px 8px" }}>State</th>
                  <th style={{ padding: "4px 0 4px 8px" }}>Cards</th>
                </tr>
              </thead>
              <tbody>
                {status.editions.map((row) => (
                  <tr key={row.set_code}>
                    <td style={{ padding: "6px 8px 6px 0", fontFamily: "monospace" }}>{row.set_code}</td>
                    <td style={{ padding: "6px 8px" }}>
                      <span
                        style={{
                          backgroundColor: STATE_COLORS[row.state],
                          color: "#fff",
                          borderRadius: 4,
                          padding: "2px 6px",
                          fontSize: "0.7rem",
                          fontWeight: 500,
                        }}
                      >
                        {STATE_LABELS[row.state]}
                      </span>
                    </td>
                    <td style={{ padding: "6px 0 6px 8px" }}>{row.updated_cards_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {jobId && !status && <div style={{ fontSize: "0.85rem" }}>Loading job…</div>}

      {status?.ended_at && (
        <p style={{ marginTop: "1rem", color: "var(--color-text-secondary)", fontSize: "0.85rem" }}>
          {status.error_message ? "Job finished (see messages above)." : "Job finished."}
        </p>
      )}
    </div>
  );
}
