import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCompany } from "../context/CompanyContext";
import api from "../utils/api";
import { User, Company } from "../types";
import { formatDate } from "../utils/formatters";
import { Plus, X, Shield, User as UserIcon } from "lucide-react";
import toast from "react-hot-toast";
import clsx from "clsx";

function CreateUserModal({ companies, onClose }: { companies: Company[]; onClose: () => void }) {
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "ar_specialist" as "ar_manager" | "ar_specialist",
    company_ids: [] as number[],
  });
  const qc = useQueryClient();

  const createMut = useMutation({
    mutationFn: () => api.post("/users", form),
    onSuccess: () => {
      toast.success("User created");
      qc.invalidateQueries({ queryKey: ["users"] });
      onClose();
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Failed to create user"),
  });

  const toggleCompany = (id: number) => {
    setForm(f => ({
      ...f,
      company_ids: f.company_ids.includes(id) ? f.company_ids.filter(c => c !== id) : [...f.company_ids, id],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between p-5 border-b border-gray-100">
          <h2 className="font-bold text-gray-900">Create User</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Full Name</label>
            <input
              value={form.full_name}
              onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
            <input
              type="password"
              value={form.password}
              onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
            <div className="flex gap-2">
              {[
                { value: "ar_specialist", label: "AR Specialist" },
                { value: "ar_manager", label: "AR Manager" },
              ].map(r => (
                <button
                  key={r.value}
                  onClick={() => setForm(f => ({ ...f, role: r.value as any }))}
                  className={clsx(
                    "flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors",
                    form.role === r.value ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-300"
                  )}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
          {form.role === "ar_specialist" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Company Access</label>
              <div className="flex flex-wrap gap-2">
                {companies.map(c => (
                  <button
                    key={c.id}
                    onClick={() => toggleCompany(c.id)}
                    className={clsx(
                      "px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors",
                      form.company_ids.includes(c.id) ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-300"
                    )}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <button
            onClick={() => createMut.mutate()}
            disabled={createMut.isPending || !form.email || !form.full_name || !form.password}
            className="w-full btn-primary justify-center py-2.5"
          >
            {createMut.isPending ? "Creating…" : "Create User"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Users() {
  const { companies } = useCompany();
  const [showCreate, setShowCreate] = useState(false);
  const qc = useQueryClient();

  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: () => api.get("/users").then(r => r.data),
  });

  const deactivateMut = useMutation({
    mutationFn: (id: number) => api.delete(`/users/${id}`),
    onSuccess: () => {
      toast.success("User deactivated");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">User Management</h1>
          <p className="text-xs text-gray-400">Manage AR team access</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="w-4 h-4" />
          Add User
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr className="text-left text-xs text-gray-400">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Companies</th>
              <th className="px-4 py-3 font-medium">Joined</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {isLoading ? (
              <tr><td colSpan={6} className="text-center py-10 text-gray-400">Loading…</td></tr>
            ) : users.map(u => {
              const userCompanies = companies.filter(c => u.company_ids.includes(c.id));
              return (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className={clsx(
                        "w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0",
                        u.role === "ar_manager" ? "bg-brand-600" : "bg-gray-400"
                      )}>
                        {u.full_name.charAt(0).toUpperCase()}
                      </div>
                      <span className="font-medium text-gray-800">{u.full_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={clsx(
                      "badge",
                      u.role === "ar_manager" ? "bg-brand-100 text-brand-700" : "bg-gray-100 text-gray-600"
                    )}>
                      {u.role === "ar_manager" ? <Shield className="w-3 h-3 inline mr-1" /> : <UserIcon className="w-3 h-3 inline mr-1" />}
                      {u.role === "ar_manager" ? "AR Manager" : "AR Specialist"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {u.role === "ar_manager" ? (
                      <span className="text-xs text-gray-400">All companies</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {userCompanies.map(c => (
                          <span key={c.id} className="badge bg-gray-100 text-gray-600">{c.name}</span>
                        ))}
                        {userCompanies.length === 0 && <span className="text-xs text-gray-400">None</span>}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{formatDate(u.created_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => deactivateMut.mutate(u.id)}
                      className="text-xs text-red-400 hover:text-red-600 transition-colors"
                    >
                      Deactivate
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showCreate && <CreateUserModal companies={companies} onClose={() => setShowCreate(false)} />}
    </div>
  );
}
