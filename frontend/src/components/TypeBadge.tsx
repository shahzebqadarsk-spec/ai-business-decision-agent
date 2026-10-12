import { Badge } from "./ui/badge";

export type EvidenceType = "fact" | "assumption" | "modelled" | "recommendation";

const STYLES: Record<EvidenceType, string> = {
  fact: "bg-blue-100 text-blue-800",
  assumption: "bg-amber-100 text-amber-800",
  modelled: "bg-violet-100 text-violet-800",
  recommendation: "bg-emerald-100 text-emerald-800",
};

export function TypeBadge({ type }: { type: EvidenceType }) {
  return <Badge className={STYLES[type]}>{type}</Badge>;
}
