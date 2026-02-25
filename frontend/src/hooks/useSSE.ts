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
      setState((s) => ({ ...s, events: [...s.events, data] }));
    });

    eventSource.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
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
