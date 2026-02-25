import { useState } from "react";
import type { ManifestDetail, ReviewRequest } from "../types/manifest";

interface Props {
  manifest: ManifestDetail;
  onApprove: (review: ReviewRequest) => void;
  onReject: (review: ReviewRequest) => void;
}

export function ManifestActions({ manifest, onApprove, onReject }: Props) {
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [notes, setNotes] = useState("");
  const [reviewer] = useState("frank");

  const unreviewedCount = manifest.sources.filter((s) => s.needs_human_review).length;
  const canApprove = unreviewedCount === 0 && manifest.status === "pending_review";

  return (
    <div className="panel manifest-actions-panel">
      <h2>Actions</h2>

      <div className="action-buttons">
        <button
          className="btn btn-approve"
          disabled={!canApprove}
          onClick={() => onApprove({ reviewer, notes: "Approved — all sources verified." })}
          title={!canApprove ? `${unreviewedCount} sources still need review` : "Approve manifest"}
        >
          Approve Manifest
          {unreviewedCount > 0 && ` (${unreviewedCount} unreviewed)`}
        </button>

        <button
          className="btn btn-reject"
          disabled={manifest.status !== "pending_review"}
          onClick={() => setShowRejectModal(true)}
        >
          Request Revision
        </button>
      </div>

      {showRejectModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Request Revision</h3>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Describe what needs to be revised..."
              rows={4}
            />
            <div className="modal-actions">
              <button
                className="btn btn-reject"
                onClick={() => {
                  onReject({ reviewer, notes });
                  setShowRejectModal(false);
                  setNotes("");
                }}
              >
                Submit
              </button>
              <button className="btn" onClick={() => setShowRejectModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
