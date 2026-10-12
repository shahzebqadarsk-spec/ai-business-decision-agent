import { Card } from "../ui/card";
import { useFileProfile } from "../../hooks/useIngestion";

export function ProfileSummary({ fileId }: { fileId: string }) {
  const profileQuery = useFileProfile(fileId);

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-slate-500">Column profile</h2>
      {profileQuery.isLoading && <p className="text-sm text-slate-500">Loading profile...</p>}
      {profileQuery.isError && <p className="text-sm text-red-600">Could not load the profile.</p>}

      {profileQuery.data && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-1 pr-3">Column</th>
                <th className="py-1 pr-3">Type</th>
                <th className="py-1 pr-3">Nulls</th>
                <th className="py-1 pr-3">Unique</th>
                <th className="py-1 pr-3">Min</th>
                <th className="py-1 pr-3">Max</th>
                <th className="py-1 pr-3">Mean</th>
                <th className="py-1">Sample</th>
              </tr>
            </thead>
            <tbody>
              {profileQuery.data.map((col) => (
                <tr key={col.column_name} className="border-b border-slate-100">
                  <td className="py-1.5 pr-3 font-medium text-slate-800">{col.column_name}</td>
                  <td className="py-1.5 pr-3 text-slate-600">{col.inferred_dtype}</td>
                  <td className="py-1.5 pr-3 text-slate-600">
                    {col.null_count} ({col.null_percentage.toFixed(1)}%)
                  </td>
                  <td className="py-1.5 pr-3 text-slate-600">{col.unique_count}</td>
                  <td className="py-1.5 pr-3 text-slate-600">{col.min_value ?? col.date_min ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-slate-600">{col.max_value ?? col.date_max ?? "—"}</td>
                  <td className="py-1.5 pr-3 text-slate-600">
                    {col.mean_value !== null ? col.mean_value.toFixed(2) : "—"}
                  </td>
                  <td className="py-1.5 text-slate-500">
                    {col.sample_values.slice(0, 3).map(String).join(", ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
