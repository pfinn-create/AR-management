import { ChevronDown, LogOut, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useCompany } from "../../context/CompanyContext";
import { formatCurrency } from "../../utils/formatters";
import clsx from "clsx";

export default function Header() {
  const { logout } = useAuth();
  const { companies, activeCompany, setActiveCompany } = useCompany();
  const [open, setOpen] = useState(false);

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shrink-0">
      {/* Company Toggle */}
      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 transition-colors"
        >
          <span className="font-semibold text-gray-800">{activeCompany?.name || "Select Company"}</span>
          {activeCompany && (
            <span className="text-xs text-gray-500">
              {formatCurrency(activeCompany.total_ar_balance)} AR
            </span>
          )}
          <ChevronDown className="w-4 h-4 text-gray-400" />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 w-80 bg-white rounded-xl shadow-lg border border-gray-200 z-50 py-1 max-h-96 overflow-y-auto">
            {companies.map((c) => (
              <button
                key={c.id}
                onClick={() => { setActiveCompany(c); setOpen(false); }}
                className={clsx(
                  "w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-gray-50 transition-colors",
                  c.id === activeCompany?.id && "bg-brand-50"
                )}
              >
                <div>
                  <div className="font-medium text-gray-800">{c.name}</div>
                  <div className="text-xs text-gray-500">
                    {c.open_invoices_count} invoices · {c.open_todos_count} todos
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-gray-700">
                    {formatCurrency(c.total_ar_balance)}
                  </div>
                  {c.overdue_amount > 0 && (
                    <div className="text-xs text-red-600">
                      {formatCurrency(c.overdue_amount)} overdue
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-3">
        {activeCompany && (
          <div className="flex items-center gap-4 text-xs text-gray-500 border-r border-gray-200 pr-4">
            {activeCompany.unanswered_emails_count > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
                {activeCompany.unanswered_emails_count} emails need response
              </span>
            )}
            {activeCompany.open_todos_count > 0 && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" />
                {activeCompany.open_todos_count} open todos
              </span>
            )}
          </div>
        )}

        <button
          onClick={logout}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </header>
  );
}
