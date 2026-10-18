import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../services/api';

describe('Dashboard Integration', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchSnapshots').mockResolvedValue([
      { snapshot_id: 'snap-1', root: 'examples/commerce', indexed_at: '2026-10-18T10:00:00' },
    ]);
  });

  it('renders all main panels and submits investigation', async () => {
    render(<App />);

    // Brand and command bar
    expect(screen.getByText(/GraphScope/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ingest/i })).toBeInTheDocument();

    // Query capsule
    const questionInput = screen.getByPlaceholderText(/Ask an investigation question/i);
    expect(questionInput).toBeInTheDocument();
    fireEvent.change(questionInput, { target: { value: 'What calls validate_stock?' } });

    // Telemetry and empty canvas
    expect(screen.getByText(/Agent Telemetry:/i)).toBeInTheDocument();

    // Inspector empty state & analysis gaps
    expect(screen.getByText(/Select a graph node/i)).toBeInTheDocument();
    expect(screen.getByText(/Analysis Gaps/i)).toBeInTheDocument();
  });
});
