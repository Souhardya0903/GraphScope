import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import CodeInspector from '../components/CodeInspector';

describe('CodeInspector', () => {
  it('renders empty state placeholder when no symbol is selected', () => {
    render(<CodeInspector selectedSymbol={null} evidence={null} />);
    expect(screen.getByText(/Select a graph node/i)).toBeInTheDocument();
  });

  it('renders source lines and SHA256 badge when evidence is provided', () => {
    const evidence = {
      edge_id: 'e1',
      caller_function: 'checkout',
      callee_function: 'validate_stock',
      file_path: 'orders/checkout.py',
      line_number: 2,
      hash: 'abc123hash',
      source_lines: ['def checkout():', '    validate_stock()', '    return True'],
    };
    render(<CodeInspector selectedSymbol="checkout" evidence={evidence} />);
    expect(screen.getByText(/orders\/checkout.py/i)).toBeInTheDocument();
    expect(screen.getByText(/SHA256 Verified/i)).toBeInTheDocument();
    expect(screen.getByText(/validate_stock\(\)/i)).toBeInTheDocument();
  });
});
