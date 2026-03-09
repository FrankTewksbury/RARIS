import { useState } from "react";
import type { Program } from "../types/manifest";

interface Props {
  programs: Program[];
}

const PAGE_SIZE = 25;

type GeoFilter = Program["geo_scope"] | "";
type StatusFilter = Program["status"] | "";

export function ProgramsTable({ programs }: Props) {
  const [filterGeo, setFilterGeo] = useState<GeoFilter>("");
  const [filterStatus, setFilterStatus] = useState<StatusFilter>("");
  const [filterReview, setFilterReview] = useState<boolean | "">("");
  const [page, setPage] = useState(0);

  let filtered = [...programs];
  if (filterGeo) filtered = filtered.filter((p) => p.geo_scope === filterGeo);
  if (filterStatus) filtered = filtered.filter((p) => p.status === filterStatus);
  if (filterReview !== "") filtered = filtered.filter((p) => p.needs_human_review === filterReview);

  filtered.sort((a, b) => b.confidence - a.confidence);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div className="panel sources-table-panel">
      <h2>Programs ({filtered.length})</h2>

      <div className="filters">
        <select
          value={filterGeo}
          onChange={(e) => { setFilterGeo(e.target.value as GeoFilter); setPage(0); }}
        >
          <option value="">All Scopes</option>
          <option value="national">National</option>
          <option value="state">State</option>
          <option value="county">County</option>
          <option value="city">City</option>
          <option value="tribal">Tribal</option>
        </select>

        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value as StatusFilter); setPage(0); }}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="closed">Closed</option>
          <option value="verification_pending">Pending Verification</option>
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
            <th>Name</th>
            <th>Entity</th>
            <th>Scope</th>
            <th>Benefits</th>
            <th>Status</th>
            <th>Confidence</th>
            <th>Review</th>
            <th>Sources</th>
          </tr>
        </thead>
        <tbody>
          {paged.map((program) => (
            <tr key={program.id} className={program.needs_human_review ? "needs-review" : ""}>
              <td>{program.name}</td>
              <td>{program.administering_entity}</td>
              <td>{program.geo_scope}</td>
              <td className="cell-truncate" title={program.benefits}>{program.benefits}</td>
              <td>
                <span className={`badge badge-${program.status === "active" ? "success" : program.status === "paused" ? "warning" : "neutral"}`}>
                  {program.status.replace("_", " ")}
                </span>
              </td>
              <td className={program.confidence < 0.7 ? "score-red" : "score-green"}>
                {(program.confidence * 100).toFixed(0)}%
              </td>
              <td>{program.needs_human_review ? "\u26A0" : "\u2713"}</td>
              <td>
                {program.source_urls.length > 0 ? (
                  <a href={program.source_urls[0]} target="_blank" rel="noopener noreferrer" title={program.source_urls.join("\n")}>
                    {program.source_urls.length} link{program.source_urls.length > 1 ? "s" : ""}
                  </a>
                ) : (
                  <span className="text-muted">none</span>
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
