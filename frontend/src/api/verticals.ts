import { api } from "./client";
import type {
  CreateVerticalRequest,
  TriggerResponse,
  VerticalDetail,
  VerticalPipelineStatus,
  VerticalSummary,
} from "../types/vertical";

export const verticalsApi = {
  list: () => api.get<VerticalSummary[]>("/verticals"),

  create: (request: CreateVerticalRequest) =>
    api.post<VerticalDetail>("/verticals", request),

  get: (id: string) => api.get<VerticalDetail>(`/verticals/${id}`),

  discover: (id: string) =>
    api.post<TriggerResponse>(`/verticals/${id}/discover`),

  acquire: (id: string) =>
    api.post<TriggerResponse>(`/verticals/${id}/acquire`),

  ingest: (id: string) =>
    api.post<TriggerResponse>(`/verticals/${id}/ingest`),

  status: (id: string) =>
    api.get<VerticalPipelineStatus>(`/verticals/${id}/status`),
};
