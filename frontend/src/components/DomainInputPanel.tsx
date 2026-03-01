import { useRef, useState } from "react";
import type { GenerateResponse } from "../types/manifest";

interface Props {
  onGenerate: (manifestId: string, streamUrl: string) => void;
  isGenerating: boolean;
}

const LLM_PROVIDERS = ["openai", "anthropic", "gemini"];
const GEO_SCOPES = ["national", "state", "municipal"] as const;
const ACCEPTED_FILE_TYPES = ".txt,.md,.pdf,.docx";
const ACCEPTED_SEED_TYPES = ".json,.jsonl,.csv,.txt,.md";
const SUPPORTED_EXTENSIONS = [".txt", ".md", ".pdf", ".docx"];
const SUPPORTED_SEED_EXTENSIONS = [".json", ".jsonl", ".csv", ".txt", ".md"];

export function DomainInputPanel({ onGenerate, isGenerating }: Props) {
  const [domain, setDomain] = useState("");
  const [provider, setProvider] = useState("openai");
  const [kDepth, setKDepth] = useState(2);
  const [geoScope, setGeoScope] = useState<(typeof GEO_SCOPES)[number]>("state");
  const [targetSegments, setTargetSegments] = useState("");
  const [constitutionFile, setConstitutionFile] = useState<File | null>(null);
  const [instructionFile, setInstructionFile] = useState<File | null>(null);
  const [seedingFiles, setSeedingFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const constitutionInputRef = useRef<HTMLInputElement>(null);
  const instructionInputRef = useRef<HTMLInputElement>(null);
  const seedingInputRef = useRef<HTMLInputElement>(null);

  const isSupportedFile = (file: File) => {
    const filename = file.name.toLowerCase();
    return SUPPORTED_EXTENSIONS.some((ext) => filename.endsWith(ext));
  };

  const isSupportedSeedFile = (file: File) => {
    const filename = file.name.toLowerCase();
    return SUPPORTED_SEED_EXTENSIONS.some((ext) => filename.endsWith(ext));
  };

  const handleFileSelection = (
    file: File | null,
    setFile: (value: File | null) => void,
  ) => {
    if (!file) return;
    if (!isSupportedFile(file)) {
      setError("Unsupported file type. Use .txt, .md, .pdf, or .docx.");
      return;
    }
    setError(null);
    setFile(file);
  };

  const handleSeedingSelection = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const selected = Array.from(files);
    const invalid = selected.find((file) => !isSupportedSeedFile(file));
    if (invalid) {
      setError("Unsupported seed file type. Use .json, .jsonl, .csv, .txt, or .md.");
      return;
    }
    setError(null);
    setSeedingFiles((current) => {
      const dedup = new Map(current.map((file) => [file.name, file]));
      selected.forEach((file) => dedup.set(file.name, file));
      return Array.from(dedup.values());
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setError(null);

    try {
      const formData = new FormData();
      formData.append("domain_description", domain.trim());
      formData.append("llm_provider", provider);
      formData.append("k_depth", String(kDepth));
      formData.append("geo_scope", geoScope);
      if (targetSegments.trim()) {
        formData.append("target_segments", targetSegments.trim());
      }
      if (constitutionFile) formData.append("constitution_file", constitutionFile);
      if (instructionFile) formData.append("instruction_file", instructionFile);
      seedingFiles.forEach((file) => formData.append("seeding_files", file));

      const response = await fetch("/api/manifests/generate", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error("Generation request failed");
      const data: GenerateResponse = await response.json();
      onGenerate(data.manifest_id, data.stream_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  return (
    <div className="panel domain-input-panel">
      <h2>Domain Discovery</h2>
      <form onSubmit={handleSubmit}>
        <textarea
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="Describe the regulatory domain to discover (e.g., 'All US Insurance regulation — federal + all 50 states')"
          rows={4}
          disabled={isGenerating}
        />
        <div className="upload-row">
          <input
            ref={constitutionInputRef}
            type="file"
            aria-label="Constitution file upload"
            accept={ACCEPTED_FILE_TYPES}
            hidden
            onChange={(e) => handleFileSelection(e.target.files?.[0] ?? null, setConstitutionFile)}
            disabled={isGenerating}
          />
          <button
            type="button"
            onClick={() => constitutionInputRef.current?.click()}
            disabled={isGenerating}
          >
            Upload Constitution
          </button>
          {constitutionFile && (
            <span className="upload-filename">
              {constitutionFile.name}
              <button
                type="button"
                className="btn-sm"
                onClick={() => setConstitutionFile(null)}
                disabled={isGenerating}
              >
                Clear
              </button>
            </span>
          )}
        </div>

        <div className="upload-row">
          <input
            ref={instructionInputRef}
            type="file"
            aria-label="Instruction file upload"
            accept={ACCEPTED_FILE_TYPES}
            hidden
            onChange={(e) => handleFileSelection(e.target.files?.[0] ?? null, setInstructionFile)}
            disabled={isGenerating}
          />
          <button
            type="button"
            onClick={() => instructionInputRef.current?.click()}
            disabled={isGenerating}
          >
            Upload Instruction / Guidance
          </button>
          {instructionFile && (
            <span className="upload-filename">
              {instructionFile.name}
              <button
                type="button"
                className="btn-sm"
                onClick={() => setInstructionFile(null)}
                disabled={isGenerating}
              >
                Clear
              </button>
            </span>
          )}
        </div>

        <div className="upload-row">
          <input
            ref={seedingInputRef}
            type="file"
            aria-label="Seeding file upload"
            accept={ACCEPTED_SEED_TYPES}
            multiple
            hidden
            onChange={(e) => handleSeedingSelection(e.target.files)}
            disabled={isGenerating}
          />
          <button
            type="button"
            onClick={() => seedingInputRef.current?.click()}
            disabled={isGenerating}
          >
            Seeding
          </button>
          {seedingFiles.length > 0 && (
            <span className="upload-filename">
              {seedingFiles.length} file(s) queued
              <button
                type="button"
                className="btn-sm"
                onClick={() => setSeedingFiles([])}
                disabled={isGenerating}
              >
                Clear All
              </button>
            </span>
          )}
        </div>
        {seedingFiles.length > 0 && (
          <div className="seed-files-list">
            {seedingFiles.map((file) => (
              <div key={file.name} className="seed-file-item">
                <span>{file.name}</span>
                <span className="seed-status">queued</span>
                <button
                  type="button"
                  className="btn-sm"
                  onClick={() => setSeedingFiles((current) => current.filter((f) => f.name !== file.name))}
                  disabled={isGenerating}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="form-row">
          <label>
            K Depth:
            <input
              type="number"
              min={1}
              max={4}
              value={kDepth}
              onChange={(e) => setKDepth(Number(e.target.value))}
              disabled={isGenerating}
            />
          </label>
          <label>
            Geo Scope:
            <select
              value={geoScope}
              onChange={(e) => setGeoScope(e.target.value as (typeof GEO_SCOPES)[number])}
              disabled={isGenerating}
            >
              {GEO_SCOPES.map((scope) => (
                <option key={scope} value={scope}>{scope}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="form-row">
          <label className="target-segments-label">
            Target Segments (comma-separated):
            <input
              type="text"
              value={targetSegments}
              onChange={(e) => setTargetSegments(e.target.value)}
              placeholder="homeowners, commercial, flood"
              disabled={isGenerating}
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            LLM Provider:
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={isGenerating}
            >
              {LLM_PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={isGenerating || !domain.trim()}>
            {isGenerating ? "Generating..." : "Generate Manifest"}
          </button>
        </div>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
