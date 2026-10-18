import React, { useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import { indexRepository } from '../services/api';
import { IndexResponse } from '../types/api';
import './IngestModal.css';

interface IngestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (res: IndexResponse) => void;
}

export default function IngestModal({ isOpen, onClose, onSuccess }: IngestModalProps) {
  const [rootPath, setRootPath] = useState('examples/commerce');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rootPath.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const response = await indexRepository(rootPath.trim());
      onSuccess(response);
      onClose();
    } catch (err: unknown) {
      setError((err as Error)?.message || 'Failed to ingest repository');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Ingest Repository</h2>
          <button className="apple-btn" onClick={onClose} style={{ padding: 4 }}>
            <X size={16} color="var(--text-secondary)" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <div>
              <label className="input-label" htmlFor="repo-path">
                Local Repository Path
              </label>
              <input
                id="repo-path"
                type="text"
                className="text-input"
                value={rootPath}
                onChange={(e) => setRootPath(e.target.value)}
                placeholder="e.g. examples/commerce or /path/to/repo"
                disabled={loading}
                autoFocus
              />
            </div>

            {error && (
              <div style={{ color: 'var(--accent-rose)', fontSize: '0.8rem', background: 'var(--accent-rose-subtle)', padding: '6px 10px', borderRadius: 6 }}>
                {error}
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="apple-btn btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="apple-btn btn-primary"
              disabled={loading || !rootPath.trim()}
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="spin" />
                  <span>Indexing...</span>
                </>
              ) : (
                <span>Start Ingest</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
