import { describe, it, expect } from 'vitest';
import { buildGraphData } from '../utils/graphLayout';

describe('buildGraphData', () => {
  it('extracts nodes and edges from caller paths and endpoints', () => {
    const evidence = {
      paths: [
        ['orders.checkout', 'cart.process', 'inventory.validate_stock'],
      ],
      potentially_affected_endpoints: ['/api/checkout'],
    };
    const { nodes, edges } = buildGraphData(evidence, 'inventory.validate_stock');
    expect(nodes.some((n) => n.id === 'inventory.validate_stock' && n.isTarget)).toBe(true);
    expect(nodes.some((n) => n.id === '/api/checkout' && n.isEndpoint)).toBe(true);
    expect(nodes.some((n) => n.id === 'orders.checkout' && !n.isTarget && !n.isEndpoint)).toBe(true);
    expect(edges.length).toBeGreaterThan(0);
  });

  it('handles null evidence gracefully with single target node', () => {
    const { nodes, edges } = buildGraphData(null, 'inventory.validate_stock');
    expect(nodes.length).toBe(1);
    expect(nodes[0].id).toBe('inventory.validate_stock');
    expect(nodes[0].isTarget).toBe(true);
    expect(edges.length).toBe(0);
  });
});
