import { useState, useEffect } from "react";
import { Shield, AlertCircle, Check } from "lucide-react";
import { getPermissions, getUsers, updateUserPermissions } from "../../lib/api";
import type { User, Permission } from "../../types";

export default function PermissionsSection() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [perms, userList] = await Promise.all([
        getPermissions(),
        getUsers(),
      ]);
      setPermissions(perms);
      setUsers(userList);
      if (userList.length > 0) {
        setSelectedUserId(String(userList[0].id));
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  const selectedUser = users.find((u) => String(u.id) === selectedUserId);

  function getPermissionIds(user?: User): string[] {
    return user ? user.permissions || [] : [];
  }

  function togglePermission(permission: Permission) {
    if (!selectedUser || saving) return;
    setError(null);
    setSuccess(null);

    const current = getPermissionIds(selectedUser);
    const next = current.includes(permission.name)
      ? current.filter((n) => n !== permission.name)
      : [...current, permission.name];

    const ids = permissions
      .filter((p) => next.includes(p.name))
      .map((p) => p.id);

    setSaving(true);
    updateUserPermissions(String(selectedUser.id), ids)
      .then(() => {
        setUsers((prev) =>
          prev.map((u) =>
            String(u.id) === String(selectedUser.id)
              ? { ...u, permissions: next }
              : u
          )
        );
        setSuccess(
          current.includes(permission.name)
            ? "Permission revoked"
            : "Permission assigned"
        );
        setTimeout(() => setSuccess(null), 2000);
      })
      .catch((err: any) => {
        setError(err.message || "Failed to update permission");
      })
      .finally(() => setSaving(false));
  }

  function userHasPermission(name: string): boolean {
    const user = users.find((u) => String(u.id) === selectedUserId);
    if (!user) return false;
    if (user.role === "admin") return true;
    return (user.permissions || []).includes(name);
  }

  // Group permissions by prefix (before the dot) for a cleaner view
  const grouped = permissions.reduce(
    (acc, perm) => {
      const cat = perm.name.includes(".")
        ? perm.name.split(".")[0]
        : "general";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(perm);
      return acc;
    },
    {} as Record<string, Permission[]>
  );

  if (selectedUser?.role === "admin") {
    return (
      <div>
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-100">Permissions</h2>
          <p className="text-sm text-gray-500">
            Manage user permissions and access control
          </p>
        </div>

        <div className="mb-6 max-w-sm">
          <label className="mb-1 block text-sm text-gray-400">
            Select User
          </label>
          <select
            value={selectedUserId}
            onChange={(e) => setSelectedUserId(e.target.value)}
            className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
          >
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username} ({u.role})
              </option>
            ))}
          </select>
        </div>

        <div className="rounded-xl border border-nexus-border bg-nexus-surface p-8 text-center">
          <Shield size={32} className="mx-auto mb-3 text-blue-500" />
          <p className="text-sm text-gray-400">
            Admin users have all permissions by default and cannot be restricted
            here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-100">Permissions</h2>
        <p className="text-sm text-gray-500">
          Manage user permissions and access control
        </p>
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

      {/* User selector */}
      <div className="mb-6 max-w-sm">
        <label className="mb-1 block text-sm text-gray-400">Select User</label>
        <select
          value={selectedUserId}
          onChange={(e) => setSelectedUserId(e.target.value)}
          className="w-full rounded-lg border border-nexus-border bg-nexus-surface px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500/50"
        >
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username} ({u.role})
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([category, perms]) => (
            <div
              key={category}
              className="rounded-xl border border-nexus-border bg-nexus-surface"
            >
              <div className="border-b border-nexus-border px-4 py-3">
                <h3 className="text-sm font-medium capitalize text-gray-200">
                  {category}
                </h3>
              </div>
              <div className="divide-y divide-nexus-border">
                {perms.map((perm) => {
                  const enabled = userHasPermission(perm.name);
                  return (
                    <div
                      key={perm.id}
                      className="flex items-center justify-between px-4 py-3"
                    >
                      <div className="pr-4">
                        <p className="text-sm text-gray-200">{perm.name}</p>
                        {perm.description && (
                          <p className="mt-0.5 text-xs text-gray-500">
                            {perm.description}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => togglePermission(perm)}
                        disabled={saving}
                        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
                          enabled ? "bg-blue-500" : "bg-gray-600"
                        }`}
                      >
                        <span
                          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                            enabled ? "left-[18px]" : "left-0.5"
                          }`}
                        />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}