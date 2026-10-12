import { useState } from "react";
import { Card } from "../ui/card";
import { StatusBadge } from "./StatusBadge";
import {
  useCanonicalFields,
  useConfirmMapping,
  useMappings,
  useProposeMappings,
  useRejectMapping,
} from "../../hooks/useIngestion";
import type { ColumnMapping } from "../../types/ingestion";

const CANONICAL_TABLE = "fact_sales";

function MappingRow({
  mapping,
  canonicalFieldNames,
  performedBy,
  onConfirm,
  onReject,
  isBusy,
}: {
  mapping: ColumnMapping;
  canonicalFieldNames: string[];
  performedBy: string;
  onConfirm: (mappingId: string, field: string) => void;
  onReject: (mappingId: string) => void;
  isBusy: boolean;
}) {
  const [chosenField, setChosenField] = useState(mapping.proposed_canonical_field ?? "");

  return (
    <tr className="border-b border-slate-100 align-top">
      <td className="py-2 pr-3 font-medium text-slate-800">{mapping.source_column}</td>
      <td className="py-2 pr-3 text-slate-600">
        {mapping.proposed_canonical_field ?? <span className="italic text-slate-400">none</span>}
      </td>
      <td className="py-2 pr-3 text-slate-600">{(mapping.confidence * 100).toFixed(0)}%</td>
      <td className="py-2 pr-3 text-slate-600">{mapping.method}</td>
      <td className="py-2 pr-3">
        <StatusBadge status={mapping.status} />
      </td>
      <td className="py-2 pr-3 text-slate-600">
        {mapping.status === "confirmed" ? (
          <span>
            {mapping.confirmed_canonical_field} <span className="text-xs text-slate-400">by {mapping.confirmed_by}</span>
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="py-2">
        <div className="flex items-center gap-2">
          <select
            value={chosenField}
            onChange={(e) => setChosenField(e.target.value)}
            disabled={isBusy}
            className="rounded border border-slate-300 px-1.5 py-0.5 text-xs"
          >
            <option value="">choose field...</option>
            {canonicalFieldNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={isBusy || chosenField === ""}
            onClick={() => onConfirm(mapping.id, chosenField)}
            className="rounded bg-emerald-700 px-2 py-0.5 text-xs text-white disabled:opacity-50"
          >
            Confirm
          </button>
          <button
            type="button"
            disabled={isBusy || mapping.status === "rejected"}
            onClick={() => onReject(mapping.id)}
            className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
        <p className="mt-1 text-[11px] text-slate-400">as: {performedBy}</p>
      </td>
    </tr>
  );
}

export function MappingReview({ fileId }: { fileId: string }) {
  const mappingsQuery = useMappings(fileId);
  const canonicalFieldsQuery = useCanonicalFields(CANONICAL_TABLE);
  const proposeMappings = useProposeMappings(fileId);
  const confirmMapping = useConfirmMapping(fileId);
  const rejectMapping = useRejectMapping(fileId);
  const [performedBy, setPerformedBy] = useState("analyst");

  const canonicalFieldNames = canonicalFieldsQuery.data?.map((f) => f.name) ?? [];
  const requiredFields = canonicalFieldsQuery.data?.filter((f) => f.required).map((f) => f.name) ?? [];
  const confirmedFields = new Set(
    (mappingsQuery.data ?? [])
      .filter((m) => m.status === "confirmed")
      .map((m) => m.confirmed_canonical_field),
  );
  const missingRequired = requiredFields.filter((f) => !confirmedFields.has(f));

  const isBusy = confirmMapping.isPending || rejectMapping.isPending;

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-500">Column mapping</h2>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">
            Reviewer name:{" "}
            <input
              value={performedBy}
              onChange={(e) => setPerformedBy(e.target.value)}
              className="w-28 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
            />
          </label>
          <button
            type="button"
            onClick={() => proposeMappings.mutate()}
            disabled={proposeMappings.isPending}
            className="rounded bg-slate-800 px-2.5 py-1 text-xs text-white disabled:opacity-50"
          >
            {mappingsQuery.data && mappingsQuery.data.length > 0 ? "Re-propose mappings" : "Propose mappings"}
          </button>
        </div>
      </div>

      {proposeMappings.isError && (
        <p className="mb-2 text-sm text-red-600">{(proposeMappings.error as Error).message}</p>
      )}
      {(confirmMapping.isError || rejectMapping.isError) && (
        <p className="mb-2 text-sm text-red-600">
          {((confirmMapping.error ?? rejectMapping.error) as Error).message}
        </p>
      )}

      {mappingsQuery.isLoading && <p className="text-sm text-slate-500">Loading mappings...</p>}
      {mappingsQuery.data && mappingsQuery.data.length === 0 && (
        <p className="text-sm text-slate-500">
          No mapping proposals yet. Click &ldquo;Propose mappings&rdquo; to generate them — nothing is
          auto-accepted; every mapping needs an explicit confirm before it can be used.
        </p>
      )}

      {mappingsQuery.data && mappingsQuery.data.length > 0 && (
        <>
          {missingRequired.length > 0 && (
            <p className="mb-2 rounded bg-amber-50 p-2 text-xs text-amber-800">
              Required canonical fields not yet confirmed: {missingRequired.join(", ")}. Materialization
              will be blocked until each has a confirmed mapping.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-1 pr-3">Source column</th>
                  <th className="py-1 pr-3">Proposed field</th>
                  <th className="py-1 pr-3">Confidence</th>
                  <th className="py-1 pr-3">Method</th>
                  <th className="py-1 pr-3">Status</th>
                  <th className="py-1 pr-3">Confirmed as</th>
                  <th className="py-1">Action</th>
                </tr>
              </thead>
              <tbody>
                {mappingsQuery.data.map((mapping) => (
                  <MappingRow
                    key={mapping.id}
                    mapping={mapping}
                    canonicalFieldNames={canonicalFieldNames}
                    performedBy={performedBy}
                    isBusy={isBusy}
                    onConfirm={(mappingId, field) =>
                      confirmMapping.mutate({ mappingId, field, confirmedBy: performedBy })
                    }
                    onReject={(mappingId) => rejectMapping.mutate({ mappingId, rejectedBy: performedBy })}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
