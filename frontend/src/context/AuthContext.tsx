import { createContext, useContext, ReactNode } from "react";
import { User } from "../types";

interface AuthContextValue {
  user: User;
  isLoading: false;
  refreshUser: () => Promise<void>;
}

const defaultUser: User = {
  id: 1,
  email: "admin@armanagement.com",
  full_name: "AR Manager",
  role: "ar_manager",
  is_active: true,
  email_consent: true,
  email_consent_at: new Date().toISOString(),
  company_ids: [],
  created_at: new Date().toISOString(),
};

const AuthContext = createContext<AuthContextValue>({
  user: defaultUser,
  isLoading: false,
  refreshUser: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider value={{ user: defaultUser, isLoading: false, refreshUser: async () => {} }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
