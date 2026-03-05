import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { useChatSessions, useChatMessages, useCreateChatSession, useSendMessage } from "@/hooks/useChat";
import { chatApi } from "@/api/chat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  MessageSquare,
  Plus,
  Send,
  Trash2,
  BookOpen,
  ExternalLink,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { Link } from "react-router-dom";
import type { ChatMessage } from "@/types";

function sourceTypeLabel(source: NonNullable<ChatMessage["sources"]>[number]): string {
  if (source.source_type === "wiki_page" || source.wiki_page_id) return "Wiki";
  if (source.source_type === "document") return "Document";
  return "Document Chunk";
}

function sourceHref(source: NonNullable<ChatMessage["sources"]>[number]): string {
  if (source.wiki_page_id) return `/wiki?pageId=${source.wiki_page_id}`;
  return "/documents";
}

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
  const [expandedSourcesByMessage, setExpandedSourcesByMessage] = useState<Record<string, boolean>>({});
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

  useEffect(() => {
    setExpandedSourcesByMessage({});
  }, [selectedSessionId]);

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
                      <div className="mt-3 border-t border-border/50 pt-2">
                        <button
                          className="mb-2 inline-flex items-center gap-1 text-xs font-medium hover:underline"
                          onClick={() =>
                            setExpandedSourcesByMessage((prev) => ({
                              ...prev,
                              [msg.id]: !prev[msg.id],
                            }))
                          }
                          type="button"
                        >
                          {expandedSourcesByMessage[msg.id] ? (
                            <ChevronDown size={12} />
                          ) : (
                            <ChevronRight size={12} />
                          )}
                          <BookOpen size={12} />
                          Sources ({msg.sources.length})
                        </button>
                        {expandedSourcesByMessage[msg.id] && (
                          <div className="space-y-2">
                            {msg.sources.map((src, i) => (
                              <div
                                key={src.wiki_page_id || src.document_id || src.chunk_id || `${msg.id}-${i}`}
                                className="rounded-md border border-border/60 bg-background/40 px-2 py-2 text-xs"
                              >
                                <div className="mb-1 flex items-center justify-between gap-2">
                                  <p className="truncate font-medium">
                                    {src.title || `Source ${i + 1}`}
                                  </p>
                                  <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                                    {sourceTypeLabel(src)}
                                  </span>
                                </div>
                                {src.snippet && (
                                  <p className="line-clamp-3 text-[11px] text-muted-foreground">
                                    {src.snippet}
                                  </p>
                                )}
                                <div className="mt-2 flex items-center justify-between">
                                  <span className="text-[10px] text-muted-foreground">
                                    Relevance: {(src.score * 100).toFixed(0)}%
                                  </span>
                                  <Link
                                    to={sourceHref(src)}
                                    className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                                  >
                                    Open
                                    <ExternalLink size={11} />
                                  </Link>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
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
