import { AlertTriangle, Info } from 'lucide-react';
import { AnalysisGapsPayload } from '../types/api';
import './AnalysisGaps.css';

interface AnalysisGapsProps {
  gaps: AnalysisGapsPayload | null;
}

export default function AnalysisGaps({ gaps }: AnalysisGapsProps) {
  const unresolved = gaps?.unresolved_calls || [];

  return (
    <div className="gaps-panel">
      <div className="gaps-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <AlertTriangle size={14} color="var(--accent-amber)" />
          <span>Analysis Gaps & Blind Spots</span>
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {unresolved.length} flagged
        </span>
      </div>

      {unresolved.length === 0 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-muted)', fontSize: '0.75rem', padding: '0.3rem 0' }}>
          <Info size={13} />
          <span>No unresolvable calls or dynamic dispatch blind spots detected.</span>
        </div>
      ) : (
        unresolved.map((gap: any, idx: number) => (
          <div key={idx} className="gap-item">
            <span className="gap-symbol">{gap.symbol || 'Dynamic Dispatch Call'}</span>
            <span className="gap-location">
              {gap.file || 'unknown'}:{gap.line || '?'} {gap.reason ? `(${gap.reason})` : ''}
            </span>
          </div>
        ))
      )}
    </div>
  );
}
