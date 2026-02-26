import { useState } from "react";
import { VerticalRegistry } from "../components/verticals/VerticalRegistry";
import { NewVerticalWizard } from "../components/verticals/NewVerticalWizard";
import { PipelineTracker } from "../components/verticals/PipelineTracker";
import { CrossVerticalDashboard } from "../components/verticals/CrossVerticalDashboard";

export function VerticalOnboarding() {
  const [activeVerticalId, setActiveVerticalId] = useState<string>();
  const [showWizard, setShowWizard] = useState(false);

  return (
    <div className="dashboard">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Vertical Onboarding</h2>
        <button onClick={() => setShowWizard(true)} disabled={showWizard}>
          New Vertical
        </button>
      </div>

      {showWizard && (
        <NewVerticalWizard
          onCreated={(id) => {
            setActiveVerticalId(id);
            setShowWizard(false);
          }}
          onCancel={() => setShowWizard(false)}
        />
      )}

      <VerticalRegistry activeId={activeVerticalId} onSelect={setActiveVerticalId} />

      {activeVerticalId && <PipelineTracker verticalId={activeVerticalId} />}

      <CrossVerticalDashboard />
    </div>
  );
}
