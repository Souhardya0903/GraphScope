import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import RepositoryAnalysis from '../components/RepositoryAnalysis';

afterEach(() => { vi.unstubAllGlobals(); });
describe('Repository analysis API integration', () => {
  it('submits repository changes and exposes the result', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ mode: 'actual-change', changes: [] }) });
    vi.stubGlobal('fetch', fetch);
    render(<RepositoryAnalysis />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyze repository' }));
    await waitFor(() => expect(screen.getByText('Export analysis JSON')).toBeInTheDocument());
    expect(fetch).toHaveBeenCalledWith('/api/analysis/changes', expect.objectContaining({ body: expect.stringContaining('worktree') }));
  });
  it('shows backend validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Missing repository' }) }));
    render(<RepositoryAnalysis />);
    fireEvent.click(screen.getByRole('button', { name: 'Analyze repository' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Missing repository');
  });
});

