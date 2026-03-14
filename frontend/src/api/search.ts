import api from "./client";
import type { SearchResponse } from "@/types";

export const searchApi = {
  search: (query: string, limit = 30) =>
    api.get<SearchResponse>("/search", { params: { q: query, limit } }),
};
