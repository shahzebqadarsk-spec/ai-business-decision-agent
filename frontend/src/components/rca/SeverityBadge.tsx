import { Badge } from "../ui/badge";
import type { IssueSeverity } from "../../types/rca";

const SEVERITY_STYLE: Record<IssueSeverity, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

export function SeverityBadge({ severity }: { severity: IssueSeverity }) {
  return <Badge className={SEVERITY_STYLE[severity]}>{severity}</Badge>;
}
