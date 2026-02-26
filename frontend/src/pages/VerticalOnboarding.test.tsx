import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { VerticalOnboarding } from "./VerticalOnboarding";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock recharts
vi.mock("recharts", () => ({
  LineChart: () => null,
  Line: () => null,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
}));

// Mock hooks
vi.mock("../hooks/useVerticals", () => ({
  useVerticalList: () => ({ data: [], isLoading: false }),
  useVertical: () => ({ data: null }),
  useVerticalStatus: () => ({ data: null }),
  useCreateVertical: () => ({ mutate: vi.fn(), isPending: false }),
  useTriggerDiscovery: () => ({ mutate: vi.fn(), isPending: false }),
  useTriggerAcquisition: () => ({ mutate: vi.fn(), isPending: false }),
  useTriggerIngestion: () => ({ mutate: vi.fn(), isPending: false }),
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

describe("VerticalOnboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderWithProviders(<VerticalOnboarding />);
    expect(screen.getByText("Vertical Onboarding")).toBeInTheDocument();
  });
});
