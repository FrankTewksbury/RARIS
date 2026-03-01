import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DomainInputPanel } from "./DomainInputPanel";

describe("DomainInputPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders upload controls and seeding button", () => {
    render(
      <DomainInputPanel
        onGenerate={vi.fn()}
        isGenerating={false}
      />,
    );

    expect(screen.getByRole("button", { name: "Upload Constitution" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload Instruction / Guidance" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seeding" })).toBeInTheDocument();
  });

  it("submits discovery request as multipart form data", async () => {
    const onGenerate = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        manifest_id: "manifest-123",
        status: "generating",
        stream_url: "/api/manifests/manifest-123/stream",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DomainInputPanel
        onGenerate={onGenerate}
        isGenerating={false}
      />,
    );

    fireEvent.change(
      screen.getByPlaceholderText(/Describe the regulatory domain/i),
      { target: { value: "US insurance regulation" } },
    );

    const constitutionFile = new File(["constitution"], "constitution.md", { type: "text/markdown" });
    const instructionFile = new File(["instruction"], "instruction.txt", { type: "text/plain" });
    const seedFileA = new File(["{\"url\":\"https://example.gov\"}"], "seed.json", { type: "application/json" });
    const seedFileB = new File(["name,url\nExample,https://example.com"], "seed.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText("Constitution file upload"), {
      target: { files: [constitutionFile] },
    });
    fireEvent.change(screen.getByLabelText("Instruction file upload"), {
      target: { files: [instructionFile] },
    });
    fireEvent.change(screen.getByLabelText("Seeding file upload"), {
      target: { files: [seedFileA, seedFileB] },
    });

    fireEvent.click(screen.getByRole("button", { name: "Generate Manifest" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/manifests/generate");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);

    const formData = options.body as FormData;
    expect(formData.get("domain_description")).toBe("US insurance regulation");
    expect(formData.get("llm_provider")).toBe("openai");
    expect(formData.get("k_depth")).toBe("2");
    expect(formData.get("geo_scope")).toBe("state");
    expect(formData.get("constitution_file")).toBeInstanceOf(File);
    expect(formData.get("instruction_file")).toBeInstanceOf(File);
    expect(formData.getAll("seeding_files")).toHaveLength(2);

    await waitFor(() =>
      expect(onGenerate).toHaveBeenCalledWith("manifest-123", "/api/manifests/manifest-123/stream"),
    );
  });
});
