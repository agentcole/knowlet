import api from "./client";
import type { WikiCategory, WikiPage, WikiPageRevision, WikiTree } from "@/types";

export const wikiApi = {
  getTree: () => api.get<WikiTree>("/wiki/tree"),

  createCategory: (data: { name: string; parent_id?: string; sort_order?: number }) =>
    api.post<WikiCategory>("/wiki/categories", data),

  updateCategory: (
    id: string,
    data: { name?: string; parent_id?: string | null; sort_order?: number },
  ) => api.put<WikiCategory>(`/wiki/categories/${id}`, data),

  deleteCategory: (id: string) => api.delete(`/wiki/categories/${id}`),

  createPage: (data: { title: string; category_id?: string; sort_order?: number; markdown_content?: string }) =>
    api.post<WikiPage>("/wiki/pages", data),

  getPage: (id: string) => api.get<WikiPage>(`/wiki/pages/${id}`),

  updatePage: (id: string, data: { title?: string; category_id?: string | null; sort_order?: number; markdown_content?: string; change_note?: string }) =>
    api.put<WikiPage>(`/wiki/pages/${id}`, data),

  deletePage: (id: string) => api.delete(`/wiki/pages/${id}`),

  search: (q: string) => api.get<WikiPage[]>("/wiki/search", { params: { q } }),

  generate: () => api.post("/wiki/generate"),

  reindex: () => api.post("/wiki/reindex"),

  listRevisions: (pageId: string) =>
    api.get<WikiPageRevision[]>(`/wiki/pages/${pageId}/revisions`),

  restoreRevision: (pageId: string, revisionId: string) =>
    api.post<WikiPage>(`/wiki/pages/${pageId}/revisions/${revisionId}/restore`),
};
