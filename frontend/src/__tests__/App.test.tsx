import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../services/api';

describe('App Shell', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchSnapshots').mockResolvedValue([]);
  });

  it('separates repository inputs from snapshot investigation and removes demo defaults', () => {
    render(<App />);
    expect(screen.queryByLabelText('Investigation question')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Repository path')).toHaveValue('');
    expect(screen.queryByText('target', { exact: true })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Stored snapshot investigation' }));
    expect(screen.getByLabelText('Investigation question')).toHaveValue('');
    expect(screen.getByLabelText('Investigation target')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Run' })).toBeDisabled();
  });

  it('renders GraphScope brand header', () => {
    render(<App />);
    expect(screen.getByText(/GraphScope/i)).toBeInTheDocument();
  });
});
