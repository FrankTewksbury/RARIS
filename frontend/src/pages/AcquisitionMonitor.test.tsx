import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AcquisitionMonitor } from "./AcquisitionMonitor";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock hooks
vi.mock("../hooks/useManifests", () => ({
  useManifestList: () => ({ data: [], isLoading: false }),
}));

vi.mock("../hooks/useAcquisitions", () => ({
  useAcquisition: () => ({ data: null }),
  useAcquisitionList: () => ({ data: [], isLoading: false }),
  useAcquisitionSources: () => ({ data: null }),
  useStartAcquisition: () => ({ mutate: vi.fn(), isPending: false }),
  useRetrySource: () => ({ mutate: vi.fn() }),
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

describe("AcquisitionMonitor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderWithProviders(<AcquisitionMonitor />);
    expect(screen.getByText("RARIS — Acquisition Monitor")).toBeInTheDocument();
  });

  it("renders without active run", () => {
    renderWithProviders(<AcquisitionMonitor />);
    // Should render the page without crashing when no run is selected
    expect(document.querySelector(".dashboard")).toBeInTheDocument();
  });
});
