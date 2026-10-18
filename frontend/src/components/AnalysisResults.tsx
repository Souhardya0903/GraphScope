import { useState } from 'react';
import GraphCanvas from './GraphCanvas';
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
  const evidence = paths.flatMap(p => records(p.evidence)).filter(e => !selected || e.caller_id === selected || e.callee_id === selected);
  const gaps = [...records(report.analysis_gaps ?? report.gaps), ...records(result.change_gaps), ...records(wrapper.service_gaps), ...records(report.unresolved_calls)];
  const limits = object(report.limits);
  const idToName = new Map(functions.map(f => [String(f.id), String(f.qualified_name)]));
  const graph: GraphEvidencePayload = { paths: paths.map(p => Array.isArray(p.function_ids) ? p.function_ids.map(id => idToName.get(String(id)) ?? String(id)) : []), potentially_affected_endpoints: endpoints.map(e => `${e.method} ${e.path}`) };

  return <div aria-label="Analysis findings">
    {comparison && <label>Snapshot side<select aria-label="Snapshot side" value={side} onChange={e => { setSide(e.target.value as 'before' | 'after'); setSelected(null); }}><option value="before">Before changes</option><option value="after">After changes</option></select></label>}
    {result.status === 'confirmation_required' && <div role="status"><p>Review and select a target, then confirm it before calculating impact.</p>{records(result.candidates).map(f => <button key={String(f.id)} className="apple-btn" onClick={() => onCandidate(String(f.qualified_name))}>Use {String(f.qualified_name)}</button>)}</div>}
    <p>{functions.length} mapped/affected functions · {endpoints.length} affected endpoints · {records(report.related_tests).length} static test links · {records(report.resource_accesses ?? report.resources).length} resource accesses</p>
    {Array.isArray(result.changes) && result.changes.length === 0 && <p>No eligible changes found between these versions.</p>}
    <p>{String(report.caveat ?? 'Static analysis is partial. An empty path does not establish safety.')}</p>
    {(limits.truncated || limits.depth_limited) ? <p role="alert">Traversal reached a limit; additional affected code may be missing.</p> : null}
    <div className="analysis-graph"><GraphCanvas evidence={graph} targetSymbol={targets.length ? String(targets[0].qualified_name) : null} selectedNodeId={selected ? idToName.get(selected) ?? selected : null} onSelectNode={name => setSelected(String(functions.find(f => f.qualified_name === name)?.id ?? name))} /></div>
    <details><summary>Affected functions and endpoints</summary><ul>{functions.map(f => <li key={String(f.id)}><button className="apple-btn" onClick={() => setSelected(String(f.id))}>{String(f.qualified_name)}</button> — {String(f.file_path)}:{String(f.start_line)}</li>)}</ul><ul>{endpoints.map(e => <li key={String(e.id)}>{String(e.method)} {String(e.path)}</li>)}</ul></details>
    <details open={selected !== null}><summary>Dependency evidence {selected ? `for ${idToName.get(selected) ?? selected}` : ''}</summary>{evidence.length ? evidence.map((e, i) => <p key={i}>{String(e.file_path)}:{String(e.line)} — {String(e.rule)} ({String(e.confidence ?? 'explicit')})</p>) : <p>Select a linked function to see path evidence. Source hashes are included in the exported report.</p>}</details>
    <details><summary>Coverage gaps ({gaps.length})</summary><ul>{gaps.map((g, i) => <li key={i}>{String(g.path ?? g.file_path ?? g.service ?? '')} {String(g.reason ?? '')}</li>)}</ul></details>
  </div>;
}
