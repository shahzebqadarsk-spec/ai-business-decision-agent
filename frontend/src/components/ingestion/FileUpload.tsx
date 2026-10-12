import { useRef } from "react";
import { Card } from "../ui/card";
import { StatusBadge } from "./StatusBadge";
import { useFiles, useUploadFile } from "../../hooks/useIngestion";
import { formatBytes } from "../../lib/format";

export function FileUpload({
  datasetId,
  selectedFileId,
  onSelectFile,
}: {
  datasetId: string;
  selectedFileId: string | null;
  onSelectFile: (fileId: string) => void;
}) {
  const filesQuery = useFiles(datasetId);
  const uploadFile = useUploadFile(datasetId);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    uploadFile.mutate(file, {
      onSuccess: (uploaded) => {
        if (uploaded.status === "validated") {
          onSelectFile(uploaded.id);
        }
      },
    });
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <Card>
      <h2 className="mb-3 text-sm font-semibold text-slate-500">Files</h2>

      <label className="mb-3 block">
        <span className="mb-1 block text-xs text-slate-500">Upload a CSV or XLSX file</span>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx"
          onChange={handleFileChosen}
          disabled={uploadFile.isPending}
          className="block w-full text-sm"
        />
      </label>
      {uploadFile.isPending && <p className="mb-2 text-sm text-slate-500">Uploading and profiling...</p>}
      {uploadFile.isError && (
        <p className="mb-2 text-sm text-red-600">{(uploadFile.error as Error).message}</p>
      )}

      {filesQuery.isLoading && <p className="text-sm text-slate-500">Loading files...</p>}
      {filesQuery.data && filesQuery.data.length === 0 && (
        <p className="text-sm text-slate-500">No files uploaded yet.</p>
      )}

      <ul className="divide-y divide-slate-100">
        {filesQuery.data?.map((file) => (
          <li key={file.id} className="py-2">
            <button
              type="button"
              disabled={file.status !== "validated"}
              onClick={() => onSelectFile(file.id)}
              className={`flex w-full flex-col gap-0.5 text-left text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
                file.id === selectedFileId ? "font-semibold text-slate-900" : "text-slate-700"
              }`}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="truncate">{file.original_filename}</span>
                <StatusBadge status={file.status} />
              </span>
              <span className="text-xs text-slate-500">
                {formatBytes(file.size_bytes)}
                {file.row_count !== null ? ` · ${file.row_count.toLocaleString()} rows` : ""}
              </span>
              {file.rejection_reason && (
                <span className="text-xs text-red-600">{file.rejection_reason}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
