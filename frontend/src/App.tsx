import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Customers from "./pages/Customers";
import Payments from "./pages/Payments";
import Emails from "./pages/Emails";
import Todos from "./pages/Todos";
import Reports from "./pages/Reports";
import Users from "./pages/Users";
import Disputes from "./pages/Disputes";
import CompanySettings from "./pages/CompanySettings";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="invoices" element={<Invoices />} />
        <Route path="customers" element={<Customers />} />
        <Route path="payments" element={<Payments />} />
        <Route path="emails" element={<Emails />} />
        <Route path="todos" element={<Todos />} />
        <Route path="disputes" element={<Disputes />} />
        <Route path="reports" element={<Reports />} />
        <Route path="users" element={<Users />} />
        <Route path="settings" element={<CompanySettings />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}
