import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { TodoItem, TodoCategory, TodoPriority, TodoStatus } from "../types";
import { formatDate, statusColor } from "../utils/formatters";
import { CheckCircle, Circle, Clock } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

const CATEGORY_LABELS: Record<TodoCategory, string> = {
  unanswered_email: "Unanswered Email",
  missing_invoice_detail: "Missing Invoice Detail",
  payment_review: "Payment Review",
  draft_approval: "Draft Approval",
  overdue_invoice: "Overdue Invoice",
  general: "General",
};

const CATEGORY_COLORS: Record<TodoCategory, string> = {
  unanswered_email: "bg-purple-100 text-purple-700",
  missing_invoice_detail: "bg-orange-100 text-orange-700",
  payment_review: "bg-blue-100 text-blue-700",
  draft_approval: "bg-yellow-100 text-yellow-700",
  overdue_invoice: "bg-red-100 text-red-700",
  general: "bg-gray-100 text-gray-600",
};

export default function Todos() {
  const { activeCompany } = useCompany();
  const [categoryFilter, setCategoryFilter] = useState<TodoCategory | "">("");
  const [priorityFilter, setPriorityFilter] = useState<TodoPriority | "">("");
  const qc = useQueryClient();

  const cid = activeCompany?.id;

  const { data: todos = [], isLoading } = useQuery<TodoItem[]>({
    queryKey: ["todos", cid, categoryFilter],
    queryFn: () => api.get(`/todos?company_id=${cid}${categoryFilter ? `&category=${categoryFilter}` : ""}`).then(r => r.data),
    enabled: !!cid,
  });

  const doneMut = useMutation({
    mutationFn: (id: number) => api.delete(`/todos/${id}`),
    onSuccess: () => {
      toast.success("Marked done");
      qc.invalidateQueries({ queryKey: ["todos", cid] });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });

  const inProgressMut = useMutation({
    mutationFn: (id: number) => api.patch(`/todos/${id}`, { status: "in_progress" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["todos", cid] }),
  });

  const filtered = todos.filter(t =>
    !priorityFilter || t.priority === priorityFilter
  );

  const grouped = filtered.reduce<Record<TodoCategory, TodoItem[]>>((acc, t) => {
    if (!acc[t.category]) acc[t.category] = [];
    acc[t.category].push(t);
    return acc;
  }, {} as Record<TodoCategory, TodoItem[]>);

  if (!activeCompany) return <p className="text-gray-400">Select a company first.</p>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">To-Do</h1>
        <p className="text-xs text-gray-400">{activeCompany.name} · {filtered.length} open items</p>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {(["",...Object.keys(CATEGORY_LABELS)] as (TodoCategory | "")[]).map(cat => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat as TodoCategory | "")}
              className={clsx(
                "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                categoryFilter === cat
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              )}
            >
              {cat === "" ? "All" : CATEGORY_LABELS[cat as TodoCategory]}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(["", "high", "medium", "low"] as (TodoPriority | "")[]).map(p => (
            <button
              key={p}
              onClick={() => setPriorityFilter(p as TodoPriority | "")}
              className={clsx(
                "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                priorityFilter === p
                  ? "bg-brand-600 text-white border-brand-600"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              )}
            >
              {p === "" ? "All Priority" : p}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <p className="text-center py-10 text-gray-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <CheckCircle className="w-10 h-10 mx-auto mb-2 text-green-400" />
          <p className="font-medium">All caught up!</p>
        </div>
      ) : (
        <div className="space-y-6">
          {(Object.keys(grouped) as TodoCategory[]).map(cat => (
            <div key={cat}>
              <h2 className="text-sm font-semibold text-gray-600 mb-2 flex items-center gap-2">
                <span className={`badge ${CATEGORY_COLORS[cat]}`}>{CATEGORY_LABELS[cat]}</span>
                <span className="text-gray-400 font-normal">{grouped[cat].length} items</span>
              </h2>
              <div className="card p-0 divide-y divide-gray-50">
                {grouped[cat].map(todo => (
                  <div key={todo.id} className="flex items-center gap-3 px-4 py-3">
                    <button
                      onClick={() => doneMut.mutate(todo.id)}
                      className="text-gray-300 hover:text-green-500 transition-colors shrink-0"
                      title="Mark done"
                    >
                      {todo.status === "in_progress"
                        ? <Clock className="w-4 h-4 text-yellow-400" />
                        : <Circle className="w-4 h-4" />}
                    </button>

                    <div className="flex-1 min-w-0">
                      <p className={clsx("text-sm", todo.status === "done" ? "line-through text-gray-400" : "text-gray-800")}>
                        {todo.title}
                      </p>
                      {todo.description && (
                        <p className="text-xs text-gray-400 mt-0.5">{todo.description}</p>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {todo.due_date && (
                        <span className="text-xs text-gray-400">{formatDate(todo.due_date)}</span>
                      )}
                      <span className={`badge ${todo.priority === "high" ? "bg-red-100 text-red-700" : todo.priority === "medium" ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-500"}`}>
                        {todo.priority}
                      </span>
                      {todo.status !== "in_progress" && (
                        <button
                          onClick={() => inProgressMut.mutate(todo.id)}
                          className="text-xs text-gray-400 hover:text-brand-600 transition-colors"
                        >
                          Start
                        </button>
                      )}
                      <button
                        onClick={() => doneMut.mutate(todo.id)}
                        className="text-xs text-gray-400 hover:text-green-600 transition-colors"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
