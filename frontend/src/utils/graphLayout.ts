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
  const nodesMap = new Map<string, { label: string; isTarget: boolean; isEndpoint: boolean; layer: number }>();
  const edgeSet = new Set<string>();
  const edges: GraphEdge[] = [];

  const effectiveTarget = targetSymbol || '';

  // Always seed target node
  const targetLabel = effectiveTarget.includes('.') ? effectiveTarget.split('.').pop()! : effectiveTarget;
  if (effectiveTarget) nodesMap.set(effectiveTarget, { label: targetLabel, isTarget: true, isEndpoint: false, layer: 0 });

  if (evidence?.paths) {
    for (const rawPath of evidence.paths) {
      // Path can be string[] or { functions: string[] } or { function_ids: string[] }
      let functionList: string[] = [];
      if (Array.isArray(rawPath)) {
        functionList = rawPath.map(String);
      } else if (rawPath && typeof rawPath === 'object') {
        const obj = rawPath as Record<string, unknown>;
        if (Array.isArray(obj.functions)) {
          functionList = obj.functions.map(String);
        } else if (Array.isArray(obj.function_ids)) {
          functionList = obj.function_ids.map(String);
        }
      }

      if (functionList.length === 0) continue;

      for (let i = 0; i < functionList.length; i++) {
        const symbol = String(functionList[i]);
        const isTarget = symbol === effectiveTarget;
        const layer = functionList.length - 1 - i;
        const label = symbol.includes('.') ? symbol.split('.').pop()! : symbol;

        if (!nodesMap.has(symbol)) {
          nodesMap.set(symbol, { label, isTarget, isEndpoint: false, layer });
        } else {
          const current = nodesMap.get(symbol)!;
          if (layer > current.layer) current.layer = layer;
        }

        if (i < functionList.length - 1) {
          const source = String(functionList[i]);
          const target = String(functionList[i + 1]);
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
    for (const rawEp of evidence.potentially_affected_endpoints) {
      let epId: string;
      let epLabel: string;

      if (typeof rawEp === 'string') {
        epId = rawEp;
        epLabel = rawEp;
      } else if (rawEp && typeof rawEp === 'object') {
        const epObj = rawEp as Record<string, unknown>;
        const method = epObj.method ? String(epObj.method) : 'ROUTE';
        const path = epObj.path ? String(epObj.path) : (epObj.id ? String(epObj.id) : 'endpoint');
        epId = `${method} ${path}`;
        epLabel = `${method} ${path}`;
      } else {
        epId = String(rawEp);
        epLabel = String(rawEp);
      }

      if (!nodesMap.has(epId)) {
        nodesMap.set(epId, { label: epLabel, isTarget: false, isEndpoint: true, layer: endpointLayer });
      }

      // Connect root callers to endpoint
      const callerCandidates = Array.from(nodesMap.keys()).filter((k) => k !== epId && !nodesMap.get(k)?.isEndpoint);
      const rootCaller = callerCandidates.find((k) => nodesMap.get(k)?.layer === maxCallerLayer) || effectiveTarget;
      const edgeId = `${epId}->${rootCaller}`;
      if (!edgeSet.has(edgeId)) {
        edgeSet.add(edgeId);
        edges.push({ id: edgeId, source: epId, target: rootCaller });
      }
    }
  }

  // Position nodes by layer
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
      const x = 100 + (endpointLayer - layer) * layerSpacingX;
      const y = startY + idx * nodeSpacingY;

      nodes.push({
        id,
        label: info.label,
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
