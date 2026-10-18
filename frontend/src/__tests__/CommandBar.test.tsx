import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CommandBar from '../components/CommandBar';

describe('CommandBar', () => {
  it('displays active snapshot root and triggers ingest modal', () => {
    const onOpenIngest = vi.fn();
    render(
      <CommandBar
        snapshots={[{ snapshot_id: 'snap-1', root: 'examples/commerce', indexed_at: '2026-10-18T10:00:00' }]}
        activeSnapshotId="snap-1"
        onSelectSnapshot={() => {}}
        onOpenIngest={onOpenIngest}
        onExportMarkdown={() => {}}
        onExportJSON={() => {}}
        hasReport={false}
      />
    );
    expect(screen.getByText(/examples\/commerce/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /ingest/i }));
    expect(onOpenIngest).toHaveBeenCalled();
  });
});
