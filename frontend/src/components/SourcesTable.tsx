import { useState } from "react";
import type { Source, Jurisdiction, SourceType } from "../types/manifest";

interface Props {
  sources: Source[];
  onUpdateSource: (sourceId: string, update: Partial<Source>) => void;
}

const PAGE_SIZE = 25;

export function SourcesTable({ sources, onUpdateSource }: Props) {
  const [filterJurisdiction, setFilterJurisdiction] = useState<Jurisdiction | "">("");
  const [filterType, setFilterType] = useState<SourceType | "">("");
  const [filterReview, setFilterReview] = useState<boolean | "">("");
  const [page, setPage] = useState(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editUrl, setEditUrl] = useState("");

  let filtered = [...sources];
  if (filterJurisdiction) filtered = filtered.filter((s) => s.jurisdiction === filterJurisdiction);
  if (filterType) filtered = filtered.filter((s) => s.type === filterType);
  if (filterReview !== "") filtered = filtered.filter((s) => s.needs_human_review === filterReview);

  // Sort by confidence ascending (low confidence first for review prioritization)
  filtered.sort((a, b) => a.confidence - b.confidence);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const startEdit = (source: Source) => {
    setEditingId(source.id);
    setEditName(source.name);
    setEditUrl(source.url);
  };

  const saveEdit = (sourceId: string) => {
    onUpdateSource(sourceId, { name: editName, url: editUrl });
    setEditingId(null);
  };

  const markReviewed = (sourceId: string) => {
    onUpdateSource(sourceId, { needs_human_review: false, review_notes: "Reviewed" });
  };

  return (
    <div className="panel sources-table-panel">
      <h2>Sources ({filtered.length})</h2>

      <div className="filters">
        <select
          value={filterJurisdiction}
          onChange={(e) => { setFilterJurisdiction(e.target.value as Jurisdiction | ""); setPage(0); }}
        >
          <option value="">All Jurisdictions</option>
          <option value="federal">Federal</option>
          <option value="state">State</option>
          <option value="municipal">Municipal</option>
        </select>

        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value as SourceType | ""); setPage(0); }}
        >
          <option value="">All Types</option>
          {["statute", "regulation", "guidance", "standard", "educational", "guide"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        <select
          value={String(filterReview)}
          onChange={(e) => {
            const v = e.target.value;
            setFilterReview(v === "" ? "" : v === "true");
            setPage(0);
          }}
        >
          <option value="">All Review Status</option>
          <option value="true">Needs Review</option>
          <option value="false">Reviewed</option>
        </select>
      </div>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Body</th>
            <th>Type</th>
            <th>Format</th>
            <th>Authority</th>
            <th>Jurisdiction</th>
            <th>Confidence</th>
            <th>Review</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {paged.map((source) => (
            <tr key={source.id} className={source.needs_human_review ? "needs-review" : ""}>
              <td>{source.id}</td>
              <td>
                {editingId === source.id ? (
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} />
                ) : (
                  source.name
                )}
              </td>
              <td>{source.regulatory_body}</td>
              <td>{source.type}</td>
              <td>{source.format}</td>
              <td>{source.authority}</td>
              <td>{source.jurisdiction}</td>
              <td className={source.confidence < 0.7 ? "score-red" : "score-green"}>
                {(source.confidence * 100).toFixed(0)}%
              </td>
              <td>{source.needs_human_review ? "\u26A0" : "\u2713"}</td>
              <td>
                {editingId === source.id ? (
                  <>
                    <button className="btn-sm" onClick={() => saveEdit(source.id)}>Save</button>
                    <button className="btn-sm" onClick={() => setEditingId(null)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <button className="btn-sm" onClick={() => startEdit(source)}>Edit</button>
                    {source.needs_human_review && (
                      <button className="btn-sm" onClick={() => markReviewed(source.id)}>
                        Approve
                      </button>
                    )}
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>Prev</button>
          <span>Page {page + 1} of {totalPages}</span>
          <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}
