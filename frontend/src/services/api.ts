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
): Promise<Record<string, EvidenceItem>> {
  if (!evidenceIds.length) return {};
  const params = new URLSearchParams({
    snapshot_id: snapshotId,
    evidence_ids: evidenceIds.join(','),
    include_source: String(includeSource),
  });
  const res = await fetch(`/api/evidence?${params.toString()}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch evidence: ${res.statusText}`);
  }
  return res.json();
}
