import { useState } from "react";
import { IngestionRunPanel } from "../components/ingestion/IngestionRunPanel";
import { DocumentPipelineView } from "../components/ingestion/DocumentPipelineView";
import { QualityGateResults } from "../components/ingestion/QualityGateResults";
import { DocumentViewer } from "../components/ingestion/DocumentViewer";
import { IndexHealthPanel } from "../components/ingestion/IndexHealthPanel";

export function CurationDashboard() {
  const [activeRunId, setActiveRunId] = useState<string>();
  const [selectedDocId, setSelectedDocId] = useState<string>();
  const [viewerDocId, setViewerDocId] = useState<string>();

  return (
    <div className="dashboard">
      <h2>Ingestion & Curation</h2>

      <IngestionRunPanel
        onRunStarted={setActiveRunId}
        activeRunId={activeRunId}
      />

      <DocumentPipelineView
        ingestionId={activeRunId}
        onSelectDocument={setSelectedDocId}
      />

      {selectedDocId && activeRunId && (
        <QualityGateResults
          documentId={selectedDocId}
          ingestionId={activeRunId}
          onClose={() => setSelectedDocId(undefined)}
        />
      )}

      <IndexHealthPanel />

      {viewerDocId && (
        <DocumentViewer
          documentId={viewerDocId}
          onClose={() => setViewerDocId(undefined)}
        />
      )}
    </div>
  );
}
