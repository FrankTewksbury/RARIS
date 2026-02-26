import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CurationDashboard } from "./CurationDashboard";
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

// Mock hooks used by child components
vi.mock("../hooks/useIngestion", () => ({
  useIngestionRun: () => ({ data: null }),
  useIngestionDocuments: () => ({ data: [] }),
  useDocument: () => ({ data: null }),
  useStartIngestion: () => ({ mutate: vi.fn(), isPending: false }),
  useApproveDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useRejectDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useIndexStats: () => ({ data: null, isLoading: false }),
}));

vi.mock("../hooks/useAcquisitions", () => ({
  useAcquisitionList: () => ({ data: [], isLoading: false }),
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

describe("CurationDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderWithProviders(<CurationDashboard />);
    expect(screen.getByText("Ingestion & Curation")).toBeInTheDocument();
  });

  it("renders without active run", () => {
    renderWithProviders(<CurationDashboard />);
    expect(document.querySelector(".dashboard")).toBeInTheDocument();
  });
});
