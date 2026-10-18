# Stage 6 — GraphScope Frontend Design Document

**Date:** 2026-10-18  
**Topic:** Stage 6 — React + Vite + TypeScript Dashboard  
**Status:** Pending Review / Approval  

---

## 1. Intent & Purpose

GraphScope provides codebase investigation and blast-radius analysis powered by FalkorDB and agentic LLMs. 
Stage 6 delivers the primary user-facing frontend: an Apple-inspired, fluid, dark-mode desktop web dashboard where engineers can:
1. Select or ingest a codebase snapshot.
2. Pose an investigation question (e.g. *"What happens if I change `inventory.validate_stock`?"*).
3. Observe live agent reasoning and tool telemetry in real time via Server-Sent Events (SSE).
4. Explore the interactive blast-radius dependency graph.
5. Inspect hash-verified code evidence and analysis blind spots side-by-side.
6. Export the final comprehensive impact report as Markdown or JSON.

---

## 2. Design System & Aesthetics (Apple Design Foundations)

Following the `apple-design` specifications:
- **Materials & Translucency:** Floating functional chrome layers using `backdrop-filter: blur(20px) saturate(180%)`, deep dark backgrounds (`#0e1117`, `#161b22`, `#1c2128`), and hairline borders (`rgba(255, 255, 255, 0.08)`).
- **Typography:** Optical sizing with platform system font stack (`system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display"`). Tight tracking on titles (`letter-spacing: -0.02em`), loose line height on body copy, and clean monospace (`SF Mono`, `ui-monospace`) for code excerpts and symbol identifiers.
- **Motion & Springs:** Critically damped spring physics (`damping: 1.0`, `response: 0.35s`) for panel sliding, tab transitions, and hover states. No hard-cuts or jarring modal pops. Instant feedback on pointer-down (`active: scale(0.98)`).
- **Spatial Consistency:** Direct manipulation, anchored popovers, and consistent dismissal trajectories.

---

## 3. Architecture & User Workflow

### Layout Structure: Split Command Center (Option C)

```
+---------------------------------------------------------------------------------------+
|  GraphScope ◉    [ Repo: examples/commerce ▾ ]   [ Ingest Local... ]   [ Export ▾ ]   | (Top Chrome)
+---------------------------------------------------------------------------------------+
|  Investigate: [ "What is the blast radius of validate_stock?" ] Target: [ inventory ] [Run] | (Query Capsule)
+---------------------------------------------------------------------------------------+
|  Agent HUD: [✓ resolve_symbol] -> [✓ trace_callers] -> [● find_endpoints] (Live SSE)  | (Telemetry Strip)
+-----------------------------------------------------------+---------------------------+
|                                                           |                           |
|                  INTERACTIVE CANVAS                       |      CODE INSPECTOR       |
|                                                           |      & BLIND SPOTS        |
|  - Live agent thoughts during execution                   |                           |
|  - Interactive Blast-Radius Graph (nodes & edges)         |  - Hash-verified source   |
|  - Function nodes -> Call edges -> Endpoint badges        |    lines with highlights  |
|  - Pan, zoom, click-to-inspect                            |  - Unresolved call gaps   |
|                                                           |  - Ambiguity flags        |
|                                                           |                           |
+-----------------------------------------------------------+---------------------------+
```

---

## 4. Key Components & Implementation Details

### 4.1 Top Control Bar & Repository Ingestion
- **Snapshot Selector:** Fetches available snapshots from `GET /api/snapshots`. Displays active snapshot root, file count, and indexed timestamp.
- **Ingestion Modal/Drawer:** Allows indexing any local directory path by calling `POST /api/index` (`{ "root": string }`). Returns snapshot stats (`files`, `functions`, `calls`, `endpoints`).
- *Note:* Remote GitHub URL cloning is explicitly deferred to a future iteration.

### 4.2 Query & Investigation Capsule
- Inputs for `question` (natural language prompt) and optional `target` (e.g. `inventory.validate_stock`).
- Model Provider dropdown: `test` (deterministic planner), `gemini`, `openai`, `ollama`, or `none`.
- `share_source` toggle (opt-in hash-verified source snippet sharing).

### 4.3 SSE Streaming Client (`useInvestigationStream`)
- Because `POST /api/investigate` streams SSE events from a POST request with a JSON body, standard browser `new EventSource()` cannot be used.
- The frontend implements a streaming reader via `fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body })` and decodes the `ReadableStream` line-by-line.
- Handles events:
  - `agent_thought`: Live reasoning and tool invocations.
  - `tool_call`: Tool return telemetry and findings.
  - `graph_evidence`: Evidence paths and affected endpoints.
  - `report_complete`: Final `ImpactReport` payload.
  - `error`: Ambiguity / clarification requirements and failures.

### 4.4 Interactive Blast-Radius Graph Canvas
- Renders the caller paths and affected endpoints returned by the investigation.
- Nodes: Target function (distinct accent color), intermediate caller functions, and affected HTTP endpoints.
- Edges: Direct and transitive call relationships.
- Interactivity: Pan, zoom to fit, node selection. Clicking a node or edge immediately focuses the Code Inspector on that specific call site or symbol.

### 4.5 Inline Code Inspector & Analysis Gaps
- Fetches source lines via `GET /api/evidence` or reads from the completed report evidence.
- Displays syntax-highlighted code block with line numbers, highlighting the exact caller line.
- Badges hash verification (`SHA256 verified`).
- Lists "Blind Spots / Analysis Gaps" (e.g. dynamic calls, unresolvable reflections) with risk explanations.

### 4.6 Impact Report Exporter
- Allows one-click export of the complete analysis:
  - **Markdown:** Formatted summary, blast radius tables, affected endpoints, and blind spots.
  - **JSON:** Complete `ImpactReport` schema.

---

## 5. Technology Stack & Packages

- **Build / Tooling:** Vite + React + TypeScript
- **Styling:** Vanilla CSS with modern CSS custom properties (variables) for theme tokens, glassmorphism, and Apple HIG typography.
- **Graph Visualization:** Clean, robust graph rendering (e.g. Cytoscape.js or React Flow / `@xyflow/react`) styled to match the dark glass UI.
- **Icons / Micro-animations:** Lucide React icons with fluid spring transitions.

---

## 6. Goals, Non-Goals, and Anti-Goals

### Goals
- Instant, fluid feedback on all user interactions.
- Real-time display of agent thinking steps without lag or UI freezes.
- Clear visual distinction between target nodes, direct callers, and public endpoints.
- Seamless evidence inspection with exact line highlights.
- Zero-friction export for team sharing.

### Non-Goals
- Git clone from GitHub URLs (deferred to future stage as requested).
- Editing or modifying backend source files from the frontend (read-only inspection).

### Anti-Goals
- Heavy, generic UI frameworks (e.g. unstyled Bootstrap, Material UI) that clash with the Apple design language.
- Cluttered, modal-heavy navigation that traps the user or hides context.

---

## 7. Decisions Left to the Builder

- Exact choice of graph rendering library (e.g., Cytoscape.js canvas vs React Flow).
- Specific directory structure for the React frontend (e.g. `frontend/` at repository root).
- Dev proxy configuration in `vite.config.ts` to seamlessly proxy `/api/*` to FastAPI on port 8000.
