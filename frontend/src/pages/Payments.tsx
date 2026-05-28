import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { Payment, RemittanceLine } from "../types";
import { formatCurrency, formatDate, statusColor, confidenceIcon } from "../utils/formatters";
import { Upload, Zap, CheckCircle, X, CalendarRange } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";
import DataFreshness from "../components/DataFreshness";

function PaymentDetail({ payment, onClose }: { payment: Payment; onClose: () => void }) {
  const qc = useQueryClient();

  const matchMut = useMutation({
    mutationFn: () => api.post(`/payments/${payment.id}/match`),
    onSuccess: () => {
      toast.success("AI matching complete");
      qc.invalidateQueries({ queryKey: ["payments"] });
      qc.invalidateQueries({ queryKey: ["todos"] });
      onClose();
    },
    onError: () => toast.error("Matching failed"),
  });

  const approveMut = useMutation({
    mutationFn: (lineIds: number[]) =>
      api.post(`/payments/${payment.id}/approve`, { remittance_line_ids: lineIds, approved: true }),
    onSuccess: () => {
      toast.success("Payment lines approved");
      qc.invalidateQueries({ queryKey: ["payments"] });
      onClose();
    },
  });

  const approvedIds = payment.remittance_lines.filter(l => !l.is_approved).map(l => l.id);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div>
            <h2 className="font-bold text-gray-900">Payment — {formatCurrency(Number(payment.amount))}</h2>
            <p className="text-xs text-gray-400">{payment.payer_name} · {formatDate(payment.payment_date)}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><p className="text-xs text-gray-400">Reference #</p><p className="font-mono">{payment.reference_number || "—"}</p></div>
            <div><p className="text-xs text-gray-400">Status</p><span className={`badge ${statusColor(payment.status)}`}>{payment.status}</span></div>
            <div><p className="text-xs text-gray-400">Source</p><p className="capitalize">{payment.source?.replace("_", " ") || "—"}</p></div>
            <div><p className="text-xs text-gray-400">Amount Applied</p><p>{formatCurrency(Number(payment.amount_applied))}</p></div>
            {payment.memo && <div className="col-span-2"><p className="text-xs text-gray-400">Memo</p><p>{payment.memo}</p></div>}
          </div>

          {payment.ai_notes && (
            <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-800">
              <p className="font-medium text-xs mb-1">AI Notes</p>
              {payment.ai_notes}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-800 text-sm">Remittance Lines</h3>
              <div className="flex gap-2">
                {payment.remittance_lines.length === 0 && (
                  <button
                    onClick={() => matchMut.mutate()}
                    disabled={matchMut.isPending}
                    className="btn-primary text-xs py-1.5"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    {matchMut.isPending ? "Matching…" : "Run AI Match"}
                  </button>
                )}
                {approvedIds.length > 0 && (
                  <button
                    onClick={() => approveMut.mutate(approvedIds)}
                    disabled={approveMut.isPending}
                    className="btn-secondary text-xs py-1.5"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Approve All
                  </button>
                )}
              </div>
            </div>

            {payment.remittance_lines.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No lines yet — run AI Match to auto-match invoices</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-100">
                    <th className="pb-1.5">Invoice #</th>
                    <th className="pb-1.5 text-right">Amount</th>
                    <th className="pb-1.5">Confidence</th>
                    <th className="pb-1.5">Notes</th>
                    <th className="pb-1.5">Approved</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {payment.remittance_lines.map(line => (
                    <tr key={line.id}>
                      <td className="py-1.5 font-mono text-blue-600">{line.invoice_number_raw || "Unmatched"}</td>
                      <td className="py-1.5 text-right">{formatCurrency(Number(line.amount))}</td>
                      <td className="py-1.5">
                        <span className={`badge ${statusColor(line.match_confidence)}`}>
                          {confidenceIcon(line.match_confidence)} {line.match_confidence}
                        </span>
                      </td>
                      <td className="py-1.5 text-gray-500 max-w-xs truncate">{line.notes || "—"}</td>
                      <td className="py-1.5">
                        {line.is_approved
                          ? <span className="text-green-600">✓ Yes</span>
                          : <span className="text-gray-400">Pending</span>}
                      </td>
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

export default function Payments() {
  const { activeCompany } = useCompany();
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<Payment | null>(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const csvRef = useRef<HTMLInputElement>(null);
  const pdfRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  const dateParams = [fromDate ? `from_date=${fromDate}` : "", toDate ? `to_date=${toDate}` : ""]
    .filter(Boolean).join("&");

  const { data: payments = [], isLoading } = useQuery<Payment[]>({
    queryKey: ["payments", cid, statusFilter],
    queryFn: () => api.get(`/payments?company_id=${cid}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  const importCsvMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const url = `/payments/import/chase/${cid}${dateParams ? `?${dateParams}` : ""}`;
      return api.post(url, fd, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (res) => {
      toast.success(`Chase CSV import: ${res.data.created} added, ${res.data.skipped} skipped`);
      qc.invalidateQueries({ queryKey: ["payments", cid] });
      qc.invalidateQueries({ queryKey: ["freshness", cid] });
    },
    onError: () => toast.error("CSV import failed"),
  });

  const importPdfMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const url = `/payments/import/chase-pdf/${cid}${dateParams ? `?${dateParams}` : ""}`;
      return api.post(url, fd, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (res) => {
      toast.success(`Chase PDF import: ${res.data.created} added, ${res.data.skipped} skipped`);
      qc.invalidateQueries({ queryKey: ["payments", cid] });
      qc.invalidateQueries({ queryKey: ["freshness", cid] });
    },
    onError: () => toast.error("PDF import failed"),
  });

  const STATUS_OPTS = [
    { label: "All", value: "" },
    { label: "Pending Review", value: "pending_review" },
    { label: "Matched", value: "matched" },
    { label: "Unmatched", value: "unmatched" },
    { label: "Applied", value: "applied" },
  ];

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Payment Application</h1>
          <div className="flex items-center gap-3 mt-0.5">
            <p className="text-xs text-gray-400">{activeCompany.name}</p>
            <DataFreshness show={["payments_last_imported"]} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Date range filter */}
          <div className="flex items-center gap-1.5 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
            <CalendarRange className="w-3.5 h-3.5 text-gray-400 shrink-0" />
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="text-xs bg-transparent border-none outline-none text-gray-600 w-32"
              title="From date"
            />
            <span className="text-gray-300 text-xs">–</span>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="text-xs bg-transparent border-none outline-none text-gray-600 w-32"
              title="To date"
            />
            {(fromDate || toDate) && (
              <button
                onClick={() => { setFromDate(""); setToDate(""); }}
                className="text-gray-400 hover:text-gray-600 ml-1"
                title="Clear dates"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          <input type="file" ref={csvRef} className="hidden" accept=".csv,.xlsx"
            onChange={(e) => e.target.files?.[0] && importCsvMut.mutate(e.target.files[0])} />
          <input type="file" ref={pdfRef} className="hidden" accept=".pdf"
            onChange={(e) => e.target.files?.[0] && importPdfMut.mutate(e.target.files[0])} />
          <button onClick={() => csvRef.current?.click()} disabled={importCsvMut.isPending} className="btn-secondary">
            <Upload className="w-4 h-4" />
            {importCsvMut.isPending ? "Importing…" : "Upload CSV"}
          </button>
          <button onClick={() => pdfRef.current?.click()} disabled={importPdfMut.isPending} className="btn-secondary">
            <Upload className="w-4 h-4" />
            {importPdfMut.isPending ? "Importing…" : "Upload PDF"}
          </button>
        </div>
      </div>

      <div className="flex gap-1">
        {STATUS_OPTS.map(opt => (
          <button
            key={opt.value}
            onClick={() => setStatusFilter(opt.value)}
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

      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-xs text-gray-400">
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Payer</th>
                <th className="px-4 py-3 font-medium">Reference</th>
                <th className="px-4 py-3 font-medium text-right">Amount</th>
                <th className="px-4 py-3 font-medium text-right">Applied</th>
                <th className="px-4 py-3 font-medium">Source</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Lines</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {isLoading ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">Loading…</td></tr>
              ) : payments.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-10 text-gray-400">No payments found</td></tr>
              ) : payments.map((p) => (
                <tr key={p.id} className="table-row-hover" onClick={() => setSelected(p)}>
                  <td className="px-4 py-2.5 text-gray-500">{formatDate(p.payment_date)}</td>
                  <td className="px-4 py-2.5 font-medium text-gray-800">{p.payer_name || "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-gray-500">{p.reference_number || "—"}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">{formatCurrency(Number(p.amount))}</td>
                  <td className="px-4 py-2.5 text-right text-gray-500">{formatCurrency(Number(p.amount_applied))}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-400 capitalize">{p.source?.replace("_", " ") || "—"}</td>
                  <td className="px-4 py-2.5"><span className={`badge ${statusColor(p.status)}`}>{p.status}</span></td>
                  <td className="px-4 py-2.5 text-center text-gray-500">{p.remittance_lines.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && <PaymentDetail payment={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
