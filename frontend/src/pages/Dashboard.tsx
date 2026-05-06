import { useQuery } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { formatCurrency, formatDate, statusColor } from "../utils/formatters";
import { Invoice, TodoItem, MonthlyTrend, AgingReport } from "../types";
import { AlertTriangle, Mail, CheckSquare, TrendingUp, FileText, CreditCard } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from "recharts";

function StatCard({
  icon: Icon, label, value, sub, color, onClick
}: {
  icon: any; label: string; value: string; sub?: string; color: string; onClick?: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`card flex items-start gap-4 text-left w-full hover:shadow-md transition-shadow ${onClick ? "cursor-pointer" : "cursor-default"}`}
    >
      <div className={`p-2.5 rounded-lg ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        <p className="text-xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </button>
  );
}

export default function Dashboard() {
  const { activeCompany } = useCompany();
  const navigate = useNavigate();
  const cid = activeCompany?.id;

  const { data: invoices = [] } = useQuery<Invoice[]>({
    queryKey: ["invoices", cid],
    queryFn: () => api.get(`/invoices?company_id=${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const { data: todos = [] } = useQuery<TodoItem[]>({
    queryKey: ["todos", cid],
    queryFn: () => api.get(`/todos?company_id=${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const { data: trends = [] } = useQuery<MonthlyTrend[]>({
    queryKey: ["trends", cid],
    queryFn: () => api.get(`/reports/trends/${cid}?months=6`).then(r => r.data),
    enabled: !!cid,
  });

  const { data: aging } = useQuery<AgingReport>({
    queryKey: ["aging", cid],
    queryFn: () => api.get(`/reports/aging/${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const overdue = invoices.filter(i => i.status === "overdue");
  const overdueAmount = overdue.reduce((s, i) => s + Number(i.balance), 0);
  const totalAR = invoices.reduce((s, i) => s + Number(i.balance), 0);
  const highTodos = todos.filter(t => t.priority === "high");

  const agingData = aging
    ? [
        { name: "Current", amount: aging.aging.current },
        { name: "1-30d", amount: aging.aging["1_30"] },
        { name: "31-60d", amount: aging.aging["31_60"] },
        { name: "61-90d", amount: aging.aging["61_90"] },
        { name: ">90d", amount: aging.aging["over_90"] },
      ]
    : [];

  if (!activeCompany) {
    return <p className="text-gray-400">Select a company to get started.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">{activeCompany.name} — Overview</h1>
        <p className="text-xs text-gray-400 mt-0.5">AR summary and action items</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={FileText} label="Total AR Balance" value={formatCurrency(totalAR)}
          sub={`${invoices.filter(i => i.status !== "paid").length} open invoices`}
          color="bg-blue-50 text-blue-600"
          onClick={() => navigate("/invoices")}
        />
        <StatCard
          icon={AlertTriangle} label="Overdue" value={formatCurrency(overdueAmount)}
          sub={`${overdue.length} invoices past due`}
          color="bg-red-50 text-red-600"
          onClick={() => navigate("/invoices")}
        />
        <StatCard
          icon={CheckSquare} label="Open To-Dos" value={String(todos.length)}
          sub={`${highTodos.length} high priority`}
          color="bg-yellow-50 text-yellow-600"
          onClick={() => navigate("/todos")}
        />
        <StatCard
          icon={Mail} label="Unanswered Emails" value={String(activeCompany.unanswered_emails_count)}
          sub="Need response"
          color="bg-purple-50 text-purple-600"
          onClick={() => navigate("/emails")}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AR Aging */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">AR Aging</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={agingData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Monthly Trends */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">6-Month Trend</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={trends} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Legend />
              <Bar dataKey="invoiced" fill="#3b82f6" name="Invoiced" radius={[4, 4, 0, 0]} />
              <Bar dataKey="collected" fill="#22c55e" name="Collected" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Priority To-Dos */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800">High Priority To-Dos</h2>
          <button onClick={() => navigate("/todos")} className="text-xs text-brand-600 hover:underline">
            View all
          </button>
        </div>
        {highTodos.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">No high priority items</p>
        ) : (
          <div className="space-y-2">
            {highTodos.slice(0, 8).map((t) => (
              <div key={t.id} className="flex items-center gap-3 p-2.5 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                <span className={`badge ${t.priority === "high" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
                  {t.priority}
                </span>
                <span className="flex-1 text-sm text-gray-700 truncate">{t.title}</span>
                <span className="text-xs text-gray-400 capitalize">{t.category.replace(/_/g, " ")}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Overdue Invoices */}
      {overdue.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-800">Overdue Invoices</h2>
            <button onClick={() => navigate("/invoices")} className="text-xs text-brand-600 hover:underline">
              View all
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="pb-2 font-medium">Invoice #</th>
                  <th className="pb-2 font-medium">Customer</th>
                  <th className="pb-2 font-medium">Due Date</th>
                  <th className="pb-2 font-medium text-right">Balance</th>
                  <th className="pb-2 font-medium text-right">Days Overdue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {overdue.slice(0, 8).map((inv) => (
                  <tr
                    key={inv.id}
                    className="table-row-hover"
                    onClick={() => navigate(`/invoices`)}
                  >
                    <td className="py-2 font-mono text-xs text-blue-600">{inv.invoice_number}</td>
                    <td className="py-2 text-gray-700">{inv.customer_name || "—"}</td>
                    <td className="py-2 text-gray-500">{formatDate(inv.due_date)}</td>
                    <td className="py-2 text-right font-semibold text-red-600">{formatCurrency(Number(inv.balance))}</td>
                    <td className="py-2 text-right">
                      {inv.days_overdue != null && (
                        <span className="badge bg-red-100 text-red-700">{inv.days_overdue}d</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
