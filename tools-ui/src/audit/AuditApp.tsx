import { useApp, useHostStyles } from "@modelcontextprotocol/ext-apps/react";
import { useCallback, useEffect, useState } from "react";
import type { McpUiHostContext } from "@modelcontextprotocol/ext-apps";
import { AuditSection } from "../components/AuditSection";
import { usePoll } from "../hooks/usePoll";
import { useApplyAudit, useGetTagAudit } from "../hooks/useMcpTools";
import type { AuditResponse } from "../hooks/useMcpTools";
import { createOnToolResult } from "../utils/mcpToolResultTextJson";

// ── Styles ───────────────────────────────────────────────────────────────────

const PAGE_STYLE: React.CSSProperties = {
  padding: "1.5rem",
  minHeight: "100%",
  backgroundColor: "var(--color-background-tertiary)",
  color: "var(--color-text-primary)",
  fontFamily: "var(--font-family-sans, sans-serif)",
  boxSizing: "border-box",
};

// ── Component ────────────────────────────────────────────────────────────────

export function AuditApp() {
  const [hostContext, setHostContext] = useState<McpUiHostContext | undefined>();
  const [auditData, setAuditData] = useState<AuditResponse | null>(null);
  const [appError, setAppError] = useState<string | null>(null);

  const { app, isConnected, error } = useApp({
    appInfo: { name: "AuditApp", version: "1.0.0" },
    capabilities: {},
    onAppCreated: (app) => {
      app.ontoolresult = createOnToolResult<AuditResponse>(setAuditData, setAppError);
      app.onteardown = async () => ({});
      app.onerror = (e) => setAppError(String(e));
      app.onhostcontextchanged = (ctx) => setHostContext((prev) => ({ ...prev, ...ctx }));
    },
  });

  useEffect(() => {
    if (app) setHostContext(app.getHostContext());
  }, [app]);

  useHostStyles(app, app?.getHostContext());

  const getTagAudit = useGetTagAudit(app);
  const applyAudit = useApplyAudit(app);

  const pollTick = useCallback(async (): Promise<boolean> => {
    if (!auditData) return false;
    try {
      const data = await getTagAudit(auditData.audit_id);
      setAuditData(data);
      return data.status !== "complete" && data.status !== "failed";
    } catch (e) {
      setAppError(`Poll failed: ${String(e)}`);
      return false;
    }
  }, [auditData, getTagAudit]);

  usePoll({
    enabled: !!auditData && auditData.status !== "complete" && auditData.status !== "failed",
    intervalMs: 4000,
    tick: pollTick,
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

  if (!isConnected || !auditData) {
    return <div style={pageStyle}>Connecting…</div>;
  }

  return (
    <div style={pageStyle}>
      {/* Header */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-tertiary)", marginBottom: 2 }}>
          Tag audit
        </div>
        <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{auditData.tag_name}</div>
        <div style={{ fontSize: "0.7rem", color: "var(--color-text-tertiary)", marginTop: 2 }}>
          {auditData.audit_id}
        </div>
      </div>

      <AuditSection
        audit={{
          audit_id: auditData.audit_id,
          status: auditData.status,
          report: auditData.report,
          suggestion: auditData.suggestion,
        }}
        onApplyAudit={() => applyAudit(auditData.tag_name)}
      />
    </div>
  );
}
