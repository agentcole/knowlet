import api from "./client";
import type { ChatSession, ChatMessage } from "@/types";

export const chatApi = {
  createSession: (title = "New Chat") =>
    api.post<ChatSession>("/chat/sessions", { title }),

  listSessions: () => api.get<ChatSession[]>("/chat/sessions"),

  getSession: (id: string) => api.get<ChatSession>(`/chat/sessions/${id}`),

  getMessages: (sessionId: string) =>
    api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),

  deleteSession: (id: string) => api.delete(`/chat/sessions/${id}`),

  sendMessage: async function* (sessionId: string, content: string) {
    const token = localStorage.getItem("access_token");
    const tenantId = localStorage.getItem("tenant_id");
    if (!token || !tenantId) {
      throw new Error("Missing auth context. Please sign in again.");
    }

    const response = await fetch(`/api/v1/chat/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-Tenant-ID": tenantId || "",
      },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `Failed to send message (${response.status})`);
    }
    if (!response.body) return;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      buffer = buffer.replace(/\r/g, "");

      let eventBoundary = buffer.indexOf("\n\n");
      while (eventBoundary !== -1) {
        const rawEvent = buffer.slice(0, eventBoundary);
        buffer = buffer.slice(eventBoundary + 2);

        const lines = rawEvent.split("\n");
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("data:")) {
            let data = line.slice(5);
            // SSE allows a single optional space after ":"; keep any intentional
            // leading spaces from the model token stream.
            if (data.startsWith(" ")) {
              data = data.slice(1);
            }
            dataLines.push(data);
          }
        }

        if (dataLines.length > 0) {
          const data = dataLines.join("\n");
          if (data === "[DONE]") return;
          yield data;
        }

        eventBoundary = buffer.indexOf("\n\n");
      }

      if (done) break;
    }
  },
};
