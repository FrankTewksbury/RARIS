import { api } from "./client";
import type {
  AcquisitionRunDetail,
  AcquisitionRunSummary,
  AcquisitionSourceStatus,
  StartAcquisitionResponse,
} from "../types/acquisition";

export const acquisitionsApi = {
  start: (manifestId: string) =>
    api.post<StartAcquisitionResponse>("/acquisitions", { manifest_id: manifestId }),

  get: (id: string) => api.get<AcquisitionRunDetail>(`/acquisitions/${id}`),

  list: () => api.get<{ acquisitions: AcquisitionRunSummary[] }>("/acquisitions"),

  getSources: (id: string) =>
    api.get<{ sources: AcquisitionSourceStatus[] }>(`/acquisitions/${id}/sources`),

  getSource: (id: string, sourceId: string) =>
    api.get<AcquisitionSourceStatus>(`/acquisitions/${id}/sources/${sourceId}`),

  retrySource: (id: string, sourceId: string) =>
    api.post<{ source_id: string; status: string; retry_count: number; message: string }>(
      `/acquisitions/${id}/sources/${sourceId}/retry`
    ),
};
