import { useState } from "react";
import { Card } from "../ui/card";
import { useMappings, useMaterialize } from "../../hooks/useIngestion";

export function MaterializePanel({
  fileId,
  datasetId,
}: {
  fileId: string;
  datasetId: string;
}) {
  const mappingsQuery = useMappings(fileId);
  const materialize = useMaterialize(fileId, datasetId);
  const [performedBy, setPerformedBy] = useState("analyst");

  const confirmedCount = (mappingsQuery.data ?? []).filter((m) => m.status === "confirmed").length;

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-slate-500">Materialize into fact_sales</h2>
      <p className="mb-3 text-sm text-slate-600">
        Writes this file&rsquo;s rows into the canonical <code>fact_sales</code> table using only
        confirmed column mappings, preserving row-level lineage back to this upload.{" "}
        {confirmedCount} mapping(s) currently confirmed.
      </p>

      <div className="flex items-center gap-2">
        <label className="text-xs text-slate-500">
          Performed by:{" "}
          <input
            value={performedBy}
            onChange={(e) => setPerformedBy(e.target.value)}
            className="w-28 rounded border border-slate-300 px-1.5 py-0.5 text-xs"
          />
        </label>
        <button
          type="button"
          onClick={() => materialize.mutate(performedBy)}
          disabled={materialize.isPending}
          className="rounded bg-slate-800 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {materialize.isPending ? "Materializing..." : "Materialize"}
        </button>
      </div>

      {materialize.isError && (
        <p className="mt-2 text-sm text-red-600">{(materialize.error as Error).message}</p>
      )}

      {materialize.data && (
        <div className="mt-3 rounded bg-emerald-50 p-2 text-sm text-emerald-800">
          <p>
            Wrote {materialize.data.rows_written.toLocaleString()} row(s); skipped{" "}
            {materialize.data.rows_skipped.toLocaleString()}.
          </p>
          {materialize.data.skipped_reasons.length > 0 && (
            <ul className="mt-1 list-inside list-disc text-xs text-emerald-700">
              {materialize.data.skipped_reasons.slice(0, 5).map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  );
}
