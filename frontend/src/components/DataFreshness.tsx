import { useQuery } from "@tanstack/react-query";
import { useCompany } from "../../context/CompanyContext";
import api from "../../utils/api";
import { Clock } from "lucide-react";

interface Freshness {
  invoices_last_imported: string | null;
  payments_last_imported: string | null;
  customers_last_synced: string | null;
}

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

const KEY_LABELS: Record<keyof Freshness, string> = {
  invoices_last_imported: "Invoices",
  payments_last_imported: "Payments",
  customers_last_synced: "Customers",
};

interface Props {
  show: (keyof Freshness)[];
}

export default function DataFreshness({ show }: Props) {
  const { activeCompany } = useCompany();
  const cid = activeCompany?.id;

  const { data } = useQuery<Freshness>({
    queryKey: ["freshness", cid],
    queryFn: () => api.get(`/companies/${cid}/freshness`).then(r => r.data),
    enabled: !!cid,
    staleTime: 30_000,
  });

  if (!data) return null;

  return (
    <div className="flex items-center gap-3 text-xs text-gray-400">
      <Clock className="w-3.5 h-3.5 shrink-0" />
      {show.map(key => (
        <span key={key}>
          <span className="text-gray-500 font-medium">{KEY_LABELS[key]}:</span>{" "}
          <span className={!data[key] ? "text-orange-400" : ""}>{timeAgo(data[key])}</span>
        </span>
      ))}
    </div>
  );
}
