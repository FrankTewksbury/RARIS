import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Dashboard } from "./Dashboard";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

// Mock hooks
vi.mock("../hooks/useManifests", () => ({
  useManifest: () => ({ data: null, refetch: vi.fn() }),
  useManifestList: () => ({ data: [], isLoading: false }),
  useUpdateSource: () => ({ mutate: vi.fn() }),
  useApproveManifest: () => ({ mutate: vi.fn() }),
  useRejectManifest: () => ({ mutate: vi.fn() }),
}));

vi.mock("../hooks/useSSE", () => ({
  useSSE: () => ({
    events: [],
    isConnected: false,
    connect: vi.fn(),
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

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderWithProviders(<Dashboard />);
    expect(screen.getByText("RARIS — Domain Discovery")).toBeInTheDocument();
  });

  it("renders domain input panel", () => {
    renderWithProviders(<Dashboard />);
    // DomainInputPanel should be present
    expect(document.querySelector(".dashboard-content")).toBeInTheDocument();
  });

  it("does not render manifest details without active manifest", () => {
    renderWithProviders(<Dashboard />);
    // No manifest list when empty
    expect(screen.queryByText("Manifests")).not.toBeInTheDocument();
  });
});
