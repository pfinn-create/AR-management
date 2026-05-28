import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { CompanySettings } from "../types";
import { Save, Plus, X, Settings } from "lucide-react";
import toast from "react-hot-toast";

export default function CompanySettingsPage() {
  const { activeCompany } = useCompany();
  const qc = useQueryClient();
  const cid = activeCompany?.id;

  const { data: settings, isLoading } = useQuery<CompanySettings>({
    queryKey: ["settings", cid],
    queryFn: () => api.get(`/settings/${cid}`).then(r => r.data),
    enabled: !!cid,
  });

  const [form, setForm] = useState<Partial<CompanySettings>>({});
  const [intervalInput, setIntervalInput] = useState("");

  useEffect(() => {
    if (settings) {
      setForm({ ...settings });
    }
  }, [settings]);

  const saveMut = useMutation({
    mutationFn: (data: Partial<CompanySettings>) => api.patch(`/settings/${cid}`, data),
    onSuccess: () => {
      toast.success("Settings saved");
      qc.invalidateQueries({ queryKey: ["settings", cid] });
    },
    onError: () => toast.error("Failed to save settings"),
  });

  const handleSave = () => {
    saveMut.mutate(form);
  };

  const addInterval = () => {
    const val = parseInt(intervalInput, 10);
    if (!isNaN(val) && val > 0) {
      const current = form.followup_intervals ?? [];
      if (!current.includes(val)) {
        setForm(f => ({ ...f, followup_intervals: [...current, val].sort((a, b) => a - b) }));
      }
      setIntervalInput("");
    }
  };

  const removeInterval = (day: number) => {
    setForm(f => ({ ...f, followup_intervals: (f.followup_intervals ?? []).filter(d => d !== day) }));
  };

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Company Settings</h1>
        <p className="text-xs text-gray-400">{activeCompany.name} · Configure AR preferences</p>
      </div>

      {isLoading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : (
        <>
          {/* Payment Terms */}
          <div className="card space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-4 h-4 text-brand-600" />
              <h2 className="font-semibold text-gray-800">Payment Terms</h2>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Default Payment Terms (days)</label>
              <input
                type="number"
                className="input w-32"
                value={form.payment_terms_days ?? 30}
                onChange={e => setForm(f => ({ ...f, payment_terms_days: parseInt(e.target.value, 10) || 30 }))}
              />
            </div>
          </div>

          {/* Email Settings */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-gray-800">Email Settings</h2>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Monitored Inbox (email address)</label>
              <input
                type="email"
                className="input w-full"
                placeholder="ar@yourcompany.com"
                value={form.monitored_inbox ?? ""}
                onChange={e => setForm(f => ({ ...f, monitored_inbox: e.target.value || null }))}
              />
              <p className="text-xs text-gray-400 mt-1">The Gmail inbox to monitor for customer emails.</p>
            </div>
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="email_auto_draft"
                checked={form.email_auto_draft ?? true}
                onChange={e => setForm(f => ({ ...f, email_auto_draft: e.target.checked }))}
                className="rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              />
              <label htmlFor="email_auto_draft" className="text-sm text-gray-700">
                Auto-generate email drafts (never sends automatically)
              </label>
            </div>
          </div>

          {/* Follow-Up Sequence */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-gray-800">Follow-Up Sequence</h2>
            <p className="text-xs text-gray-500">Days after invoice due date to trigger follow-up reminders.</p>
            <div className="flex flex-wrap gap-2">
              {(form.followup_intervals ?? []).map(day => (
                <span
                  key={day}
                  className="flex items-center gap-1 bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-1 rounded-full"
                >
                  Day {day}
                  <button
                    onClick={() => removeInterval(day)}
                    className="hover:text-red-500 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="number"
                className="input w-24"
                placeholder="e.g. 7"
                value={intervalInput}
                onChange={e => setIntervalInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && addInterval()}
                min={1}
              />
              <button onClick={addInterval} className="btn-secondary py-1.5 text-xs">
                <Plus className="w-3.5 h-3.5" />
                Add Day
              </button>
            </div>
          </div>

          {/* Escalation Thresholds */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-gray-800">Escalation Thresholds</h2>
            <p className="text-xs text-gray-500">Automatically flag accounts for escalation when both conditions are met.</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Days Overdue</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    className="input w-24"
                    value={form.escalation_days_overdue ?? 60}
                    onChange={e => setForm(f => ({ ...f, escalation_days_overdue: parseInt(e.target.value, 10) || 60 }))}
                    min={1}
                  />
                  <span className="text-xs text-gray-400">days</span>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Minimum Amount Overdue</label>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">$</span>
                  <input
                    type="number"
                    className="input w-32"
                    value={form.escalation_min_amount ?? 10000}
                    onChange={e => setForm(f => ({ ...f, escalation_min_amount: parseFloat(e.target.value) || 10000 }))}
                    min={0}
                    step={500}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Bank Statement Format */}
          <div className="card space-y-4">
            <h2 className="font-semibold text-gray-800">Bank Statement Import</h2>
            <div>
              <label className="block text-xs text-gray-500 mb-2">Default Chase Statement Format</label>
              <div className="flex gap-4">
                {(["csv", "pdf"] as const).map(fmt => (
                  <label key={fmt} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="bank_format"
                      value={fmt}
                      checked={form.bank_format === fmt}
                      onChange={() => setForm(f => ({ ...f, bank_format: fmt }))}
                      className="text-brand-600 focus:ring-brand-500"
                    />
                    <span className="text-sm text-gray-700 uppercase font-medium">{fmt}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-1.5">Both formats can always be uploaded manually regardless of this setting.</p>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saveMut.isPending}
              className="btn-primary"
            >
              <Save className="w-4 h-4" />
              {saveMut.isPending ? "Saving…" : "Save Settings"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
