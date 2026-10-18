import React, { useState } from 'react';
import { Search, Play, Square, Sparkles } from 'lucide-react';
import { InvestigateRequest } from '../types/api';
import './QueryCapsule.css';

interface QueryCapsuleProps {
  snapshotId: string | null;
  isStreaming: boolean;
  onInvestigate: (req: InvestigateRequest) => void;
  onStop: () => void;
}

export default function QueryCapsule({
  snapshotId,
  isStreaming,
  onInvestigate,
  onStop,
}: QueryCapsuleProps) {
  const [question, setQuestion] = useState('What functions and endpoints are impacted if I change validate_stock?');
  const [target, setTarget] = useState('inventory.validate_stock');
  const [provider, setProvider] = useState<'none' | 'test' | 'openai' | 'gemini' | 'ollama'>('test');
  const [shareSource, setShareSource] = useState(false);

  const handleRun = (e: React.FormEvent) => {
    e.preventDefault();
    if (!snapshotId || !question.trim()) return;

    onInvestigate({
      snapshot_id: snapshotId,
      question: question.trim(),
      target: target.trim() || undefined,
      provider,
      share_source: shareSource,
    });
  };

  return (
    <div className="query-capsule-container">
      <form onSubmit={handleRun}>
        <div className="query-bar">
          <Search size={16} color="var(--text-secondary)" />
          <input
            type="text"
            className="query-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask an investigation question (e.g. What happens if I modify inventory.validate_stock?)"
            disabled={isStreaming}
          />

          <input
            type="text"
            className="target-input"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="Target symbol (optional)"
            disabled={isStreaming}
            title="Qualified symbol name, e.g. inventory.validate_stock"
          />

          {isStreaming ? (
            <button
              type="button"
              className="apple-btn btn-secondary"
              onClick={onStop}
              style={{ color: 'var(--accent-rose)' }}
            >
              <Square size={13} fill="var(--accent-rose)" />
              <span>Stop</span>
            </button>
          ) : (
            <button
              type="submit"
              className="apple-btn btn-primary"
              disabled={!snapshotId || !question.trim()}
              style={{ opacity: !snapshotId || !question.trim() ? 0.5 : 1 }}
            >
              <Play size={13} fill="#fff" />
              <span>Run</span>
            </button>
          )}
        </div>

        <div className="query-options">
          <div className="options-left">
            <div className="option-item">
              <Sparkles size={13} color="var(--accent-blue)" />
              <span>Model Provider:</span>
              <select
                className="select-pill"
                value={provider}
                onChange={(e) => setProvider(e.target.value as any)}
                disabled={isStreaming}
              >
                <option value="test">Deterministic (test planner)</option>
                <option value="gemini">Gemini</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (local)</option>
                <option value="none">None (direct graph resolve)</option>
              </select>
            </div>

            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={shareSource}
                onChange={(e) => setShareSource(e.target.checked)}
                disabled={isStreaming}
              />
              <span>Share hash-verified source with model</span>
            </label>
          </div>

          <div style={{ color: 'var(--text-muted)' }}>
            Snapshot: {snapshotId ? snapshotId.slice(0, 8) : 'none selected'}
          </div>
        </div>
      </form>
    </div>
  );
}
