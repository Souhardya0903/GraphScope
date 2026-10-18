import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TelemetryHUD from '../components/TelemetryHUD';

describe('TelemetryHUD', () => {
  it('renders step pills for agent thoughts', () => {
    const thoughts = [
      { step: 'resolve_symbol', detail: 'Resolving inventory.validate_stock' },
      { step: 'trace_callers', detail: 'Found 3 caller paths' },
    ];
    render(<TelemetryHUD thoughts={thoughts} isStreaming={true} />);
    expect(screen.getByText(/resolve_symbol/i)).toBeInTheDocument();
    expect(screen.getByText(/trace_callers/i)).toBeInTheDocument();
  });

  it('renders empty placeholder when no thoughts exist', () => {
    render(<TelemetryHUD thoughts={[]} isStreaming={false} />);
    expect(screen.getByText(/Agent idle/i)).toBeInTheDocument();
  });
});
