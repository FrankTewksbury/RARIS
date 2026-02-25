# DFW Glossary — DevFlywheel Terminology Reference

> **Location:** This file MUST be accessible to all agents. Store in the project's `docs/` directory
> and in the Obsidian vault at `meta/dfw-glossary.md`.
> **Last Updated:** 2026-02-20

---

## Core Terms

| Term | Definition |
|------|-----------|
| **DFW** | Development Flywheel — the project management and development lifecycle methodology governing all projects. Not an acronym for anything else. When you see "DFW" in any context within this ecosystem, it means DevFlywheel. |
| **DevFlywheel** | Full name for DFW. The meta-project that optimizes the machine that builds everything else. |
| **Flywheel Effect** | The compounding benefit where every session, every project, and every artifact makes the next one better. Context accumulates; it is never discarded. |
| **Constitution** | The set of principles (P1–P9) that govern all agent behavior. Global constitution applies everywhere. Project constitutions extend but never contradict the global one. |
| **Amendment** | A formal change to a principle or rule. Requires explicit rationale and must be tracked. |

## Scope Terms

| Term | Definition |
|------|-----------|
| **Global Scope** | Rules, conventions, and artifacts that apply across ALL projects. Lives in the Obsidian vault (`meta/`, `journal/`) and `~/.claude/CLAUDE.md`. |
| **Project Scope** | Rules, deliverables, and state specific to ONE project. Lives in the project directory. |
| **Subproject Scope** | Feature or component-level work within a project. Inherits project scope. |
| **Scope Bleed** | When project-specific concerns leak into global scope or vice versa. A violation of P7. |

## Artifact Terms

| Term | Definition |
|------|-----------|
| **Sequenced Artifact** | Any file following the `NNN-type-slug.md` naming convention. Provides guaranteed chronological ordering independent of filesystem timestamps. |
| **Structural File** | Files prefixed with `_` (e.g., `_TODO.md`, `_ACTIVE_CONTEXT.md`). These are living documents that get updated in place, not sequenced. |
| **Active Context** | `context/_ACTIVE_CONTEXT.md` — the single most important file in a DFW project. Records current state, what's in progress, and what's next. Read at session start, updated at session close. |
| **Handoff** | A structured document that transfers context between tools or sessions. Lives in `prompts/handoffs/`. The bridge that prevents cold starts. |
| **Retrospective (Retro)** | A post-failure or post-session analysis. Persisted as `NNN-retro-*.md` in `context/`. Failures without retros are wasted learning. |
| **ADR** | Architecture Decision Record — a document capturing a significant design or technology decision, the alternatives considered, and the rationale. |

## Tag Terms

| Term | Definition |
|------|-----------|
| **Tag** | A `#category/value` string embedded in markdown content. Tags are the DFW context language — they encode lifecycle state, priority, origin, and routing in a machine-readable, human-scannable format. |
| **Status Tag** | `#status/<value>` — tracks where a task is in its lifecycle: `backlog → active → build → deploy → done` |
| **Priority Tag** | `#priority/<value>` — ranks urgency: `critical`, `important`, `normal`, `low` |
| **Source Tag** | `#source/<value>` — records where an item originated: `session`, `review`, `dfw-feedback`, `ambiguity`, `manual` |
| **Route Tag** | `#route/<value>` — tells the agent where to file something: `journal`, `todo`, `global`, `project`, `dfw` |
| **DFW Feedback Tag** | `#source/dfw-feedback` — special tag indicating methodology friction that should enter the DFW project's own backlog. This is how the flywheel improves itself. |
| **Ambiguity Tag** | `#source/ambiguity` — special tag indicating a gap that caused confusion (P3). Auto-routes to DFW backlog via `#route/dfw`. |

## Tool Terms

| Term | Definition |
|------|-----------|
| **Claude Desktop** | AI chat interface used for planning, synthesis, research, and reasoning. Connects to Obsidian and Notion via MCP. |
| **Cursor** | AI-enhanced IDE used for flow-state coding, visual implementation, and debugging. |
| **Claude Code** | CLI-based AI agent for autonomous multi-file operations, scripting, and CI/CD. |
| **Obsidian** | Markdown-based knowledge management app. Serves as the long-term memory and global state layer for DFW. |
| **MCP** | Model Context Protocol — the integration layer that allows Claude Desktop to read/write files in project directories and the Obsidian vault. |
| **DFW Extension** | VSCode/Cursor extension (`dfw-project-scaffold`) that scaffolds new DFW projects and enforces directory conventions. |
| **CardBoard** | Obsidian plugin providing Kanban board views over DFW tasks. Boards are views — DFW owns the data (markdown + tags). |

## Session Terms

| Term | Definition |
|------|-----------|
| **Session** | A single working period with an AI agent. Has a defined start (context loading), work phase, and close (context persistence). |
| **Session ID** | `S<YYYYMMDD>_<HHMM>` format identifier linking all artifacts created in the same session. |
| **Cold Start** | When a session begins without context — the exact thing DFW is designed to prevent. |
| **Bootstrap** | The one-time setup that connects a Claude Desktop project to the DFW constitution via Custom Instructions. |

## Persona Terms

| Term | Definition |
|------|-----------|
| **Persona** | The assigned identity for an AI agent within a project. Naming convention: exotic dancer names. Default: Donna. |
| **Donna** | Default persona name (as in Donna Paulsen from Suits). Used when no custom persona is assigned. |

---

*This glossary is a living document. When new DFW terminology is introduced, it MUST be added here.*
