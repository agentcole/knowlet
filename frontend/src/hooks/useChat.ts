import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback } from "react";
import { chatApi } from "@/api/chat";

export function useChatSessions() {
  return useQuery({
    queryKey: ["chat-sessions"],
    queryFn: () => chatApi.listSessions().then((r) => r.data),
  });
}

export function useChatMessages(sessionId: string) {
  return useQuery({
    queryKey: ["chat-messages", sessionId],
    queryFn: () => chatApi.getMessages(sessionId).then((r) => r.data),
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) => chatApi.createSession(title).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions"] }),
  });
}

export function useSendMessage(sessionId: string) {
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const send = useCallback(
    async (content: string) => {
      setIsStreaming(true);
      setStreamingContent("");
      setError(null);

      try {
        for await (const chunk of chatApi.sendMessage(sessionId, content)) {
          setStreamingContent((prev) => prev + chunk);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to send message");
        throw err;
      } finally {
        setIsStreaming(false);
        setStreamingContent("");
        queryClient.invalidateQueries({ queryKey: ["chat-messages", sessionId] });
      }
    },
    [sessionId, queryClient]
  );

  return { send, streamingContent, isStreaming, error };
}
