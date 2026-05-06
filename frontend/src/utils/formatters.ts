import { format, parseISO, isValid } from "date-fns";

export function formatCurrency(amount: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const d = parseISO(dateStr);
  return isValid(d) ? format(d, "MMM d, yyyy") : "—";
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  const d = parseISO(dateStr);
  return isValid(d) ? format(d, "MMM d, yyyy HH:mm") : "—";
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    open: "bg-blue-100 text-blue-800",
    partial: "bg-yellow-100 text-yellow-800",
    paid: "bg-green-100 text-green-800",
    overdue: "bg-red-100 text-red-800",
    disputed: "bg-orange-100 text-orange-800",
    written_off: "bg-gray-100 text-gray-500",
    pending_review: "bg-yellow-100 text-yellow-800",
    matched: "bg-blue-100 text-blue-800",
    partially_matched: "bg-orange-100 text-orange-800",
    unmatched: "bg-red-100 text-red-800",
    applied: "bg-green-100 text-green-800",
    unread: "bg-purple-100 text-purple-800",
    needs_response: "bg-red-100 text-red-800",
    draft_ready: "bg-yellow-100 text-yellow-800",
    responded: "bg-green-100 text-green-800",
    closed: "bg-gray-100 text-gray-500",
    high: "bg-red-100 text-red-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-green-100 text-green-800",
    flagged: "bg-orange-100 text-orange-800",
  };
  return map[status] || "bg-gray-100 text-gray-600";
}

export function confidenceIcon(confidence: string): string {
  const map: Record<string, string> = {
    high: "✓",
    medium: "~",
    low: "?",
    flagged: "⚠",
  };
  return map[confidence] || "?";
}
