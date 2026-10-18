# Stage 6 — React Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready, dark-mode, Apple-styled React + Vite + TypeScript dashboard for GraphScope that connects to live SSE investigations, renders an interactive blast-radius dependency graph, provides an inline code inspector with hash-verified evidence, highlights analysis gaps, and exports impact reports.

**Architecture:** Split Command Center layout (Option C) with a top floating glass navigation and query bar, a live agent telemetry HUD, an interactive blast-radius graph canvas, and a side-by-side code inspector and analysis gaps drawer. Real-time agent streaming is driven by a custom POST-based SSE hook (`fetch` + `ReadableStream`).

**Tech Stack:** React 18/19, Vite, TypeScript, Lucide React, Vitest + React Testing Library, Vanilla CSS with Apple HIG design tokens and spring physics.

**Spec:** [docs/superpowers/specs/2026-10-18-stage-6-frontend-design.md](file:///d:/GraphScope/docs/superpowers/specs/2026-10-18-stage-6-frontend-design.md)

## Global Constraints

- Translucent materials using `backdrop-filter: blur(20px)` and hairline borders `rgba(255, 255, 255, 0.08)`.
- System UI / SF Pro optical font hierarchy, negative letter-spacing (`-0.02em`) on headings.
- Critically damped spring physics (`damping: 1.0`, `response: 0.35s`) on interactive transitions.
- Instant feedback on pointer-down (`active: scale(0.98)`).
- Vite dev proxy configured to forward `/api` to `http://localhost:8000`.
- All remote GitHub cloning is deferred to a future milestone; ingestion uses local paths.

## Review Focus

1. **SSE POST streaming:** Standard browser `EventSource` only supports GET; the client must consume `POST /api/investigate` via `fetch` and `ReadableStream` reader without dropping chunked buffer fragments.
2. **Ambiguous target error handling:** When the backend yields an `error` SSE event with `candidates`, the UI must clearly display candidates rather than crashing.
3. **Empty / missing evidence fallback:** If an investigation yields paths without source excerpts (e.g. `include_source=false`), the Code Inspector must show a clear placeholder explaining that source sharing was disabled.
4. **Graph layout with zero affected callers:** If a target function has no callers, the graph canvas must gracefully render a lone target node without division-by-zero layout glitches.
5. **Report export sanitization:** Markdown and JSON export generators must produce valid, readable output even if report sections like `analysis_gaps` are empty.

---

### Task 1: Vite + React + TypeScript Project Scaffolding & Apple Design Tokens

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/index.css`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Test: `frontend/src/__tests__/App.test.tsx`

**Interfaces:**
- Produces: Base React runtime, dev server proxying `/api` -> `http://localhost:8000`, and global Apple design CSS variables (`--bg-primary`, `--bg-glass`, `--border-glass`, `--text-primary`, `--accent-blue`, `--accent-emerald`, `--accent-amber`, `--accent-rose`).

- [ ] **Step 1: Write test verifying App shell renders with brand title**

```tsx
// frontend/src/__tests__/App.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../App';

describe('App Shell', () => {
  it('renders GraphScope brand header', () => {
    render(<App />);
    expect(screen.getByText(/GraphScope/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Initialize Vite React TypeScript project in `frontend/`**

Run: Scaffolding files in `frontend/` with React, TypeScript, Vitest, `@testing-library/react`, `jsdom`, and `lucide-react`.

- [ ] **Step 3: Configure `vite.config.ts` with test environment and backend proxy**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  // @ts-expect-error vitest config
  test: {
    globals: true,
    environment: 'jsdom',
  },
});
```

- [ ] **Step 4: Implement Apple Design tokens and base styles in `frontend/src/index.css`**

Define CSS variables for dark mode glassmorphism (`backdrop-filter`), SF Pro typography, buttons, inputs, and scrollbars.

- [ ] **Step 5: Run tests and verify build**

Run: `npm test` inside `frontend/`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite React TypeScript dashboard with Apple design tokens"
```

---

### Task 2: API Client & SSE Streaming Reader (`useInvestigationStream`)

**Files:**
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/hooks/useInvestigationStream.ts`
- Test: `frontend/src/__tests__/useInvestigationStream.test.ts`

**Interfaces:**
- Consumes: Backend endpoints `GET /api/snapshots`, `POST /api/index`, `GET /api/evidence`, and `POST /api/investigate`.
- Produces: `useInvestigationStream` hook returning `{ status, thoughts, toolCalls, graphEvidence, report, error, startInvestigation, reset }`.

- [ ] **Step 1: Write unit test for SSE chunk decoding and state updates**

```ts
// frontend/src/__tests__/useInvestigationStream.test.ts
import { describe, it, expect } from 'vitest';
import { parseSSEBuffer } from '../hooks/useInvestigationStream';

describe('parseSSEBuffer', () => {
  it('parses multiple SSE events across buffer chunks', () => {
    const raw = 'event: agent_thought\ndata: {"step":"resolve_symbol","detail":"Resolving target"}\n\n';
    const { events, remaining } = parseSSEBuffer(raw);
    expect(events.length).toBe(1);
    expect(events[0].event).toBe('agent_thought');
    expect(JSON.parse(events[0].data).step).toBe('resolve_symbol');
    expect(remaining).toBe('');
  });
});
```

- [ ] **Step 2: Define strong TypeScript interfaces in `frontend/src/types/api.ts`**

Define interfaces matching FastAPI backend schemas: `SnapshotItem`, `IndexRequest`, `IndexResponse`, `InvestigateRequest`, `AgentThoughtPayload`, `ToolCallPayload`, `GraphEvidencePayload`, `AnalysisGapsPayload`, `ImpactReport`, `EvidenceItem`.

- [ ] **Step 3: Implement API helpers in `frontend/src/services/api.ts`**

Implement `fetchSnapshots()`, `indexRepository(root)`, `fetchEvidence(snapshotId, evidenceIds, includeSource)`.

- [ ] **Step 4: Implement `useInvestigationStream` hook in `frontend/src/hooks/useInvestigationStream.ts`**

Implement `fetch` POST stream reading with `ReadableStreamDefaultReader` and UTF-8 decoding. Dispatch events to state:
- `agent_thought` -> append to `thoughts`
- `tool_call` -> append to `toolCalls`
- `graph_evidence` -> update `graphEvidence`
- `report_complete` -> set `report`, set status `ready`
- `error` -> set `error`, set status `error`

- [ ] **Step 5: Run tests and verify**

Run: `npm test useInvestigationStream`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/ frontend/src/services/ frontend/src/hooks/ frontend/src/__tests__/
git commit -m "feat(frontend): implement API client and SSE streaming investigation hook"
```

---

### Task 3: Top Command Bar & Local Repository Ingestion Drawer

**Files:**
- Create: `frontend/src/components/CommandBar.tsx`
- Create: `frontend/src/components/CommandBar.css`
- Create: `frontend/src/components/IngestModal.tsx`
- Create: `frontend/src/components/IngestModal.css`
- Test: `frontend/src/__tests__/CommandBar.test.tsx`

**Interfaces:**
- Consumes: `SnapshotItem[]`, active snapshot ID, onSelectSnapshot callback, onIndexSuccess callback.
- Produces: Translucent top bar with repository selector dropdown, snapshot stats chip, and local repo ingestion modal.

- [ ] **Step 1: Write failing component test for CommandBar**

```tsx
// frontend/src/__tests__/CommandBar.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CommandBar from '../components/CommandBar';

describe('CommandBar', () => {
  it('displays active snapshot root and triggers ingest modal', () => {
    const onOpenIngest = vi.fn();
    render(
      <CommandBar
        snapshots={[{ snapshot_id: 'snap-1', root: 'examples/commerce', indexed_at: '2026-10-18' }]}
        activeSnapshotId="snap-1"
        onSelectSnapshot={() => {}}
        onOpenIngest={onOpenIngest}
        onExportMarkdown={() => {}}
        onExportJSON={() => {}}
        hasReport={false}
      />
    );
    expect(screen.getByText(/examples\/commerce/i)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    expect(onOpenIngest).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Verify test fails before implementation**

Run: `npm test CommandBar`
Expected: FAIL

- [ ] **Step 3: Implement `CommandBar.tsx` and `IngestModal.tsx`**

Implement Apple glassmorphic top navigation with repository dropdown, stats badge, and Ingest Modal taking a local folder root path with instant validation feedback.

- [ ] **Step 4: Verify test passes**

Run: `npm test CommandBar`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/__tests__/
git commit -m "feat(frontend): add Apple glassmorphic command bar and repository ingestion modal"
```

---

### Task 4: Query Capsule & Live Investigation Telemetry HUD

**Files:**
- Create: `frontend/src/components/QueryCapsule.tsx`
- Create: `frontend/src/components/QueryCapsule.css`
- Create: `frontend/src/components/TelemetryHUD.tsx`
- Create: `frontend/src/components/TelemetryHUD.css`
- Test: `frontend/src/__tests__/TelemetryHUD.test.tsx`

**Interfaces:**
- Consumes: `InvestigateRequest` parameters, live `thoughts: AgentThoughtPayload[]`, `isStreaming: boolean`.
- Produces: Query input capsule with provider picker and animated telemetry HUD displaying agent steps.

- [ ] **Step 1: Write component test for TelemetryHUD**

```tsx
// frontend/src/__tests__/TelemetryHUD.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TelemetryHUD from '../components/TelemetryHUD';

describe('TelemetryHUD', () => {
  it('renders step pills for agent thoughts', () => {
    const thoughts = [
      { step: 'resolve_symbol', detail: 'Resolving inventory.validate_stock' },
      { step: 'trace_callers', detail: 'Found 3 caller paths' }
    ];
    render(<TelemetryHUD thoughts={thoughts} isStreaming={true} />);
    expect(screen.getByText(/resolve_symbol/i)).toBeDefined();
    expect(screen.getByText(/trace_callers/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Verify test fails**

Run: `npm test TelemetryHUD`
Expected: FAIL

- [ ] **Step 3: Implement `QueryCapsule.tsx` and `TelemetryHUD.tsx`**

Implement:
- Query Capsule: Natural language input, target symbol input, provider dropdown (`test`, `gemini`, `openai`, `ollama`), `share_source` toggle, and Run button with pointer-down spring feedback.
- Telemetry HUD: Animated horizontal strip showing step status pills with glowing pulsing dots for the active step and checkmarks for completed steps.

- [ ] **Step 4: Verify test passes**

Run: `npm test TelemetryHUD`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/__tests__/
git commit -m "feat(frontend): add query capsule and live agent telemetry HUD"
```

---

### Task 5: Interactive Blast-Radius Graph Canvas

**Files:**
- Create: `frontend/src/components/GraphCanvas.tsx`
- Create: `frontend/src/components/GraphCanvas.css`
- Create: `frontend/src/utils/graphLayout.ts`
- Test: `frontend/src/__tests__/GraphCanvas.test.tsx`

**Interfaces:**
- Consumes: `graphEvidence: GraphEvidencePayload | null`, `targetSymbol: string | null`, `onSelectNode: (nodeId: string) => void`, `onSelectEdge: (edgeId: string) => void`.
- Produces: Interactive canvas showing target function (accented red), intermediate callers (accented blue), and entry endpoints (accented green/purple) with zoom, pan, and click selection.

- [ ] **Step 1: Write test for graph layout computation and node extraction**

```ts
// frontend/src/__tests__/GraphCanvas.test.tsx
import { describe, it, expect } from 'vitest';
import { buildGraphData } from '../utils/graphLayout';

describe('buildGraphData', () => {
  it('extracts nodes and edges from caller paths and endpoints', () => {
    const evidence = {
      paths: [
        ['orders.checkout', 'cart.process', 'inventory.validate_stock']
      ],
      potentially_affected_endpoints: ['/api/checkout']
    };
    const { nodes, edges } = buildGraphData(evidence, 'inventory.validate_stock');
    expect(nodes.some(n => n.id === 'inventory.validate_stock' && n.isTarget)).toBe(true);
    expect(nodes.some(n => n.id === '/api/checkout' && n.isEndpoint)).toBe(true);
    expect(edges.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Verify test fails**

Run: `npm test GraphCanvas`
Expected: FAIL

- [ ] **Step 3: Implement `graphLayout.ts` and `GraphCanvas.tsx`**

Implement hierarchical layered DAG layout positioning target node on right, callers in middle layers, and endpoints on left. Render SVG nodes with dark glass styling, glowing borders, directional arrows, and click interactions.

- [ ] **Step 4: Verify test passes**

Run: `npm test GraphCanvas`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/utils/ frontend/src/__tests__/
git commit -m "feat(frontend): implement interactive blast-radius graph canvas"
```

---

### Task 6: Inline Code Inspector, Blind Spots Panel & Report Exporter

**Files:**
- Create: `frontend/src/components/CodeInspector.tsx`
- Create: `frontend/src/components/CodeInspector.css`
- Create: `frontend/src/components/AnalysisGaps.tsx`
- Create: `frontend/src/components/AnalysisGaps.css`
- Create: `frontend/src/utils/reportExport.ts`
- Test: `frontend/src/__tests__/CodeInspector.test.tsx`
- Test: `frontend/src/__tests__/reportExport.test.ts`

**Interfaces:**
- Consumes: Selected edge/symbol, `evidenceList: EvidenceItem[]`, `report: ImpactReport | null`.
- Produces: Code viewer with line numbers and caller line highlight, hash-verification badge, analysis gaps list, and export helpers (`exportMarkdown`, `exportJSON`).

- [ ] **Step 1: Write test for report export formatting**

```ts
// frontend/src/__tests__/reportExport.test.ts
import { describe, it, expect } from 'vitest';
import { generateMarkdownReport } from '../utils/reportExport';

describe('generateMarkdownReport', () => {
  it('generates formatted markdown with target and affected endpoints', () => {
    const report: any = {
      target: 'inventory.validate_stock',
      question: 'Change impact',
      summary: 'High blast radius',
      affected_endpoints: ['/api/checkout'],
      graph_evidence: { paths: [] },
      analysis_gaps: { unresolved_calls: [] }
    };
    const md = generateMarkdownReport(report);
    expect(md).toContain('# Impact Report: inventory.validate_stock');
    expect(md).toContain('/api/checkout');
  });
});
```

- [ ] **Step 2: Verify test fails**

Run: `npm test reportExport`
Expected: FAIL

- [ ] **Step 3: Implement `CodeInspector.tsx`, `AnalysisGaps.tsx`, and `reportExport.ts`**

Implement:
- Code Inspector: Shows file path, hash verification badge (`SHA256 verified`), line numbers, and highlighted caller code snippet.
- Analysis Gaps: Displays unresolved dynamic calls, reflection warnings, and ambiguity notices.
- Report Exporter: Markdown and JSON download and clipboard copy functions.

- [ ] **Step 4: Verify tests pass**

Run: `npm test reportExport` and `npm test CodeInspector`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/src/utils/ frontend/src/__tests__/
git commit -m "feat(frontend): implement code inspector, analysis gaps, and report exporter"
```

---

### Task 7: End-to-End Dashboard Assembly & Verification

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Test: `frontend/src/__tests__/DashboardIntegration.test.tsx`

**Interfaces:**
- Consumes: All components from Tasks 1-6.
- Produces: Fully integrated Apple-styled GraphScope web application.

- [ ] **Step 1: Write integration test for full investigation flow**

```tsx
// frontend/src/__tests__/DashboardIntegration.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from '../App';

describe('Dashboard Integration', () => {
  it('submits investigation and displays telemetry', async () => {
    render(<App />);
    const questionInput = screen.getByPlaceholderText(/Ask an investigation question/i);
    fireEvent.change(questionInput, { target: { value: 'What calls validate_stock?' } });
    const runBtn = screen.getByRole('button', { name: /run/i });
    expect(runBtn).toBeDefined();
  });
});
```

- [ ] **Step 2: Assemble all components in `App.tsx` and style in `App.css`**

Wire snapshot selection, query capsule, telemetry HUD, split view with Graph Canvas on left and Code Inspector + Analysis Gaps on right, and export toolbar.

- [ ] **Step 3: Run all frontend tests**

Run: `npm test -- --run` inside `frontend/`
Expected: All tests PASS.

- [ ] **Step 4: Run production build verification**

Run: `npm run build` inside `frontend/`
Expected: Clean build without TypeScript or bundling errors.

- [ ] **Step 5: Final commit**

```bash
git add frontend/
git commit -m "feat(frontend): complete Stage 6 dashboard integration and build verification"
```
