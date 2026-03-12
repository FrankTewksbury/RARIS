---
type: note
created: 2026-03-11T12:00:00
sessionId: S20260311_0000
source: cursor-agent
description: Registry of Gemini API accounts used for RARIS project
---

# Gemini Account Registry — RARIS Project

## Account 1 — GCP API

| Field | Value |
|---|---|
| **Account** | NTecAccount (Google Cloud Platform) |
| **Project** | RARIS |
| **API Type** | GCP Vertex AI / Gemini API via GCP project |
| **Usage** | Primary backend LLM provider for discovery runs |
| **Key Location** | `.env` → `GEMINI_API_KEY` |

## Account 2 — AI Studio (Personal)

| Field | Value |
|---|---|
| **Account** | Personal Google account |
| **Project** | RARIS (AI Studio project) |
| **API Type** | Google AI Studio API key |
| **Usage** | Secondary / fallback; personal quota |
| **Key Location** | `.env` → `GEMINI_API_KEY` (swap as needed) |

## Quota Reference

| Tier | RPM | TPM | RPD |
|---|---|---|---|
| Free Tier | 15 | 1M | 1,500 |
| Paid Tier 1 | 150–300 | 1M | 1,500 |

## Notes

- The **1,500 RPD cap** is the binding constraint for long BFS discovery runs (504+ queue items).
- When one account hits its daily quota, swap the API key to the other account.
- GCP NTecAccount project quota may differ from AI Studio personal quota — check GCP console for current limits.
- Pacing the engine to ≤15 RPM (1 call every 4 seconds) keeps runs within Free Tier RPM; paid tier allows faster pacing.
- Model in use: `gemini-3.1-pro-preview` — consider `gemini-2.0-flash` for BFS expansion (higher quota, lower cost, sufficient quality for statute enumeration).
