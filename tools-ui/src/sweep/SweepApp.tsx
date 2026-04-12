import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import Markdown from "react-markdown";
import { usePoll } from "../hooks/usePoll";
import type { ReadonlyRecord } from "../types/utils";

// ── Types ────────────────────────────────────────────────────────────────────

type BatchCounts = Readonly<{
  total: number;
  pending: number;
  submitted: number;
  complete: number;
  failed: number;
}>;

const AuditStatusValues = ["pending", "in_progress", "complete", "failed"] as const;
type AuditStatusValue = (typeof AuditStatusValues)[number];

const SweepStatusValues = ["pending", "open", "auditing", "complete", "failed"] as const;
type SweepStatusValue = (typeof SweepStatusValues)[number];

type AuditStatus = Readonly<{
  audit_id: string;
  status: AuditStatusValue;
  report: string | null;
}>;

type SweepStatusResponse = Readonly<{
  sweep_id: string;
  tag_name: string;
  status: SweepStatusValue;
  triggered_at: string;
  completed_at: string | null;
  batch_counts: BatchCounts;
  audit: AuditStatus | null;
}>;

type TextToolContentPart = Readonly<{ type: string; text?: string }>;

type SweepCreateResultPayload = Readonly<{ sweep_id: string }>;

// ── Styles ───────────────────────────────────────────────────────────────────

const PAGE_STYLE: React.CSSProperties = {
  padding: "1.5rem",
  minHeight: "100%",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-family-sans, sans-serif)",
  boxSizing: "border-box",
};

const STATUS_COLORS: ReadonlyRecord<SweepStatusValue, string> = {
  pending: "#3b82f6",
  open: "#6b7280",
  auditing: "#f59e0b",
  complete: "#22c55e",
  failed: "#ef4444",
};

const STATUS_LABELS: ReadonlyRecord<SweepStatusValue, string> = {
  pending: "Sweeping…",
  open: "Partial",
  auditing: "Auditing…",
  complete: "Complete",
  failed: "Failed",
};

const AUDIT_STATUS_LABELS: ReadonlyRecord<AuditStatusValue, string> = {
  pending: "Pending",
  in_progress: "Running…",
  complete: "Complete",
  failed: "Failed",
};

// ── Component ────────────────────────────────────────────────────────────────

export function SweepApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [sweepId, setSweepId] = useState<string | null>(null);
  const [status, setStatus] = useState<SweepStatusResponse | null>(null);
  const [appError, setAppError] = useState<string | null>(null);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "SweepApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (app) => {
      app.ontoolresult = async (result) => {
        try {
          const textBlock = (result.content as readonly TextToolContentPart[]).find(
            (c) => c.type === "text",
          );
          if (!textBlock?.text) return;
          const data = JSON.parse(textBlock.text) as SweepCreateResultPayload;
          setSweepId(data.sweep_id);
        } catch {
          setAppError("Could not parse sweep result.");
        }
      };
      app.onteardown = async () => ({});
      app.onerror = (e) => setAppError(String(e));
      app.onhostcontextchanged = (ctx) => setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) setHostContext(app.getHostContext());
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const pollSweepStatus = useCallback(async (): Promise<boolean> => {
    if (!app || !sweepId) return false;
    try {
      const result = await app.callServerTool({
        name: "get_sweep_status",
        arguments: { sweep_id: sweepId },
      });
      const textBlock = (result.content as readonly TextToolContentPart[]).find(
        (c) => c.type === "text",
      );
      if (!textBlock?.text) return false;
      const data = JSON.parse(textBlock.text) as SweepStatusResponse;
      setStatus(data);
      return data.status !== "complete" && data.status !== "failed";
    } catch (e) {
      setAppError(`Poll failed: ${String(e)}`);
      return false;
    }
  }, [app, sweepId]);

  usePoll({
    enabled: Boolean(app && sweepId),
    intervalMs: 4000,
    tick: pollSweepStatus,
  });

  const insets = hostContext?.safeAreaInsets;
  const pageStyle: React.CSSProperties = insets
    ? {
        ...PAGE_STYLE,
        padding: `${insets.top}px ${insets.right}px ${insets.bottom}px ${insets.left}px`,
      }
    : PAGE_STYLE;

  if (error || appError) {
    return (
      <div style={pageStyle}>
        <strong>Error:</strong> {error?.message ?? appError}
      </div>
    );
  }

  if (!isConnected || !sweepId) {
    return <div style={pageStyle}>Connecting…</div>;
  }

  if (!status) {
    return <div style={pageStyle}>Loading sweep status…</div>;
  }

  const { tag_name, batch_counts: bc, audit } = status;
  const color = STATUS_COLORS[status.status];
  const progressPct = bc.total > 0 ? Math.round((bc.complete / bc.total) * 100) : 0;

  return (
    <div style={pageStyle}>
      {/* Header */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: 2 }}>
          Tag sweep
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontWeight: 600, fontSize: "1.1rem" }}>{tag_name}</span>
          <span
            style={{
              backgroundColor: color,
              color: "#fff",
              borderRadius: "0.25rem",
              padding: "0 0.4rem",
              fontSize: "0.75rem",
              fontWeight: 500,
            }}
          >
            {STATUS_LABELS[status.status]}
          </span>
        </div>
        <div style={{ fontSize: "0.7rem", color: "var(--color-text-tertiary)", marginTop: 2 }}>
          {status.sweep_id}
        </div>
      </div>

      {/* Progress bar */}
      {bc.total > 0 && (
        <div style={{ marginBottom: "1rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.75rem",
              marginBottom: 4,
              color: "var(--color-text-secondary)",
            }}
          >
            <span>Batches</span>
            <span>
              {bc.complete} / {bc.total} ({progressPct}%)
            </span>
          </div>
          <div
            style={{
              height: 6,
              borderRadius: 3,
              backgroundColor: "var(--color-background-secondary, #e5e7eb)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${progressPct}%`,
                backgroundColor: color,
                transition: "width 0.4s ease",
              }}
            />
          </div>
          <div
            style={{
              display: "flex",
              gap: "1rem",
              fontSize: "0.7rem",
              marginTop: 6,
              color: "var(--color-text-tertiary)",
            }}
          >
            {bc.pending > 0 && <span>Pending: {bc.pending}</span>}
            {bc.submitted > 0 && <span>Submitted: {bc.submitted}</span>}
            {bc.complete > 0 && <span>Complete: {bc.complete}</span>}
            {bc.failed > 0 && (
              <span style={{ color: STATUS_COLORS.failed }}>Failed: {bc.failed}</span>
            )}
          </div>
        </div>
      )}

      {/* Audit section */}
      {audit && (
        <div
          style={{
            borderTop: "1px solid var(--color-border, #e5e7eb)",
            paddingTop: "1rem",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "0.75rem",
            }}
          >
            <span style={{ fontWeight: 600 }}>Audit</span>
            <span
              style={{
                backgroundColor:
                  audit.status === "complete"
                    ? STATUS_COLORS.complete
                    : audit.status === "failed"
                      ? STATUS_COLORS.failed
                      : STATUS_COLORS.auditing,
                color: "#fff",
                borderRadius: "0.25rem",
                padding: "0 0.4rem",
                fontSize: "0.75rem",
                fontWeight: 500,
              }}
            >
              {AUDIT_STATUS_LABELS[audit.status]}
            </span>
          </div>
          {audit.report && (
            <div className="prose prose-sm prose-sweep-report max-w-none dark:prose-invert">
              <Markdown>{audit.report}</Markdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
