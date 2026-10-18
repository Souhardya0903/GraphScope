import { useState, useEffect, useCallback } from 'react';
import CommandBar from './components/CommandBar';
import IngestModal from './components/IngestModal';
import QueryCapsule from './components/QueryCapsule';
import TelemetryHUD from './components/TelemetryHUD';
import GraphCanvas from './components/GraphCanvas';
import CodeInspector from './components/CodeInspector';
import AnalysisGaps from './components/AnalysisGaps';
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
      if (list.length > 0 && !activeSnapshotId) {
        setActiveSnapshotId(list[0].snapshot_id);
      }
    } catch (e) {
      console.warn('Could not load snapshots:', e);
    }
  }, [activeSnapshotId]);

  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

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
      const evidenceMap = await fetchEvidence(activeSnapshotId, [nodeId], true);
      const ev = evidenceMap[nodeId] || null;
      setActiveEvidence(ev);
    } catch {
      setActiveEvidence(null);
    }
  };

  // Export handlers
  const handleExportMarkdown = () => {
    if (!report) return;
    const md = generateMarkdownReport(report);
    downloadFile(md, `impact-report-${report.target || 'investigation'}.md`, 'text/markdown');
  };

  const handleExportJSON = () => {
    if (!report) return;
    const jsonStr = generateJSONReport(report);
    downloadFile(jsonStr, `impact-report-${report.target || 'investigation'}.json`, 'application/json');
  };

  return (
    <div className="app-layout">
      <CommandBar
        snapshots={snapshots}
        activeSnapshotId={activeSnapshotId}
        onSelectSnapshot={setActiveSnapshotId}
        onOpenIngest={() => setIsIngestOpen(true)}
        onExportMarkdown={handleExportMarkdown}
        onExportJSON={handleExportJSON}
        hasReport={report !== null}
      />

      <QueryCapsule
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
          <GraphCanvas
            evidence={graphEvidence || report?.graph_evidence || null}
            targetSymbol={report?.target || null}
            selectedNodeId={selectedNodeId}
            onSelectNode={handleSelectNode}
          />
        </section>

        <aside className="inspector-pane">
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <CodeInspector
              selectedSymbol={selectedNodeId}
              evidence={activeEvidence}
            />
          </div>
          <AnalysisGaps gaps={report?.analysis_gaps || null} />
        </aside>
      </div>

      <IngestModal
        isOpen={isIngestOpen}
        onClose={() => setIsIngestOpen(false)}
        onSuccess={handleIngestSuccess}
      />
    </div>
  );
}
