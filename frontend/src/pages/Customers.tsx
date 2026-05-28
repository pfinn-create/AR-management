import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { Customer, Invoice } from "../types";
import { formatCurrency, formatDate, statusColor } from "../utils/formatters";
import { Upload, X, Mail, Phone, RefreshCw } from "lucide-react";
import toast from "react-hot-toast";

function CustomerDetail({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { activeCompany } = useCompany();
  const { data: invoices = [] } = useQuery<Invoice[]>({
    queryKey: ["invoices-customer", customer.id],
    queryFn: () => api.get(`/invoices?company_id=${activeCompany?.id}&customer_id=${customer.id}`).then(r => r.data),
  });

  const open = invoices.filter(i => i.status === "open" || i.status === "partial");
  const overdue = invoices.filter(i => i.status === "overdue");
  const paid = invoices.filter(i => i.status === "paid");
  const totalOpen = open.reduce((s, i) => s + Number(i.balance), 0);
  const totalOverdue = overdue.reduce((s, i) => s + Number(i.balance), 0);
  const totalPaid = paid.reduce((s, i) => s + Number(i.amount), 0);

  const agingBuckets = [
    { label: "Current", amount: invoices.filter(i => (i.days_overdue ?? 0) <= 0 && i.status !== "paid").reduce((s, i) => s + Number(i.balance), 0) },
    { label: "1–30d", amount: overdue.filter(i => (i.days_overdue ?? 0) <= 30).reduce((s, i) => s + Number(i.balance), 0) },
    { label: "31–60d", amount: overdue.filter(i => (i.days_overdue ?? 0) > 30 && (i.days_overdue ?? 0) <= 60).reduce((s, i) => s + Number(i.balance), 0) },
    { label: "61–90d", amount: overdue.filter(i => (i.days_overdue ?? 0) > 60 && (i.days_overdue ?? 0) <= 90).reduce((s, i) => s + Number(i.balance), 0) },
    { label: ">90d", amount: overdue.filter(i => (i.days_overdue ?? 0) > 90).reduce((s, i) => s + Number(i.balance), 0) },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-100">
          <div>
            <h2 className="font-bold text-gray-900 text-lg">{customer.name}</h2>
            <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
              {customer.email && <a href={`mailto:${customer.email}`} className="flex items-center gap-1 text-blue-500 hover:underline"><Mail className="w-3 h-3" />{customer.email}</a>}
              {customer.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{customer.phone}</span>}
              {customer.contact_name && <span>{customer.contact_name}</span>}
              <span>Net {customer.payment_terms_days}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-5 space-y-5 overflow-y-auto">

          {/* Summary stat cards */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-blue-50 rounded-xl p-3">
              <p className="text-xs text-blue-500 font-medium">Open Balance</p>
              <p className="text-lg font-bold text-blue-700">{formatCurrency(totalOpen)}</p>
              <p className="text-xs text-blue-400">{open.length} invoices</p>
            </div>
            <div className={`rounded-xl p-3 ${totalOverdue > 0 ? "bg-red-50" : "bg-gray-50"}`}>
              <p className={`text-xs font-medium ${totalOverdue > 0 ? "text-red-500" : "text-gray-400"}`}>Overdue</p>
              <p className={`text-lg font-bold ${totalOverdue > 0 ? "text-red-700" : "text-gray-400"}`}>{formatCurrency(totalOverdue)}</p>
              <p className={`text-xs ${totalOverdue > 0 ? "text-red-400" : "text-gray-300"}`}>{overdue.length} invoices</p>
            </div>
            <div className="bg-green-50 rounded-xl p-3">
              <p className="text-xs text-green-500 font-medium">Collected (all time)</p>
              <p className="text-lg font-bold text-green-700">{formatCurrency(totalPaid)}</p>
              <p className="text-xs text-green-400">{paid.length} paid invoices</p>
            </div>
          </div>

          {/* Aging breakdown */}
          {totalOverdue > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Aging Breakdown</h3>
              <div className="flex gap-2">
                {agingBuckets.map(b => (
                  <div key={b.label} className={`flex-1 rounded-lg p-2.5 text-center ${b.amount > 0 ? "bg-orange-50 border border-orange-100" : "bg-gray-50"}`}>
                    <p className="text-xs text-gray-400">{b.label}</p>
                    <p className={`text-sm font-bold ${b.amount > 0 ? "text-orange-700" : "text-gray-300"}`}>{formatCurrency(b.amount)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Invoice list */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              All Invoices ({invoices.length})
            </h3>
            {invoices.length === 0 ? (
              <p className="text-gray-400 text-sm text-center py-4">No invoices</p>
            ) : (
              <div className="rounded-xl border border-gray-100 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr className="text-left text-gray-400">
                      <th className="px-3 py-2 font-medium">Invoice #</th>
                      <th className="px-3 py-2 font-medium">Invoice Date</th>
                      <th className="px-3 py-2 font-medium">Due Date</th>
                      <th className="px-3 py-2 font-medium text-right">Amount</th>
                      <th className="px-3 py-2 font-medium text-right">Balance</th>
                      <th className="px-3 py-2 font-medium">Status</th>
                      <th className="px-3 py-2 font-medium text-right">Days Overdue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {invoices.map(inv => (
                      <tr key={inv.id} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-mono text-blue-600">{inv.invoice_number}</td>
                        <td className="px-3 py-2 text-gray-500">{formatDate(inv.invoice_date)}</td>
                        <td className="px-3 py-2 text-gray-500">{formatDate(inv.due_date)}</td>
                        <td className="px-3 py-2 text-right">{formatCurrency(Number(inv.amount))}</td>
                        <td className="px-3 py-2 text-right font-semibold">{formatCurrency(Number(inv.balance))}</td>
                        <td className="px-3 py-2"><span className={`badge ${statusColor(inv.status)}`}>{inv.status}</span></td>
                        <td className="px-3 py-2 text-right">
                          {inv.days_overdue != null && inv.days_overdue > 0
                            ? <span className="text-red-600 font-semibold">{inv.days_overdue}d</span>
                            : <span className="text-gray-300">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-gray-50 border-t border-gray-200">
                    <tr>
                      <td colSpan={3} className="px-3 py-2 text-xs font-semibold text-gray-600">Total</td>
                      <td className="px-3 py-2 text-right text-xs font-semibold">{formatCurrency(invoices.reduce((s, i) => s + Number(i.amount), 0))}</td>
                      <td className="px-3 py-2 text-right text-xs font-bold text-blue-700">{formatCurrency(invoices.reduce((s, i) => s + Number(i.balance), 0))}</td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Customers() {
  const { activeCompany } = useCompany();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Customer | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  const { data: customers = [], isLoading } = useQuery<Customer[]>({
    queryKey: ["customers", cid],
    queryFn: () => api.get(`/customers?company_id=${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const syncMut = useMutation({
    mutationFn: () => api.post(`/customers/sync/${cid}`),
    onSuccess: (res) => {
      toast.success(`Synced: ${res.data.customers_created} customers created, ${res.data.invoices_linked} invoices linked`);
      qc.invalidateQueries({ queryKey: ["customers", cid] });
    },
    onError: () => toast.error("Sync failed"),
  });

  const importMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post(`/customers/import/${cid}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (res) => {
      toast.success(`Imported: ${res.data.created} new, ${res.data.updated} updated`);
      qc.invalidateQueries({ queryKey: ["customers", cid] });
    },
    onError: () => toast.error("Import failed"),
  });

  const filtered = customers.filter(c =>
    !search ||
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.email || "").toLowerCase().includes(search.toLowerCase()) ||
    (c.customer_code || "").toLowerCase().includes(search.toLowerCase())
  );

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Customers</h1>
          <p className="text-xs text-gray-400">{activeCompany.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="file" ref={fileRef} className="hidden" accept=".csv,.xlsx"
            onChange={(e) => e.target.files?.[0] && importMut.mutate(e.target.files[0])} />
          <button onClick={() => syncMut.mutate()} disabled={syncMut.isPending} className="btn-secondary">
            <RefreshCw className="w-4 h-4" />
            {syncMut.isPending ? "Syncing…" : "Sync from Invoices"}
          </button>
          <button onClick={() => fileRef.current?.click()} disabled={importMut.isPending} className="btn-secondary">
            <Upload className="w-4 h-4" />
            {importMut.isPending ? "Importing…" : "Import CSV"}
          </button>
        </div>
      </div>

      <input
        type="text"
        placeholder="Search by name, email, or code…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-full max-w-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />

      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-xs text-gray-400">
                <th className="px-4 py-3 font-medium">Customer</th>
                <th className="px-4 py-3 font-medium">Contact</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Terms</th>
                <th className="px-4 py-3 font-medium text-right">Open Balance</th>
                <th className="px-4 py-3 font-medium text-right">Overdue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-400">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={6} className="text-center py-10 text-gray-400">No customers found</td></tr>
              ) : filtered.map((c) => (
                <tr key={c.id} className="table-row-hover" onClick={() => setSelected(c)}>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-gray-800">{c.name}</div>
                    {c.customer_code && <div className="text-xs text-gray-400">{c.customer_code}</div>}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">{c.contact_name || "—"}</td>
                  <td className="px-4 py-2.5 text-blue-600">{c.email || "—"}</td>
                  <td className="px-4 py-2.5 text-gray-500">Net {c.payment_terms_days}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">{formatCurrency(c.open_balance || 0)}</td>
                  <td className="px-4 py-2.5 text-right">
                    {(c.overdue_balance || 0) > 0
                      ? <span className="text-red-600 font-semibold">{formatCurrency(c.overdue_balance || 0)}</span>
                      : <span className="text-gray-300">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <CustomerDetail customer={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
