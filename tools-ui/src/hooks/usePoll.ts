import { useCallback, useEffect, useRef } from "react";

export type UsePollOptions = Readonly<{
  enabled: boolean;
  intervalMs: number;
  /** Return `true` to schedule another tick after `intervalMs`. */
  tick: () => Promise<boolean>;
}>;

export function usePoll(options: UsePollOptions): void {
  const { enabled, intervalMs, tick } = options;
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runTick = useCallback(async () => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    const continuePolling = await tick();
    if (continuePolling) {
      timeoutRef.current = setTimeout(() => {
        void runTick();
      }, intervalMs);
    }
  }, [intervalMs, tick]);

  useEffect(() => {
    if (!enabled) {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      return;
    }

    void runTick();

    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [enabled, runTick]);
}
