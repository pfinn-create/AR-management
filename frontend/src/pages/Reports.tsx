import { useQuery } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { AgingReport, MonthlyTrend } from "../types";
import { formatCurrency } from "../utils/formatters";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend, PieChart, Pie, Cell
} from "recharts";
import { useState } from "react";

const AGING_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#7c3aed"];

type AgingCustomer = {
  name: string;
  current: number;
  "1_30": number;
  "31_60": number;
  "61_90": number;
  over_90: number;
  total: number;
};

export default function Reports() {
  const { activeCompany } = useCompany();
  const [trendMonths, setTrendMonths] = useState(6);
  const cid = activeCompany?.id;

  const { data: aging } = useQuery<AgingReport>({
    queryKey: ["aging", cid],
    queryFn: () => api.get(`/reports/aging/${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const { data: agingCustomers = [] } = useQuery<AgingCustomer[]>({
    queryKey: ["aging-customers", cid],
    queryFn: () => api.get(`/reports/aging-by-customer/${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const { data: trends = [] } = useQuery<MonthlyTrend[]>({
    queryKey: ["trends", cid, trendMonths],
    queryFn: () => api.get(`/reports/trends/${cid}?months=${trendMonths}`).then(r => r.data),
    enabled: !!cid,
  });

  const agingBuckets = aging
    ? [
        { name: "Current", value: aging.aging.current, color: AGING_COLORS[0] },
        { name: "1-30d", value: aging.aging["1_30"], color: AGING_COLORS[1] },
        { name: "31-60d", value: aging.aging["31_60"], color: AGING_COLORS[2] },
        { name: "61-90d", value: aging.aging["61_90"], color: AGING_COLORS[3] },
        { name: ">90d", value: aging.aging["over_90"], color: AGING_COLORS[4] },
      ]
    : [];

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Reports & Trends</h1>
        <p className="text-xs text-gray-400">{activeCompany.name}</p>
      </div>

      {/* Aging Summary */}
      {aging && (
        <div className="grid grid-cols-5 gap-3">
          {agingBuckets.map((b) => (
            <div key={b.name} className="card text-center">
              <p className="text-xs text-gray-400 font-medium">{b.name}</p>
              <p className="text-lg font-bold mt-1" style={{ color: b.color }}>
                {formatCurrency(b.value)}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                {aging.total > 0 ? ((b.value / aging.total) * 100).toFixed(1) : "0"}%
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Aging Donut */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">AR Aging Breakdown</h2>
          <div className="flex items-center gap-6">
            <PieChart width={160} height={160}>
              <Pie
                data={agingBuckets}
                dataKey="value"
                cx={75}
                cy={75}
                innerRadius={45}
                outerRadius={75}
              >
                {agingBuckets.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
            </PieChart>
            <div className="space-y-1.5">
              {agingBuckets.map((b) => (
                <div key={b.name} className="flex items-center gap-2 text-xs">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: b.color }} />
                  <span className="text-gray-600 w-16">{b.name}</span>
                  <span className="font-semibold text-gray-800">{formatCurrency(b.value)}</span>
                </div>
              ))}
              {aging && (
                <div className="border-t border-gray-100 pt-1.5 flex items-center gap-2 text-xs">
                  <span className="w-3 h-3 shrink-0" />
                  <span className="text-gray-600 w-16 font-medium">Total</span>
                  <span className="font-bold text-gray-900">{formatCurrency(aging.total)}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Trend chart */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-800">Monthly Trend</h2>
            <div className="flex gap-1">
              {[3, 6, 12].map(m => (
                <button
                  key={m}
                  onClick={() => setTrendMonths(m)}
                  className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                    trendMonths === m ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {m}m
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Legend />
              <Line type="monotone" dataKey="invoiced" stroke="#3b82f6" name="Invoiced" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="collected" stroke="#22c55e" name="Collected" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="overdue" stroke="#ef4444" name="Overdue" strokeWidth={2} dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Aging by Customer */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">Aging by Customer (Top {Math.min(agingCustomers.length, 20)})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100">
                <th className="pb-2 font-medium">Customer</th>
                <th className="pb-2 font-medium text-right">Current</th>
                <th className="pb-2 font-medium text-right">1-30d</th>
                <th className="pb-2 font-medium text-right">31-60d</th>
                <th className="pb-2 font-medium text-right">61-90d</th>
                <th className="pb-2 font-medium text-right">&gt;90d</th>
                <th className="pb-2 font-medium text-right">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {agingCustomers.slice(0, 20).map((c) => (
                <tr key={c.name} className="hover:bg-gray-50">
                  <td className="py-1.5 font-medium text-gray-800">{c.name}</td>
                  <td className="py-1.5 text-right text-green-700">{c.current > 0 ? formatCurrency(c.current) : "—"}</td>
                  <td className="py-1.5 text-right text-blue-600">{c["1_30"] > 0 ? formatCurrency(c["1_30"]) : "—"}</td>
                  <td className="py-1.5 text-right text-yellow-600">{c["31_60"] > 0 ? formatCurrency(c["31_60"]) : "—"}</td>
                  <td className="py-1.5 text-right text-orange-600">{c["61_90"] > 0 ? formatCurrency(c["61_90"]) : "—"}</td>
                  <td className="py-1.5 text-right text-red-600">{c["over_90"] > 0 ? formatCurrency(c["over_90"]) : "—"}</td>
                  <td className="py-1.5 text-right font-bold text-gray-900">{formatCurrency(c.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
