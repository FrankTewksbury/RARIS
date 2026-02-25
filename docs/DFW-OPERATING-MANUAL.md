# DFW Operating Manual — Development Flywheel Methodology

> **This is the DFW operating manual.** It defines the tools, processes, and conventions
> that make the Development Flywheel work. The constitution (`DFW-CONSTITUTION.md`) defines the
> principles and rules. This document defines the **how**.
>
> **If you are an AI agent reading this file, you were directed here by the constitution or model file.**
> Everything in this document is mandatory. Treat it with the same authority as the constitution.

---

## 1. What DFW Is — Read This First

**DFW stands for Development Flywheel.** It is the mandatory project management and development lifecycle methodology for every project in this ecosystem.

- Every project we **create** follows DFW from day one.
- Every project we **adopt** (existing codebase, inherited repo) gets migrated to DFW.
- Every AI agent working in this ecosystem operates under DFW rules.
- There are no DFW-exempt projects.

**The core thesis:** Context, memory, state, rules, and skills compound across sessions and projects. Every project makes the next one better. Every session starts where the last one left off — not from zero. This compounding effect is the flywheel.

**If you are an agent and you don't know what DFW is, re-read this section. Do not proceed until you understand it.**

---

## 2. The Three-Tier Scope Model

All work exists at one of three scope levels. The scope level determines where artifacts live, which rules apply, and how context flows.

| Tier | Where It Lives | What Belongs Here | Examples |
|------|---------------|-------------------|----------|
| **Global** | Obsidian vault (`meta/`, `journal/`) + `~/.claude/CLAUDE.md` | Cross-project rules, methodology, daily journals, tag taxonomy | Tag routing, scope rules, DFW principles, journal entries |
| **Project** | Project directory (`<project>/`) + project `CLAUDE.md` | Project-specific deliverables, state, decisions, context | Specs, plans, TODOs, active context, ADRs, code |
| **Subproject** | Subdirectory within a project | Feature or component-level work | Feature branch context, sprint-level state |

**The rule:** Global scope serves all projects. Project scope serves one. Never let project concerns pollute global scope, and never let global conventions be overridden locally without explicit amendment.

---

## 3. DFW Standard Directory Structure

Every DFW project MUST have this directory structure. The DFW Extension scaffolds it automatically. If adopting an existing project, these directories MUST be created.

```
<project-root>/
├── .dfw/                    # DFW metadata — project identity, constitution
│   ├── project.json         # Project manifest (name, type, version, DFW version)
│   ├── constitution.json    # Project-level rules (tool conventions, naming)
│   └── personal-config.md   # Environment-specific paths and tool mappings (NOT committed)
├── docs/                    # Long-lived documentation, specs, ADRs, architecture
│   ├── DFW-GLOSSARY.md      # DFW terminology reference (copy from template)
│   └── DFW-OPERATING-MANUAL.md  # This file (copy from template)
├── plans/                   # TODOs, roadmaps, wishlists, sprint plans
│   └── _TODO.md             # Active task list (structural file, not sequenced)
├── prompts/                 # System prompts, handoffs, reusable templates
│   └── handoffs/            # Tool-to-tool and session-to-session handoffs
├── context/                 # Active context, decisions, retrospectives
│   ├── _ACTIVE_CONTEXT.md   # Current state — what we're working on NOW
│   └── _DECISIONS_LOG.md    # Running log of architectural/design decisions
├── research/                # Research artifacts, analysis, reference material
├── scripts/                 # Automation, hooks, utility scripts
├── tests/                   # Test artifacts
├── CLAUDE.md                # Project-specific agent constitution
└── README.md                # Project overview
```

---

## 4. DFW Tagging — The Context Language

Tags are the DFW context language. They encode lifecycle state, priority, origin, and routing in a format that is both machine-readable and human-scannable. Every AI agent MUST understand and apply DFW tags correctly.

**Format:** `#category/value` — always lowercase, always this structure.

### 4.1 Status Tags — Task Lifecycle

Status tags track where a task sits in its lifecycle. Every task in `_TODO.md` and every task-bearing markdown file MUST have exactly one status tag.

```
#status/backlog → #status/active → #status/build → #status/deploy → #status/done
```

| Tag | Meaning | When to Apply |
|-----|---------|---------------|
| `#status/backlog` | Identified but not started | New task discovered during a session |
| `#status/active` | Currently being worked on | Task picked up for the current session or sprint |
| `#status/build` | In implementation | Code is being written, artifact is being produced |
| `#status/deploy` | Built, awaiting validation or deployment | Implementation complete, pending review |
| `#status/done` | Complete | Task finished — add `@completed(YYYY-MM-DDTHH:MM:SS-TZ)` timestamp |

**Completion convention:** When marking a task done, append a timestamp:
```markdown
- [x] Implement login flow #status/done @completed(2026-02-20T14:30:00-05:00)
```

### 4.2 Priority Tags

Every new task MUST receive both a `#status/` tag AND a `#priority/` tag at creation.

