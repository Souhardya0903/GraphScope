type Data = Record<string, unknown>;
const records = (value: unknown): Data[] => Array.isArray(value) ? value.filter(v => v && typeof v === 'object') : [];
export function workspaceSnapshots(result: Data): Array<[string, Data]> {
  return Object.entries((result.snapshots ?? {}) as Record<string, Data>);
}
export function workspaceReport(result: Data, service = ''): Data {
  const snapshots = workspaceSnapshots(result).filter(([id]) => !service || id === service);
  const merge = (key: string) => snapshots.flatMap(([id, snapshot]) => records(snapshot[key]).map(record => ({ ...record, service: id })));
  const functions: Data[] = snapshots.flatMap(([id, snapshot]) => records(snapshot.functions).map(fn => ({ ...fn, qualified_name: `${id}::${fn.qualified_name}`, service: id })));
  const ids = new Set(functions.map(fn => fn.id));
  const links = records(result.service_links).filter(link => ids.has(link.caller_id) && ids.has(link.callee_id)).map(link => ({ ...link, file_path: (link.request_evidence as Data)?.file_path, line: (link.request_evidence as Data)?.line }));
  return { functions, endpoints: merge('endpoints'), calls: [...merge('calls'), ...links], callsites: merge('callsites'), resources: merge('resources'), gaps: merge('gaps'), caveat: 'Workspace source map. Function names are prefixed with service IDs. Cross-service edges are inferred from declared HTTP or message contracts; runtime traffic is not observed.' };
}
