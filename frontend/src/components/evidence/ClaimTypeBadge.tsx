import { Badge } from "../ui/badge";
import type { ClaimType } from "../../types/evidence";

const CLAIM_STYLE: Record<ClaimType, string> = {
  fact: "bg-slate-100 text-slate-700",
  contribution: "bg-blue-100 text-blue-700",
  inference: "bg-purple-100 text-purple-700",
  recommendation: "bg-emerald-100 text-emerald-700",
};

const CLAIM_LABEL: Record<ClaimType, string> = {
  fact: "Fact",
  contribution: "Contribution",
  inference: "Inference",
  recommendation: "Recommendation",
};

/** Shared by every phase that writes Evidence rows. Phase 4 (RCA) only ever produces "fact" and
 * "contribution"; Phase 5 (Forecasting) is the first production user of "inference". */
export function ClaimTypeBadge({ claimType }: { claimType: ClaimType }) {
  return <Badge className={CLAIM_STYLE[claimType]}>{CLAIM_LABEL[claimType]}</Badge>;
}
