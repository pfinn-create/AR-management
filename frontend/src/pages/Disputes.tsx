import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { Dispute, DisputeStatus, DisputeReason, EscalationFlag, EscalationStatus } from "../types";
import { formatDate, statusColor } from "../utils/formatters";
import { AlertTriangle, TrendingUp, Plus, X, ChevronDown, ChevronUp } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

// ─── Labels ─────────────────────────────────────────────────────────────────

const REASON_LABELS: Record<DisputeReason, string> = {
  incorrect_amount: "Incorrect Amount",
  duplicate_invoice: "Duplicate Invoice",
  goods_not_received: "Goods Not Received",
  quality_issue: "Quality Issue",
  already_paid: "Already Paid",
  contract_dispute: "Contract Dispute",
  other: "Other",
};

const DISPUTE_STATUS_OPTS: { label: string; value: DisputeStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Open", value: "open" },
  { label: "Under Review", value: "under_review" },
  { label: "Resolved", value: "resolved" },
  { label: "Rejected", value: "rejected" },
];

const ESC_STATUS_OPTS: { label: string; value: EscalationStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Flagged", value: "flagged" },
  { label: "Under Review", value: "under_review" },
  { label: "Escalated", value: "escalated_to_manager" },
  { label: "Resolved", value: "resolved" },
];

// ─── Raise Dispute Modal ─────────────────────────────────────────────────

