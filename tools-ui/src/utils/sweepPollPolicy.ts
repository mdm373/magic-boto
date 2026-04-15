import type { AuditStatusValue, SweepStatusResponse } from "../hooks/useMcpTools";

const TERMINAL_AUDIT_STATUSES: ReadonlySet<AuditStatusValue> = new Set([
  "complete",
  "failed",
]);

/**
 * Whether to schedule another `get_sweep_status` poll after this payload.
 *
 * - If an audit row exists: keep polling until the audit is `complete` or `failed`.
 * - If there is no audit: keep polling only while the sweep is still `pending` or
 *   `auditing`; stop once the sweep is `open` (partial), `complete`, or `failed`.
 */
export function shouldContinuePollingSweepView(data: SweepStatusResponse): boolean {
  if (data.audit != null) {
    return !TERMINAL_AUDIT_STATUSES.has(data.audit.status);
  }
  return data.status === "pending" || data.status === "auditing";
}

/**
 * Keep polling `list_sweeps` while any row would still need updates in the single-sweep view.
 */
export function shouldContinuePollingSweepList(rows: readonly SweepStatusResponse[]): boolean {
  if (rows.length === 0) {
    return false;
  }
  return rows.some((row) => shouldContinuePollingSweepView(row));
}
