import { useState } from "react";
import { Card } from "../components/ui/card";
import { StatusBadge } from "../components/ingestion/StatusBadge";
import { DatasetList } from "../components/ingestion/DatasetList";
import { FileUpload } from "../components/ingestion/FileUpload";
import { ProfileSummary } from "../components/ingestion/ProfileSummary";
import { QualityIssuesList } from "../components/ingestion/QualityIssuesList";
import { MappingReview } from "../components/ingestion/MappingReview";
import { MaterializePanel } from "../components/ingestion/MaterializePanel";
import { useDataset } from "../hooks/useIngestion";

type FileTab = "profile" | "quality" | "mapping" | "materialize";

const TABS: { id: FileTab; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "quality", label: "Data quality" },
  { id: "mapping", label: "Column mapping" },
  { id: "materialize", label: "Materialize" },
];

export function IngestionPage() {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<FileTab>("profile");

  const datasetQuery = useDataset(selectedDatasetId);

  function handleSelectDataset(datasetId: string) {
    setSelectedDatasetId(datasetId);
    setSelectedFileId(null);
    setActiveTab("profile");
  }

  function handleSelectFile(fileId: string) {
    setSelectedFileId(fileId);
    setActiveTab("profile");
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <DatasetList selectedDatasetId={selectedDatasetId} onSelect={handleSelectDataset} />
        {selectedDatasetId && (
          <FileUpload
            datasetId={selectedDatasetId}
            selectedFileId={selectedFileId}
            onSelectFile={handleSelectFile}
          />
        )}
      </div>

      <div className="space-y-4">
        {!selectedDatasetId && (
          <Card>
            <p className="text-sm text-slate-500">
              Select or create a dataset on the left, then upload a file to begin ingestion.
            </p>
          </Card>
        )}

        {selectedDatasetId && !selectedFileId && (
          <Card>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-700">{datasetQuery.data?.name}</span>
              {datasetQuery.data && <StatusBadge status={datasetQuery.data.status} />}
            </div>
            <p className="text-sm text-slate-500">
              Upload a file and select it from the list on the left to view its profile, data-quality
              issues, and column mapping.
            </p>
          </Card>
        )}

        {selectedDatasetId && selectedFileId && (
          <>
            <Card>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-slate-700">{datasetQuery.data?.name}</span>
                {datasetQuery.data && <StatusBadge status={datasetQuery.data.status} />}
              </div>
              <nav className="mt-3 flex gap-1 border-b border-slate-200">
                {TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActiveTab(tab.id)}
                    className={`px-3 py-1.5 text-sm ${
                      activeTab === tab.id
                        ? "border-b-2 border-slate-800 font-medium text-slate-900"
                        : "text-slate-500"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </Card>

            {activeTab === "profile" && <ProfileSummary fileId={selectedFileId} />}
            {activeTab === "quality" && <QualityIssuesList fileId={selectedFileId} />}
            {activeTab === "mapping" && <MappingReview fileId={selectedFileId} />}
            {activeTab === "materialize" && (
              <MaterializePanel fileId={selectedFileId} datasetId={selectedDatasetId} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
