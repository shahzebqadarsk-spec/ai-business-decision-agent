import { useState } from "react";
import { Card } from "../ui/card";
import { StatusBadge } from "./StatusBadge";
import { useCreateDataset, useDatasets } from "../../hooks/useIngestion";

export function DatasetList({
  selectedDatasetId,
  onSelect,
}: {
  selectedDatasetId: string | null;
  onSelect: (datasetId: string) => void;
}) {
  const datasetsQuery = useDatasets();
  const createDataset = useCreateDataset();
  const [name, setName] = useState("");

  function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    createDataset.mutate(trimmed, {
      onSuccess: (dataset) => {
        setName("");
        onSelect(dataset.id);
      },
    });
  }

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-slate-500">Datasets</h2>

      <form onSubmit={handleCreate} className="mb-3 flex gap-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New dataset name"
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <button
          type="submit"
          disabled={createDataset.isPending || name.trim() === ""}
          className="rounded bg-slate-800 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          Create
        </button>
      </form>
      {createDataset.isError && (
        <p className="mb-2 text-sm text-red-600">{(createDataset.error as Error).message}</p>
      )}

      {datasetsQuery.isLoading && <p className="text-sm text-slate-500">Loading datasets...</p>}
      {datasetsQuery.isError && <p className="text-sm text-red-600">Could not reach the backend.</p>}
      {datasetsQuery.data && datasetsQuery.data.length === 0 && (
        <p className="text-sm text-slate-500">No datasets yet. Create one to get started.</p>
      )}

      <ul className="divide-y divide-slate-100">
        {datasetsQuery.data?.map((dataset) => (
          <li key={dataset.id}>
            <button
              type="button"
              onClick={() => onSelect(dataset.id)}
              className={`flex w-full items-center justify-between gap-2 py-2 text-left text-sm ${
                dataset.id === selectedDatasetId ? "font-semibold text-slate-900" : "text-slate-700"
              }`}
            >
              <span>{dataset.name}</span>
              <StatusBadge status={dataset.status} />
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
