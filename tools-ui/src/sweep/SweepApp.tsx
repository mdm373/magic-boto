import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import { AuditSection } from "../components/AuditSection";
import { usePoll } from "../hooks/usePoll";
import { useApplyAudit, useGetSweepStatus } from "../hooks/useMcpTools";
import type {
  ApplyAuditResult,
  SweepStatusResponse,
  SweepStatusValue,
} from "../hooks/useMcpTools";
import type { ReadonlyRecord } from "../types/utils";
import { createOnToolResult } from "../utils/mcpToolResultTextJson";
import { shouldContinuePollingSweepView } from "../utils/sweepPollPolicy";

// ── Types ────────────────────────────────────────────────────────────────────

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

// ── Component ────────────────────────────────────────────────────────────────

export function SweepApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [sweepId, setSweepId] = useState<string | null>(null);
  const [status, setStatus] = useState<SweepStatusResponse | null>(null);
  const [appError, setAppError] = useState<string | null>(null);
  /** True while `apply_audit` is in flight — stops polling so a deleted sweep is not re-fetched. */
  const [applyingAudit, setApplyingAudit] = useState(false);
  /** After apply removed the open sweep; show completion UI and keep polling off. */
  const [sweepEndedAfterApply, setSweepEndedAfterApply] = useState(false);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "SweepApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (app) => {
      app.ontoolresult = createOnToolResult<SweepCreateResultPayload>(
        (data) => setSweepId(data.sweep_id),
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

  const getSweepStatus = useGetSweepStatus(app);
  const applyAudit = useApplyAudit(app);

  const pollSweepStatus = useCallback(async (): Promise<boolean> => {
    if (!sweepId) return false;
    try {
      const data = await getSweepStatus(sweepId);
      setStatus(data);
      return shouldContinuePollingSweepView(data);
    } catch (e) {
      setAppError(`Poll failed: ${String(e)}`);
      return false;
    }
  }, [sweepId, getSweepStatus]);

  usePoll({
    enabled: Boolean(app && sweepId && !applyingAudit && !sweepEndedAfterApply),
    intervalMs: 4000,
    tick: pollSweepStatus,
  });

  const handleApplyAudit = useCallback(async (): Promise<
    Readonly<{ cards_cleared: number; sweep_reset: boolean }>
  > => {
    if (!status) throw new Error("No sweep loaded.");
    setApplyingAudit(true);
    setAppError(null);
    try {
      const result: ApplyAuditResult = await applyAudit(status.tag_name);
      if (result.sweep_reset) {
        setSweepEndedAfterApply(true);
      }
      return { cards_cleared: result.cards_cleared, sweep_reset: result.sweep_reset };
    } finally {
      setApplyingAudit(false);
    }
  }, [status, applyAudit]);

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

  if (sweepEndedAfterApply && status) {
    return (
      <div style={pageStyle}>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: 4 }}>
          Tag sweep
        </div>
        <div style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: "0.75rem" }}>
          {status.tag_name}
        </div>
        <p
          style={{
            fontSize: "0.85rem",
            lineHeight: 1.5,
            color: "var(--color-text-secondary)",
            margin: 0,
          }}
        >
          The open sweep for this tag was removed after applying the audit.
        </p>
      </div>
    );
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
      {audit && <AuditSection audit={audit} onApplyAudit={handleApplyAudit} />}
    </div>
  );
}
