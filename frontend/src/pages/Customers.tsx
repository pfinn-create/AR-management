import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { Customer, Invoice } from "../types";
import { formatCurrency, formatDate, statusColor } from "../utils/formatters";
import { Upload, X, Mail, Phone } from "lucide-react";
import toast from "react-hot-toast";

function CustomerDetail({ customer, onClose }: { customer: Customer; onClose: () => void }) {
  const { activeCompany } = useCompany();
  const { data: invoices = [] } = useQuery<Invoice[]>({
    queryKey: ["invoices-customer", customer.id],
    queryFn: () => api.get(`/invoices?company_id=${activeCompany?.id}&customer_id=${customer.id}`).then(r => r.data),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="font-bold text-gray-900">{customer.name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 text-sm">
            {customer.contact_name && <div><p className="text-xs text-gray-400">Contact</p><p>{customer.contact_name}</p></div>}
            {customer.email && (
              <div><p className="text-xs text-gray-400">Email</p>
                <a href={`mailto:${customer.email}`} className="text-blue-600 flex items-center gap-1">
                  <Mail className="w-3 h-3" />{customer.email}
                </a>
              </div>
            )}
            {customer.phone && (
              <div><p className="text-xs text-gray-400">Phone</p>
                <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{customer.phone}</span>
              </div>
            )}
            <div><p className="text-xs text-gray-400">Payment Terms</p><p>Net {customer.payment_terms_days}</p></div>
            {customer.credit_limit && <div><p className="text-xs text-gray-400">Credit Limit</p><p>{formatCurrency(Number(customer.credit_limit))}</p></div>}
            <div><p className="text-xs text-gray-400">Open Balance</p><p className="font-semibold">{formatCurrency(customer.open_balance || 0)}</p></div>
            {(customer.overdue_balance || 0) > 0 && (
              <div><p className="text-xs text-gray-400">Overdue Balance</p><p className="font-semibold text-red-600">{formatCurrency(customer.overdue_balance || 0)}</p></div>
            )}
          </div>

          <div>
            <h3 className="font-semibold text-gray-800 mb-2 text-sm">Invoice History</h3>
            {invoices.length === 0 ? (
              <p className="text-gray-400 text-sm">No invoices</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-100">
                    <th className="pb-1.5">Invoice #</th>
                    <th className="pb-1.5">Due Date</th>
                    <th className="pb-1.5 text-right">Balance</th>
                    <th className="pb-1.5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {invoices.map(inv => (
                    <tr key={inv.id}>
                      <td className="py-1.5 font-mono text-blue-600">{inv.invoice_number}</td>
                      <td className="py-1.5 text-gray-500">{formatDate(inv.due_date)}</td>
                      <td className="py-1.5 text-right font-semibold">{formatCurrency(Number(inv.balance))}</td>
                      <td className="py-1.5"><span className={`badge ${statusColor(inv.status)}`}>{inv.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
