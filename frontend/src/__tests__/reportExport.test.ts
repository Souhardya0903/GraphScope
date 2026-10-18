import { describe, it, expect } from 'vitest';
import { generateMarkdownReport, generateJSONReport } from '../utils/reportExport';
import { ImpactReport } from '../types/api';

describe('reportExport', () => {
  const sampleReport: ImpactReport = {
    snapshot_id: 'snap-12345',
    target: 'inventory.validate_stock',
    question: 'Change impact',
    summary: 'High blast radius across orders and checkout routes',
    affected_endpoints: ['/api/checkout', '/api/orders'],
    graph_evidence: {
      paths: [['orders.checkout', 'inventory.validate_stock']],
    },
    analysis_gaps: {
      unresolved_calls: [{ symbol: 'dynamic_dispatch', file: 'dispatcher.py', line: 42 }],
    },
    recommendations: ['Add regression tests for checkout endpoints'],
  };

  it('generates formatted markdown with target and affected endpoints', () => {
    const md = generateMarkdownReport(sampleReport);
    expect(md).toContain('# Impact Report: inventory.validate_stock');
    expect(md).toContain('/api/checkout');
    expect(md).toContain('dynamic_dispatch');
    expect(md).toContain('High blast radius');
  });

  it('generates valid JSON export string', () => {
    const jsonStr = generateJSONReport(sampleReport);
    const parsed = JSON.parse(jsonStr);
    expect(parsed.target).toBe('inventory.validate_stock');
    expect(parsed.snapshot_id).toBe('snap-12345');
  });
});
