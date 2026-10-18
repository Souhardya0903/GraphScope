import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AnalysisResults from '../components/AnalysisResults';
import { evidenceForNode } from '../utils/evidenceSelection';

describe('Change analysis workflow', () => {
  it('separates historical and current findings', () => {
    const before = { affected_functions: [{ id: 'old', qualified_name: 'deleted.work', file_path: 'old.py', start_line: 2 }] };
    render(<AnalysisResults result={{ before, after: { affected_functions: [] } }} onCandidate={vi.fn()} />);
    expect(screen.queryByText('deleted.work')).toBeNull();
    fireEvent.change(screen.getByLabelText('Snapshot side'), { target: { value: 'before' } });
    expect(screen.getByText('deleted.work')).toBeInTheDocument();
  });
  it('requires selection before confirmation', () => {
    const select = vi.fn();
    render(<AnalysisResults result={{ status: 'confirmation_required', candidates: [{ id: 'id', qualified_name: 'app.work' }] }} onCandidate={select} />);
    fireEvent.click(screen.getByText('Use app.work'));
    expect(select).toHaveBeenCalledWith('app.work');
  });
  it('maps graph names to evidence call-site IDs', () => {
    const graph = { paths: [{ functions: ['app.caller', 'app.work'], function_ids: ['a', 'b'], evidence_ids: ['site'] }] };
    expect(evidenceForNode(graph as never, 'app.work')).toEqual(['site']);
    expect(evidenceForNode(graph as never, 'unknown')).toEqual([]);
  });
});
