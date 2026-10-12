import { Card } from "../ui/card";
import { ClaimTypeBadge } from "./ClaimTypeBadge";
import { useEvidence } from "../../hooks/useEvidence";

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <p className="flex justify-between gap-3">
      <span className="text-slate-400">{label}</span>
      <span className="text-right text-slate-700">{value || "—"}</span>
    </p>
  );
}

/** Slide-over panel showing one Evidence record's claim text, claim type, and full calculation
 * lineage (Phase 4 spec sections 10/11/14: "every important number traceable to an Evidence
 * ID"; Phase 5 reuses it unchanged for forecast fit/inference evidence). Fetches /evidence/{id}
 * on demand -- it is never passed a pre-fetched object, so the same component works for
 * evidence reached from any issue, breakdown, or forecast. */
export function EvidenceDrawer({ evidenceId, onClose }: { evidenceId: string | null; onClose: () => void }) {
  const evidenceQuery = useEvidence(evidenceId ?? undefined);

  if (evidenceId === null) return null;
  const evidence = evidenceQuery.data;

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md overflow-y-auto border-l border-slate-200 bg-white p-4 shadow-lg">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Evidence</h3>
        <button type="button" onClick={onClose} className="text-sm text-slate-400 hover:text-slate-600">
          Close
        </button>
      </div>

      {evidenceQuery.isLoading && <p className="text-sm text-slate-500">Loading evidence...</p>}
      {evidenceQuery.isError && <p className="text-sm text-red-600">Could not load this evidence record.</p>}

      {evidence && (
        <div className="space-y-3">
          <ClaimTypeBadge claimType={evidence.claim_type} />
          <p className="text-sm text-slate-700">{evidence.claim}</p>

          <Card className="space-y-1 text-xs">
            <Row label="Evidence ID" value={evidence.id} />
            <Row label="Metric" value={evidence.metric} />
            <Row label="Period" value={evidence.period_key} />
            <Row label="Comparison period" value={evidence.comparison_period_key} />
            <Row label="Dimension" value={evidence.dimension} />
            <Row label="Dimension value" value={evidence.dimension_value} />
            <Row
              label="Contribution %"
              value={
                evidence.contribution_to_total_pct !== null
                  ? `${evidence.contribution_to_total_pct.toFixed(1)}%`
                  : null
              }
            />
          </Card>

          <Card className="space-y-1 text-xs">
            <p className="mb-1 font-semibold text-slate-500">Calculation lineage</p>
            <Row label="Calculation" value={evidence.calculation_name} />
            <Row label="Version" value={evidence.calculation_version} />
            <Row label="Source fields" value={evidence.source_fields.join(", ")} />
            <Row label="Source files" value={evidence.source_file_ids.join(", ")} />
          </Card>

          <p className="text-xs text-slate-400">
            This record was produced by deterministic analytics and cannot be edited by the AI
            narrator -- it is the lineage a future narrative must cite rather than restate.
          </p>
        </div>
      )}
    </div>
  );
}
