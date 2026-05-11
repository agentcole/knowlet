import api from "./client";
import type { Meeting, Transcript, PaginatedResponse } from "@/types";

export const meetingsApi = {
  upload: (file: File, title: string, language: string, meetingDate?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title);
    formData.append("language", language);
    if (meetingDate) formData.append("meeting_date", meetingDate);
    return api.post("/meetings/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  list: (page = 1, pageSize = 20) =>
    api.get<PaginatedResponse<Meeting>>("/meetings/", {
      params: { page, page_size: pageSize },
    }),

  get: (id: string) => api.get<Meeting>(`/meetings/${id}`),

  delete: (id: string) => api.delete(`/meetings/${id}`),

  getTranscript: (id: string) =>
    api.get<Transcript>(`/meetings/${id}/transcript`),

  getSummary: (id: string) =>
    api.get<{ summary: string; action_items: Array<Record<string, string>> }>(
      `/meetings/${id}/summary`
    ),
};
