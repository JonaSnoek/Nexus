import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Square, Sparkles, StopCircle, AlertCircle, AlertTriangle, ImagePlus, Image as ImageIcon, Loader2 } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import type { Message, ChatResponse } from "../types";
import { getChat, sendMessageStream, createChat, updateChat, generateImage } from "../lib/api";
import MessageContent from "./MessageContent";
import ChatImage from "./ChatImage";

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
  const [mode, setMode] = useState<"chat" | "image">("chat");
  const [imageGenerating, setImageGenerating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
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
    if (!imageGenerating) {
      setElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      250
    );
    return () => clearInterval(timer);
  }, [imageGenerating]);

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
    if (!content || streaming || imageGenerating) return;

    if (mode === "image") {
      await handleImageSend(content);
      return;
    }

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

  async function handleImageSend(prompt: string) {
    setInput("");
    setError(null);
    setErrorKind("error");

    async function run(targetChatId: string) {
      setImageGenerating(true);
      try {
        const image = await generateImage({
          prompt,
          chat_id: targetChatId ? Number(targetChatId) : null,
        });
        // Refresh the chat so the persisted image message appears.
        const chatData: ChatResponse = await getChat(targetChatId);
        if (chatData.messages?.length > 0) {
          setMessages(chatData.messages);
        }
        return Boolean(image);
      } catch (err: any) {
        if (err.message !== "Unauthorized") {
          setError(err.message || "Bildgenerierung fehlgeschlagen");
          setErrorKind(
            typeof err.message === "string" && err.message.includes("Limit")
              ? "limit"
              : "error"
          );
        }
        return false;
      } finally {
        setImageGenerating(false);
      }
    }

    if (!chatId) {
      try {
        const newChat = await createChat();
        onChatCreated?.(String(newChat.id));
        navigate(`/chat/${newChat.id}`, { replace: true });
        setTimeout(() => run(String(newChat.id)), 100);
      } catch (err: any) {
        setError(err.message || "Chat konnte nicht erstellt werden");
      }
      return;
    }

    await run(chatId);
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
                      <div>
                        <MessageContent content={msg.content} />
                        {msg.image ? <ChatImage image={msg.image} /> : null}
                      </div>
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
            {canGenerateImage && (
              <button
                onClick={() => setMode(mode === "image" ? "chat" : "image")}
                title={mode === "image" ? "Zurück zum Chat-Modus" : "Bild generieren (Image-Modus)"}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
                  mode === "image"
                    ? "bg-purple-500/20 text-purple-300"
                    : "text-gray-400 hover:bg-nexus-elevated hover:text-gray-200"
                }`}
              >
                <ImagePlus size={16} />
              </button>
            )}
            {mode === "image" && (
              <span className="flex h-9 shrink-0 items-center rounded-lg bg-purple-500/10 px-2 text-[11px] font-medium text-purple-300">
                Bild
              </span>
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === "image"
                  ? "Beschreibe das Bild, das NEXUS generieren soll…"
                  : "Type a message..."
              }
              rows={1}
              className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-gray-100 placeholder-gray-500 outline-none"
            />
            <div className="flex items-center gap-1">
              {imageGenerating ? (
                <div className="flex items-center gap-2 px-1 text-xs text-gray-400">
                  <Loader2 size={14} className="animate-spin" />
                  <span>{elapsed}s</span>
                </div>
              ) : streaming ? (
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
                  {mode === "image" ? <ImageIcon size={14} /> : <Send size={14} />}
                </button>
              )}
            </div>
          </div>
          <div className="mt-2 flex items-center justify-center gap-3 text-center text-[11px] text-gray-600">
            <span>{mode === "image" ? "NEXUS Bildgenerierung" : "NEXUS AI Assistant"}</span>
            {imageGenerating && <span className="text-gray-500">Bild wird generiert…</span>}
          </div>
        </div>
      </div>
    </div>
  );
}