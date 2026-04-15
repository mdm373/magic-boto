import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import { useListSweeps, type SweepStatusResponse, type SweepStatusValue } from "../hooks/useMcpTools";
import { usePoll } from "../hooks/usePoll";
import type { ReadonlyRecord } from "../types/utils";
import { shouldContinuePollingSweepList } from "../utils/sweepPollPolicy";

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

const ROW_BOX: React.CSSProperties = {
  padding: "0.75rem 1rem",
  marginBottom: "0.5rem",
  borderRadius: 8,
  border: "1px solid var(--color-border-subtle, rgba(148, 163, 184, 0.25))",
  backgroundColor: "var(--color-background-secondary, rgba(255, 255, 255, 0.04))",
};

export function SweepCatchupApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [rows, setRows] = useState<readonly SweepStatusResponse[] | null>(null);
  const [appError, setAppError] = useState<string | null>(null);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "SweepCatchupApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (a) => {
      a.onteardown = async () => ({});
      a.onerror = (e) => setAppError(String(e));
      a.onhostcontextchanged = (ctx) => setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) setHostContext(app.getHostContext());
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const listSweeps = useListSweeps(app);

  const pollList = useCallback(async (): Promise<boolean> => {
    try {
      const data = await listSweeps();
      setRows(data.rows);
      return shouldContinuePollingSweepList(data.rows);
    } catch (e) {
      setAppError(`Poll failed: ${String(e)}`);
      return false;
    }
  }, [listSweeps]);

  usePoll({
    enabled: Boolean(app && isConnected),
    intervalMs: 4000,
    tick: pollList,
  });

  const insets = hostContext?.safeAreaInsets;
  const pageStyle: React.CSSProperties = insets
    ? {
        ...PAGE_STYLE,
        padding: `${insets.top}px ${insets.right}px ${insets.bottom}px ${insets.left}px`,
      }
    : PAGE_STYLE;

  const activeCount = useMemo(() => {
    if (rows == null) return 0;
    return rows.filter((r) => shouldContinuePollingSweepList([r])).length;
  }, [rows]);

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

  if (rows === null) {
    return <div style={pageStyle}>Loading sweep status…</div>;
  }

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: 4 }}>
          Global sweep catch-up
        </div>
        <div style={{ fontWeight: 600, fontSize: "1.05rem" }}>Status</div>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-secondary)", marginTop: 4 }}>
          {rows.length} tag{rows.length === 1 ? "" : "s"} with a sweep record
          {activeCount > 0 ? ` · ${activeCount} still updating` : " · all idle or terminal"}
        </div>
      </div>

      {rows.length === 0 ? (
        <p style={{ fontSize: "0.85rem", color: "var(--color-text-secondary)", margin: 0 }}>
          No tag sweeps on record yet. Run a per-tag sweep first; then global catch-up will appear
          here.
        </p>
      ) : (
        rows.map((status) => (
          <SweepRow key={status.sweep_id} status={status} />
        ))
      )}
    </div>
  );
}

function SweepRow({ status }: Readonly<{ status: SweepStatusResponse }>) {
  const { tag_name, batch_counts: bc } = status;
  const color = STATUS_COLORS[status.status];
  const progressPct = bc.total > 0 ? Math.round((bc.complete / bc.total) * 100) : 0;

  return (
    <div style={ROW_BOX}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600 }}>{tag_name}</span>
        <span
          style={{
            backgroundColor: color,
            color: "#fff",
            borderRadius: "0.25rem",
            padding: "0 0.4rem",
            fontSize: "0.7rem",
            fontWeight: 500,
          }}
        >
          {STATUS_LABELS[status.status]}
        </span>
      </div>
      <div style={{ fontSize: "0.65rem", color: "var(--color-text-tertiary)", marginTop: 2 }}>
        {status.sweep_id}
      </div>
      {bc.total > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.7rem",
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
              height: 4,
              borderRadius: 2,
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
              gap: "0.75rem",
              fontSize: "0.65rem",
              marginTop: 4,
              color: "var(--color-text-tertiary)",
              flexWrap: "wrap",
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
    </div>
  );
}
