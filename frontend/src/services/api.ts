import { SnapshotItem, IndexResponse, EvidenceItem } from '../types/api';

export async function fetchSnapshots(): Promise<SnapshotItem[]> {
  const res = await fetch('/api/snapshots');
  if (!res.ok) {
    throw new Error(`Failed to fetch snapshots: ${res.statusText}`);
  }
  const data = await res.json();
  return data.snapshots || [];
}

export async function indexRepository(root: string): Promise<IndexResponse> {
  const res = await fetch('/api/index', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to index repository');
  }
  return res.json();
}

export async function fetchEvidence(
  snapshotId: string,
  evidenceIds: string[],
  includeSource: boolean = true
): Promise<{ evidence: EvidenceItem[]; missing_ids: string[] }> {
  if (!evidenceIds.length) return { evidence: [], missing_ids: [] };
  const params = new URLSearchParams({
    snapshot_id: snapshotId,
    evidence_ids: evidenceIds.join(','),
    include_source: String(includeSource),
  });
  const res = await fetch(`/api/evidence?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch evidence: ${res.statusText}`);
  }
  const data = await res.json();
  return {
    evidence: (data.evidence ?? []).map((item: Record<string, unknown>) => ({
      edge_id: String(item.id ?? item.edge_id ?? ''),
      caller_function: String(item.caller_function ?? ''),
      callee_function: String(item.target_text ?? item.callee_function ?? ''),
      file_path: String(item.file_path ?? ''),
      line_number: Number(item.line ?? item.line_number ?? 1),
      hash: String(item.content_hash ?? item.hash ?? ''),
      source_lines: typeof item.source === 'string' ? item.source.replace(/\n$/, '').split('\n') : undefined,
    })),
    missing_ids: data.missing_ids ?? [],
  };
}
