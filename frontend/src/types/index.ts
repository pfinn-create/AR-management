export type UserRole = "ar_manager" | "ar_specialist";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  company_ids: number[];
  created_at: string;
}

export interface Company {
  id: number;
  code: string;
  name: string;
  default_payment_terms_days: number;
  is_active: boolean;
  created_at: string;
  open_invoices_count: number;
  total_ar_balance: number;
  overdue_amount: number;
  open_todos_count: number;
  unanswered_emails_count: number;
}

export type InvoiceStatus = "open" | "partial" | "paid" | "overdue" | "disputed" | "written_off";

export interface Invoice {
  id: number;
  company_id: number;
  customer_id: number | null;
  invoice_number: string;
  po_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  amount: number;
  amount_paid: number;
  balance: number;
  currency: string;
  payment_terms_days: number;
  status: InvoiceStatus;
  customer_name: string | null;
  notes: string | null;
  netsuite_id: string | null;
  imported_at: string;
  days_overdue: number | null;
}

export interface Customer {
  id: number;
  company_id: number;
  customer_code: string | null;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  payment_terms_days: number;
  credit_limit: number | null;
  is_active: boolean;
  created_at: string;
  open_balance: number | null;
  overdue_balance: number | null;
}

export type PaymentStatus = "pending_review" | "matched" | "partially_matched" | "unmatched" | "applied";
export type MatchConfidence = "high" | "medium" | "low" | "flagged";

export interface RemittanceLine {
  id: number;
  payment_id: number;
  invoice_id: number | null;
  invoice_number_raw: string | null;
  amount: number | null;
  match_confidence: MatchConfidence;
  is_approved: boolean;
  notes: string | null;
}

export interface Payment {
  id: number;
  company_id: number;
  payment_date: string | null;
  amount: number;
  amount_applied: number;
  currency: string;
  payer_name: string | null;
  reference_number: string | null;
  bank_transaction_id: string | null;
  memo: string | null;
  source: string | null;
  status: PaymentStatus;
  ai_notes: string | null;
  created_at: string;
  remittance_lines: RemittanceLine[];
}

export type ThreadStatus = "unread" | "needs_response" | "draft_ready" | "responded" | "closed";
export type EmailSource = "gmail" | "outlook";

export interface EmailMessage {
  id: number;
  sender: string | null;
  recipient: string | null;
  body_text: string | null;
  received_at: string | null;
  is_draft: boolean;
  is_outbound: boolean;
}

export interface EmailThread {
  id: number;
  company_id: number;
  customer_id: number | null;
  subject: string | null;
  source: EmailSource | null;
  mailbox: string | null;
  status: ThreadStatus;
  last_message_at: string | null;
  snippet: string | null;
  linked_invoice_numbers: string | null;
  messages: EmailMessage[];
}

export type TodoCategory = "unanswered_email" | "missing_invoice_detail" | "payment_review" | "draft_approval" | "overdue_invoice" | "general";
export type TodoPriority = "high" | "medium" | "low";
export type TodoStatus = "open" | "in_progress" | "done" | "snoozed";

export interface TodoItem {
  id: number;
  company_id: number;
  category: TodoCategory;
  priority: TodoPriority;
  status: TodoStatus;
  title: string;
  description: string | null;
  assigned_to: number | null;
  due_date: string | null;
  linked_invoice_id: number | null;
  linked_thread_id: number | null;
  linked_payment_id: number | null;
  is_auto_generated: boolean;
  created_at: string;
}

export interface AgingReport {
  company_id: number;
  as_of: string;
  aging: {
    current: number;
    "1_30": number;
    "31_60": number;
    "61_90": number;
    over_90: number;
  };
  total: number;
}

export interface MonthlyTrend {
  month: string;
  invoiced: number;
  collected: number;
  overdue: number;
}
