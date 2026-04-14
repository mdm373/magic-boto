import { useState } from "react";
import Markdown from "react-markdown";
import type { ReadonlyRecord } from "../types/utils";
import type { AuditSectionData, AuditStatusValue } from "../hooks/useMcpTools";

export type { AuditSectionData, AuditStatusValue };

type ApplyResult = Readonly<{ cards_cleared: number; sweep_reset: boolean }>;
type ConfirmState = "idle" | "confirming" | "applying" | "done" | "error";

const AUDIT_STATUS_COLORS: ReadonlyRecord<AuditStatusValue, string> = {
  pending: "#6b7280",
  in_progress: "#f59e0b",
  complete: "#22c55e",
  failed: "#ef4444",
};

const AUDIT_STATUS_LABELS: ReadonlyRecord<AuditStatusValue, string> = {
  pending: "Pending",
  in_progress: "Running…",
  complete: "Complete",
  failed: "Failed",
};

const BTN_BASE: React.CSSProperties = {
  border: "none",
  borderRadius: "0.25rem",
  padding: "0.35rem 0.8rem",
  fontSize: "0.8rem",
  fontWeight: 500,
  cursor: "pointer",
};

interface AuditSectionProps {
  audit: AuditSectionData;
  /** When provided, an Apply Audit action is shown once the audit is complete. */
  onApplyAudit?: () => Promise<ApplyResult>;
  /** When true, no outer chrome — parent supplies padding/border (e.g. sweep UI card). */
  embedded?: boolean;
}

export function AuditSection({ audit, onApplyAudit, embedded = false }: AuditSectionProps) {
  const [confirmState, setConfirmState] = useState<ConfirmState>("idle");
  const [applyMessage, setApplyMessage] = useState<string | null>(null);

  const handleConfirm = async () => {
    if (!onApplyAudit) return;
    setConfirmState("applying");
    try {
      const result = await onApplyAudit();
      setApplyMessage(
        `Applied. ${result.cards_cleared} card(s) cleared.${result.sweep_reset ? " Sweep reset." : ""}`,
      );
      setConfirmState("done");
    } catch (e) {
      setApplyMessage(String(e));
      setConfirmState("error");
    }
  };

  const showApply =
    onApplyAudit && audit.status === "complete" && confirmState !== "done";

  const rootChrome: React.CSSProperties = embedded
    ? { padding: 0 }
    : {
        borderTop: "1px solid var(--color-border, #e5e7eb)",
        padding: "1.25rem 0 0",
      };

  return (
    <div style={rootChrome}>
      {/* Header row */}
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
            backgroundColor: AUDIT_STATUS_COLORS[audit.status],
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

      {/* Suggestion */}
      {audit.suggestion && (
        <div
          style={{
            fontSize: "0.8rem",
            color: "var(--color-text-secondary)",
            marginBottom: "0.75rem",
            borderLeft: "3px solid var(--color-border, #e5e7eb)",
            paddingLeft: "0.75rem",
            fontStyle: "italic",
          }}
        >
          {audit.suggestion}
        </div>
      )}

      {/* Report */}
      {audit.report && (
        <div className="prose prose-sm prose-sweep-report max-w-none dark:prose-invert">
          <Markdown>{audit.report}</Markdown>
        </div>
      )}

      {/* Apply audit flow */}
      {showApply && (
        <div style={{ marginTop: "1rem" }}>
          {confirmState === "idle" && (
            <button
              style={{ ...BTN_BASE, backgroundColor: "#3b82f6", color: "#fff" }}
              onClick={() => setConfirmState("confirming")}
            >
              Apply Audit
            </button>
          )}

          {confirmState === "confirming" && (
            <div
              style={{
                backgroundColor: "var(--color-background-secondary, #f3f4f6)",
                borderRadius: "0.375rem",
                padding: "0.75rem",
                fontSize: "0.8rem",
                color: "var(--color-text-secondary)",
              }}
            >
              <div style={{ marginBottom: "0.6rem" }}>
                This will apply the audit suggestion, clear all tagged cards, and delete the open
                sweep. This cannot be undone.
              </div>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button
                  style={{ ...BTN_BASE, backgroundColor: "#ef4444", color: "#fff" }}
                  onClick={() => void handleConfirm()}
                >
                  Confirm
                </button>
                <button
                  style={{
                    ...BTN_BASE,
                    backgroundColor: "transparent",
                    color: "var(--color-text-secondary)",
                    border: "1px solid var(--color-border, #d1d5db)",
                  }}
                  onClick={() => setConfirmState("idle")}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {confirmState === "applying" && (
            <button style={{ ...BTN_BASE, backgroundColor: "#3b82f6", color: "#fff", opacity: 0.6, cursor: "default" }} disabled>
              Applying…
            </button>
          )}

          {confirmState === "error" && (
            <div>
              <div style={{ fontSize: "0.75rem", color: "#ef4444", marginBottom: "0.4rem" }}>
                {applyMessage}
              </div>
              <button
                style={{ ...BTN_BASE, backgroundColor: "#ef4444", color: "#fff" }}
                onClick={() => setConfirmState("idle")}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      )}

      {/* Success */}
      {confirmState === "done" && applyMessage && (
        <div style={{ marginTop: "1rem", fontSize: "0.8rem", color: "#22c55e" }}>
          {applyMessage}
        </div>
      )}
    </div>
  );
}
