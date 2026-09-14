import { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Plus,
  MessageSquare,
  Trash2,
  Search,
  LogOut,
  User,
  Shield,
  Menu,
  X,
  Settings,
} from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import type { Chat } from "../types";
import { listChats, createChat, deleteChat } from "../lib/api";

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const { chatId } = useParams();
  const [chats, setChats] = useState<Chat[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [loadingChats, setLoadingChats] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    loadChats();
  }, []);

  async function loadChats() {
    try {
      const data = await listChats();
      setChats(data);
    } catch {
      // ignore
    } finally {
      setLoadingChats(false);
    }
  }

  async function handleNewChat() {
    try {
      const chat = await createChat();
      setChats((prev) => [chat, ...prev]);
      navigate(`/chat/${chat.id}`);
      setMobileOpen(false);
    } catch {
      // ignore
    }
  }

  async function handleDeleteChat(e: React.MouseEvent, id: string | number) {
    e.stopPropagation();
    if (deletingId) return;
    const idStr = String(id);
    setDeletingId(idStr);
    try {
      await deleteChat(idStr);
      setChats((prev) => prev.filter((c) => String(c.id) !== idStr));
      if (chatId === idStr) {
        navigate("/chat");
      }
    } catch {
      // ignore
    } finally {
      setDeletingId(null);
    }
  }

  function handleSelectChat(id: string | number) {
    navigate(`/chat/${String(id)}`);
    setMobileOpen(false);
  }

  const filtered = chats.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex h-screen bg-[#0a0a0a]">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed z-50 flex h-full w-64 flex-col border-r border-nexus-border bg-nexus-surface transition-transform duration-200 lg:relative lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-nexus-border px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-500 text-xs font-bold text-white">
              N
            </div>
            <span className="text-sm font-semibold text-gray-100">NEXUS</span>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="rounded p-1 text-gray-400 hover:bg-nexus-elevated hover:text-gray-200 lg:hidden"
          >
            <X size={16} />
          </button>
        </div>

        {/* New Chat */}
        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="flex w-full items-center gap-2 rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-200 transition-colors hover:bg-[#222]"
          >
            <Plus size={16} />
            New Chat
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              type="text"
              placeholder="Search chats..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-nexus-border bg-nexus-elevated py-1.5 pl-8 pr-3 text-xs text-gray-200 placeholder-gray-500 outline-none focus:border-blue-500/50"
            />
          </div>
        </div>

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto px-2">
          {loadingChats ? (
            <div className="flex justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-2 py-8 text-center text-xs text-gray-500">
              {chats.length === 0
                ? "No chats yet. Start a new conversation."
                : "No chats match your search."}
            </div>
          ) : (
            filtered.map((chat) => (
              <div
                key={chat.id}
                onClick={() => handleSelectChat(chat.id)}
                className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                  String(chatId) === String(chat.id)
                    ? "bg-nexus-elevated text-gray-100"
                    : "text-gray-400 hover:bg-nexus-elevated hover:text-gray-200"
                }`}
              >
                <MessageSquare size={14} className="shrink-0" />
                <span className="flex-1 truncate">{chat.title || "Untitled"}</span>
                <button
                  onClick={(e) => handleDeleteChat(e, chat.id)}
                  disabled={deletingId === chat.id}
                  className="hidden shrink-0 rounded p-1 text-gray-500 hover:text-red-400 group-hover:block"
                >
                  {deletingId === chat.id ? (
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border border-red-400 border-t-transparent" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                </button>
              </div>
            ))
          )}
        </div>

        {/* Bottom nav */}
        <div className="border-t border-nexus-border p-3 space-y-1">
          <button
            onClick={() => {
              navigate("/profile");
              setMobileOpen(false);
            }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
          >
            <User size={15} />
            <span className="truncate">{user?.display_name || user?.username}</span>
          </button>

          {isAdmin && (
            <button
              onClick={() => {
                navigate("/admin");
                setMobileOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
            >
              <Shield size={15} />
              Admin
            </button>
          )}

          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-red-400"
          >
            <LogOut size={15} />
            Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex min-w-0 flex-1 flex-col">
        {/* Mobile header */}
        <div className="flex items-center border-b border-nexus-border px-4 py-2 lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded p-1 text-gray-400 hover:text-gray-200"
          >
            <Menu size={20} />
          </button>
          <div className="ml-3 flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-500 text-[10px] font-bold text-white">
              N
            </div>
            <span className="text-sm font-semibold text-gray-100">NEXUS</span>
          </div>
        </div>

        {children}
      </main>
    </div>
  );
}
