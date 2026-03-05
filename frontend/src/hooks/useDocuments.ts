import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "@/api/documents";

export function useDocuments(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["documents", page, pageSize],
    queryFn: () => documentsApi.list(page, pageSize).then((r) => r.data),
    refetchInterval: 5000,
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => documentsApi.get(id).then((r) => r.data),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => documentsApi.upload(file).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}
