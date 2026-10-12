import { Badge } from "../ui/badge";

const STYLES: Record<string, string> = {
  uploaded: "bg-slate-100 text-slate-700",
  profiled: "bg-blue-100 text-blue-800",
  mapping: "bg-amber-100 text-amber-800",
  materialized: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  validated: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
  proposed: "bg-amber-100 text-amber-800",
  confirmed: "bg-emerald-100 text-emerald-800",
  unresolved: "bg-slate-200 text-slate-700",
  info: "bg-slate-100 text-slate-700",
  warning: "bg-amber-100 text-amber-800",
  error: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge className={STYLES[status] ?? "bg-slate-100 text-slate-700"}>{status}</Badge>;
}
