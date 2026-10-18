import { useState } from 'react';
import GraphCanvas from './GraphCanvas';
import CoveragePanel from './CoveragePanel';
import { GraphEvidencePayload } from '../types/api';

type Data = Record<string, unknown>;
const object = (value: unknown): Data => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Data : {};
const records = (value: unknown): Data[] => Array.isArray(value) ? value.map(object) : [];

export default function AnalysisResults({ result, onCandidate }: { result: Data; onCandidate: (name: string) => void }) {
  const [side, setSide] = useState<'before' | 'after'>('after');
  const [selected, setSelected] = useState<string | null>(null);
  const comparison = result.before !== undefined && result.after !== undefined;
  const wrapper = comparison ? object(result[side]) : result;
  const report = Object.keys(object(wrapper.report)).length ? object(wrapper.report) : wrapper;
  const targets = records(report.targets);
  const paths = records(report.paths);
  const functions = records(report.affected_functions ?? report.functions);
  const endpoints = records(report.potentially_affected_endpoints ?? report.endpoints);
  const calls = records(report.calls);
  const evidence = [...paths.flatMap(p => records(p.evidence)), ...calls].filter(e => !selected || e.caller_id === selected || e.callee_id === selected);
  const extraGaps = [...records(result.change_gaps), ...records(wrapper.service_gaps)];
  const limits = object(report.limits);
  const idToName = new Map(functions.map(f => [String(f.id), String(f.qualified_name)]));
  const allGraphPaths = paths.length
    ? paths.map(p => Array.isArray(p.function_ids) ? p.function_ids.map(id => idToName.get(String(id)) ?? String(id)) : [])
    : calls.map(c => [idToName.get(String(c.caller_id)) ?? String(c.caller_id), idToName.get(String(c.callee_id)) ?? String(c.callee_id)]);
  const graph: GraphEvidencePayload = { paths: allGraphPaths.slice(0, 200), potentially_affected_endpoints: endpoints.map(e => `${e.method} ${e.path}`) };

  if (result.status === 'confirmation_required' || result.status === 'clarification_required') return <div className="proposal-review" aria-label="Proposal review">
    <span className="eyebrow">{result.provider ? `${String(result.provider).toUpperCase()} SUGGESTION` : 'TARGET REVIEW'}</span>
    <h3>{result.status === 'clarification_required' ? 'More detail needed' : 'Review the suggested targets'}</h3>
    <p>{result.status === 'clarification_required' ? String(result.message) : 'Select a candidate, review the target field, then confirm it before calculating impact. Suggestions do not establish complete change coverage.'}</p>
    {records(result.candidates).map(f => <button key={String(f.id)} className="apple-btn btn-secondary candidate-button" onClick={() => onCandidate(String(f.qualified_name))}>Use {String(f.qualified_name)}</button>)}
    {result.status === 'confirmation_required' && !records(result.candidates).length && <p>No lexical matches found. Name a function in the description, enter an exact qualified target, or try a model provider.</p>}
    {Array.isArray(result.suggestions) && result.suggestions.length > 0 && <div><h4>Suggested manual checks</h4>{result.suggestions.map((item, index) => <p key={index}>{String(item)}</p>)}</div>}
    <p>No blast radius has been calculated yet.</p>
  </div>;

  return <div aria-label="Analysis findings">
    {comparison && <label>Snapshot side<select aria-label="Snapshot side" value={side} onChange={e => { setSide(e.target.value as 'before' | 'after'); setSelected(null); }}><option value="before">Before changes</option><option value="after">After changes</option></select></label>}
    <div className="metric-grid" aria-label="Analysis summary">
      <div className="metric-card"><span>Functions</span><strong>{functions.length}</strong><small>Mapped / potentially affected</small></div>
      <div className="metric-card"><span>Endpoints</span><strong>{endpoints.length}</strong><small>Potentially affected routes</small></div>
      <div className="metric-card"><span>Test links</span><strong>{records(report.related_tests).length}</strong><small>Static caller relationships</small></div>
      <div className="metric-card"><span>Resources</span><strong>{records(report.resource_accesses ?? report.resources).length}</strong><small>Detected accesses</small></div>
    </div>
    {Array.isArray(result.changes) && result.changes.length === 0 && <p>No eligible changes found between these versions.</p>}
    <p>{String(report.caveat ?? 'Static analysis is partial. An empty path does not establish safety.')}</p>
    {(limits.truncated || limits.depth_limited) ? <p role="alert">Traversal reached a limit; additional affected code may be missing.</p> : null}
    {allGraphPaths.length > 200 && <p>Graph preview shows the first 200 paths. Export JSON for all relationships.</p>}
    <div className="graph-heading"><h3>Dependency graph</h3><span>Select a node to inspect evidence · Drag to pan</span></div>
    <div className="analysis-graph"><GraphCanvas evidence={graph} targetSymbol={targets.length ? String(targets[0].qualified_name) : null} selectedNodeId={selected ? idToName.get(selected) ?? selected : null} onSelectNode={name => setSelected(String(functions.find(f => f.qualified_name === name)?.id ?? name))} /></div>
    <div className="findings-grid"><details><summary>Affected functions and endpoints</summary><ul>{functions.map(f => <li key={String(f.id)}><button className="apple-btn btn-secondary" onClick={() => setSelected(String(f.id))}>{String(f.qualified_name)}</button> — {String(f.file_path)}:{String(f.start_line)}</li>)}</ul><ul>{endpoints.map(e => <li key={String(e.id)}>{String(e.method)} {String(e.path)}</li>)}</ul></details>
    <details open={selected !== null}><summary>Dependency evidence {selected ? `for ${idToName.get(selected) ?? selected}` : ''}</summary>{evidence.length ? evidence.map((e, i) => <p key={i}>{String(e.file_path)}:{String(e.line)} — {String(e.rule)} ({String(e.confidence ?? 'explicit')})</p>) : <p>Select a linked function to see path evidence. Source hashes are included in the exported report.</p>}</details>
    </div><CoveragePanel key={side} report={report} extraGaps={extraGaps} />
  </div>;
}
