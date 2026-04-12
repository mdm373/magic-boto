import { useCallback } from "react";
import type { App } from "@modelcontextprotocol/ext-apps";
import { useServerTool } from "./useServerTool";

// ── Shared API types ─────────────────────────────────────────────────────────

export const AuditStatusValues = ["pending", "in_progress", "complete", "failed"] as const;
export type AuditStatusValue = (typeof AuditStatusValues)[number];

export type AuditSectionData = Readonly<{
  audit_id: string;
  status: AuditStatusValue;
  report: string | null;
  suggestion?: string | null;
}>;

export type BatchCounts = Readonly<{
  total: number;
  pending: number;
  submitted: number;
  complete: number;
  failed: number;
}>;

const SweepStatusValues = ["pending", "open", "auditing", "complete", "failed"] as const;
export type SweepStatusValue = (typeof SweepStatusValues)[number];

export type SweepStatusResponse = Readonly<{
  sweep_id: string;
  tag_name: string;
  status: SweepStatusValue;
  triggered_at: string;
  completed_at: string | null;
  batch_counts: BatchCounts;
  audit: AuditSectionData | null;
}>;

export type AuditResponse = Readonly<{
  audit_id: string;
  tag_name: string;
  status: AuditStatusValue;
  report: string | null;
  suggestion: string | null;
  triggered_at: string;
}>;

export type ApplyAuditResult = Readonly<{
  tag_name: string;
  new_description: string;
  cards_cleared: number;
  sweep_reset: boolean;
}>;

// ── Named tool hooks ─────────────────────────────────────────────────────────

export function useGetSweepStatus(app: App | null) {
  const callTool = useServerTool(app);
  return useCallback(
    (sweepId: string) =>
      callTool<SweepStatusResponse>("get_sweep_status", { sweep_id: sweepId }),
    [callTool],
  );
}

export function useGetTagAudit(app: App | null) {
  const callTool = useServerTool(app);
  return useCallback(
    (auditId: string) => callTool<AuditResponse>("get_tag_audit", { audit_id: auditId }),
    [callTool],
  );
}

export function useApplyAudit(app: App | null) {
  const callTool = useServerTool(app);
  return useCallback(
    (tagName: string, opts?: { deleteTagged?: boolean; deleteSideTags?: boolean }) =>
      callTool<ApplyAuditResult>("apply_audit", {
        tag_name: tagName,
        delete_tagged: opts?.deleteTagged ?? true,
        delete_side_tags: opts?.deleteSideTags ?? true,
      }),
    [callTool],
  );
}
