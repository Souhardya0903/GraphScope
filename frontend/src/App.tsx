import { useState, useEffect, useCallback } from 'react';
import CommandBar from './components/CommandBar';
import RepositoryAnalysis from './components/RepositoryAnalysis';
import { evidenceForNode } from './utils/evidenceSelection';
import IngestModal from './components/IngestModal';
import QueryCapsule from './components/QueryCapsule';
import TelemetryHUD from './components/TelemetryHUD';
import GraphCanvas from './components/GraphCanvas';
import CodeInspector from './components/CodeInspector';
import AnalysisGaps from './components/AnalysisGaps';
import ErrorBoundary from './components/ErrorBoundary';
import { useInvestigationStream } from './hooks/useInvestigationStream';
import { fetchSnapshots, fetchEvidence } from './services/api';
import { SnapshotItem, IndexResponse, EvidenceItem } from './types/api';
import {
  generateMarkdownReport,
  generateJSONReport,
  downloadFile,
} from './utils/reportExport';
import './App.css';

export default function App() {
  const [workflow, setWorkflow] = useState<'repository' | 'snapshot'>('repository');
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>([]);
  const [activeSnapshotId, setActiveSnapshotId] = useState<string | null>(null);
  const [isIngestOpen, setIsIngestOpen] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activeEvidence, setActiveEvidence] = useState<EvidenceItem | null>(null);

  const {
    status,
    thoughts,
    graphEvidence,
    report,
    error,
    candidates,
    startInvestigation,
    reset,
  } = useInvestigationStream();

  // Load snapshots on mount
  const loadSnapshots = useCallback(async () => {
    try {
      const list = await fetchSnapshots();
      setSnapshots(list);
      setActiveSnapshotId(current => current ?? list[0]?.snapshot_id ?? null);
    } catch (e) {
      console.warn('Could not load snapshots:', e);
    }
  }, []);

  useEffect(() => {
    if (workflow === 'snapshot') loadSnapshots();
  }, [loadSnapshots, workflow]);

  // Handle successful ingestion
  const handleIngestSuccess = (res: IndexResponse) => {
    const newSnap: SnapshotItem = {
      snapshot_id: res.snapshot_id,
      root: 'Ingested Snapshot',
      indexed_at: new Date().toISOString(),
    };
    setSnapshots((prev) => [newSnap, ...prev]);
    setActiveSnapshotId(res.snapshot_id);
  };

  // Node selection in graph -> fetch evidence if available
  const handleSelectNode = async (nodeId: string) => {
    setSelectedNodeId(nodeId);
    if (!activeSnapshotId) return;

    try {
      const ids = evidenceForNode(graphEvidence || report?.graph_evidence || null, nodeId);
      const evidenceRes: any = await fetchEvidence(activeSnapshotId, ids, true);
      let ev: EvidenceItem | null = null;
      if (Array.isArray(evidenceRes?.evidence)) {
        ev = evidenceRes.evidence[0] || null;
      } else if (evidenceRes && typeof evidenceRes === 'object') {
        ev = evidenceRes[nodeId] || null;
      }
      setActiveEvidence(ev);
    } catch {
      setActiveEvidence(null);
    }
  };

  // Export handlers
  const handleExportMarkdown = () => {
    if (!report) return;
    const md = generateMarkdownReport(report);
    downloadFile(md, `impact-report-${report.target_id || (report as any).target || 'investigation'}.md`, 'text/markdown');
  };

  const handleExportJSON = () => {
    if (!report) return;
    const jsonStr = generateJSONReport(report);
    downloadFile(jsonStr, `impact-report-${report.target_id || (report as any).target || 'investigation'}.json`, 'application/json');
  };

  return (
    <div className="app-layout">
      <CommandBar
        showSnapshotControls={workflow === 'snapshot'}
        snapshots={snapshots}
        activeSnapshotId={activeSnapshotId}
        onSelectSnapshot={id => { reset(); setActiveEvidence(null); setSelectedNodeId(null); setActiveSnapshotId(id); }}
        onOpenIngest={() => setIsIngestOpen(true)}
        onExportMarkdown={handleExportMarkdown}
        onExportJSON={handleExportJSON}
        hasReport={report !== null}
      />

      <nav className="workflow-tabs" aria-label="Analysis workflow">
        <button className="apple-btn btn-secondary" aria-pressed={workflow === 'repository'} onClick={() => { reset(); setWorkflow('repository'); }}>Repository analysis</button>
        <button className="apple-btn btn-secondary" aria-pressed={workflow === 'snapshot'} onClick={() => setWorkflow('snapshot')}>Stored snapshot investigation</button>
      </nav>
      {workflow === 'repository' ? <RepositoryAnalysis /> : <>
      <p className="snapshot-context">Investigating stored repository: {snapshots.find(s => s.snapshot_id === activeSnapshotId)?.root ?? 'Select or ingest a repository above'}. This is independent of repository analysis.</p>

      <QueryCapsule
        key={activeSnapshotId}
        snapshotId={activeSnapshotId}
        isStreaming={status === 'streaming'}
        onInvestigate={startInvestigation}
        onStop={reset}
      />

      <TelemetryHUD
        thoughts={thoughts}
        isStreaming={status === 'streaming'}
      />

      {error && (
        <div className="error-banner">
          <div>
            <strong>Investigation Error:</strong> {error}
            {candidates && candidates.length > 0 && (
              <div style={{ marginTop: '0.25rem', fontSize: '0.75rem' }}>
                Ambiguous target candidates: {candidates.join(', ')}
              </div>
            )}
          </div>
          <button
            className="apple-btn"
            onClick={reset}
            style={{ color: 'var(--text-primary)', fontSize: '0.75rem' }}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="workspace-split">
        <section className="canvas-pane">
          <ErrorBoundary fallbackTitle="Graph Canvas Render Error">
            <GraphCanvas
              evidence={graphEvidence || report?.graph_evidence || null}
              targetSymbol={(report?.graph_evidence?.target as {qualified_name?: string} | undefined)?.qualified_name || report?.target_id || null}
              selectedNodeId={selectedNodeId}
              onSelectNode={handleSelectNode}
            />
          </ErrorBoundary>
        </section>

        <aside className="inspector-pane">
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <ErrorBoundary fallbackTitle="Code Inspector Render Error">
              <CodeInspector
                selectedSymbol={selectedNodeId}
                evidence={activeEvidence}
              />
            </ErrorBoundary>
          </div>
          <ErrorBoundary fallbackTitle="Analysis Gaps Render Error">
            <AnalysisGaps gaps={report?.analysis_gaps || null} />
          </ErrorBoundary>
        </aside>
      </div>

      </>}

      <IngestModal
        isOpen={isIngestOpen}
        onClose={() => setIsIngestOpen(false)}
        onSuccess={handleIngestSuccess}
      />
    </div>
  );
}
