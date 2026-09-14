import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Square, Sparkles, StopCircle, AlertCircle, AlertTriangle } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import type { Message, ChatResponse } from "../types";
import { getChat, sendMessageStream, createChat, updateChat } from "../lib/api";
import MessageContent from "./MessageContent";

interface ChatAreaProps {
  chatId: string | null;
  onChatCreated?: (chatId: string) => void;
}

export default function ChatArea({ chatId, onChatCreated }: ChatAreaProps) {
  const { user, checkPermission } = useAuth();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<"error" | "limit">("error");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const streamingContentRef = useRef("");

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (chatId) {
      loadChat(chatId);
    } else {
      setMessages([]);
      setError(null);
      setErrorKind("error");
    }
  }, [chatId]);

  async function loadChat(id: string) {
    setLoading(true);
    setError(null);
    setErrorKind("error");
    try {
      const data: ChatResponse = await getChat(id);
      setMessages(data.messages || []);
    } catch (err: any) {
      setError(err.message || "Failed to load chat");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleSend() {
    const content = input.trim();
    if (!content || streaming) return;

    if (!chatId) {
      try {
        const newChat = await createChat();
        onChatCreated?.(String(newChat.id));
        navigate(`/chat/${newChat.id}`, { replace: true });
        setInput("");
        setTimeout(() => handleSendWithId(String(newChat.id), content), 100);
        return;
      } catch (err: any) {
        setError(err.message || "Failed to create chat");
        return;
      }
    }

    handleSendWithId(chatId, content);
  }

  async function handleSendWithId(targetChatId: string, content: string) {
    setInput("");
    setError(null);
    setErrorKind("error");

    const userMessage: Message = {
      id: "temp-" + Date.now(),
      role: "user",
      content,
      tokens: 0,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => {
      if (prev.some((m) => m.id === userMessage.id)) return prev;
      return [...prev, userMessage];
    });

    setStreaming(true);
    streamingContentRef.current = "";

    const assistantMessage: Message = {
      id: "streaming-" + Date.now(),
      role: "assistant",
      content: "",
      tokens: 0,
      created_at: new Date().toISOString(),
    };

    try {
      const stream = sendMessageStream(targetChatId, content);

      setMessages((prev) => [...prev, assistantMessage]);

      for await (const chunk of stream) {
        streamingContentRef.current += chunk;
        const currentContent = streamingContentRef.current;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessage.id
              ? { ...m, content: currentContent }
              : m
          )
        );
      }

      // Refresh chat to get proper persisted messages
      try {
        const chatData = await getChat(targetChatId);
        if (chatData.messages?.length > 0) {
          setMessages(chatData.messages);
        }
      } catch {
        // Use streaming messages as-is
      }
    } catch (err: any) {
      if (err.message !== "Unauthorized") {
        setError(err.message || "Failed to get response");
        if (err.code === "LIMIT_REACHED") {
          setErrorKind("limit");
        }
      }
      // The backend rejected/rolled back the optimistic messages (e.g. quota
      // exhausted), so restore the actually persisted state.
      setMessages((prev) =>
        prev.filter(
          (m) => m.id !== userMessage.id && m.id !== assistantMessage.id
        )
      );
    } finally {
      setStreaming(false);
      streamingContentRef.current = "";
    }
  }

  function adjustTextarea() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  useEffect(() => {
    adjustTextarea();
  }, [input]);

  const canGenerateImage = checkPermission("image.generate");

  if (!chatId && !loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-500/10">
            <Sparkles size={24} className="text-blue-500" />
          </div>
          <h2 className="mb-2 text-lg font-medium text-gray-200">
            Start a conversation
          </h2>
          <p className="text-sm text-gray-500">
            Send a message to begin chatting with NEXUS.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          </div>
        ) : (
          <div className="mx-auto max-w-3xl px-4 py-6">
            {messages.map((msg) => (
              <div key={msg.id} className="mb-6 last:mb-0">
                <div
                  className={`flex ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                      msg.role === "user"
                        ? "bg-blue-500/10 text-gray-100"
                        : "bg-nexus-elevated text-gray-200"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <MessageContent content={msg.content} />
                    ) : (
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">
                        {msg.content}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {streaming &&
              messages.length > 0 &&
              !messages[messages.length - 1]?.content && (
                <div className="flex justify-start">
                  <div className="rounded-2xl bg-nexus-elevated px-4 py-3">
                    <div className="flex gap-1">
                      <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.3s]" />
                      <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500 [animation-delay:-0.15s]" />
                      <div className="h-2 w-2 animate-bounce rounded-full bg-gray-500" />
                    </div>
                  </div>
                </div>
              )}

            {error && (
              <div
                className={`mt-4 flex items-start gap-2 rounded-lg border px-4 py-3 text-sm ${
                  errorKind === "limit"
                    ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-300"
                    : "border-red-500/20 bg-red-500/5 text-red-400"
                }`}
              >
                {errorKind === "limit" ? (
                  <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                ) : (
                  <AlertCircle size={14} className="mt-0.5 shrink-0" />
                )}
                <span>{error}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-nexus-border bg-[#0a0a0a] p-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex items-end gap-2 rounded-2xl border border-nexus-border bg-nexus-surface p-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              rows={1}
              className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none"
            />
            <div className="flex items-center gap-1">
              {streaming ? (
                <button
                  onClick={() => setStreaming(false)}
                  title="Stop generating"
                  className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/20 text-red-400 transition-colors hover:bg-red-500/30"
                >
                  <StopCircle size={14} />
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500 text-white transition-colors hover:bg-blue-600 disabled:opacity-30 disabled:hover:bg-blue-500"
                >
                  <Send size={14} />
                </button>
              )}
            </div>
          </div>
          <div className="mt-2 text-center text-[11px] text-gray-600">
            NEXUS AI Assistant
          </div>
        </div>
      </div>
    </div>
  );
}