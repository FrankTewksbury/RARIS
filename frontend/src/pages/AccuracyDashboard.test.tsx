import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AccuracyDashboard } from "./AccuracyDashboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock recharts to avoid canvas rendering issues in jsdom
vi.mock("recharts", () => ({
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
}));

// Mock the hooks
vi.mock("../hooks/useFeedback", () => ({
  useFeedbackList: () => ({ data: [], isLoading: false }),
  useResolveFeedback: () => ({ mutate: vi.fn(), isPending: false }),
  useCurationQueue: () => ({ data: [], isLoading: false }),
  useProcessQueueItem: () => ({ mutate: vi.fn(), isPending: false }),
  useChangeList: () => ({ data: [], isLoading: false }),
  useTriggerMonitor: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false, data: null }),
  useAccuracyDashboard: () => ({
    data: {
      current: {
        total_feedback: 50,
        correct_count: 40,
        inaccurate_count: 5,
        outdated_count: 3,
        incomplete_count: 1,
        irrelevant_count: 1,
        accuracy_score: 0.889,
        resolution_rate: 0.92,
        avg_source_confidence: 0.85,
        stale_sources: 0,
        pending_queue_items: 2,
        unresolved_changes: 1,
      },
      trends: [],
      by_feedback_type: { correct: 40, inaccurate: 5 },
      by_vertical: { Insurance: 0.92 },
    },
    isLoading: false,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AccuracyDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page title", () => {
    renderWithProviders(<AccuracyDashboard />);
    expect(screen.getByText("Accuracy & Feedback")).toBeInTheDocument();
  });

  it("renders all tab buttons", () => {
    renderWithProviders(<AccuracyDashboard />);
    // "Corpus Health" appears both in tab and panel heading
    expect(screen.getAllByText("Corpus Health").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Feedback")).toBeInTheDocument();
    expect(screen.getByText("Re-Curation Queue")).toBeInTheDocument();
    expect(screen.getByText("Change Monitor")).toBeInTheDocument();
  });

  it("shows corpus health by default", () => {
    renderWithProviders(<AccuracyDashboard />);
    // Should show accuracy metrics from mocked data
    expect(screen.getByText("89%")).toBeInTheDocument(); // accuracy_score rounded
    expect(screen.getByText("92%")).toBeInTheDocument(); // resolution_rate rounded
    expect(screen.getByText("Accuracy")).toBeInTheDocument();
  });

  it("shows total feedback count", () => {
    renderWithProviders(<AccuracyDashboard />);
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText("Total Feedback")).toBeInTheDocument();
  });
});
