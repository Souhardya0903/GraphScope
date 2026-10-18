import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchEvidence } from '../services/api';

afterEach(() => { vi.unstubAllGlobals(); });
describe('Evidence API contract', () => {
  it('normalizes actual backend hashes and source line offsets', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ evidence: [{ id: 'site', file_path: 'app.py', line: 40, content_hash: 'verified', source: 'work()\n' }], missing_ids: [] }) }));
    const response = await fetchEvidence('snapshot', ['site'], true);
    expect(response.evidence[0]).toMatchObject({ edge_id: 'site', line_number: 40, hash: 'verified', source_lines: ['work()'] });
  });
});
