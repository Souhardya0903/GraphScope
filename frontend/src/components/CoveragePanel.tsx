import { useState } from 'react';

type RecordData = Record<string, unknown>;
const records = (value: unknown): RecordData[] => Array.isArray(value) ? value.filter(v => v && typeof v === 'object') : [];

function ReasonGroups({ items }: { items: RecordData[] }) {
  const groups = new Map<string, RecordData[]>();
  for (const item of items) {
    const reason = String(item.reason || 'Unclassified limitation');
    groups.set(reason, [...(groups.get(reason) ?? []), item]);
  }
  return <div>{[...groups].sort((a, b) => b[1].length - a[1].length).map(([reason, entries]) => <details key={reason}>
    <summary>{reason} <span className="coverage-count">{entries.length}</span></summary>
    <ul>{entries.slice(0, 8).map((entry, index) => <li key={index}><code>{String(entry.path ?? entry.file_path ?? entry.service ?? '')}{entry.line ? `:${entry.line}` : ''}</code>{entry.target_text ? ` — ${entry.target_text}` : ''}</li>)}</ul>
    {entries.length > 8 && <p>Showing 8 of {entries.length} records. Export JSON for the full list.</p>}
  </details>)}</div>;
}

export default function CoveragePanel({ report, extraGaps = [] }: { report: RecordData; extraGaps?: RecordData[] }) {
  const [scope, setScope] = useState('affected');
  const impact = Array.isArray(report.affected_functions);
  const functions = records(report.affected_functions);
  const affectedIds = new Set(functions.map(f => f.id));
  const affectedFiles = new Set(functions.map(f => f.file_path));
  const limitations = [...records(report.analysis_gaps ?? report.gaps), ...extraGaps];
  const unresolved = Array.isArray(report.unresolved_calls) ? records(report.unresolved_calls) : records(report.callsites).filter(c => !c.target_id);
  const builtin = (item: RecordData) => String(item.reason).startsWith('Python builtin call;');
  const local = impact && scope === 'affected';
  const calls = local ? unresolved.filter(c => affectedIds.has(c.owner_id)) : unresolved;
  const gaps = local ? limitations.filter(g => affectedFiles.has(g.path ?? g.file_path)) : limitations;
  const builtins = calls.filter(builtin);
  const unknown = calls.filter(c => !builtin(c));
  return <details className="coverage-panel"><summary>Analysis coverage & limitations</summary>
    <p>Repository-wide: {limitations.length} limitation records · {unresolved.length} calls without repository targets. These are separate categories, may overlap, and are not a count of defects or affected functions.</p>
    {impact && <label>Coverage scope<select value={scope} onChange={event => setScope(event.target.value)}><option value="affected">Found affected functions / files</option><option value="repository">Whole repository</option></select></label>}
    <div className="coverage-totals"><span><strong>{unknown.length}</strong> unresolved calls {local ? 'inside found affected functions' : 'across repository'}</span><span><strong>{builtins.length}</strong> builtin calls without repository targets</span><span><strong>{gaps.length}</strong> limitation records {local ? 'in affected files' : 'across repository'}</span></div>
    <p>Unknown and external calls remain unresolved; builtin calls are identified separately without inventing dependencies. Calls outside the found affected set may still hide additional incoming dependencies. This view does not establish complete coverage.</p>
    <h4>Unresolved call reasons</h4>{unknown.length ? <ReasonGroups items={unknown} /> : <p>No unresolved calls recorded in this scope.</p>}
    {builtins.length > 0 && <details><summary>Python builtin calls ({builtins.length})</summary><ReasonGroups items={builtins} /></details>}
    <h4>Extraction and change limitations</h4>{gaps.length ? <ReasonGroups items={gaps} /> : <p>No limitation records in this scope.</p>}
  </details>;
}
