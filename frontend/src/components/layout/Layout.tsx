import { ReactNode } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import EmailConsentModal from "./EmailConsentModal";
import { useAuth } from "../../context/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { user, refreshUser } = useAuth();

  // Show consent modal if user has never been asked (email_consent_at is null)
  const needsConsent = user && user.email_consent_at === null;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
      {needsConsent && <EmailConsentModal onDone={refreshUser} />}
    </div>
  );
}
