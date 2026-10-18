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


it('shows workspace totals, namespaced functions, and per-service details', () => {
  const result = { mode: 'workspace-map', snapshots: {
    stock: { functions: [{ id: 's', qualified_name: 'app.work', file_path: 'app.py' }], endpoints: [{ id: 'route', method: 'GET', path: '/stock', handler_id: 's' }] },
    client: { functions: [{ id: 'c', qualified_name: 'app.work', file_path: 'app.py' }], calls: [], endpoints: [] },
  }, service_links: [{ source_service: 'client', target_service: 'stock', kind: 'http-contract', caller_id: 'c', callee_id: 's', confidence: 'inferred', rule: 'contract-test', request_evidence: { file_path: 'client.ts', line: 4 }, endpoint_evidence: { file_path: 'app.py', line: 8 } }] };
  render(<AnalysisResults result={result} onCandidate={vi.fn()} />);
  expect(screen.getByLabelText('Workspace overview')).toHaveTextContent('2 services · 1 inferred service contracts');
  expect(screen.getByLabelText('Analysis summary').querySelector('strong')).toHaveTextContent('2');
  expect(screen.getByRole('button', { name: 'Inspect stock::app.work' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Inspect client::app.work' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Service view'), { target: { value: 'stock' } });
  expect(screen.getByLabelText('Analysis summary').querySelector('strong')).toHaveTextContent('1');
  expect(screen.queryByRole('button', { name: 'Inspect client::app.work' })).not.toBeInTheDocument();
});
