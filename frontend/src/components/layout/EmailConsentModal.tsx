import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Mail, ShieldCheck, ShieldOff } from "lucide-react";
import api from "../../utils/api";
import toast from "react-hot-toast";

interface Props {
  onDone: () => void;
}

export default function EmailConsentModal({ onDone }: Props) {
  const qc = useQueryClient();

  const consentMut = useMutation({
    mutationFn: (consent: boolean) =>
      api.post("/users/me/email-consent", { consent }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      onDone();
    },
    onError: () => toast.error("Failed to save preference"),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-blue-50 rounded-xl">
              <Mail className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h2 className="font-bold text-gray-900">Email Access</h2>
              <p className="text-xs text-gray-400">One-time preference</p>
            </div>
          </div>

          <p className="text-sm text-gray-600 leading-relaxed">
            This dashboard can connect to your Gmail to monitor your inbox, surface
            customer queries, and draft replies for your review.
          </p>

          <div className="bg-blue-50 rounded-xl p-4 space-y-1.5 text-xs text-blue-800">
            <p className="font-semibold">What the system will do:</p>
            <p>✓ Read emails in your inbox</p>
            <p>✓ Draft replies (never sends automatically)</p>
            <p>✓ Add draft reviews to your To-Do list</p>
            <p className="font-semibold mt-2">What it will never do:</p>
            <p>✗ Send emails without your explicit approval</p>
            <p>✗ Access personal emails outside AR context</p>
          </div>

          <p className="text-xs text-gray-400">
            You can connect Gmail afterwards via the Emails tab. This preference can be
            changed any time from your account settings.
          </p>

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => consentMut.mutate(true)}
              disabled={consentMut.isPending}
              className="flex-1 btn-primary justify-center py-2.5 gap-2"
            >
              <ShieldCheck className="w-4 h-4" />
              Allow Email Access
            </button>
            <button
              onClick={() => consentMut.mutate(false)}
              disabled={consentMut.isPending}
              className="flex-1 btn-secondary justify-center py-2.5 gap-2"
            >
              <ShieldOff className="w-4 h-4" />
              Not Now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
