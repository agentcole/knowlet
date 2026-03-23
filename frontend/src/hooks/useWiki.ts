import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { wikiApi } from "@/api/wiki";

export function useWikiTree() {
  return useQuery({
    queryKey: ["wiki-tree"],
    queryFn: () => wikiApi.getTree().then((r) => r.data),
  });
}

export function useWikiAssets(query: string, page = 1, pageSize = 24) {
  return useQuery({
    queryKey: ["wiki-assets", query, page, pageSize],
    queryFn: () =>
      wikiApi
        .listAssets({
          q: query || undefined,
          page,
          page_size: pageSize,
        })
        .then((r) => r.data),
  });
}

export function useWikiPage(id: string) {
  return useQuery({
    queryKey: ["wiki-page", id],
    queryFn: () => wikiApi.getPage(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useWikiSearch(query: string) {
  return useQuery({
    queryKey: ["wiki-search", query],
    queryFn: () => wikiApi.search(query).then((r) => r.data),
    enabled: query.length > 0,
  });
}

export function useCreateWikiPage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { title: string; category_id?: string; sort_order?: number; markdown_content?: string }) =>
      wikiApi.createPage(data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["wiki-tree"] }),
  });
}

export function useCreateWikiCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; parent_id?: string; sort_order?: number }) =>
      wikiApi.createCategory(data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["wiki-tree"] }),
  });
}

export function useUpdateWikiCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      name?: string;
      parent_id?: string | null;
      sort_order?: number;
    }) => wikiApi.updateCategory(id, data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["wiki-tree"] }),
  });
}

export function useDeleteWikiCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => wikiApi.deleteCategory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["wiki-tree"] }),
  });
}

export function useUpdateWikiPage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      title?: string;
      category_id?: string | null;
      sort_order?: number;
      markdown_content?: string;
      change_note?: string;
    }) =>
      wikiApi.updatePage(id, data).then((r) => r.data),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
      queryClient.invalidateQueries({ queryKey: ["wiki-page", vars.id] });
      queryClient.invalidateQueries({ queryKey: ["wiki-revisions", vars.id] });
    },
  });
}

export function useDeleteWikiPage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => wikiApi.deletePage(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
      queryClient.invalidateQueries({ queryKey: ["wiki-page", id] });
      queryClient.invalidateQueries({ queryKey: ["wiki-revisions", id] });
    },
  });
}

export function useUploadWikiAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => wikiApi.uploadAsset(file).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wiki-assets"] });
    },
  });
}

export function useDeleteWikiAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => wikiApi.deleteAsset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wiki-assets"] });
    },
  });
}

export function useWikiRevisions(pageId: string) {
  return useQuery({
    queryKey: ["wiki-revisions", pageId],
    queryFn: () => wikiApi.listRevisions(pageId).then((r) => r.data),
    enabled: !!pageId,
  });
}

export function useRestoreWikiRevision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pageId, revisionId }: { pageId: string; revisionId: string }) =>
      wikiApi.restoreRevision(pageId, revisionId).then((r) => r.data),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
      queryClient.invalidateQueries({ queryKey: ["wiki-page", vars.pageId] });
      queryClient.invalidateQueries({ queryKey: ["wiki-revisions", vars.pageId] });
    },
  });
}

export function useReindexWiki() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => wikiApi.reindex().then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wiki-tree"] });
    },
  });
}
