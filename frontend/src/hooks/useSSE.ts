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

    eventSource.addEventListener("step", (e) => {
      const data = JSON.parse(e.data) as AgentStepEvent;
      // #region agent log
      if (data.step === "program_enumerator" || data.step === "source_hunter") {
        fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Debug-Session-Id": "2fe1ec",
          },
          body: JSON.stringify({
            sessionId: "2fe1ec",
            runId: "sse-stream",
            hypothesisId: "H4",
            location: "frontend/src/hooks/useSSE.ts:step",
            message: "SSE step event received",
            data: { step: data.step, status: data.status, message: data.message ?? null },
            timestamp: Date.now(),
          }),
        }).catch(() => {});
      }
      // #endregion
      setState((s) => ({ ...s, events: [...s.events, data] }));
    });

    eventSource.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
      // #region agent log
      fetch("http://127.0.0.1:7884/ingest/644327d9-ea5d-464a-b97e-a7bf1c844fd6", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Debug-Session-Id": "2fe1ec",
        },
        body: JSON.stringify({
          sessionId: "2fe1ec",
          runId: "sse-stream",
          hypothesisId: "H1",
          location: "frontend/src/hooks/useSSE.ts:progress",
          message: "SSE progress event received",
          data: {
            sources_found: data.sources_found ?? null,
            bodies_processed: data.bodies_processed ?? null,
            total_bodies: data.total_bodies ?? null,
            message: data.message ?? null,
          },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
      // #endregion
      setState((s) => ({ ...s, events: [...s.events, { step: "progress", status: "update", ...data }] }));
    });

    eventSource.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        isConnected: false,
        events: [...s.events, { step: "complete", status: "complete", ...data }],
      }));
      eventSource.close();
    });

    eventSource.addEventListener("error", (e) => {
      const data = JSON.parse((e as MessageEvent).data || "{}");
      setState((s) => ({
        ...s,
        isConnected: false,
        error: data.message || "Connection error",
      }));
      eventSource.close();
    });

    eventSource.onerror = () => {
      setState((s) => ({ ...s, isConnected: false }));
      eventSource.close();
    };
  }, []);

  const disconnect = useCallback(() => {
    sourceRef.current?.close();
    setState((s) => ({ ...s, isConnected: false }));
  }, []);

  return { ...state, connect, disconnect };
}
