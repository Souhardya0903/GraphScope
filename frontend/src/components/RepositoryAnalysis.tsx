import { FormEvent, useEffect, useRef, useState } from 'react';
import AnalysisResults from './AnalysisResults';
import { downloadFile } from '../utils/reportExport';
import './RepositoryAnalysis.css';

type Mode = 'map' | 'changes' | 'impact' | 'propose' | 'workspace';
export type AnalysisResult = Record<string, unknown>;

export default function RepositoryAnalysis() {
  const [mode, setMode] = useState<Mode>('changes');
  const [root, setRoot] = useState('');
  const [targets, setTargets] = useState('');
  const [description, setDescription] = useState('');
  const [base, setBase] = useState('HEAD');
  const [head, setHead] = useState('worktree');
  const [service, setService] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [resource, setResource] = useState('');
  const [changedService, setChangedService] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);

  function cancel() { active.current?.abort(); active.current = null; setBusy(false); setError('Request cancelled. Server work already running may finish; its result will not be shown.'); }

  async function submit(event: FormEvent) {
    event.preventDefault(); active.current?.abort(); const controller = new AbortController(); active.current = controller; setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`/api/analysis/${mode}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ root, targets: ['impact', 'propose', 'workspace'].includes(mode) ? targets.split(',').map(t => t.trim()).filter(Boolean) : [], description: mode === 'propose' ? description : '', base, head, service: mode === 'workspace' ? service || null : null, changed_service: mode === 'workspace' ? changedService || null : null, resource: mode === 'impact' ? resource || null : null, confirm: mode === 'propose' && confirm }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check analysis inputs');
      if (active.current === controller) setResult(data);
    } catch (e) { if (active.current === controller && !controller.signal.aborted) setError(e instanceof TypeError ? 'Cannot reach the GraphScope API. Check that the local server is running and reopen its URL (normally http://127.0.0.1:8080).' : e instanceof Error ? e.message : 'Analysis failed'); }
    finally { if (active.current === controller) { active.current = null; setBusy(false); } }
  }

  return <section className="repository-analysis" aria-label="Repository change analysis">
    <header className="analysis-heading"><div><span className="eyebrow">REPOSITORY INTELLIGENCE</span><h2>Understand the impact.<br /><span>Before you change the code.</span></h2><p>Explore dependencies and trace potential changes through your codebase.</p></div><span className="local-badge">● Local source analysis</span></header>
    <div className="analysis-workspace"><aside className="setup-panel"><div className="panel-heading"><span className="step-number">01</span><div><h3>Configure analysis</h3><p>Choose a repository and scope.</p></div></div>
    <form onSubmit={submit} onChange={() => setResult(null)}><fieldset disabled={busy}>
      <label>Analysis mode<select value={mode} onChange={e => { setMode(e.target.value as Mode); setResult(null); setConfirm(false); }}>
        <option value="changes">Git changes</option><option value="map">Repository mapping</option>
        <option value="impact">Selected targets</option><option value="propose">Proposed change</option><option value="workspace">Service workspace</option>
      </select></label>
      <label>{mode === 'workspace' ? 'Workspace manifest path' : 'Repository path'}<input required placeholder="Absolute path to your repository" value={root} onChange={e => { setRoot(e.target.value); setConfirm(false); setResult(null); }} /></label>
      {(mode === 'changes' || mode === 'workspace') && <><label>Base revision<input value={base} onChange={e => setBase(e.target.value)} /></label><label>Compare with<input value={head} onChange={e => setHead(e.target.value)} placeholder="worktree, index, or commit" /></label></>}
      {['impact', 'propose', 'workspace'].includes(mode) && <label>Qualified targets (comma separated)<input value={targets} onChange={e => { setTargets(e.target.value); setConfirm(false); }} placeholder="package.module.function" /></label>}
      {mode === 'workspace' && <label>Service ID (for target impact)<input value={service} onChange={e => setService(e.target.value)} /></label>}
      {mode === 'workspace' && <label>Changed service ID (for Git impact)<input value={changedService} onChange={e => setChangedService(e.target.value)} /></label>}
      {mode === 'impact' && <label>Or resource identity<input value={resource} onChange={e => setResource(e.target.value)} placeholder="redis:inventory" /></label>}
      {mode === 'propose' && <><label>Describe the proposed change<textarea required value={description} onChange={e => { setDescription(e.target.value); setConfirm(false); }} /></label>
        <label><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />I confirm the explicit targets above</label></>}
      <button className="apple-btn btn-primary" disabled={busy || (mode === 'propose' && confirm && !targets.trim())} type="submit">{busy ? 'Analyzing…' : 'Analyze repository'}</button>
    </fieldset></form><p className="setup-note">Source is analyzed locally without executing it. No model or stored snapshot required.</p></aside>
    <main className="results-panel" aria-label="Analysis workspace">
    {busy && <div role="status">Analyzing repository… <button className="apple-btn btn-secondary" onClick={cancel}>Cancel request</button></div>}
    {error && <p role="alert">{error}</p>}
    {result && <div><div className="results-heading"><div><span className="eyebrow">ANALYSIS RESULTS</span><h3>Dependency & impact report</h3><p className="result-path">Results for {root}</p></div><button className="apple-btn btn-secondary" onClick={() => downloadFile(JSON.stringify(result, null, 2), 'repository-analysis.json', 'application/json')}>Export analysis JSON</button></div>
      <AnalysisResults key={`${mode}-${root}`} result={result} onCandidate={name => { setTargets(name); setConfirm(false); }} />
      <details><summary>Full analysis JSON</summary><pre>{JSON.stringify(result, null, 2)}</pre></details></div>}
    {!result && !busy && !error && <div className="analysis-empty"><div className="empty-orbit">⌘</div><span className="eyebrow">YOUR CODEBASE, CONNECTED</span><h3>See what a change touches.</h3><p>Configure your analysis on the left to explore function dependencies, affected endpoints, and linked tests.</p><div className="empty-steps"><span>01 Select repository</span><span>02 Define scope</span><span>03 Explore impact</span></div></div>}
    </main></div>
  </section>;
}
