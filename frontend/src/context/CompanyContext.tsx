import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../utils/api";
import { Company } from "../types";
import { useAuth } from "./AuthContext";

interface CompanyContextValue {
  companies: Company[];
  activeCompany: Company | null;
  setActiveCompany: (c: Company) => void;
  isLoading: boolean;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function CompanyProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [activeCompany, setActiveCompanyState] = useState<Company | null>(null);

  const { data: companies = [], isLoading } = useQuery<Company[]>({
    queryKey: ["companies"],
    queryFn: () => api.get("/companies").then((r) => r.data),
    enabled: !!user,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (companies.length > 0 && !activeCompany) {
      const saved = localStorage.getItem("ar_active_company");
      const found = saved ? companies.find((c) => c.id === parseInt(saved)) : null;
      setActiveCompanyState(found || companies[0]);
    }
  }, [companies]);

  const setActiveCompany = (c: Company) => {
    setActiveCompanyState(c);
    localStorage.setItem("ar_active_company", String(c.id));
  };

  return (
    <CompanyContext.Provider value={{ companies, activeCompany, setActiveCompany, isLoading }}>
      {children}
    </CompanyContext.Provider>
  );
}

export function useCompany() {
  const ctx = useContext(CompanyContext);
  if (!ctx) throw new Error("useCompany must be inside CompanyProvider");
  return ctx;
}
