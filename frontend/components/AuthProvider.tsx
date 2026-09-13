"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { User } from "@/types/project";
import { getMe, getToken, setToken as persistToken, login as apiLogin, register as apiRegister } from "@/lib/api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string; password: string; role: "analyst" | "contractor"; full_name: string; organization?: string;
  }) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => { throw new Error("AuthProvider not mounted"); },
  register: async () => { throw new Error("AuthProvider not mounted"); },
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => persistToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const result = await apiLogin(email, password);
    persistToken(result.access_token);
    setUser(result.user);
    return result.user;
  };

  const register = async (payload: {
    email: string; password: string; role: "analyst" | "contractor"; full_name: string; organization?: string;
  }) => {
    const result = await apiRegister(payload);
    persistToken(result.access_token);
    setUser(result.user);
    return result.user;
  };

  const logout = () => {
    persistToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Redirect to /login if not authenticated (after the initial load finishes).
 * Use inside a page component: `useRequireAuth()` at the top. */
export function useRequireAuth(role?: "analyst" | "contractor") {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (role && user.role !== role) {
      router.replace(user.role === "contractor" ? "/contractor" : "/");
    }
  }, [user, loading, role, router]);

  return { user, loading };
}
