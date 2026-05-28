import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { Invoice, InvoiceStatus } from "../types";
import { formatCurrency, formatDate, statusColor } from "../utils/formatters";
import { Upload, ChevronDown, ChevronUp, X } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

const STATUS_OPTIONS: { label: string; value: InvoiceStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Open", value: "open" },
  { label: "Partial", value: "partial" },
  { label: "Overdue", value: "overdue" },
  { label: "Paid", value: "paid" },
  { label: "Disputed", value: "disputed" },
];

function InvoiceDetail({ invoice, onClose }: { invoice: Invoice; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="font-bold text-gray-900">Invoice {invoice.invoice_number}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div><p className="text-xs text-gray-400">Customer</p><p className="font-medium">{invoice.customer_name || "—"}</p></div>
            <div><p className="text-xs text-gray-400">Status</p><span className={`badge ${statusColor(invoice.status)}`}>{invoice.status}</span></div>
            <div><p className="text-xs text-gray-400">Invoice Date</p><p>{formatDate(invoice.invoice_date)}</p></div>
            <div><p className="text-xs text-gray-400">Due Date</p><p>{formatDate(invoice.due_date)}</p></div>
            <div><p className="text-xs text-gray-400">Total Amount</p><p className="font-semibold">{formatCurrency(Number(invoice.amount))}</p></div>
            <div><p className="text-xs text-gray-400">Amount Paid</p><p>{formatCurrency(Number(invoice.amount_paid))}</p></div>
            <div><p className="text-xs text-gray-400">Balance Due</p><p className="font-bold text-red-600">{formatCurrency(Number(invoice.balance))}</p></div>
            <div><p className="text-xs text-gray-400">Payment Terms</p><p>Net {invoice.payment_terms_days}</p></div>
            {invoice.po_number && <div><p className="text-xs text-gray-400">PO Number</p><p>{invoice.po_number}</p></div>}
            {invoice.netsuite_id && <div><p className="text-xs text-gray-400">NetSuite ID</p><p className="font-mono text-xs">{invoice.netsuite_id}</p></div>}
          </div>
          {invoice.days_overdue != null && invoice.days_overdue > 0 && (
            <div className="bg-red-50 rounded-lg p-3 text-red-700 text-xs">
              This invoice is <strong>{invoice.days_overdue} days overdue</strong>
            </div>
          )}
          {invoice.notes && (
            <div><p className="text-xs text-gray-400 mb-1">Notes</p><p className="text-gray-600">{invoice.notes}</p></div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Invoices() {
  const { activeCompany } = useCompany();
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [sortKey, setSortKey] = useState<keyof Invoice>("due_date");
  const [sortAsc, setSortAsc] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  const { data: invoices = [], isLoading } = useQuery<Invoice[]>({
    queryKey: ["invoices", cid, statusFilter],
    queryFn: () => api.get(`/invoices?company_id=${cid}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  const importMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.post(`/invoices/import/${cid}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (res) => {
      const { created, updated, skipped, errors, columns_found } = res.data;
      if (skipped > 0 && created === 0 && updated === 0) {
        toast.error(`All ${skipped} rows skipped. Columns found: ${columns_found.join(", ")}`);
      } else {
        toast.success(`Imported: ${created} new, ${updated} updated, ${skipped} skipped`);
      }
      if (errors.length > 0) toast.error(`${errors.length} row errors`);
      qc.invalidateQueries({ queryKey: ["invoices", cid] });
      qc.invalidateQueries({ queryKey: ["companies"] });
      qc.invalidateQueries({ queryKey: ["todos", cid] });
    },
    onError: () => toast.error("Import failed"),
  });

  const handleSort = (key: keyof Invoice) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const filtered = invoices
    .filter(i =>
      !search ||
      i.invoice_number.toLowerCase().includes(search.toLowerCase()) ||
      (i.customer_name || "").toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      const av = a[sortKey] ?? "";
      const bv = b[sortKey] ?? "";
      return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });

  const SortIcon = ({ k }: { k: keyof Invoice }) =>
    sortKey === k ? (sortAsc ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />) : null;

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Invoices</h1>
          <p className="text-xs text-gray-400">{activeCompany.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="file"
            ref={fileRef}
            className="hidden"
            accept=".csv,.xlsx"
            onChange={(e) => e.target.files?.[0] && importMut.mutate(e.target.files[0])}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={importMut.isPending}
            className="btn-secondary"
          >
            <Upload className="w-4 h-4" />
            {importMut.isPending ? "Importing…" : "Import NetSuite CSV"}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search invoice # or customer…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm flex-1 max-w-xs focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <div className="flex gap-1">
          {STATUS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value as InvoiceStatus | "")}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                statusFilter === opt.value
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary strip */}
      <div className="flex gap-4 text-xs text-gray-500">
        <span>{filtered.length} invoices</span>
        <span>Total AR: <strong className="text-gray-800">{formatCurrency(filtered.reduce((s, i) => s + Number(i.balance), 0))}</strong></span>
        <span>Overdue: <strong className="text-red-600">{formatCurrency(filtered.filter(i => i.status === "overdue").reduce((s, i) => s + Number(i.balance), 0))}</strong></span>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-xs text-gray-400">
                {[
                  { label: "Invoice #", key: "invoice_number" },
                  { label: "Customer", key: "customer_name" },
                  { label: "Invoice Date", key: "invoice_date" },
                  { label: "Due Date", key: "due_date" },
                  { label: "Amount", key: "amount" },
                  { label: "Balance", key: "balance" },
                  { label: "Status", key: "status" },
                  { label: "Overdue", key: "days_overdue" },
                ].map(col => (
                  <th
                    key={col.key}
                    className="px-4 py-3 font-medium cursor-pointer select-none hover:text-gray-600"
                    onClick={() => handleSort(col.key as keyof Invoice)}
                  >
                    <span className="flex items-center gap-1">
                      {col.label}
                      <SortIcon k={col.key as keyof Invoice} />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">No invoices found</td></tr>
              ) : filtered.map((inv) => (
                <tr
                  key={inv.id}
                  className="table-row-hover"
                  onClick={() => setSelected(inv)}
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-blue-600">{inv.invoice_number}</td>
                  <td className="px-4 py-2.5 text-gray-700">{inv.customer_name || "—"}</td>
                  <td className="px-4 py-2.5 text-gray-500">{formatDate(inv.invoice_date)}</td>
                  <td className="px-4 py-2.5 text-gray-500">{formatDate(inv.due_date)}</td>
                  <td className="px-4 py-2.5 text-right">{formatCurrency(Number(inv.amount))}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">{formatCurrency(Number(inv.balance))}</td>
                  <td className="px-4 py-2.5">
                    <span className={`badge ${statusColor(inv.status)}`}>{inv.status}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {inv.days_overdue != null && inv.days_overdue > 0 && (
                      <span className="badge bg-red-100 text-red-700">{inv.days_overdue}d</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <InvoiceDetail invoice={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
