import { FolderGit2, Plus, Download, FileJson } from 'lucide-react';
import { SnapshotItem } from '../types/api';
import './CommandBar.css';

interface CommandBarProps {
  snapshots: SnapshotItem[];
  activeSnapshotId: string | null;
  onSelectSnapshot: (id: string) => void;
  onOpenIngest: () => void;
  onExportMarkdown: () => void;
  onExportJSON: () => void;
  hasReport: boolean;
}

export default function CommandBar({
  snapshots,
  activeSnapshotId,
  onSelectSnapshot,
  onOpenIngest,
  onExportMarkdown,
  onExportJSON,
  hasReport,
}: CommandBarProps) {

  return (
    <header className="command-bar">
      <div className="brand-section">
        <div className="brand-indicator" />
        <h1 className="brand-title">GraphScope</h1>
        <span className="brand-badge">Gemini</span>
      </div>

      <div className="repo-controls">
        <FolderGit2 size={16} color="var(--text-secondary)" />
        {snapshots.length > 0 ? (
          <select
            className="snapshot-select"
            value={activeSnapshotId || ''}
            onChange={(e) => onSelectSnapshot(e.target.value)}
          >
            {snapshots.map((s) => (
              <option key={s.snapshot_id} value={s.snapshot_id}>
                {s.root} ({s.snapshot_id.slice(0, 8)})
              </option>
            ))}
          </select>
        ) : (
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            No snapshots available
          </span>
        )}

        <button
          className="apple-btn btn-secondary"
          onClick={onOpenIngest}
          aria-label="Ingest Local Repository"
        >
          <Plus size={14} />
          <span>Ingest Local</span>
        </button>
      </div>

      <div className="export-group">
        <button
          className="apple-btn btn-secondary"
          onClick={onExportMarkdown}
          disabled={!hasReport}
          style={{ opacity: hasReport ? 1 : 0.4, cursor: hasReport ? 'pointer' : 'not-allowed' }}
        >
          <Download size={14} />
          <span>Markdown</span>
        </button>
        <button
          className="apple-btn btn-secondary"
          onClick={onExportJSON}
          disabled={!hasReport}
          style={{ opacity: hasReport ? 1 : 0.4, cursor: hasReport ? 'pointer' : 'not-allowed' }}
        >
          <FileJson size={14} />
          <span>JSON</span>
        </button>
      </div>
    </header>
  );
}
