import { useQuery } from "@tanstack/react-query";
import { searchApi } from "@/api/search";

export function useSearchAll(query: string, limit = 30) {
  return useQuery({
    queryKey: ["search-all", query, limit],
    queryFn: () => searchApi.search(query, limit).then((r) => r.data),
    enabled: query.trim().length >= 2,
  });
}
