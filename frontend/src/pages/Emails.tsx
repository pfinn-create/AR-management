import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { EmailThread, ThreadStatus } from "../types";
import { formatDateTime, statusColor } from "../utils/formatters";
import { Wand2, RefreshCw, X, ChevronRight, Mail, Trash2, Plus, ExternalLink } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

// ─── Types ──────────────────────────────────────────────────────────────────

interface ConnectedMailbox {
  id: number;
  mailbox: string;
  connected_at: string | null;
  scopes: string | null;
}

// ─── Status filter options ────────────────────────────────────────────────

const STATUS_OPTS: { label: string; value: ThreadStatus | "" }[] = [
  { label: "All", value: "" },
  { label: "Unread", value: "unread" },
  { label: "Needs Response", value: "needs_response" },
  { label: "Draft Ready", value: "draft_ready" },
  { label: "Responded", value: "responded" },
  { label: "Closed", value: "closed" },
];

// ─── Gmail Connection Panel ───────────────────────────────────────────────

function GmailPanel({ companyId }: { companyId: number }) {
  const qc = useQueryClient();

  const { data: mailboxes = [], isLoading } = useQuery<ConnectedMailbox[]>({
    queryKey: ["gmail-mailboxes", companyId],
    queryFn: () => api.get(`/gmail/mailboxes?company_id=${companyId}`).then(r => r.data),
  });

  const connectMut = useMutation({
    mutationFn: () => api.get(`/gmail/authorize?company_id=${companyId}`),
    onSuccess: (res) => {
      // Open OAuth URL in current tab — Google redirects back to /gmail/callback
      window.location.href = res.data.authorize_url;
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || "Failed to start OAuth — check GMAIL_CLIENT_ID in .env");
    },
  });

  const disconnectMut = useMutation({
    mutationFn: (tokenId: number) =>
      api.delete(`/gmail/mailboxes/${tokenId}?company_id=${companyId}`),
    onSuccess: () => {
      toast.success("Mailbox disconnected");
      qc.invalidateQueries({ queryKey: ["gmail-mailboxes", companyId] });
    },
  });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Mail className="w-4 h-4 text-red-500" />
          <h2 className="font-semibold text-gray-800 text-sm">Connected Gmail Mailboxes</h2>
        </div>
        <button
          onClick={() => connectMut.mutate()}
          disabled={connectMut.isPending}
          className="btn-secondary text-xs py-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          Connect Gmail
        </button>
      </div>

      {isLoading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : mailboxes.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500">No Gmail accounts connected yet.</p>
          <p className="text-xs text-gray-400 mt-1">
            Click <strong>Connect Gmail</strong> to link a Google account to this company.
            Each company can have multiple mailboxes (shared and individual).
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {mailboxes.map((mb) => (
            <div
              key={mb.id}
              className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full text-xs"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              <span className="text-green-800 font-medium">{mb.mailbox}</span>
              <button
                onClick={() => disconnectMut.mutate(mb.id)}
                className="text-green-500 hover:text-red-500 transition-colors ml-1"
                title="Disconnect"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 mt-3">
        Gmail access is read-only + draft creation. Emails are <strong>never sent automatically</strong> — all drafts go to your Gmail Drafts folder for review.
      </p>
    </div>
  );
}

// ─── Thread detail modal ──────────────────────────────────────────────────

function ThreadDetail({ thread, onClose }: { thread: EmailThread; onClose: () => void }) {
  const [instructions, setInstructions] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftSubject, setDraftSubject] = useState("");
  const [gmailDraftId, setGmailDraftId] = useState<string | null>(null);
  const qc = useQueryClient();

  const draftMut = useMutation({
    mutationFn: () => api.post("/emails/draft", {
      thread_id: thread.id,
      instructions: instructions || undefined,
    }),
    onSuccess: (res) => {
      setDraftBody(res.data.draft_body);
      setDraftSubject(res.data.subject);
      setGmailDraftId(res.data.external_draft_id);
      if (res.data.external_draft_id) {
        toast.success("Draft saved to Gmail Drafts folder — review before sending");
      } else {
        toast.success("Draft created — review before sending");
      }
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
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-100">
          <div className="min-w-0 flex-1">
            <h2 className="font-bold text-gray-900 truncate pr-4">{thread.subject || "(No subject)"}</h2>
            <div className="flex items-center gap-2 text-xs text-gray-400 mt-1 flex-wrap">
              <span className={`badge ${statusColor(thread.status)}`}>
                {thread.status.replace("_", " ")}
              </span>
              {thread.source && (
                <span className="capitalize flex items-center gap-1">
                  <Mail className="w-3 h-3" />{thread.source}
                </span>
              )}
              {thread.mailbox && <span>{thread.mailbox}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => statusMut.mutate("responded")}
              className="btn-secondary text-xs py-1.5"
            >
              Mark Responded
            </button>
            <button
              onClick={() => statusMut.mutate("closed")}
              className="btn-secondary text-xs py-1.5"
            >
              Close
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 ml-1">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Conversation */}
          <div className="space-y-3">
            {nonDraftMessages.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-4">No messages loaded yet — sync emails to pull messages</p>
            )}
            {nonDraftMessages.map(msg => (
              <div
                key={msg.id}
                className={clsx(
                  "rounded-xl p-3.5 text-sm",
                  msg.is_outbound
                    ? "bg-brand-50 border border-brand-100 ml-8"
                    : "bg-gray-50 border border-gray-100 mr-8"
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-xs text-gray-600 truncate">{msg.sender}</span>
                  <span className="text-xs text-gray-400 shrink-0 ml-2">
                    {formatDateTime(msg.received_at)}
                  </span>
                </div>
                <p className="text-gray-700 whitespace-pre-wrap text-xs leading-relaxed">{msg.body_text}</p>
              </div>
            ))}
          </div>

          {/* Existing local drafts */}
          {drafts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-yellow-700 mb-2 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-yellow-400" />
                Draft Response
                {drafts[0].draft_external_id && " (saved to Gmail Drafts)"}
              </p>
              {drafts.map(msg => (
                <div key={msg.id} className="bg-yellow-50 border border-yellow-200 rounded-xl p-3.5 text-sm">
                  <p className="text-gray-700 whitespace-pre-wrap text-xs leading-relaxed">{msg.body_text}</p>
                </div>
              ))}
            </div>
          )}

          {/* AI Draft Generator */}
          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-2">Generate AI Draft Reply</h3>
            {thread.source === "gmail" && (
              <p className="text-xs text-green-700 bg-green-50 rounded-lg px-3 py-2 mb-2">
                Gmail connected — draft will be pushed to your Gmail Drafts folder automatically.
              </p>
            )}
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Optional: add specific instructions (e.g. 'request payment by Friday', 'mention invoice INV-1234')"
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
              <div className="mt-4 border border-yellow-200 rounded-xl bg-yellow-50 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-yellow-700">
                    {gmailDraftId
                      ? "Draft saved to Gmail Drafts — open Gmail to review and send"
                      : "Draft created locally — review and send manually"}
                  </p>
                  {gmailDraftId && (
                    <a
                      href="https://mail.google.com/mail/#drafts"
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 flex items-center gap-1 hover:underline"
                    >
                      Open Gmail <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <p className="text-xs text-gray-500"><strong>Subject:</strong> {draftSubject}</p>
                <pre className="text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">{draftBody}</pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Emails page ─────────────────────────────────────────────────────

export default function Emails() {
  const { activeCompany } = useCompany();
  const [statusFilter, setStatusFilter] = useState<ThreadStatus | "">("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<EmailThread | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  // Handle OAuth callback redirect
  useEffect(() => {
    if (searchParams.get("gmail_connected") === "1") {
      const mailbox = searchParams.get("mailbox") || "";
      toast.success(`Gmail connected: ${mailbox}`);
      qc.invalidateQueries({ queryKey: ["gmail-mailboxes"] });
      setSearchParams({});
    }
    if (searchParams.get("gmail_error") === "1") {
      toast.error(`Gmail connection failed: ${searchParams.get("detail") || "unknown error"}`);
      setSearchParams({});
    }
  }, [searchParams]);

  const { data: threads = [], isLoading } = useQuery<EmailThread[]>({
    queryKey: ["emails", cid, statusFilter],
    queryFn: () =>
      api.get(`/emails?company_id=${cid}${statusFilter ? `&status=${statusFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  const syncMut = useMutation({
    mutationFn: () => api.post(`/emails/sync/${cid}`),
    onSuccess: (res) => {
      const g = res.data.gmail;
      if (g?.status === "ok") {
        toast.success(`Synced: ${g.new_threads} new, ${g.updated_threads} updated`);
        if (g.errors?.length > 0) {
          g.errors.forEach((e: string) => toast.error(e, { duration: 6000 }));
        }
      } else if (g?.status === "not_connected") {
        toast.error("No Gmail mailboxes connected — add one below");
      } else {
        toast(g?.reason || "Sync complete");
      }
      qc.invalidateQueries({ queryKey: ["emails", cid] });
      qc.invalidateQueries({ queryKey: ["todos", cid] });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
    onError: () => toast.error("Sync failed"),
  });

  const filtered = threads.filter(t =>
    !search ||
    (t.subject || "").toLowerCase().includes(search.toLowerCase()) ||
    (t.snippet || "").toLowerCase().includes(search.toLowerCase())
  );

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Emails</h1>
          <p className="text-xs text-gray-400">{activeCompany.name}</p>
        </div>
        <button
          onClick={() => syncMut.mutate()}
          disabled={syncMut.isPending}
          className="btn-primary"
        >
          <RefreshCw className={clsx("w-4 h-4", syncMut.isPending && "animate-spin")} />
          {syncMut.isPending ? "Syncing…" : "Sync Now"}
        </button>
      </div>

      {/* Gmail connection panel */}
      <GmailPanel companyId={activeCompany.id} />

      {/* Filters */}
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

      {/* Thread list */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <p className="text-center py-10 text-gray-400">Loading…</p>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-gray-400 space-y-1">
            <Mail className="w-8 h-8 mx-auto text-gray-300" />
            <p className="text-sm">No email threads</p>
            <p className="text-xs">Connect Gmail above and click Sync Now to pull in threads</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {filtered.map((t) => (
              <button
                key={t.id}
                onClick={() => setSelected(t)}
                className="w-full flex items-center gap-4 px-4 py-3.5 text-left hover:bg-gray-50 transition-colors"
              >
                {/* Status dot */}
                <span className={clsx(
                  "w-2 h-2 rounded-full shrink-0",
                  t.status === "unread" || t.status === "needs_response" ? "bg-red-400" :
                  t.status === "draft_ready" ? "bg-yellow-400" :
                  t.status === "responded" ? "bg-green-400" : "bg-gray-300"
                )} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={clsx(
                      "font-medium text-sm truncate",
                      t.status === "unread" ? "text-gray-900" : "text-gray-600"
                    )}>
                      {t.subject || "(No subject)"}
                    </span>
                    <span className={`badge shrink-0 ${statusColor(t.status)}`}>
                      {t.status.replace("_", " ")}
                    </span>
                    {t.source && (
                      <span className="text-xs text-gray-400 capitalize shrink-0 flex items-center gap-0.5">
                        <Mail className="w-3 h-3" />{t.source}
                      </span>
                    )}
                  </div>
                  {t.snippet && (
                    <p className="text-xs text-gray-400 truncate mt-0.5">{t.snippet}</p>
                  )}
                  {t.mailbox && (
                    <p className="text-xs text-gray-300 mt-0.5">{t.mailbox}</p>
                  )}
                </div>

                <div className="text-xs text-gray-400 shrink-0 text-right">
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
