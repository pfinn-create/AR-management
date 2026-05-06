import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Layout from "./components/layout/Layout";
import Dashboard from "./pages/Dashboard";
import Invoices from "./pages/Invoices";
import Customers from "./pages/Customers";
import Payments from "./pages/Payments";
import Emails from "./pages/Emails";
import Todos from "./pages/Todos";
import Reports from "./pages/Reports";
import Users from "./pages/Users";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center text-gray-400">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <PrivateRoute>
            <Layout>
              <Routes>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="invoices" element={<Invoices />} />
                <Route path="customers" element={<Customers />} />
                <Route path="payments" element={<Payments />} />
                <Route path="emails" element={<Emails />} />
                <Route path="todos" element={<Todos />} />
                <Route path="reports" element={<Reports />} />
                <Route path="users" element={<Users />} />
              </Routes>
            </Layout>
          </PrivateRoute>
        }
      />
    </Routes>
  );
}
