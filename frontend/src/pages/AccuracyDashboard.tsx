import { useState } from "react";
import { CorpusHealth } from "../components/feedback/CorpusHealth";
import { AccuracyTrends } from "../components/feedback/AccuracyTrends";
import { FeedbackFeed } from "../components/feedback/FeedbackFeed";
import { ReCurationQueue } from "../components/feedback/ReCurationQueue";
import { ChangeMonitor } from "../components/feedback/ChangeMonitor";

type Tab = "health" | "feedback" | "queue" | "changes";

export function AccuracyDashboard() {
  const [tab, setTab] = useState<Tab>("health");

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Accuracy & Feedback</h2>

      <div style={{ display: "flex", gap: "0.25rem", marginBottom: "1rem" }}>
        {([
          { key: "health", label: "Corpus Health" },
          { key: "feedback", label: "Feedback" },
          { key: "queue", label: "Re-Curation Queue" },
          { key: "changes", label: "Change Monitor" },
        ] as const).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "0.4rem 0.75rem",
              fontSize: "0.85rem",
              fontWeight: tab === t.key ? 700 : 400,
              borderBottom: tab === t.key ? "2px solid var(--primary)" : "2px solid transparent",
              background: "none",
              border: "none",
              borderBottomWidth: "2px",
              borderBottomStyle: "solid",
              borderBottomColor: tab === t.key ? "var(--primary)" : "transparent",
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "health" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <CorpusHealth />
          <AccuracyTrends />
        </div>
      )}
      {tab === "feedback" && <FeedbackFeed />}
      {tab === "queue" && <ReCurationQueue />}
      {tab === "changes" && <ChangeMonitor />}
    </div>
  );
}
