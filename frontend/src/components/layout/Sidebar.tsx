import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, FileText, Users, CreditCard,
  Mail, CheckSquare, BarChart2, UserCog, Building2,
  AlertOctagon, Settings
} from "lucide-react";
import clsx from "clsx";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/invoices", icon: FileText, label: "Invoices" },
  { to: "/customers", icon: Users, label: "Customers" },
  { to: "/payments", icon: CreditCard, label: "Payments" },
  { to: "/emails", icon: Mail, label: "Emails" },
  { to: "/todos", icon: CheckSquare, label: "To-Do" },
  { to: "/disputes", icon: AlertOctagon, label: "Disputes" },
  { to: "/reports", icon: BarChart2, label: "Reports" },
  { to: "/users", icon: UserCog, label: "Users" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-brand-900 flex flex-col shrink-0">
      <div className="px-4 py-5 flex items-center gap-2">
        <Building2 className="text-white w-6 h-6" />
        <span className="text-white font-bold text-sm leading-tight">AR Management</span>
      </div>

      <nav className="flex-1 px-2 pb-4 space-y-0.5">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-700 text-white"
                  : "text-brand-100 hover:bg-brand-800 hover:text-white"
              )
            }
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
