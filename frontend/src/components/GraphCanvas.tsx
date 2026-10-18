import React, { useState, useMemo } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Crosshair } from 'lucide-react';
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

export default function GraphCanvas({
  evidence,
  targetSymbol,
  selectedNodeId,
  onSelectNode,
}: GraphCanvasProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 50, y: 50 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });

  const graphData = useMemo(
    () => buildGraphData(evidence, targetSymbol),
    [evidence, targetSymbol]
  );

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    // Only pan if clicking canvas background
    if ((e.target as HTMLElement).tagName === 'svg') {
      setIsPanning(true);
      setStartPos({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (isPanning) {
      setPan({ x: e.clientX - startPos.x, y: e.clientY - startPos.y });
    }
  };

  const handlePointerUp = () => setIsPanning(false);

  const handleReset = () => {
    setZoom(1);
    setPan({ x: 50, y: 50 });
  };

  return (
    <div className="graph-canvas-container">
      <div className="canvas-toolbar">
        <button
          className="apple-btn"
          style={{ padding: 4 }}
          onClick={() => setZoom((z) => Math.min(z + 0.15, 2.5))}
          title="Zoom In"
        >
          <ZoomIn size={14} color="var(--text-secondary)" />
        </button>
        <button
          className="apple-btn"
          style={{ padding: 4 }}
          onClick={() => setZoom((z) => Math.max(z - 0.15, 0.4))}
          title="Zoom Out"
        >
          <ZoomOut size={14} color="var(--text-secondary)" />
        </button>
        <button
          className="apple-btn"
          style={{ padding: 4 }}
          onClick={handleReset}
          title="Reset View"
        >
          <RotateCcw size={14} color="var(--text-secondary)" />
        </button>
      </div>

      <div className="canvas-legend">
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--accent-purple)' }} />
          <span>HTTP Endpoint</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--accent-blue)' }} />
          <span>Caller Function</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--accent-rose)' }} />
          <span>Target Symbol</span>
        </div>
      </div>

      <svg
        className="graph-svg"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <defs>
          <marker
            id="arrowhead"
            markerWidth="8"
            markerHeight="6"
            refX="7"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 8 3, 0 6" fill="rgba(255, 255, 255, 0.4)" />
          </marker>
        </defs>

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {graphData.edges.map((edge) => {
            const srcNode = graphData.nodes.find((n) => n.id === edge.source);
            const tgtNode = graphData.nodes.find((n) => n.id === edge.target);
            if (!srcNode || !tgtNode) return null;

            const x1 = srcNode.x + 90;
            const y1 = srcNode.y + 20;
            const x2 = tgtNode.x - 90;
            const y2 = tgtNode.y + 20;
            const dx = Math.abs(x2 - x1) * 0.5;

            const pathData = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

            return (
              <path
                key={edge.id}
                d={pathData}
                className="edge-path"
                markerEnd="url(#arrowhead)"
              />
            );
          })}

          {/* Nodes */}
          {graphData.nodes.map((node) => {
            const isSelected = node.id === selectedNodeId;
            let nodeClass = 'caller';
            if (node.isTarget) nodeClass = 'target';
            else if (node.isEndpoint) nodeClass = 'endpoint';

            const width = 180;
            const height = 44;

            return (
              <g
                key={node.id}
                className="graph-node"
                transform={`translate(${node.x - width / 2}, ${node.y})`}
                onClick={() => onSelectNode(node.id)}
              >
                <rect
                  width={width}
                  height={height}
                  className={`node-rect ${nodeClass} ${isSelected ? 'selected' : ''}`}
                />
                <text
                  x={14}
                  y={22}
                  fill="var(--text-primary)"
                  fontSize="12"
                  fontWeight="600"
                  fontFamily="var(--font-sans)"
                >
                  {node.label}
                </text>
                <text
                  x={14}
                  y={35}
                  fill="var(--text-muted)"
                  fontSize="9.5"
                  fontFamily="var(--font-mono)"
                >
                  {node.id.length > 24 ? node.id.slice(0, 24) + '...' : node.id}
                </text>
                {node.isTarget && (
                  <Crosshair
                    x={width - 24}
                    y={12}
                    size={16}
                    color="var(--accent-rose)"
                  />
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
