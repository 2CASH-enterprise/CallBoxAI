"use client";

/**
 * Contexte d'authentification (section 24 du cahier des charges).
 * Le token JWT est conservé dans le localStorage du navigateur ; l'identité
 * et les rôles de l'utilisateur sont toujours revérifiés côté backend via
 * /auth/me (jamais fait confiance à des données locales pour les décisions
 * de sécurité — uniquement pour l'affichage).
 */
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api, Me, ApiError, getStoredToken, setStoredToken, clearStoredToken } from "./api";

interface AuthContextValue {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
    organization_country?: string;
  }) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const PUBLIC_PATHS = ["/login", "/register"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      setUser(me);
    } catch (e) {
      clearStoredToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Protection des routes : redirige vers /login si non connecté (sauf sur
  // les pages publiques). Contrôle client-side simple, adapté au MVP — le
  // vrai contrôle d'accès reste toujours fait côté backend (section 24).
  useEffect(() => {
    if (loading) return;
    const isPublic = PUBLIC_PATHS.includes(pathname || "");
    if (!user && !isPublic) {
      router.replace("/login");
    }
    if (user && isPublic) {
      router.replace("/dashboard");
    }
  }, [user, loading, pathname, router]);

  const login = async (email: string, password: string) => {
    const { access_token } = await api.login(email, password);
    setStoredToken(access_token);
    await refresh();
  };

  const register = async (data: {
    email: string;
    password: string;
    full_name: string;
    organization_name: string;
    organization_country?: string;
  }) => {
    const { access_token } = await api.register(data);
    setStoredToken(access_token);
    await refresh();
  };

  const logout = () => {
    clearStoredToken();
    setUser(null);
    router.replace("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return ctx;
}

export { ApiError };
