import { workspaceSnapshots } from '../utils/workspaceReport';
type Data = Record<string, unknown>;
const records = (value: unknown): Data[] => Array.isArray(value) ? value : [];
export default function WorkspaceOverview({ result, service, onService }: { result: Data; service: string; onService: (id: string) => void }) {
  const snapshots = workspaceSnapshots(result);
  const links = records(result.service_links);
  const names = new Map(snapshots.flatMap(([id, snapshot]) => records(snapshot.functions).map(fn => [String(fn.id), `${id}::${fn.qualified_name}`] as const)));
  return <section className="workspace-overview" aria-label="Workspace overview">
    <h3>Service workspace</h3><p>{snapshots.length} services · {links.length} inferred service contracts</p>
    <div className="workspace-service-grid">{snapshots.map(([id, snapshot]) => <button className="apple-btn btn-secondary service-card" key={id} aria-pressed={service === id} onClick={() => onService(service === id ? '' : id)}><strong>{id}</strong><span>{records(snapshot.functions).length} functions · {records(snapshot.endpoints).length} endpoints</span></button>)}</div>
    <label>Service view<select value={service} onChange={event => onService(event.target.value)}><option value="">All services</option>{snapshots.map(([id]) => <option key={id} value={id}>{id}</option>)}</select></label>
    <details><summary>Inferred service contracts ({links.length})</summary><p>Arrows follow dependency direction: the source depends on the target. Message contracts connect the consumer to the producer.</p>
      {links.length ? <ul>{links.map((link, index) => {
        const request = (link.request_evidence ?? {}) as Data;
        const destination = (link.endpoint_evidence ?? {}) as Data;
        return <li key={index}><strong>{String(link.source_service)} → {String(link.target_service)}</strong> · {String(link.kind)} · {String(link.confidence)}<p>{names.get(String(link.caller_id))} → {names.get(String(link.callee_id))}</p><p>{String(request.file_path)}:{String(request.line)} → {String(destination.file_path)}:{String(destination.line)} · {String(link.rule)}</p></li>;
      })}</ul> : <p>No matching service contracts found. Review service gaps; this does not establish that services are independent.</p>}
    </details>
  </section>;
}
