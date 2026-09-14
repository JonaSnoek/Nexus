import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import type { User } from "../types";
import {
  getMe,
  login as apiLogin,
  clearToken,
  checkHealth,
  getSetupStatus,
} from "../lib/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  setupRequired: boolean;
  oidcEnabled: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  checkPermission: (name: string) => boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [setupRequired, setSetupRequired] = useState(false);
  const [oidcEnabled, setOidcEnabled] = useState(false);
  const navigate = useNavigate();

  const refreshUser = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch {
      setUser(null);
      clearToken();
    }
  }, []);

  useEffect(() => {
    async function init() {
      try {
        const health = await checkHealth();
        setSetupRequired(health.setup_required);
        setOidcEnabled(health.oidc_enabled);

        if (health.setup_required) {
          navigate("/setup", { replace: true });
          setLoading(false);
          return;
        }

        const token = localStorage.getItem("nexus_token");
        if (token) {
          await refreshUser();
        }
      } catch {
        // Backend unreachable
      }
      setLoading(false);
    }
    init();
  }, [navigate, refreshUser]);

  const login = useCallback(
    async (username: string, password: string) => {
      await apiLogin({ username, password });
      const me = await getMe();
      setUser(me);
      navigate("/chat", { replace: true });
    },
    [navigate]
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const checkPermission = useCallback(
    (name: string) => {
      if (!user) return false;
      if (user.role === "admin") return true;
      return (user.permissions || []).includes(name);
    },
    [user]
  );

  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        setupRequired,
        oidcEnabled,
        login,
        logout,
        refreshUser,
        checkPermission,
        isAdmin,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}