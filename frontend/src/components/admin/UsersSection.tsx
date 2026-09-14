import { useState, useEffect } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  X,
  AlertCircle,
  Check,
  Search,
} from "lucide-react";
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  updateUserLimits,
  getUserLimitsConfig,
} from "../../lib/api";
import type {
  User,
  UserCreate,
  UserUpdate,
  UserLimits,
  UpdateLimitsRequest,
} from "../../types";

type LimitMode = "standard" | "custom" | "unlimited";

export default function UsersSection() {
  const [users, setUsers] = useState<User[]>([]);
  const [limits, setLimits] = useState<Record<string, UserLimits>>({});
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [createForm, setCreateForm] = useState<UserCreate>({
    username: "",
    display_name: "",
    email: "",
    password: "",
    role: "user",
  });

  const [editForm, setEditForm] = useState<
    Partial<UserUpdate> & {
      limits_mode: LimitMode;
      custom_monthly_token_limit?: number;
      monthly_message_limit?: number;
    }
  >({ limits_mode: "standard" });

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    setLoading(true);
    try {
      const data = await getUsers();
      setUsers(data);
      await loadLimits(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  async function loadLimits(userList: User[]) {
    try {
      const entries: Record<string, UserLimits> = {};
      for (const u of userList) {
        try {
          entries[String(u.id)] = await getUserLimitsConfig(u.id);
        } catch {
          // ignore per-user load failure
        }
      }
      setLimits(entries);
    } catch {
      // ignore
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const user = await createUser(createForm);
      setUsers((prev) => [...prev, user]);
      setShowCreate(false);
      setCreateForm({
        username: "",
        display_name: "",
        email: "",
        password: "",
        role: "user",
      });
      setSuccess("User created successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to create user");
    }
  }

  function openEdit(user: User) {
    const cfg = limits[String(user.id)];
    const isUnlimited = cfg ? cfg.unlimited : user.unlimited === true;
    const isExempt = cfg ? cfg.limits_exempt : user.limits_exempt === true;
    let mode: LimitMode = "standard";
    if (isUnlimited) mode = "unlimited";
    else if (isExempt) mode = "custom";
    setEditingUser(user);
    setEditForm({
      display_name: user.display_name || undefined,
      email: user.email || undefined,
      role: user.role,
      is_active: user.is_active,
      limits_mode: mode,
      custom_monthly_token_limit:
        cfg?.custom_monthly_token_limit ??
        user.custom_monthly_token_limit ??
        (isExempt ? user.effective_token_limit ?? user.monthly_token_limit : 100),
      monthly_message_limit: user.monthly_message_limit,
    });
    setError(null);
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editingUser) return;
    setError(null);
    try {
      const { limits_mode, custom_monthly_token_limit, monthly_message_limit, ...userUpdates } =
        editForm;

      if (Object.keys(userUpdates).length > 0) {
        const updated = await updateUser(editingUser.id, userUpdates);
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      }

      const limitsPayload: UpdateLimitsRequest = {
        monthly_message_limit: monthly_message_limit ?? editingUser.monthly_message_limit,
      };
      if (limits_mode === "standard") {
        limitsPayload.limits_exempt = false;
      } else if (limits_mode === "custom") {
        limitsPayload.limits_exempt = true;
        limitsPayload.unlimited = false;
        limitsPayload.custom_monthly_token_limit =
          custom_monthly_token_limit ?? 100;
      } else {
        limitsPayload.limits_exempt = true;
        limitsPayload.unlimited = true;
      }

      await updateUserLimits(String(editingUser.id), limitsPayload);
      await loadUsers();
      setEditingUser(null);
      setSuccess("User updated successfully");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to update user");
    }
  }

  async function handleDelete(userId: string | number) {
    setDeletingId(String(userId));
    try {
      await deleteUser(userId);
      setUsers((prev) => prev.filter((u) => String(u.id) !== String(userId)));
      setSuccess("User deleted");
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to delete user");
    } finally {
      setDeletingId(null);
    }
  }

  const filtered = users.filter(
    (u) =>
      u.username.toLowerCase().includes(search.toLowerCase()) ||
      (u.email && u.email.toLowerCase().includes(search.toLowerCase())) ||
      (u.display_name && u.display_name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Users</h2>
          <p className="text-sm text-gray-500">
            Manage user accounts, roles and monthly quotas
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500"
            />
            <input
              type="text"
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 rounded-lg border border-nexus-border bg-nexus-surface py-1.5 pl-8 pr-3 text-xs text-gray-200 placeholder-gray-500 outline-none focus:border-blue-500/50"
            />
          </div>
          <button
            onClick={() => {
              setShowCreate(true);
              setError(null);
            }}
            className="flex items-center gap-1.5 rounded-lg bg-blue-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-600"
          >
            <Plus size={14} />
            Add User
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-sm text-red-400">
          <AlertCircle size={14} className="shrink-0" />
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/5 px-3 py-2 text-sm text-green-400">
          <Check size={14} className="shrink-0" />
          {success}
        </div>
      )}

      {/* Create user modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-md rounded-xl border border-nexus-border bg-nexus-surface p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-100">
                Create User
              </h3>
              <button
                onClick={() => setShowCreate(false)}
                className="rounded p-1 text-gray-400 hover:text-gray-200"
              >
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Username
                </label>
                <input
                  type="text"
                  value={createForm.username}
                  onChange={(e) =>
                    setCreateForm((p) => ({ ...p, username: e.target.value }))
                  }
                  required
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Display Name
                </label>
                <input
                  type="text"
                  value={createForm.display_name}
                  onChange={(e) =>
                    setCreateForm((p) => ({
                      ...p,
                      display_name: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Email
                </label>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(e) =>
                    setCreateForm((p) => ({ ...p, email: e.target.value }))
                  }
                  required
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm((p) => ({ ...p, password: e.target.value }))
                  }
                  required
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Role
                </label>
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm((p) => ({
                      ...p,
                      role: e.target.value as "admin" | "user",
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Message limit / month (optional)
                </label>
                <input
                  type="number"
                  min={0}
                  placeholder="Default"
                  value={createForm.monthly_message_limit ?? ""}
                  onChange={(e) =>
                    setCreateForm((p) => ({
                      ...p,
                      monthly_message_limit: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-blue-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-600"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit user modal */}
      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-md rounded-xl border border-nexus-border bg-nexus-surface p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-100">
                Edit User: {editingUser.username}
              </h3>
              <button
                onClick={() => setEditingUser(null)}
                className="rounded p-1 text-gray-400 hover:text-gray-200"
              >
                <X size={16} />
              </button>
            </div>
            <form onSubmit={handleEdit} className="space-y-3">
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Display Name
                </label>
                <input
                  type="text"
                  value={editForm.display_name || ""}
                  onChange={(e) =>
                    setEditForm((p) => ({
                      ...p,
                      display_name: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Email
                </label>
                <input
                  type="email"
                  value={editForm.email || ""}
                  onChange={(e) =>
                    setEditForm((p) => ({ ...p, email: e.target.value }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Role
                </label>
                <select
                  value={editForm.role || "user"}
                  onChange={(e) =>
                    setEditForm((p) => ({
                      ...p,
                      role: e.target.value as "admin" | "user",
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {/* Token quota: three states */}
              <div>
                <label className="mb-1.5 block text-xs text-gray-400">
                  Token-Limit pro Monat (Nutzung & Limits)
                </label>
                <div className="grid grid-cols-3 gap-1 rounded-lg bg-nexus-elevated p-1">
                  {(
                    [
                      ["standard", "Standard"],
                      ["custom", "Benutzerdefiniert"],
                      ["unlimited", "Unbegrenzt"],
                    ] as [LimitMode, string][]
                  ).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() =>
                        setEditForm((p) => ({ ...p, limits_mode: value }))
                      }
                      className={`rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                        editForm.limits_mode === value
                          ? "bg-blue-500/20 text-blue-300"
                          : "text-gray-400 hover:text-gray-200"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <p className="mt-1 text-[11px] text-gray-500">
                  {editForm.limits_mode === "standard"
                    ? "Nutzung des globalen Standard-Limits aus den Einstellungen."
                    : editForm.limits_mode === "custom"
                      ? "Dieser Benutzer erhält ein eigenes, festes Kontingent."
                      : "Dieser Benutzer wird nie blockiert (Verbrauch wird weiter erfasst)."}
                </p>
              </div>

              {editForm.limits_mode === "custom" && (
                <div>
                  <label className="mb-1 block text-xs text-gray-400">
                    Individuelles Token-Limit / Monat
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={editForm.custom_monthly_token_limit ?? ""}
                    onChange={(e) =>
                      setEditForm((p) => ({
                        ...p,
                        custom_monthly_token_limit: e.target.value
                          ? Number(e.target.value)
                          : undefined,
                      }))
                    }
                    className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                  />
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs text-gray-400">
                  Message limit / month
                </label>
                <input
                  type="number"
                  min={0}
                  value={editForm.monthly_message_limit ?? ""}
                  onChange={(e) =>
                    setEditForm((p) => ({
                      ...p,
                      monthly_message_limit: e.target.value
                        ? Number(e.target.value)
                        : undefined,
                    }))
                  }
                  className="w-full rounded-lg border border-nexus-border bg-nexus-elevated px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-active"
                  checked={editForm.is_active !== false}
                  onChange={(e) =>
                    setEditForm((p) => ({
                      ...p,
                      is_active: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-gray-600 bg-nexus-elevated"
                />
                <label htmlFor="edit-active" className="text-xs text-gray-400">
                  Active
                </label>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  className="rounded-lg border border-nexus-border px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-blue-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-600"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Users table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : filtered.length === 0 ? (
        <p className="py-16 text-center text-sm text-gray-500">No users found</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-nexus-border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-nexus-border bg-nexus-surface">
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  Username
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 sm:table-cell">
                  Email
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  Role
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 md:table-cell">
                  Status
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 lg:table-cell">
                  Token-Limit
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 xl:table-cell">
                  Verbrauch
                </th>
                <th className="hidden px-4 py-3 text-xs font-medium text-gray-400 xl:table-cell">
                  Nachrichten
                </th>
                <th className="px-4 py-3 text-xs font-medium text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-nexus-border">
              {filtered.map((user) => {
                const cfg = limits[String(user.id)];
                const unlimited = cfg
                  ? cfg.unlimited
                  : user.unlimited === true;
                const isCustom = cfg
                  ? cfg.limits_exempt && !cfg.unlimited
                  : user.limits_exempt === true && user.unlimited !== true;
                const effective =
                  cfg?.effective_token_limit ?? user.effective_token_limit;
                const used = cfg?.tokens_used ?? user.tokens_used_month ?? 0;
                const remaining =
                  cfg?.tokens_remaining ?? user.tokens_remaining;
                const effectiveLabel =
                  cfg?.has_token_limit ?? user.has_token_limit !== false;
                return (
                  <tr
                    key={user.id}
                    className="transition-colors hover:bg-nexus-elevated/50"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-200">
                        {user.username}
                      </div>
                      <div className="text-xs text-gray-500 sm:hidden">
                        {user.email}
                      </div>
                    </td>
                    <td className="hidden px-4 py-3 text-gray-400 sm:table-cell">
                      {user.email}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          user.role === "admin"
                            ? "bg-blue-500/10 text-blue-400"
                            : "bg-gray-500/10 text-gray-400"
                        }`}
                      >
                        {user.role}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 md:table-cell">
                      <span
                        className={`inline-flex items-center gap-1 text-xs ${
                          user.is_active ? "text-green-400" : "text-gray-500"
                        }`}
                      >
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${
                            user.is_active ? "bg-green-400" : "bg-gray-500"
                          }`}
                        />
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="hidden px-4 py-3 lg:table-cell">
                      {unlimited ? (
                        <span className="text-xs font-medium text-emerald-400">
                          ∞ Unbegrenzt
                        </span>
                      ) : (
                        <div className="flex flex-col gap-0.5">
                          <span className="text-xs text-gray-300">
                            {effective != null
                              ? effective.toLocaleString()
                              : (user.monthly_token_limit ?? 0).toLocaleString()}
                          </span>
                          {isCustom && (
                            <span className="text-[10px] text-blue-400">
                              Individuell
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 xl:table-cell">
                      {unlimited ? (
                        <span className="text-xs text-gray-500">
                          {used.toLocaleString()} verbraucht
                        </span>
                      ) : effectiveLabel && effective ? (
                        <div className="flex flex-col gap-1">
                          <span className="text-xs text-gray-500">
                            {used.toLocaleString()} /{" "}
                            {effective.toLocaleString()} ·{" "}
                            <span
                              className={
                                (remaining ?? 0) <= 0
                                  ? "font-medium text-red-400"
                                  : "text-green-400"
                              }
                            >
                              {remaining != null
                                ? remaining.toLocaleString()
                                : 0}{" "}
                              übrig
                            </span>
                          </span>
                          <div className="h-1 overflow-hidden rounded-full bg-nexus-elevated">
                            <div
                              className={`h-full rounded-full ${
                                (used / effective) >= 0.9
                                  ? "bg-red-500"
                                  : (used / effective) >= 0.6
                                    ? "bg-yellow-500"
                                    : "bg-blue-500"
                              }`}
                              style={{
                                width: `${Math.min(100, (used / effective) * 100)}%`,
                              }}
                            />
                          </div>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-500">
                          {used.toLocaleString()} verbraucht
                        </span>
                      )}
                    </td>
                    <td className="hidden px-4 py-3 text-xs text-gray-500 xl:table-cell">
                      {(user.monthly_message_limit ?? 0).toLocaleString()} /{" "}
                      {(user.messages_remaining_month ?? 0).toLocaleString()}{" "}
                      übrig
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => openEdit(user)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-nexus-elevated hover:text-gray-200"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(user.id)}
                          disabled={deletingId === String(user.id)}
                          className="rounded p-1.5 text-gray-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
                        >
                          {deletingId === String(user.id) ? (
                            <div className="h-3.5 w-3.5 animate-spin rounded-full border border-red-400 border-t-transparent" />
                          ) : (
                            <Trash2 size={14} />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}