function RaiseDisputeModal({ companyId, onClose }: { companyId: number; onClose: () => void }) {
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [reason, setReason] = useState<DisputeReason>("other");
  const [description, setDescription] = useState("");
  const [invoiceId, setInvoiceId] = useState<number | null>(null);
  const qc = useQueryClient();

  // Search invoices by number
  const { data: invoices = [] } = useQuery({
    queryKey: ["invoices", companyId],
    queryFn: () => api.get(`/invoices?company_id=${companyId}`).then(r => r.data),
  });

  const filtered = invoices.filter((inv: any) =>
    invoiceNumber ? inv.invoice_number.toLowerCase().includes(invoiceNumber.toLowerCase()) : true
  ).slice(0, 5);

  const createMut = useMutation({
    mutationFn: () => api.post(`/disputes?company_id=${companyId}`, { invoice_id: invoiceId, reason, description }),
    onSuccess: () => {
      toast.success("Dispute raised");
      qc.invalidateQueries({ queryKey: ["disputes", companyId] });
      qc.invalidateQueries({ queryKey: ["todos", companyId] });
      onClose();
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || "Failed"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="font-bold text-gray-900">Raise Dispute</h2>
          <button onClick={onClose}><X className="w-5 h-5 text-gray-400" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Invoice Number</label>
            <input
              value={invoiceNumber}
              onChange={e => setInvoiceNumber(e.target.value)}
              placeholder="Search invoice…"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            {invoiceNumber && (
              <div className="mt-1 border border-gray-200 rounded-lg overflow-hidden">
                {filtered.map((inv: any) => (
                  <button
                    key={inv.id}
                    onClick={() => { setInvoiceId(inv.id); setInvoiceNumber(inv.invoice_number); }}
                    className={clsx(
                      "w-full flex items-center justify-between px-3 py-2 text-sm text-left hover:bg-gray-50",
                      invoiceId === inv.id && "bg-brand-50"
                    )}
                  >
                    <span className="font-mono text-blue-600">{inv.invoice_number}</span>
                    <span className="text-gray-500 text-xs">{inv.customer_name}</span>
                  </button>
                ))}
                {filtered.length === 0 && <p className="px-3 py-2 text-xs text-gray-400">No matches</p>}
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Reason</label>
            <select
              value={reason}
              onChange={e => setReason(e.target.value as DisputeReason)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {Object.entries(REASON_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="Describe the dispute…"
            />
          </div>

          <button
            onClick={() => createMut.mutate()}
            disabled={!invoiceId || createMut.isPending}
            className="w-full btn-primary justify-center py-2.5"
          >
            {createMut.isPending ? "Raising…" : "Raise Dispute"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Dispute row detail ──────────────────────────────────────────────────

function DisputeRow({ dispute }: { dispute: Dispute }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const updateMut = useMutation({
    mutationFn: (update: { status?: DisputeStatus; resolution_notes?: string }) =>
      api.patch(`/disputes/${dispute.id}`, update),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disputes"] }),
    onError: () => toast.error("Update failed"),
  });

  const [notes, setNotes] = useState(dispute.resolution_notes || "");

  return (
    <>
      <tr
        className="table-row-hover cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        <td className="px-4 py-3 font-mono text-xs text-blue-600">{dispute.invoice_number || "—"}</td>
        <td className="px-4 py-3 text-gray-700">{dispute.customer_name || "—"}</td>
        <td className="px-4 py-3 text-gray-600 text-xs">{REASON_LABELS[dispute.reason]}</td>
        <td className="px-4 py-3">
          <span className={`badge ${statusColor(dispute.status)}`}>
            {dispute.status.replace("_", " ")}
          </span>
        </td>
        <td className="px-4 py-3 text-gray-400 text-xs">{formatDate(dispute.created_at)}</td>
        <td className="px-4 py-3 text-gray-300">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} className="bg-gray-50 px-6 py-4">
            <div className="space-y-3 max-w-2xl">
              {dispute.description && (
                <p className="text-sm text-gray-700">{dispute.description}</p>
              )}
              <div className="flex gap-2 flex-wrap">
                {(["open", "under_review", "resolved", "rejected"] as DisputeStatus[]).map(s => (
                  <button
                    key={s}
                    onClick={() => updateMut.mutate({ status: s })}
                    disabled={dispute.status === s}
                    className={clsx(
                      "px-3 py-1 rounded-lg text-xs font-medium border transition-colors",
                      dispute.status === s
                        ? "bg-brand-600 text-white border-brand-600"
                        : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                    )}
                  >
                    {s.replace("_", " ")}
                  </button>
                ))}
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Resolution Notes</label>
                <div className="flex gap-2">
                  <input
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="Add resolution notes…"
                  />
                  <button
                    onClick={() => updateMut.mutate({ resolution_notes: notes })}
                    className="btn-secondary text-xs py-1.5"
                  >
                    Save
                  </button>
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Escalations tab ─────────────────────────────────────────────────────

function EscalationsTab({ companyId }: { companyId: number }) {
  const [statusFilter, setStatusFilter] = useState<EscalationStatus | "">("");
  const qc = useQueryClient();

  const { data: flags = [], isLoading } = useQuery<EscalationFlag[]>({
    queryKey: ["escalations", companyId, statusFilter],
    queryFn: () =>
      api.get(`/escalations?company_id=${companyId}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, update }: { id: number; update: any }) =>
      api.patch(`/escalations/${id}`, update),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["escalations", companyId] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex gap-1 flex-wrap">
        {ESC_STATUS_OPTS.map(opt => (
          <button
            key={opt.value}
            onClick={() => setStatusFilter(opt.value as EscalationStatus | "")}
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
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr className="text-left text-xs text-gray-400">
              <th className="px-4 py-3 font-medium">Customer</th>
              <th className="px-4 py-3 font-medium">Trigger</th>
              <th className="px-4 py-3 font-medium text-right">Overdue $</th>
              <th className="px-4 py-3 font-medium text-right">Days</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Flagged</th>
              <th className="px-4 py-3 font-medium">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400">Loading…</td></tr>
            ) : flags.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-10 text-gray-400">No escalations</td></tr>
            ) : flags.map(flag => (
              <tr key={flag.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-800">{flag.customer_name || `#${flag.customer_id}`}</td>
                <td className="px-4 py-3 text-xs text-gray-500 capitalize">{flag.trigger_reason?.replace("_", " ")}</td>
                <td className="px-4 py-3 text-right font-semibold text-red-600">
                  ${(flag.amount_overdue || 0).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="badge bg-red-100 text-red-700">{flag.days_overdue}d</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`badge ${statusColor(flag.status)}`}>{flag.status.replace("_", " ")}</span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">{formatDate(flag.created_at)}</td>
                <td className="px-4 py-3">
                  <select
                    value={flag.status}
                    onChange={e => updateMut.mutate({ id: flag.id, update: { status: e.target.value } })}
                    className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none"
                  >
                    <option value="flagged">Flagged</option>
                    <option value="under_review">Under Review</option>
                    <option value="escalated_to_manager">Escalate to Manager</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────

export default function Disputes() {
  const { activeCompany } = useCompany();
  const [tab, setTab] = useState<"disputes" | "escalations">("disputes");
  const [statusFilter, setStatusFilter] = useState<DisputeStatus | "">("");
  const [showRaise, setShowRaise] = useState(false);

  const cid = activeCompany?.id;

  const { data: disputes = [], isLoading } = useQuery<Dispute[]>({
    queryKey: ["disputes", cid, statusFilter],
    queryFn: () =>
      api.get(`/disputes?company_id=${cid}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Disputes & Escalations</h1>
          <p className="text-xs text-gray-400">{activeCompany.name}</p>
        </div>
        {tab === "disputes" && (
          <button onClick={() => setShowRaise(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            Raise Dispute
          </button>
        )}
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 border-b border-gray-200 pb-0">
        {[
          { key: "disputes", label: "Disputes", icon: AlertTriangle },
          { key: "escalations", label: "Escalations", icon: TrendingUp },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key as any)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
              tab === key
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "disputes" && (
        <div className="space-y-3">
          <div className="flex gap-1">
            {DISPUTE_STATUS_OPTS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value as DisputeStatus | "")}
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
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr className="text-left text-xs text-gray-400">
                  <th className="px-4 py-3 font-medium">Invoice #</th>
                  <th className="px-4 py-3 font-medium">Customer</th>
                  <th className="px-4 py-3 font-medium">Reason</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Raised</th>
                  <th className="px-4 py-3 font-medium w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {isLoading ? (
                  <tr><td colSpan={6} className="text-center py-10 text-gray-400">Loading…</td></tr>
                ) : disputes.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-10 text-gray-400">No disputes</td></tr>
                ) : disputes.map(d => <DisputeRow key={d.id} dispute={d} />)}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "escalations" && <EscalationsTab companyId={activeCompany.id} />}

      {showRaise && (
        <RaiseDisputeModal companyId={activeCompany.id} onClose={() => setShowRaise(false)} />
      )}
    </div>
  );
}
