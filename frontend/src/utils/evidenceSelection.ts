import { GraphEvidencePayload } from '../types/api';

export function evidenceForNode(evidence: GraphEvidencePayload | null, node: string): string[] {
  const ids = new Set<string>();
  for (const value of evidence?.paths ?? []) {
    if (Array.isArray(value) || !value || typeof value !== 'object') continue;
    const path = value as Record<string, unknown>;
    const names = Array.isArray(path.functions) ? path.functions : [];
    const functions = Array.isArray(path.function_ids) ? path.function_ids : [];
    const edges = Array.isArray(path.evidence_ids) ? path.evidence_ids : [];
    for (let i = 0; i < Math.max(names.length, functions.length); i++) {
      if (names[i] === node || functions[i] === node) {
        if (typeof edges[i] === 'string') ids.add(edges[i] as string);
        if (typeof edges[i - 1] === 'string') ids.add(edges[i - 1] as string);
      }
    }
  }
  return [...ids];
}
