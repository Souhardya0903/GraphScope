import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../App';

describe('App Shell', () => {
  it('renders GraphScope brand header', () => {
    render(<App />);
    expect(screen.getByText(/GraphScope/i)).toBeInTheDocument();
  });
});
