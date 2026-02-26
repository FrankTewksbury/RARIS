import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryInterface } from "./QueryInterface";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock recharts
vi.mock("recharts", () => ({
  LineChart: () => null,
  Line: () => null,
  BarChart: () => null,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
}));

// Mock hooks
vi.mock("../hooks/useRetrieval", () => ({
  useSubmitQuery: () => ({ mutate: vi.fn(), isPending: false, data: null }),
  useQueryResult: () => ({ data: null }),
  useSubmitAnalysis: () => ({ mutate: vi.fn(), isPending: false, data: null }),
  useAnalysisResult: () => ({ data: null }),
  useCorpusStats: () => ({
    data: {
      total_documents: 100,
      indexed_documents: 95,
      total_chunks: 5000,
      indexed_chunks: 4800,
      by_jurisdiction: {},
      by_document_type: {},
      by_regulatory_body: {},
    },
  }),
  useCorpusSources: () => ({ data: [] }),
  useCitation: () => ({ data: null }),
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

describe("QueryInterface", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderWithProviders(<QueryInterface />);
    expect(screen.getByText("Query Interface")).toBeInTheDocument();
  });
});
