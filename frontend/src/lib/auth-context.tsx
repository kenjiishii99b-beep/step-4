"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { getSession, refreshSession, setSession, subscribeSession } from "@/lib/token-store";
import { StaffSession } from "@/types/auth";

interface AuthContextValue {
  session: StaffSession | null;
  isLoading: boolean;
  login: (staffId: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<StaffSession | null>(getSession());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = subscribeSession(setSessionState);
    // ページ再読み込み時、HttpOnly Cookie の Refresh Token からセッション
    // 復元を試みる（サイレントログイン）。
    refreshSession().finally(() => setIsLoading(false));
    return unsubscribe;
  }, []);

  const login = useCallback(async (staffId: string, password: string) => {
    const response = await apiClient.post<StaffSession>("/auth/login", {
      staff_id: staffId,
      password,
    });
    setSession(response.data);
  }, []);

  const logout = useCallback(async () => {
    setSession(null);
    try {
      await fetch("/api/bff/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      // ログアウト自体はクライアント側のセッション破棄で完結するため、
      // Cookie削除リクエストの失敗は握りつぶしてよい。
    }
  }, []);

  return (
    <AuthContext.Provider value={{ session, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth は AuthProvider の内部で使用してください。");
  }
  return context;
}