| Tag | Meaning |
|-----|---------|
| `#priority/critical` | Blocking other work. Address immediately. |
| `#priority/important` | High impact. Address this session or next. |
| `#priority/normal` | Standard priority. Scheduled in normal flow. |
| `#priority/low` | Nice to have. Address when bandwidth allows. |

### 4.3 Source Tags — Where It Came From

Source tags record the origin of a task or artifact. This enables traceability.

| Tag | Meaning |
|-----|---------|
| `#source/session` | Created during a working session |
| `#source/review` | Created during code review or retrospective |
| `#source/dfw-feedback` | Methodology friction discovered during product work — auto-routes to the DFW project backlog |
| `#source/ambiguity` | Created when P3 (Ambiguity Stops Work) was triggered — records a gap that caused confusion. **Auto-routes to DFW backlog** alongside `#route/dfw` so the methodology can be improved to prevent recurrence. |
| `#source/manual` | Manually added by a human outside a session |

### 4.4 Route Tags — Where the Agent Should Put It

When an item surfaces mid-conversation and needs to be filed, route tags tell the agent where it belongs.

| Tag | Meaning |
|-----|---------|
| `#route/todo` | Add to the current project's `plans/_TODO.md` |
| `#route/journal` | Include in the session's journal entry |
| `#route/global` | This applies across projects — route to Obsidian global scope |
| `#route/project` | This is project-specific — keep in the project directory |
| `#route/dfw` | This is methodology feedback — route to the DevFlywheel project backlog |

### 4.5 Tagging Rules for Agents

These are enforceable. All agents MUST follow them.

1. **Every new task** created by an agent MUST have both `#status/` and `#priority/` tags.
2. **Every completed task** MUST have `#status/done` and an `@completed()` timestamp.
3. **Every methodology friction item** MUST be tagged `#source/dfw-feedback #route/dfw`.
4. **Every ambiguity resolution** MUST be tagged `#source/ambiguity #route/dfw` — ambiguity always auto-routes to the DFW backlog so the methodology can be improved.
5. **When routing is unclear**, ask the user (P3) — do not guess the route tag.
6. **Tags are append-only in context.** When a status changes, update the tag in place — do not create duplicate entries.

---

## 5. Context Preservation — The MUST DOs

Context is currency (P1). These are non-negotiable actions that preserve it:

**`context/_ACTIVE_CONTEXT.md`** — The single most important file in any DFW project.
- MUST be read at the start of every session.
- MUST be updated at the end of every session with: what was done, what's next, what's blocked.
- This is how sessions hand off to each other. Without it, the next session starts cold.

**`plans/_TODO.md`** — The living task list.
- MUST be read at session start to understand priorities.
- MUST be updated when tasks are completed, added, or re-prioritized.
- Every task MUST have `#status/` and `#priority/` tags (see Section 4).
- Completed tasks MUST have `#status/done` and `@completed()` timestamps.
- New tasks discovered mid-session get `#status/backlog #priority/<level> #source/session`.

**`context/_DECISIONS_LOG.md`** — Why we chose what we chose.
- MUST be appended when a significant architectural, design, or tooling decision is made.
- Entries include: the decision, alternatives considered, rationale, and date.

**Sequenced artifacts** — Everything else persisted with `NNN-type-slug.md` naming (see Section 9).

---

## 6. Handoff Protocol

Every tool transition and every session boundary requires a handoff. The handoff is how context survives tool boundaries and session gaps.

A handoff MUST include:
- **Context:** What was done, what state are we in, what decisions were made
- **Intent:** What needs to happen next and why
- **Constraints:** What must not change, what boundaries apply
- **Acceptance:** How will we know the next phase succeeded
- **Files:** Which files are involved, where they are
- **Open Questions:** What's unresolved — tag each with `#source/ambiguity #route/dfw` if it represents a methodology gap

Handoffs live in `prompts/handoffs/` with the naming pattern: `YYYY-MM-DD_<slug>-handoff.md`

---

## 7. Fit-for-Purpose Tool Assignments

Each tool has a defined role. Using a tool outside its purpose creates friction. When friction is identified, tag it `#source/dfw-feedback #route/dfw`.

| Tool | Primary Role | Use For | Don't Use For |
|------|-------------|---------|---------------|
| **Claude Desktop** | Planning, synthesis, research, reasoning | Architecture decisions, prompt design, research, session planning, journal writing, Obsidian/Notion interaction | Code execution, file editing, CI/CD |
| **Cursor** | Flow-state implementation | Code writing, inline edits, visual diffs, debugging, frontend work | Long autonomous runs, documentation generation, research |
| **Claude Code** | Autonomous multi-file operations | Large refactors, test generation, parallel execution, scripting, CI/CD | Visual editing, flow-state coding, architecture planning |
| **Obsidian** | Long-term memory and global state | Journals, cross-project search, tag routing, methodology docs, project stubs | Code editing, real-time collaboration, project deliverables |
| **Notion** | External-facing content and team collaboration | Roadmaps, meeting notes, stakeholder comms, pitch materials | Development state, code handoffs, personal workflow |

---

## 8. Session Lifecycle

Every working session follows this pattern. All agents MUST follow this regardless of provider (Claude, Gemini, GPT, Grok).

