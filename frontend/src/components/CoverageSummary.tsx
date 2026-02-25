import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import type { CoverageAssessment } from "../types/manifest";

interface Props {
  coverage: CoverageAssessment;
}

const COLORS = ["#2563eb", "#16a34a", "#eab308", "#ef4444", "#8b5cf6", "#ec4899"];

const SEVERITY_COLORS: Record<string, string> = {
  high: "#ef4444",
  medium: "#eab308",
  low: "#3b82f6",
};

export function CoverageSummary({ coverage }: Props) {
  const jurisdictionData = Object.entries(coverage.by_jurisdiction).map(([name, value]) => ({
    name,
    count: value,
  }));

  const typeData = Object.entries(coverage.by_type).map(([name, value]) => ({
    name,
    value,
  }));

  return (
    <div className="panel coverage-summary-panel">
      <h2>Coverage Assessment</h2>

      <div className="coverage-grid">
        <div className="chart-section">
          <h3>By Jurisdiction</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={jurisdictionData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="chart-section">
          <h3>By Type</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={typeData} dataKey="value" nameKey="name" outerRadius={70} label>
                {typeData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {coverage.known_gaps.length > 0 && (
        <div className="gaps-section">
          <h3>Known Gaps</h3>
          <ul>
            {coverage.known_gaps.map((gap, i) => (
              <li key={i}>
                <span
                  className="severity-badge"
                  style={{ backgroundColor: SEVERITY_COLORS[gap.severity] }}
                >
                  {gap.severity}
                </span>
                {gap.description}
                {gap.mitigation && <em> — {gap.mitigation}</em>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
