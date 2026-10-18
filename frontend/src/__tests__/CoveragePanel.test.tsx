import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import CoveragePanel from '../components/CoveragePanel';

describe('Coverage reporting', () => {
  it('separates repository totals from calls in found affected functions', () => {
    render(<CoveragePanel report={{ affected_functions: [{ id: 'target', file_path: 'a.py' }], analysis_gaps: [{ path: 'a.py', reason: 'Nested function body skipped' }, { path: 'b.py', reason: 'Unsupported decorator' }], unresolved_calls: [{ owner_id: 'target', file_path: 'a.py', line: 4, target_text: 'other()', reason: 'Unknown target' }, { owner_id: 'outside', file_path: 'b.py', line: 3, reason: 'Outside target' }, { owner_id: 'target', reason: 'Python builtin call; no repository function target' }] }} />);
    fireEvent.click(screen.getByText('Analysis coverage & limitations'));
    expect(screen.getByText(/Repository-wide: 2 limitation records/)).toBeInTheDocument();
    expect(screen.getByText('Unknown target')).toBeInTheDocument();
    expect(screen.queryByText('Outside target')).not.toBeInTheDocument();
    expect(screen.getByText(/inside found affected functions/)).toHaveTextContent('1 unresolved calls');
    fireEvent.change(screen.getByLabelText('Coverage scope'), { target: { value: 'repository' } });
    expect(screen.getByText('Outside target')).toBeInTheDocument();
  });
  it('includes unresolved callsites in mapping reports', () => {
    render(<CoveragePanel report={{ callsites: [{ target_id: null, reason: 'Dynamic target' }, { target_id: 'resolved', reason: 'Explicit' }] }} />);
    fireEvent.click(screen.getByText('Analysis coverage & limitations'));
    expect(screen.getByText('Dynamic target')).toBeInTheDocument();
    expect(screen.queryByText('Explicit')).not.toBeInTheDocument();
  });
});
