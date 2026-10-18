import { useId, useMemo, useState, PointerEvent } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { GraphEvidencePayload } from '../types/api';
import { buildGraphData } from '../utils/graphLayout';
import './GraphCanvas.css';

interface GraphCanvasProps {
  evidence: GraphEvidencePayload | null;
  targetSymbol: string | null;
  selectedNodeId: string | null;
  onSelectNode: (id: string) => void;
  onSelectEdge?: (edgeId: string) => void;
}
const WIDTH = 280;
const HEIGHT = 68;

export default function GraphCanvas({ evidence, targetSymbol, selectedNodeId, onSelectNode }: GraphCanvasProps) {
  const markerId = useId().replace(/:/g, '');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const graph = useMemo(() => buildGraphData(evidence, targetSymbol), [evidence, targetSymbol]);
  const nodes = useMemo(() => new Map(graph.nodes.map(node => [node.id, node])), [graph]);
  const bounds = useMemo(() => {
    const xs = graph.nodes.map(n => n.x);
    const ys = graph.nodes.map(n => n.y);
    const left = Math.min(...xs) - WIDTH / 2 - 50;
    const top = Math.min(...ys) - 70;
    return { x: left, y: top, width: Math.max(...xs) + WIDTH / 2 + 50 - left, height: Math.max(340, Math.max(...ys) + HEIGHT + 70 - top) };
  }, [graph]);
  const viewWidth = bounds.width / zoom;
  const viewHeight = bounds.height / zoom;
  const viewX = bounds.x + (bounds.width - viewWidth) / 2 - pan.x;
  const viewY = bounds.y + (bounds.height - viewHeight) / 2 - pan.y;
  function move(event: PointerEvent<SVGSVGElement>) {
    if (!drag) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const scale = Math.max(viewWidth / rect.width, viewHeight / rect.height);
    setPan(p => ({ x: p.x + (event.clientX - drag.x) * scale, y: p.y + (event.clientY - drag.y) * scale }));
    setDrag({ x: event.clientX, y: event.clientY });
  }
  if (!graph.nodes.length) return <div className="graph-empty" role="status">No dependency graph to display. Run an analysis to see resolved relationships.</div>;
  return <div className="graph-canvas-container">
    <div className="canvas-toolbar">
      <button className="apple-btn" onClick={() => setZoom(z => Math.min(z * 1.3, 12))} title="Zoom In" aria-label="Zoom in"><ZoomIn size={16} /></button>
      <button className="apple-btn" onClick={() => setZoom(z => Math.max(z / 1.3, .4))} title="Zoom Out" aria-label="Zoom out"><ZoomOut size={16} /></button>
      <span>{Math.round(zoom * 100)}%</span>
      <button className="apple-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} title="Fit graph" aria-label="Fit graph"><Maximize2 size={16} /></button>
    </div>
    <div className="canvas-legend"><span><i className="legend-dot caller" />Function</span><span><i className="legend-dot target" />Change target</span><span><i className="legend-dot endpoint" />Endpoint</span></div>
    <svg className="graph-svg" aria-label="Dependency graph" viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`}
      onPointerDown={event => { if (!(event.target as Element).closest('.graph-node')) { event.currentTarget.setPointerCapture(event.pointerId); setDrag({ x: event.clientX, y: event.clientY }); } }}
      onPointerMove={move} onPointerUp={() => setDrag(null)} onPointerCancel={() => setDrag(null)}>
      <defs><marker id={markerId} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#647b91" /></marker></defs>
      {graph.edges.map(edge => {
        const source = nodes.get(edge.source); const target = nodes.get(edge.target);
        if (!source || !target) return null;
        const x1 = source.x + WIDTH / 2; const x2 = target.x - WIDTH / 2;
        const y1 = source.y + HEIGHT / 2; const y2 = target.y + HEIGHT / 2;
        const bend = Math.max(45, Math.abs(x2 - x1) / 2);
        return <path key={edge.id} d={`M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`} className="edge-path" data-source={edge.source} data-target={edge.target} markerEnd={`url(#${markerId})`} />;
      })}
      {graph.nodes.map(node => <g key={node.id} className="graph-node" transform={`translate(${node.x - WIDTH / 2},${node.y})`}
        role="button" tabIndex={0} aria-label={`Inspect ${node.id}`} aria-pressed={node.id === selectedNodeId}
        onClick={() => onSelectNode(node.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectNode(node.id); } }}>
        <title>{node.id}</title>
        <rect width={WIDTH} height={HEIGHT} className={`node-rect ${node.isTarget ? 'target' : node.isEndpoint ? 'endpoint' : 'caller'} ${node.id === selectedNodeId ? 'selected' : ''}`} />
        <foreignObject x={16} y={12} width={WIDTH - 32} height={HEIGHT - 20} pointerEvents="none">
          <div className="node-label">{node.label}</div><div className="node-qualified">{node.id}</div>
        </foreignObject>
      </g>)}
    </svg>
  </div>;
}
