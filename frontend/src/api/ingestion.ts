import { api } from "./client";
import type {
  DocumentDetail,
  DocumentSummary,
  IndexStats,
  IngestionRunDetail,
  StartIngestionResponse,
} from "../types/ingestion";

export const ingestionApi = {
  start: (acquisitionId: string) =>
    api.post<StartIngestionResponse>("/ingestion/run", {
      acquisition_id: acquisitionId,
    }),

  get: (ingestionId: string) =>
    api.get<IngestionRunDetail>(`/ingestion/${ingestionId}`),

  listDocuments: (ingestionId: string) =>
    api.get<DocumentSummary[]>(`/ingestion/${ingestionId}/documents`),

  getDocument: (docId: string) =>
    api.get<DocumentDetail>(`/documents/${docId}`),

  approveDocument: (docId: string) =>
    api.patch<{ document_id: string; status: string }>(
      `/documents/${docId}/approve`,
      {}
    ),

  rejectDocument: (docId: string, reason: string) =>
    api.patch<{ document_id: string; status: string }>(
      `/documents/${docId}/reject`,
      { reason }
    ),

  indexStats: () => api.get<IndexStats>("/index/stats"),
};
