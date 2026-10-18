import React from 'react';
import { Activity, CheckCircle2, ChevronRight } from 'lucide-react';
import { AgentThoughtPayload } from '../types/api';
import './TelemetryHUD.css';

interface TelemetryHUDProps {
  thoughts: AgentThoughtPayload[];
  isStreaming: boolean;
}

export default function TelemetryHUD({ thoughts, isStreaming }: TelemetryHUDProps) {
  if (thoughts.length === 0) {
    return (
      <div className="telemetry-hud">
        <div className="hud-label">
          <Activity size={13} color="var(--text-muted)" />
          <span>Agent Telemetry:</span>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Agent idle. Submit a query above to stream investigation steps.
        </span>
      </div>
    );
  }

  return (
    <div className="telemetry-hud">
      <div className="hud-label">
        <Activity size={13} color={isStreaming ? 'var(--accent-blue)' : 'var(--accent-emerald)'} />
        <span>Agent Telemetry:</span>
      </div>

      <div className="step-pill-list">
        {thoughts.map((th, index) => {
          const isLast = index === thoughts.length - 1;
          const isActive = isLast && isStreaming;

          return (
            <React.Fragment key={index}>
              <div
                className={`step-pill ${isActive ? 'active' : 'completed'}`}
                title={th.detail}
              >
                {isActive ? (
                  <div className="pulse-dot" />
                ) : (
                  <CheckCircle2 size={12} color="var(--accent-emerald)" />
                )}
                <span style={{ fontWeight: 500 }}>{th.step}</span>
                {th.detail && (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                    ({th.detail.length > 30 ? th.detail.slice(0, 30) + '...' : th.detail})
                  </span>
                )}
              </div>
              {!isLast && <ChevronRight size={12} color="var(--border-highlight)" />}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