**START:**
1. Read `CLAUDE.md` (global + project) — this file is the constitution
2. Read `docs/DFW-OPERATING-MANUAL.md` — this file is the methodology
3. Read `.dfw/personal-config.md` — environment-specific paths and mappings
4. **Check for active state file.** Read `.dfw/session-state.json` (or `X:\DFW\Tools\.dfw-state\` for kickstart). If a state file exists with incomplete steps, **resume from `lastCompletedStep`** — do not re-execute completed steps, do not re-ask questions stored in the `inputs` field. See Section 19 for full protocol.
5. Read `context/_ACTIVE_CONTEXT.md` — understand current state
6. Read `plans/_TODO.md` — understand priorities and active tasks
7. Understand current state before doing anything

**WORK:**
8. Execute against the plan
9. Persist all artifacts to the correct DFW directories (see Section 3)
10. Apply proper tags to all tasks and artifacts (see Section 4)
11. When ambiguity arises — STOP, ask, record with `#source/ambiguity #route/dfw` (P3)
12. For multi-step operations, update the state file after each completed step (see Section 19)

**CLOSE:**
13. Update `context/_ACTIVE_CONTEXT.md` with what was accomplished and what's next
14. Update `plans/_TODO.md`:
    - Completed tasks → `#status/done` + `@completed()` timestamp
    - Discovered tasks → new entry with `#status/backlog #priority/<level> #source/session`
15. If significant work: create or suggest a journal entry in the Obsidian vault
16. If tool transition needed: write a handoff to `prompts/handoffs/`
17. If a state file exists and all steps are complete, archive it (see Section 19)

**FLYWHEEL FEEDBACK:**
18. Did we hit methodology friction? → Tag `#source/dfw-feedback #route/dfw`
19. Did ambiguity arise? → Already auto-routed via `#source/ambiguity #route/dfw` (step 11)
20. Did a rule fail or prove insufficient? → Propose an amendment with rationale
21. Did we discover a reusable pattern? → Capture it as a skill

---

## 9. Artifact Sequencing Convention

All persisted artifacts (except structural `_` files) follow this naming convention:

**Pattern:** `NNN-type-slug.md`
- `NNN` = 3-digit zero-padded sequence number (001, 002, 003...)
- `type` = artifact type (see table below)
- `slug` = kebab-case descriptive name

| Type | Used For | Target Directory |
|------|----------|------------------|
| `plan` | Plans, roadmaps, sprint plans | `plans/` |
| `spec` | Specifications, requirements | `docs/` |
| `doc` | General documentation, guides | `docs/` |
| `adr` | Architecture Decision Records | `docs/` |
| `prompt` | Reusable prompts, system prompts | `prompts/` |
| `handoff` | Context handoffs between tools/sessions | `prompts/` |
| `research` | Research findings, literature reviews | `research/` |
| `analysis` | Analysis, deep dives | `research/` |
| `retro` | Retrospectives, post-session learnings | `context/` |
| `context` | Active context snapshots | `context/` |
| `decision` | Decision records | `context/` |
| `journal` | Journal entries, session logs | `context/` |

**Sequencing rules:**
- Per-directory independent counters
- Before creating, scan the directory and use `(max NNN) + 1`
- Never reuse a sequence number
- Directory names are ALWAYS lowercase

**Required frontmatter:**
```yaml
---
type: plan
created: 2026-02-20T14:30:00
sessionId: S20260220_1430
source: claude-desktop
description: One-line summary
tags: [#status/active, #priority/important]
---
```

---

## 10. Journal System

Journals are the long-term memory of the project portfolio. They live in the Obsidian vault at the global scope.

- **Location:** `journal/YYYY-MM-DD_<Slug>.md`
- **Content:** Executive summary, sessions breakdown, artifacts created, decisions made, carried-forward items, key insights, reflection
- **When:** After any session with significant outcomes — always ASK before creating (P2)
- **Purpose:** Future sessions reference journals to understand history, patterns, and decisions
- **Tags in journals:** Journal entries SHOULD include relevant `#source/` and `#route/` tags to aid future search and routing

---

## 11. The Flywheel Effect

This is why it's called Development Flywheel:

1. Every session produces artifacts (context, decisions, handoffs, retros)
2. Those artifacts inform the next session (no cold starts)
3. Methodology friction gets tagged `#source/dfw-feedback #route/dfw` and enters the DFW project backlog
4. Ambiguity gaps get tagged `#source/ambiguity #route/dfw` and enter the DFW backlog
5. DFW improvements ship → all projects benefit
6. Better projects generate higher-level friction → repeat at a higher level

Two feedback loops run simultaneously:
- **Inner loop:** Project work → project board → operational improvement
- **Outer loop:** Product work → DFW board → methodology improvement

The flywheel only works if:
- Context is preserved (P1) — every session ends with updated `_ACTIVE_CONTEXT.md`
- Artifacts are persisted (Section 5) — nothing lives only in chat
- Tags are applied (Section 4) — everything is findable and trackable
- Feedback closes the loop (P6) — friction becomes improvement, not frustration

---

## 12. Kanban and CardBoard Integration

> **PLACEHOLDER — To be expanded**
>
> Covers how DFW tags drive CardBoard Kanban views in Obsidian.
> Key concepts: tag-based columns, path-filtered project boards, three-tier
> board model (Global Inbox → Project Boards → DFW Feedback Loop).
> See `docs/DFW-Kanban-CardBoard-Spec.md` in the DevFlywheel project for current spec.

---

## 13. DFW Extension Commands

> **PLACEHOLDER — To be expanded**
>
> Covers the VSCode/Cursor DFW Extension commands:
> - `DFW: New Project` — scaffolds full directory structure
> - `DFW: New Subproject` — scaffolds nested subproject
> - `DFW: Align` — validates project structure compliance
> - `DFW: Sync Tools` — imports rules, skills, scripts, constitution, manuals from Tools directory
> - `DFW: Sync CardBoard Boards` — scans vault, adds missing Kanban boards
> See the DFWExtension project `docs/` for full spec.

---

## 14. MCP Configuration and Agent File Access

> **PLACEHOLDER — To be expanded**
>
> Covers how AI agents access project files via MCP:
> - Claude Desktop MCP filesystem server entries
> - Least-privilege directory exposure (7 DFW dirs, not project root)
> - Obsidian MCP REST API integration
> - Notion MCP server integration
> See `docs/DFW-Claude-Desktop-MCP-Integration-Spec.md` in the DevFlywheel project for current spec.

---

## 15. Skills Library

> **PLACEHOLDER — To be expanded**
>
> Covers the reusable patterns catalog:
> - Where skills live (global vs project scope)
> - How skills are captured from session work
> - How agents discover and apply existing skills
> - Naming and indexing conventions

---

## 16. Constitution Amendment Process

> **PLACEHOLDER — To be expanded**
>
> Covers how DFW principles and rules get changed:
> - Who can propose an amendment (any agent or human)
> - What rationale is required
> - Where amendment history is tracked
> - How amendments propagate to fraternal twins (CLAUDE.md ↔ agent-constitution.mdc)
> - Version numbering convention

---

## 17. Cross-Agent Compatibility

> **PLACEHOLDER — To be expanded**
>
> Covers how non-Claude agents consume DFW rules:
> - Claude Code: auto-reads CLAUDE.md natively
> - Claude Desktop: bootstrap via Custom Instructions (see CLAUDE.md Section 8)
> - Cursor: reads .cursor/rules/*.mdc (fraternal twin)
> - Gemini: requires system prompt injection — paste DFW section or provide file path
> - GPT / Codex: requires system prompt injection or project knowledge upload
> - Grok: requires system prompt injection
> - API-based agents: include CLAUDE.md content in system prompt
>
> The file stays named CLAUDE.md for Claude Code auto-loading. For non-Claude agents,
> provide this file's content via whatever system prompt or project knowledge mechanism
> the agent supports.

---

## 18. New Project Scaffold Protocol

> **This is the executable procedure for creating a new DFW project from scratch.**
> Any agent with filesystem access (MCP or direct) MUST follow these steps exactly.
> This protocol produces the same output as the DFW Extension's `DFW: New Project` command.
>
> **Precondition:** The agent MUST have MCP filesystem access to:
> - `X:\DFW\Tools` (or `C:\DATA\Tool`) — the canonical template repository
> - The target directory where the project will be created
> - `X:\DFW\Vault` (or `C:\DATA\DFW\Vault`) — the Obsidian vault (for stub creation)
>
> **Note:** `X:` and `C:\DATA` are equivalent (via `subst`). Use whichever is accessible.
> See personal config for drive equivalence details.

### Resume Check

**Before starting Step 0**, check for an existing state file:
- Look at `X:\DFW\Tools\.dfw-state\<project-name>-scaffold.json`
- If found and `lastCompletedStep` is set, **resume from the next incomplete step**
- All inputs are in the state file's `inputs` field — do NOT re-ask the user

If no state file exists, proceed to Target Directory Validation.

### Target Directory Validation

Before gathering inputs, verify that the target project path is within the
configured Target Directory:

1. Read the Target Directory from `personal-config.md` (or `X:\DFW\Tools\Constitution\personal-config.md` for kickstart)
2. If the user-provided project path is NOT a child of the Target Directory, WARN:
   `"WARNING: <path> is outside the Target Directory (<target-dir>). All DFW projects
   should be within the Target Directory for security. Continue anyway? (y/N)"`
3. If the user confirms, proceed but log the override in the state file notes.
4. If the user declines, ask for a new path.

### Quick Reference Checklist

| Step | Action | State Key |
|------|--------|-----------|
| 0 | Gather inputs from user | `gather-inputs` |
| 1 | Create directory tree (`.dfw-state/` first) | `create-directories` |
| 2 | Generate `.dfw/project.json` | `generate-project-json` |
| 3 | Generate `.dfw/constitution.json` | `generate-constitution-json` |
| 4 | Generate `.dfw/personal-config.md` | `generate-personal-config` |
| 5 | Copy files from `X:\DFW\Tools` | `copy-from-tool` |
| 6 | Write structural files | `write-structural-files` |
| 7 | Create Obsidian vault stub | `create-vault-stub` |
| 8 | Display status card | `display-status-card` |
| 9 | Write initial handoff (optional) | `write-handoff` |

**After each step:** Update the state file — set the step to `done`, update `lastCompletedStep` and `updatedAt`. See Section 19 for state file schema.

### Step 0: Gather Inputs

Ask the user for these inputs. Do NOT proceed until all required inputs are confirmed.

| Input | Required | Options | Default |
|-------|----------|---------|---------|
| **Project name** | YES | kebab-case string (e.g., `my-project`) | — |
| **Project directory** | YES | Full path (e.g., `X:\my-project`) | `X:\<project-name>` |
| **Project type** | YES | `application`, `library`, `platform`, `research`, `vertical` | — |
| **Architecture** | Only if type = `application` | `backend-only`, `frontend-only`, `full-stack`, `manual` | — |
| **Include source dirs** | NO | `yes` / `no` | `yes` for application, `no` for others |
| **Persona** | NO | Exotic dancer name | `Donna` |

**After gathering inputs:** Create the initial state file at `X:\DFW\Tools\.dfw-state\<project-name>-scaffold.json` with all inputs stored and `gather-inputs` set to `done`. This is the first write — if the session dies after this point, the next session has all inputs and never re-asks.

### Step 1: Create Directory Tree

Create all directories. The exact tree depends on project type and architecture.

**First:** Create `.dfw-state/` in the project root. This is the FIRST directory created so the state file can be moved from `X:\DFW\Tools\.dfw-state\` into the project immediately. Then create the rest.

**Core directories (ALL project types):**

```
<project-root>/
├── .dfw-state/
├── .dfw/
├── .cursor/
│   ├── rules/
│   └── skills/
├── docs/
│   └── ADR/
├── plans/
├── prompts/
│   ├── system/
│   ├── handoffs/
│   └── templates/
├── context/
│   └── retrospectives/
├── research/
│   └── sources/
└── scripts/
    ├── scaffold/
    └── hooks/
```

**Source directories (if `includeSource = yes`):**

| Architecture | Directories |
|-------------|-------------|
| `backend-only` | `app/`, `tests/` |
| `frontend-only` | `src/`, `tests/` |
| `full-stack` | `backend/app/`, `backend/tests/`, `frontend/src/`, `frontend/tests/` |
| `manual` | *(none — user creates their own)* |
| *(non-application types)* | `src/`, `tests/` |

### Step 2: Generate `.dfw/project.json`

Write this file with the following JSON structure. Replace placeholders with actual values.

**PID Generation:** Generate a unique Project ID (`PID-XXXXX`) — 5 random uppercase alphanumeric characters prefixed with `PID-`. Verify uniqueness against the global registry at `X:\DFW\Vault\projects\_pid-registry.md` before writing.

```json
{
  "pid": "PID-XXXXX",
  "name": "<project-name>",
  "type": "<project-type>",
  "version": "1.0.0",
  "created": "<YYYY-MM-DD>",
  "methodology": "devflywheel",
  "dfwVersion": "0.8.0",
  "subprojects": [],
  "constitution": "./constitution.json",
  "tags": {},
  "architecture": "<architecture-if-application>"
}
```

Omit the `"architecture"` field if the project type is not `application`.

### Step 2A: Register PID in Global Registry

Append a row to `X:\DFW\Vault\projects\_pid-registry.md` with the new project's PID, name, directory, type, and status. This registry is the single source of truth for PID-to-project mapping across the entire DFW ecosystem.

### Step 3: Generate `.dfw/constitution.json`

```json
{
  "schemaVersion": 1,
  "naming": { "project": "lowercase-kebab-case" },
  "scopeBoundaries": "root-global, subproject-local",
  "notes": "Project-level conventions for DevFlywheel tooling."
}
```

### Step 4: Generate `.dfw/personal-config.md`

Read the template at `X:\DFW\Tools\Constitution\personal-config-template.md` and fill in the values:

```markdown
# DFW Personal Configuration

> This file is NOT committed to git. Add `.dfw/personal-config.md` to `.gitignore`.

## Environment

| Setting | Value |
|---------|-------|
| **DFW Root** | `<parent directory of project>` |
| **Tool Repository** | `X:\DFW\Tools` |
| **Obsidian Vault** | `X:\DFW\Vault` |
| **Drive Alias** | `X:` → `C:\DATA` via `subst` |

## Tool-to-Directory Mappings

| Tool | Path |
|------|------|
| Cursor Workspace | `<project-path>` |

> Template source: `X:\DFW\Tools\Constitution\personal-config-template.md`
```

### Step 5: Copy Files from `X:\DFW\Tools`

Copy these files from the Tool repository into the new project. If a source file does not exist, skip it gracefully and inform the user.

| Source | Destination | Notes |
|--------|-------------|-------|
| `X:\DFW\Tools\Constitution\CLAUDE-PROJECT-TEMPLATE.md` | `<project>/CLAUDE.md` | Rename on copy — Claude model entry point |
| `X:\DFW\Tools\Constitution\DFW-CONSTITUTION.md` | `<project>/docs/DFW-CONSTITUTION.md` | Universal rules |
| `X:\DFW\Tools\Manuals\DFW-OPERATING-MANUAL.md` | `<project>/docs/DFW-OPERATING-MANUAL.md` | Methodology |
| `X:\DFW\Tools\Constitution\DFW-GLOSSARY.md` | `<project>/docs/DFW-GLOSSARY.md` | Terminology |
| `X:\DFW\Tools\rules/*.mdc` (ALL `.mdc` files) | `<project>/.cursor/rules/<filename>` | Copy each file |
| `X:\DFW\Tools\scripts\Resync-PromptsAndPlans.ps1` | `<project>/scripts/Resync-PromptsAndPlans.ps1` | |

### Step 6: Write Structural Files

Create each of these files with the exact content shown. Replace `<name>` with the kebab-case project name, `<DisplayName>` with title-cased name, and `<date>` with today's date (YYYY-MM-DD).

#### `docs/PROJECT_OVERVIEW.md`
```markdown
---
type: project-overview
created: <date>
status: active
tags: [<name>]
---

# <DisplayName> — Project Overview

> **Mission:** [Define the project's purpose]

---

## Scope

## Success Metrics

## Links
```

#### `docs/ARCHITECTURE.md`
```markdown
---
type: architecture
created: <date>
status: draft
tags: [<name>, architecture]
---

# <DisplayName> — Architecture

## Overview

## Key Decisions
```

#### `docs/CHANGELOG.md`
```markdown
# Changelog

## [Unreleased]

- Initial scaffold (<date>)
```

#### `docs/ADR/_TEMPLATE.md`
```markdown
---
type: adr
created: <date>
status: proposed
---

# ADR — <Title>

## Context

## Decision

## Consequences
```

#### `plans/_TODO.md`
```markdown
---
type: task-list
project: <name>
updated: <date>
---

# Active Tasks

## In Progress

## Up Next

## Blocked
```

#### `plans/_WISHLIST.md`
```markdown
# Wishlist

- 
```

#### `plans/_ROADMAP.md`
```markdown
# Roadmap

## Phase 0
- 
```

#### `prompts/handoffs/_TEMPLATE.md`
```markdown
---
type: handoff
from: <tool>
to: <tool>
created: <date>
---

# Context Handoff

## Current State

## What Was Accomplished

## What's Next

## Key Decisions Made

## Open Questions
```

#### `context/_ACTIVE_CONTEXT.md`
```markdown
# Active Context

- Updated: <date>
- Current focus: 
- Agent constitution: [CLAUDE.md](../CLAUDE.md)
- Operating manual: [docs/DFW-OPERATING-MANUAL.md](docs/DFW-OPERATING-MANUAL.md)

## Notes
```

#### `context/_DECISIONS_LOG.md`
```markdown
# Decisions Log

## <date>
- Initial scaffold created.
```

#### `scripts/scaffold/README.md`
```markdown
# Scaffold Scripts

Place automation here.
```

#### `scripts/hooks/README.md`
```markdown
# Git Hooks

Place hook scripts here.
```

#### `.gitignore`

Base content (always include):
```
.env
.DS_Store
Thumbs.db

# DFW caches, personal config, and state files
.dfw/.resync-sequence-cache.json
.dfw/.resync-graph-cache.json
.dfw/personal-config.md
.dfw/session-state.json
.dfw-state/
```

Add architecture-specific blocks:

| Architecture | Add |
|-------------|-----|
| `backend-only` | `\n# Python\n.venv/\nvenv/\n__pycache__/\n*.pyc\n.pytest_cache/\n*.egg-info/` |
| `frontend-only` | `\n# Node / TypeScript\nnode_modules/\ndist/\nout/` |
| `full-stack` | Both Python and Node blocks |
| *(default)* | Node block |

#### `README.md`

```markdown
# <DisplayName>

Generated by DevFlywheel scaffolding.

## Layout
- docs/ — long-lived documentation
- plans/ — TODOs, wishlist, roadmap
- prompts/ — system prompts and handoffs
- context/ — active context and decisions
- .dfw/ — project metadata
```

Append architecture-specific lines:

| Architecture | Append |
|-------------|--------|
| `backend-only` | `- app/ — Python application source\n- tests/ — Python tests` |
| `frontend-only` | `- src/ — TypeScript / React source\n- tests/ — Frontend tests` |
| `full-stack` | `- backend/ — Python backend (app/, tests/)\n- frontend/ — TypeScript frontend (src/, tests/)` |

### Step 7: Create Obsidian Vault Stub

Write a project stub at `X:\DFW\Vault\projects/<project-name>/_index.md`:

```markdown
---
type: project-stub
pid: <PID-XXXXX>
status: active
project_dir: <project-path>
last_session: <date>
tags: [project, <project-name>]
---

# <DisplayName>

**PID:** `<PID-XXXXX>`
**Directory:** `<project-path>`
**Type:** <project-type>
**Status:** active
```

Create the `X:\DFW\Vault\projects/<project-name>/` directory if it does not exist.

### Step 7B: Create CardBoard Kanban Board

Add a CardBoard board entry for the new project to the Obsidian vault's CardBoard plugin config.

**Config file:** `C:\DATA\DFW\Vault\.obsidian\plugins\card-board\data.json`

> **CRITICAL — Path and Timing Rules:**
> - **Always write via `C:\DATA\...`** (the real filesystem path), NEVER via a `subst` alias like `X:\`. Obsidian uses the real path internally; writes to the alias may not be seen.
> - **Obsidian MUST be fully closed** before writing `data.json`. If CardBoard's view was open, its in-memory state will overwrite any external changes on startup. Verify no `Obsidian.exe` process exists in Task Manager.
> - **Remove stale CardBoard view from `workspace.json`** if present. If `workspace.json` contains a leaf with `"type": "card-board-view"`, delete that leaf entry and set `"currentTab"` to `0` — otherwise Obsidian restores the view on launch and can clobber the config.

**Procedure:**

1. Read the existing `data.json`. If it does not exist, create the default structure (version `"0.13.0"`, empty `boardConfigs`, standard `globalSettings`).
2. Check if a board with the project name already exists — if so, skip.
3. Append a new board to `data.json > data > boardConfigs`:

```json
{
  "columns": [
    {
      "tag": "namedTag",
      "data": { "collapsed": false, "name": "status/backlog", "tag": "status/backlog" }
    },
    {
      "tag": "namedTag",
      "data": { "collapsed": false, "name": "status/active", "tag": "status/active" }
    },
    {
      "tag": "namedTag",
      "data": { "collapsed": false, "name": "status/build", "tag": "status/build" }
    },
    {
      "tag": "namedTag",
      "data": { "collapsed": false, "name": "status/deploy", "tag": "status/deploy" }
    }
  ],
  "filters": [
    { "tag": "pathFilter", "data": "projects/<project-name>/" }
  ],
  "filterPolarity": "Allow",
  "filterScope": "Both",
  "name": "<DisplayName>",
  "showColumnTags": true,
  "showFilteredTags": true
}
```

> **Schema notes (verified against CardBoard v0.13.0 Elm source):**
> - **Columns:** Each uses `{ "tag": "namedTag", "data": { "collapsed": bool, "name": string, "tag": string } }`. The `tag` field inside `data` is the tag without the `#` prefix.
> - **Filters:** Use `{ "tag": "pathFilter", "data": "<path-string>" }` — the tag is `"pathFilter"` (not `"path"`), and `data` is a **plain string** (not an object). For tag filters: `"tagFilter"`. For file filters: `"fileFilter"`.
> - **showColumnTags / showFilteredTags:** Must be `true` for proper rendering.
> - **Completed column (optional):** Add `{ "tag": "completed", "data": { "collapsed": false, "index": <N>, "limit": 10, "name": "Completed" } }` where `<N>` is the column's zero-based position.

4. Write the updated `data.json` back to `C:\DATA\DFW\Vault\...`. Preserve all existing boards and `globalSettings`.
5. Inform the user: "Close and reopen Obsidian, then click the CardBoard ribbon icon to see the new board."

### Step 7C: MCP Config — Add Project Path

Ask the user: **"MCP Config: Is this a DFW project, a service, or a standalone project?"**

- Default answer: **project** (most common)
- The answer determines which MCP filesystem server in `claude_desktop_config.json` gets the new path.

| Answer | MCP Server Key | What Gets Added |
|--------|---------------|-----------------|
| `dfw` | `dfw-filesystem` | `X:\<project-name>` and `C:\DATA\<project-name>` |
| `service` | `services-filesystem` | `X:\<project-name>` and `C:\DATA\<project-name>` |
| `project` | `projects-filesystem` | `X:\<project-name>` and `C:\DATA\<project-name>` |

Read `claude_desktop_config.json` (typically at `%APPDATA%\Claude\claude_desktop_config.json` on Windows), append the path(s) to the correct server's `args` array, and write it back.

> **MCP Path Rule:** Only add the project ROOT path to the MCP config.
> The filesystem server grants recursive access to all subdirectories automatically.
> Do NOT list individual subdirectories (`docs/`, `plans/`, etc.) — this is
> redundant and creates maintenance burden.

**Warn the user:** "Claude Desktop must be restarted for MCP config changes to take effect."

If the agent cannot access the Claude Desktop config file (permissions, path unknown), inform the user and provide the manual JSON snippet to add.

### Step 8: Display Constitution Status Card

After completing all steps, display:

```
╔══════════════════════════════════════════════════════╗
║  DFW PROJECT CREATED                                 ║
╠══════════════════════════════════════════════════════╣
║  Persona:    <persona>                               ║
║  Project:    <project-name>                          ║
║  Type:       <project-type>                          ║
║  Arch:       <architecture or n/a>                   ║
║  Directory:  <project-path>                          ║
║  Vault Stub: ✅ CREATED                              ║
║  CLAUDE.md:  ✅ copied                               ║
║  Manual:     ✅ copied                               ║
║  Rules:      ✅ <N> .mdc files copied                ║
║  Config:     ✅ generated                            ║
║  CardBoard:  ✅ board created                        ║
║  MCP Config: ✅ path added / ⚠️ manual required     ║
╚══════════════════════════════════════════════════════╝
```

### Step 9: Write Initial Handoff (Optional)

If the project was created in Claude Desktop and will be picked up by Cursor or Claude Code, write an initial handoff at `<project>/prompts/handoffs/<YYYY-MM-DD>_initial-scaffold-handoff.md`:

```markdown
---
type: handoff
from: Claude Desktop
to: Cursor Agent
created: <date>
sessionId: <sessionId>
source: claude-desktop
description: Initial project scaffold — ready for implementation
---

# Handoff — Initial Scaffold

**Project:** <DisplayName>
**Type:** <project-type>
**Architecture:** <architecture>
**Directory:** <project-path>

## What Was Created
- Full DFW directory structure
- CLAUDE.md (agent constitution)
- DFW Operating Manual
- DFW Glossary
- <N> Cursor rules (.mdc files)
- Resync script
- Personal config
- Obsidian vault stub

## What's Next
- [ ] Open in Cursor and verify structure with `DFW: Doctor`
- [ ] Run `DFW: Align` to validate compliance
- [ ] Begin implementation planning
```

---

## 19. Progressive State Protocol

> **Any multi-step operation that could be interrupted MUST use a progressive state file.**
> This includes scaffolding, refactoring, migrations, multi-file edits, and research tasks.
> The state file is updated after EVERY completed step so that a crashed or timed-out session
> can be resumed without re-executing completed work or re-asking answered questions.

### State File Location

| Scenario | Location |
|----------|----------|
| **In-project** (project directory exists) | `<project>/.dfw/session-state.json` |
| **Kickstart** (no project yet) | `X:\DFW\Tools\.dfw-state\<project-name>-<operation>.json` |
| **Post-scaffold** (project just created) | Move kickstart state to `<project>/.dfw/session-state.json` |

### JSON Schema

```json
{
  "sessionId": "S20260220_1600",
  "operation": "scaffold",
  "project": "my-project",
  "projectPath": "X:\\my-project",
  "inputs": {
    "type": "application",
    "architecture": "backend-only",
    "persona": "Donna",
    "includeSource": true
  },
  "startedAt": "2026-02-20T16:00:00",
  "updatedAt": "2026-02-20T16:03:22",
  "steps": {
    "gather-inputs": "done",
    "create-directories": "done",
    "generate-project-json": "done",
    "generate-constitution-json": "done",
    "generate-personal-config": "in-progress",
    "copy-from-tool": "pending",
    "write-structural-files": "pending",
    "create-vault-stub": "pending",
    "display-status-card": "pending",
    "write-handoff": "pending"
  },
  "lastCompletedStep": "generate-constitution-json",
  "notes": "User confirmed all inputs. Using C:\\DATA paths for MCP."
}
```

### Step Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Not yet started |
| `in-progress` | Currently executing (set before starting, updated to `done` on completion) |
| `done` | Successfully completed |
| `skipped` | Intentionally skipped (e.g., user declined optional step) |

### Rules

1. **Write Before Move** — After completing a step, update the state file to `done` and set `lastCompletedStep` BEFORE starting the next step.
2. **Inputs Persist** — All user-provided inputs (name, type, architecture, persona, paths) MUST be stored in the `inputs` field so they are never re-asked.
3. **Resume Check** — On session start, check for an active state file BEFORE initiating any protocol. If one exists with incomplete steps, resume from `lastCompletedStep`. Do not re-execute `done` steps.
4. **Idempotent Steps** — When resuming, the step after `lastCompletedStep` may have been partially executed. Steps MUST be written to be safe to re-run (check if directory exists before creating, check if file exists before copying).
5. **Cleanup on Completion** — When ALL steps are `done` or `skipped`:
   - Move the state file to `.dfw/archive/` (or `X:\DFW\Tools\.dfw-state\archive\` for kickstart)
   - Write the appropriate retro/handoff artifact in Markdown
6. **State File Is Not a Deliverable** — It is a transient machine file. It does NOT follow `NNN-type-slug.md` naming. It does NOT get committed to git. Add `.dfw/session-state.json` to `.gitignore`.

### Extending Beyond Scaffolding

The same pattern applies to any multi-step operation. Adjust the `operation` field and `steps` object:

| Operation | Steps |
|-----------|-------|
| `scaffold` | gather-inputs, create-directories, generate-project-json, ... (see Section 18) |
| `refactor` | analyze, plan, edit-file-1, edit-file-2, ..., verify, update-context |
| `migration` | backup, transform-schema, migrate-data, verify, cleanup |
| `research` | define-scope, source-1, source-2, ..., synthesize, persist-findings |

---

> **End of DFW Operating Manual.**
> This is a living document. It evolves alongside `CLAUDE.md` through the DFW amendment process.
> When methodology friction is found, tag it `#source/dfw-feedback #route/dfw`.
