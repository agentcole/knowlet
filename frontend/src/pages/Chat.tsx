import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useChatSessions, useChatMessages, useCreateChatSession, useSendMessage } from "@/hooks/useChat";
import { chatApi } from "@/api/chat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { MessageSquare, Plus, Send, Trash2, BookOpen } from "lucide-react";

export function ChatPage() {
  const {
    data: sessions,
    refetch: refetchSessions,
    error: sessionsError,
  } = useChatSessions();
  const createSession = useCreateChatSession();
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const { data: messages, error: messagesError } = useChatMessages(selectedSessionId || "");
  const {
    send,
    streamingContent,
    isStreaming,
    error: sendError,
  } = useSendMessage(selectedSessionId || "");
  const [input, setInput] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  useEffect(() => {
    if (!sessions || sessions.length === 0) {
      setSelectedSessionId(null);
      return;
    }

    if (!selectedSessionId || !sessions.some((session) => session.id === selectedSessionId)) {
      setSelectedSessionId(sessions[0].id);
    }
  }, [sessions, selectedSessionId]);

  const handleSend = async () => {
    if (!input.trim() || !selectedSessionId || isStreaming) return;
    const msg = input;
    setInput("");
    setPendingUserMessage(msg);
    try {
      await send(msg);
    } catch {
      setInput(msg);
    } finally {
      setPendingUserMessage(null);
    }
  };

  const handleNewChat = async () => {
    const session = await createSession.mutateAsync("New Chat");
    setSelectedSessionId(session.id);
  };

  const handleDelete = async (id: string) => {
    await chatApi.deleteSession(id);
    if (selectedSessionId === id) setSelectedSessionId(null);
    refetchSessions();
  };

  return (
    <div className="flex h-full">
      {/* Session list */}
      <div className="w-72 border-r border-border p-4 overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">Chats</h2>
          <Button variant="ghost" size="icon" onClick={handleNewChat}>
            <Plus size={16} />
          </Button>
        </div>

        {sessions?.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">No chat sessions yet</p>
        )}
        {sessionsError && (
          <p className="text-sm text-destructive text-center py-2">
            Failed to load chat sessions.
          </p>
        )}

        <div className="space-y-1">
          {sessions?.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center justify-between px-2 py-1.5 rounded text-sm cursor-pointer ${
                selectedSessionId === session.id ? "bg-primary text-primary-foreground" : "hover:bg-accent"
              }`}
              onClick={() => setSelectedSessionId(session.id)}
            >
              <span className="truncate">{session.title}</span>
              <button
                onClick={(e) => { e.stopPropagation(); handleDelete(session.id); }}
                className="opacity-0 group-hover:opacity-100 hover:text-destructive"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {selectedSessionId ? (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-auto p-6 space-y-4">
              {messages?.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[70%] rounded-lg px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted"
                    }`}
                  >
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-border/50">
                        <p className="text-xs font-medium mb-1 flex items-center gap-1">
                          <BookOpen size={12} /> Sources
                        </p>
                        {msg.sources.map((src, i) => (
                          <p key={i} className="text-xs opacity-75">{src.title || `Source ${i + 1}`}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {pendingUserMessage && (
                <div className="flex justify-end">
                  <div className="max-w-[70%] rounded-lg px-4 py-3 bg-primary text-primary-foreground">
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown>{pendingUserMessage}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
              {isStreaming && streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[70%] rounded-lg px-4 py-3 bg-muted">
                    <div className="prose prose-sm max-w-none">
                      <ReactMarkdown>{streamingContent}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-border p-4">
              {(messagesError || sendError) && (
                <div className="mb-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {sendError || "Failed to load chat messages."}
                </div>
              )}
              <form
                onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                className="flex gap-2"
              >
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about your knowledge base..."
                  disabled={isStreaming}
                  className="flex-1"
                />
                <Button type="submit" disabled={isStreaming || !input.trim()}>
                  <Send size={16} />
                </Button>
              </form>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <MessageSquare size={48} className="mx-auto mb-3 opacity-50" />
              <p>Select a chat or start a new one</p>
              <Button variant="outline" className="mt-4" onClick={handleNewChat}>
                <Plus size={16} /> New Chat
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
