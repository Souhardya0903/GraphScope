import { Code2, ShieldCheck, FileText } from 'lucide-react';
import { EvidenceItem } from '../types/api';
import './CodeInspector.css';

interface CodeInspectorProps {
  selectedSymbol: string | null;
  evidence: EvidenceItem | null;
}

export default function CodeInspector({ selectedSymbol, evidence }: CodeInspectorProps) {
  if (!selectedSymbol && !evidence) {
    return (
      <div className="inspector-panel">
        <div className="empty-inspector">
          <Code2 size={28} color="var(--text-muted)" />
          <p style={{ fontSize: '0.85rem' }}>Select a graph node or caller to inspect code evidence.</p>
          <span style={{ fontSize: '0.72rem' }}>Source lines are hash-verified directly from the snapshot.</span>
        </div>
      </div>
    );
  }

  let lines: string[] = [];
  if (Array.isArray(evidence?.source_lines)) {
    lines = evidence.source_lines;
  } else if (typeof (evidence as any)?.source === 'string') {
    lines = (evidence as any).source.split('\n');
  }

  const targetLine = evidence?.line_number || (evidence as any)?.line || 1;

  return (
    <div className="inspector-panel">
      <div className="inspector-header">
        <div className="inspector-title">
          <Code2 size={15} color="var(--accent-blue)" />
          <span>Code Inspector</span>
        </div>
        {evidence?.hash && (
          <div className="hash-badge" title={`SHA256: ${evidence.hash}`}>
            <ShieldCheck size={12} />
            <span>SHA256 Verified</span>
          </div>
        )}
      </div>

      <div className="file-meta">
        <span>{evidence?.file_path || selectedSymbol || 'Unknown file'}</span>
        {evidence?.line_number && <span>Line {evidence.line_number}</span>}
      </div>

      <div className="code-viewer">
        {lines.length > 0 ? (
          lines.map((lineContent, idx) => {
            const currentLineNum = targetLine + idx;
            const isHighlighted = currentLineNum === targetLine;

            return (
              <div
                key={idx}
                className={`code-line ${isHighlighted ? 'highlighted' : ''}`}
              >
                <span className="line-number">{currentLineNum}</span>
                <span className="line-content">{lineContent}</span>
              </div>
            );
          })
        ) : (
          <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            <FileText size={20} style={{ margin: '0 auto 0.5rem auto', display: 'block' }} />
            No inline source excerpt captured for this symbol.
            <div style={{ fontSize: '0.7rem', marginTop: '0.25rem' }}>
              (Enable "Share hash-verified source" to view full context)
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
