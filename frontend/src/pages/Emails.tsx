import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { EmailThread, EmailMessage, ThreadStatus } from "../types";
import { formatDateTime, statusColor } from "../utils/formatters";
import { Wand2, RefreshCw, X, Send, ChevronRight } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

const STATUS_OPTS: { label: string; value: ThreadStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Unread", value: "unread" },
  { label: "Needs Response", value: "needs_response" },
  { label: "Draft Ready", value: "draft_ready" },
  { label: "Responded", value: "responded" },
  { label: "Closed", value: "closed" },
];

function ThreadDetail({ thread, onClose }: { thread: EmailThread; onClose: () => void }) {
  const [instructions, setInstructions] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftSubject, setDraftSubject] = useState("");
  const qc = useQueryClient();

  const draftMut = useMutation({
    mutationFn: () => api.post("/emails/draft", { thread_id: thread.id, instructions: instructions || undefined }),
    onSuccess: (res) => {
      setDraftBody(res.data.draft_body);
      setDraftSubject(res.data.subject);
      toast.success("Draft created — review before sending");
      qc.invalidateQueries({ queryKey: ["emails"] });
      qc.invalidateQueries({ queryKey: ["todos"] });
    },
    onError: () => toast.error("Draft generation failed"),
  });

  const statusMut = useMutation({
    mutationFn: (status: ThreadStatus) =>
      api.patch(`/emails/${thread.id}/status?status=${status}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["emails"] });
      onClose();
    },
  });

  const nonDraftMessages = thread.messages.filter(m => !m.is_draft);
  const drafts = thread.messages.filter(m => m.is_draft);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <div className="min-w-0 flex-1">
            <h2 className="font-bold text-gray-900 truncate">{thread.subject || "(No subject)"}</h2>
            <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
              <span className={`badge ${statusColor(thread.status)}`}>{thread.status.replace("_", " ")}</span>
              <span>{thread.mailbox}</span>
              {thread.source && <span className="capitalize">{thread.source}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-3">
            <button
              onClick={() => statusMut.mutate("closed")}
              className="btn-secondary text-xs py-1.5"
            >
              Mark Closed
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-1"><X className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Messages */}
          <div className="space-y-3">
            {nonDraftMessages.map(msg => (
              <div
                key={msg.id}
                className={clsx(
                  "rounded-lg p-3 text-sm",
                  msg.is_outbound ? "bg-brand-50 border border-brand-100 ml-8" : "bg-gray-50 border border-gray-100 mr-8"
                )}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-medium text-xs text-gray-600">{msg.sender}</span>
                  <span className="text-xs text-gray-400">{formatDateTime(msg.received_at)}</span>
                </div>
                <p className="text-gray-700 whitespace-pre-wrap">{msg.body_text}</p>
              </div>
            ))}
          </div>

          {/* Existing drafts */}
          {drafts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-yellow-600 mb-2">Draft Response (in Drafts folder)</p>
              {drafts.map(msg => (
                <div key={msg.id} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
                  <p className="text-gray-700 whitespace-pre-wrap">{msg.body_text}</p>
                </div>
              ))}
            </div>
          )}

          {/* AI Draft Generator */}
          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">Generate AI Draft Reply</h3>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Optional: add specific instructions (e.g. 'focus on invoice INV-1234, offer 5-day extension')"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
              rows={2}
            />
            <button
              onClick={() => draftMut.mutate()}
              disabled={draftMut.isPending}
              className="btn-primary mt-2"
            >
              <Wand2 className="w-4 h-4" />
              {draftMut.isPending ? "Generating…" : "Generate Draft"}
            </button>

            {draftBody && (
              <div className="mt-4 border border-yellow-200 rounded-lg bg-yellow-50 p-4">
                <p className="text-xs font-medium text-yellow-700 mb-1">Draft created — review & send from your email client</p>
                <p className="text-xs text-gray-500 mb-1"><strong>Subject:</strong> {draftSubject}</p>
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{draftBody}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Emails() {
  const { activeCompany } = useCompany();
  const [statusFilter, setStatusFilter] = useState<ThreadStatus | "">("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<EmailThread | null>(null);
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  const { data: threads = [], isLoading } = useQuery<EmailThread[]>({
    queryKey: ["emails", cid, statusFilter],
    queryFn: () => api.get(`/emails?company_id=${cid}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  const syncMut = useMutation({
    mutationFn: () => api.post(`/emails/sync/${cid}`),
    onSuccess: (res) => {
      toast.success("Email sync triggered");
      qc.invalidateQueries({ queryKey: ["emails", cid] });
    },
  });

  const filtered = threads.filter(t =>
    !search ||
    (t.subject || "").toLowerCase().includes(search.toLowerCase()) ||
    (t.snippet || "").toLowerCase().includes(search.toLowerCase())
  );

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Emails</h1>
          <p className="text-xs text-gray-400">{activeCompany.name}</p>
        </div>
        <button onClick={() => syncMut.mutate()} disabled={syncMut.isPending} className="btn-secondary">
          <RefreshCw className={clsx("w-4 h-4", syncMut.isPending && "animate-spin")} />
          Sync Emails
        </button>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search subject or snippet…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <div className="flex gap-1 flex-wrap">
          {STATUS_OPTS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value as ThreadStatus | "")}
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

      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <p className="text-center py-10 text-gray-400">Loading…</p>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p>No email threads found</p>
            <p className="text-xs mt-1">Connect Gmail or Outlook and sync to pull in threads</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {filtered.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t)}
                className="w-full flex items-center gap-4 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800 truncate">
                      {t.subject || "(No subject)"}
                    </span>
                    <span className={`badge shrink-0 ${statusColor(t.status)}`}>
                      {t.status.replace("_", " ")}
                    </span>
                    {t.source && <span className="text-xs text-gray-400 capitalize shrink-0">{t.source}</span>}
                  </div>
                  {t.snippet && (
                    <p className="text-xs text-gray-400 truncate mt-0.5">{t.snippet}</p>
                  )}
                </div>
                <div className="text-xs text-gray-400 shrink-0">
                  {formatDateTime(t.last_message_at)}
                </div>
                <ChevronRight className="w-4 h-4 text-gray-300 shrink-0" />
              </button>
            ))}
          </div>
        )}
      </div>

      {selected && <ThreadDetail thread={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
