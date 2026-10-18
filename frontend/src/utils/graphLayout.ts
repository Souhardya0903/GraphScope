import { GraphEvidencePayload } from '../types/api';

export interface GraphNode {
  id: string;
  label: string;
  isTarget: boolean;
  isEndpoint: boolean;
  x: number;
  y: number;
  layer: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export function buildGraphData(
  evidence: GraphEvidencePayload | null,
  targetSymbol: string | null
): GraphData {
  const nodesMap = new Map<string, { isTarget: boolean; isEndpoint: boolean; layer: number }>();
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];

  const effectiveTarget = targetSymbol || 'target';

  // Always seed target node
  nodesMap.set(effectiveTarget, { isTarget: true, isEndpoint: false, layer: 0 });

  if (evidence?.paths) {
    for (const path of evidence.paths) {
      if (!Array.isArray(path) || path.length === 0) continue;

      // Paths are typically caller -> ... -> target or target -> ...
      for (let i = 0; i < path.length; i++) {
        const symbol = path[i];
        const isTarget = symbol === effectiveTarget;
        const layer = path.length - 1 - i; // distance from target

        if (!nodesMap.has(symbol)) {
          nodesMap.set(symbol, { isTarget, isEndpoint: false, layer });
        } else {
          const current = nodesMap.get(symbol)!;
          if (layer > current.layer) current.layer = layer;
        }

        if (i < path.length - 1) {
          const source = path[i];
          const target = path[i + 1];
          const edgeId = `${source}->${target}`;
          if (!edgeSet.has(edgeId)) {
            edgeSet.add(edgeId);
            edges.push({ id: edgeId, source, target });
          }
        }
      }
    }
  }

  // Endpoints are layer = max layer + 1
  const maxCallerLayer = Array.from(nodesMap.values()).reduce((max, n) => Math.max(max, n.layer), 0);
  const endpointLayer = maxCallerLayer + 1;

  if (evidence?.potentially_affected_endpoints) {
    for (const ep of evidence.potentially_affected_endpoints) {
      if (!nodesMap.has(ep)) {
        nodesMap.set(ep, { isTarget: false, isEndpoint: true, layer: endpointLayer });
      }
      // Connect first caller or target to endpoint
      const callerCandidates = Array.from(nodesMap.keys()).filter((k) => k !== ep && !nodesMap.get(k)?.isEndpoint);
      const rootCaller = callerCandidates.find((k) => nodesMap.get(k)?.layer === maxCallerLayer) || effectiveTarget;
      const edgeId = `${ep}->${rootCaller}`;
      if (!edgeSet.has(edgeId)) {
        edgeSet.add(edgeId);
        edges.push({ id: edgeId, source: ep, target: rootCaller });
      }
    }
  }

  // Position nodes by layer (horizontal DAG: Endpoints (left) -> Callers (middle) -> Target (right))
  const layersMap = new Map<number, string[]>();
  nodesMap.forEach((info, id) => {
    const list = layersMap.get(info.layer) || [];
    list.push(id);
    layersMap.set(info.layer, list);
  });

  const nodes: GraphNode[] = [];
  const layerSpacingX = 260;
  const nodeSpacingY = 90;

  layersMap.forEach((idsInLayer, layer) => {
    const totalHeight = (idsInLayer.length - 1) * nodeSpacingY;
    const startY = 200 - totalHeight / 2;

    idsInLayer.forEach((id, idx) => {
      const info = nodesMap.get(id)!;
      // Invert x so Endpoint is on the left, Target is on the right
      const x = 100 + (endpointLayer - layer) * layerSpacingX;
      const y = startY + idx * nodeSpacingY;

      nodes.push({
        id,
        label: id.includes('.') ? id.split('.').pop()! : id,
        isTarget: info.isTarget,
        isEndpoint: info.isEndpoint,
        x,
        y,
        layer,
      });
    });
  });

  return { nodes, edges };
}
