import { describe, it, expect } from 'vitest';
import { buildGraphData } from '../utils/graphLayout';

describe('buildGraphData', () => {
  it('does not invent a target when no analysis exists', () => {
    expect(buildGraphData(null, null)).toEqual({ nodes: [], edges: [] });
  });
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

  it('handles real backend payload with object caller_paths and endpoint dicts', () => {
    const realBackendEvidence = {
      paths: [
        {
          functions: ['orders.checkout', 'cart.process', 'inventory.validate_stock'],
          function_ids: ['fn_1', 'fn_2', 'fn_3'],
          evidence_ids: ['ev_1', 'ev_2'],
        },
      ],
      potentially_affected_endpoints: [
        {
          id: 'ep_1',
          method: 'POST',
          path: '/api/checkout',
          handler_id: 'fn_1',
        },
      ],
    };
    const { nodes, edges } = buildGraphData(realBackendEvidence as any, 'inventory.validate_stock');
    expect(nodes.length).toBeGreaterThan(1);
    expect(edges.length).toBeGreaterThan(0);
    const epNode = nodes.find((n) => n.isEndpoint);
    expect(epNode).toBeDefined();
    expect(typeof epNode?.id).toBe('string');
    expect(typeof epNode?.label).toBe('string');
    expect(epNode?.label).toContain('/api/checkout');
  });
});


it('connects each endpoint only to its declared handler across branches', () => {
  const graph = buildGraphData({ paths: [['orders.create', 'inventory.check'], ['reservations.reserve', 'inventory.check']], potentially_affected_endpoints: [
    { id: 'orders-route', method: 'POST', path: '/orders', handler_symbol: 'orders.create' },
    { id: 'reserve-route', method: 'POST', path: '/reservations', handler_symbol: 'reservations.reserve' },
    { id: 'unknown-route', method: 'GET', path: '/unknown' },
  ] }, 'inventory.check');
  expect(graph.edges.filter(edge => edge.source.endsWith('-route'))).toEqual([
    { id: 'orders-route->orders.create', source: 'orders-route', target: 'orders.create' },
    { id: 'reserve-route->reservations.reserve', source: 'reserve-route', target: 'reservations.reserve' },
  ]);
});

it('resolves stored-snapshot handler IDs through path identity metadata', () => {
  const graph = buildGraphData({ paths: [{ function_ids: ['a', 'b'], functions: ['orders.create', 'inventory.check'] }], potentially_affected_endpoints: [{ id: 'route', method: 'POST', path: '/orders', handler_id: 'a' }] }, 'inventory.check');
  expect(graph.edges).toContainEqual({ id: 'route->orders.create', source: 'route', target: 'orders.create' });
});
