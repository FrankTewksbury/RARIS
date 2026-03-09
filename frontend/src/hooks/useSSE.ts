import { useCallback, useRef, useState } from "react";
import type { AgentStepEvent } from "../types/manifest";

interface SSEState {
  events: AgentStepEvent[];
  isConnected: boolean;
  error: string | null;
}

export function useSSE() {
  const [state, setState] = useState<SSEState>({
    events: [],
    isConnected: false,
    error: null,
  });
  const sourceRef = useRef<EventSource | null>(null);

  const connect = useCallback((url: string) => {
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const eventSource = new EventSource(url);
    sourceRef.current = eventSource;
    setState((s) => ({ ...s, isConnected: true, events: [], error: null }));

    // ── V5 BFS events ────────────────────────────────────────────────────

    eventSource.addEventListener("sector_start", (e) => {
      const data = JSON.parse(e.data);
      // #region agent log
      fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "ea4deb" },
        body: JSON.stringify({ sessionId: "ea4deb", runId: "sse-v5", hypothesisId: "H-SSE", location: "useSSE.ts:sector_start", message: "sector_start received", data, timestamp: Date.now() }),
      }).catch(() => {});
      // #endregion
      setState((s) => ({
        ...s,
        events: [...s.events, {
          step: `sector:${data.sector_key}`,
          status: "running",
          message: `[${data.sector_n}/${data.sector_total}] ${data.sector_label} — starting…`,
          ...data,
        }],
      }));
    });

    eventSource.addEventListener("sector_complete", (e) => {
      const data = JSON.parse(e.data);
      // #region agent log
      fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "ea4deb" },
        body: JSON.stringify({ sessionId: "ea4deb", runId: "sse-v5", hypothesisId: "H-SSE", location: "useSSE.ts:sector_complete", message: "sector_complete received", data, timestamp: Date.now() }),
      }).catch(() => {});
      // #endregion
      const statusLabel = data.status === "failed" ? "failed" : "complete";
      setState((s) => ({
        ...s,
        events: [...s.events, {
          step: `sector:${data.sector_key}`,
          status: statusLabel,
          message: data.status === "failed"
            ? `${data.sector_label} — failed: ${data.error}`
            : `${data.sector_label} — ${data.entities_found ?? 0} entities found`,
          ...data,
        }],
      }));
    });

    eventSource.addEventListener("l1_assembly_complete", (e) => {
      const data = JSON.parse(e.data);
      // #region agent log
      fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "ea4deb" },
        body: JSON.stringify({ sessionId: "ea4deb", runId: "sse-v5", hypothesisId: "H-SSE", location: "useSSE.ts:l1_assembly_complete", message: "l1_assembly_complete received", data, timestamp: Date.now() }),
      }).catch(() => {});
      // #endregion
      setState((s) => ({
        ...s,
        events: [...s.events, {
          step: "l1_assembly",
          status: "complete",
          message: `L1 complete — ${data.total_entities ?? 0} entities, ${data.total_sources ?? 0} sources across ${data.sector_count ?? 0} sectors`,
          ...data,
        }],
      }));
    });

    eventSource.addEventListener("entity_expansion_start", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        events: [...s.events, {
          step: `expand:${data.entity_id}`,
          status: "running",
          message: `[L${data.depth + 1}][${data.jurisdiction_code || data.jurisdiction || '?'}] ${data.entity_name} (${data.entity_n}/${data.entity_total})`,
          ...data,
        }],
      }));
    });

    eventSource.addEventListener("entity_expansion_complete", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        events: [...s.events, {
          step: `expand:${data.entity_id}`,
          status: data.status === "failed" ? "failed" : "complete",
          message: data.status === "failed"
            ? `Expand failed: ${data.entity_name}`
            : `${data.entity_name} — ${data.programs_found ?? 0} programs`,
          ...data,
        }],
      }));
    });

    // ── Legacy V3 events (keep for backwards compatibility) ───────────────

    eventSource.addEventListener("step", (e) => {
      const data = JSON.parse(e.data) as AgentStepEvent;
      setState((s) => ({ ...s, events: [...s.events, data] }));
    });

    eventSource.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({ ...s, events: [...s.events, { step: "progress", status: "update", ...data }] }));
    });

    // ── Terminal events ───────────────────────────────────────────────────

    eventSource.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data);
      // #region agent log
      fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "ea4deb" },
        body: JSON.stringify({ sessionId: "ea4deb", runId: "sse-v5", hypothesisId: "H-SSE", location: "useSSE.ts:complete", message: "complete received", data, timestamp: Date.now() }),
      }).catch(() => {});
      // #endregion
      setState((s) => ({
        ...s,
        isConnected: false,
        events: [...s.events, { step: "complete", status: "complete", ...data }],
      }));
      eventSource.close();
    });

    eventSource.addEventListener("error", (e) => {
      const raw = (e as MessageEvent).data;
      const data = raw ? JSON.parse(raw) : {};
      setState((s) => ({
        ...s,
        isConnected: false,
        error: data.message || "Connection error",
      }));
      eventSource.close();
    });

    eventSource.onerror = () => {
      setState((s) => ({
        ...s,
        isConnected: false,
        error: s.error || "Live progress stream disconnected. The run may have completed or the backend may have restarted.",
      }));
      eventSource.close();
    };
  }, []);

  const disconnect = useCallback(() => {
    sourceRef.current?.close();
    setState((s) => ({ ...s, isConnected: false }));
  }, []);

  const reset = useCallback(() => {
    sourceRef.current?.close();
    setState({ events: [], isConnected: false, error: null });
  }, []);

  return { ...state, connect, disconnect, reset };
}
