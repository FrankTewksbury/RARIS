import { api } from "./client";
import type {
  GenerateRequest,
  GenerateResponse,
  ManifestDetail,
  ManifestSummary,
  ReviewRequest,
  Source,
} from "../types/manifest";

export const manifestsApi = {
  generate: (req: GenerateRequest) =>
    api.post<GenerateResponse>("/manifests/generate", req),

  get: (id: string) => api.get<ManifestDetail>(`/manifests/${id}`),

  list: () => api.get<{ manifests: ManifestSummary[] }>("/manifests"),

  updateSource: (manifestId: string, sourceId: string, update: Partial<Source>) =>
    api.patch<Source>(`/manifests/${manifestId}/sources/${sourceId}`, update),

  addSource: (manifestId: string, source: Omit<Source, "id">) =>
    api.post<Source>(`/manifests/${manifestId}/sources`, source),

  approve: (id: string, review: ReviewRequest) =>
    api.post<{ manifest_id: string; status: string; approved_at: string }>(
      `/manifests/${id}/approve`,
      review
    ),

  reject: (id: string, review: ReviewRequest) =>
    api.post<{ manifest_id: string; status: string; rejection_notes: string }>(
      `/manifests/${id}/reject`,
      review
    ),
};
