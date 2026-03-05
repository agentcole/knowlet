import api from "./client";
import type {
  Document,
  DocumentChunk,
  DocumentWikiWorkflow,
  PaginatedResponse,
  WikiPlacement,
} from "@/types";

export const documentsApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post<Document>("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  list: (page = 1, pageSize = 20, status?: string) =>
    api.get<PaginatedResponse<Document>>("/documents/", {
      params: { page, page_size: pageSize, status },
    }),

  get: (id: string) => api.get<Document>(`/documents/${id}`),

  getContent: (id: string) =>
    api.get<{ markdown_content: string }>(`/documents/${id}/content`),

  getChunks: (id: string) =>
    api.get<DocumentChunk[]>(`/documents/${id}/chunks`),

  delete: (id: string) => api.delete(`/documents/${id}`),

  reprocess: (id: string) => api.post(`/documents/${id}/reprocess`),

  getWikiWorkflow: (id: string) =>
    api.get<DocumentWikiWorkflow>(`/documents/${id}/wiki-workflow`),

  approveWikiPlacement: (
    id: string,
    payload: { placement?: WikiPlacement; revision_note?: string },
  ) => api.post<DocumentWikiWorkflow>(`/documents/${id}/wiki-approve`, payload),
};
