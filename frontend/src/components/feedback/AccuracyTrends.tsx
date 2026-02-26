import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { useAccuracyDashboard } from "../../hooks/useFeedback";

export function AccuracyTrends() {
  const { data: dashboard } = useAccuracyDashboard();

  if (!dashboard || dashboard.trends.length === 0) {
    return (
      <div className="panel">
        <h3>Accuracy Trends</h3>
        <p className="text-muted">No trend data available yet.</p>
      </div>
    );
  }

  const chartData = dashboard.trends.map((t) => ({
    date: t.date,
    accuracy: Math.round(t.accuracy_score * 100),
    resolution: Math.round(t.resolution_rate * 100),
    feedback: t.total_feedback,
  }));

  return (
    <div className="panel">
      <h3>Accuracy Trends</h3>

      <div style={{ marginBottom: "1rem" }}>
        <h4 style={{ marginBottom: "0.5rem", fontSize: "0.9rem" }}>
          Accuracy & Resolution Rate (%)
        </h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis domain={[0, 100]} tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="accuracy"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
              name="Accuracy %"
            />
            <Line
              type="monotone"
              dataKey="resolution"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Resolution %"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h4 style={{ marginBottom: "0.5rem", fontSize: "0.9rem" }}>Total Feedback Over Time</h4>
        <ResponsiveContainer width="100%" height={150}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="feedback"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              name="Total Feedback"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
