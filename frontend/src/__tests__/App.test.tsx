import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../App';
import * as api from '../services/api';

describe('App Shell', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchSnapshots').mockResolvedValue([]);
  });

  it('renders GraphScope brand header', () => {
    render(<App />);
    expect(screen.getByText(/GraphScope/i)).toBeInTheDocument();
  });
});
