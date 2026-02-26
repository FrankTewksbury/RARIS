import { api } from "./client";
import type {
  AccuracyDashboardData,
  ChangeEvent,
  CurationQueueItem,
  FeedbackDetail,
  ResolveFeedbackRequest,
  SubmitFeedbackRequest,
  TriggerMonitorResponse,
} from "../types/feedback";

export const feedbackApi = {
  submit: (request: SubmitFeedbackRequest) =>
    api.post<FeedbackDetail>("/feedback", request),

  list: (params?: { status?: string; feedback_type?: string; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.feedback_type) searchParams.set("feedback_type", params.feedback_type);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<FeedbackDetail[]>(`/feedback${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => api.get<FeedbackDetail>(`/feedback/${id}`),

  resolve: (id: string, request: ResolveFeedbackRequest) =>
    api.patch<FeedbackDetail>(`/feedback/${id}/resolve`, request),

  listQueue: (params?: { status?: string; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<CurationQueueItem[]>(`/curation-queue${qs ? `?${qs}` : ""}`);
  },

  processQueueItem: (id: string) =>
    api.post<CurationQueueItem>(`/curation-queue/${id}/process`),

  listChanges: (params?: { status?: string; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<ChangeEvent[]>(`/changes${qs ? `?${qs}` : ""}`);
  },

  getChange: (id: string) => api.get<ChangeEvent>(`/changes/${id}`),

  triggerMonitor: () => api.post<TriggerMonitorResponse>("/monitor/run"),

  dashboard: () => api.get<AccuracyDashboardData>("/accuracy/dashboard"),
};
