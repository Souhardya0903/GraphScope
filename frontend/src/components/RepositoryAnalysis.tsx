import { FormEvent, useState } from 'react';
import { downloadFile } from '../utils/reportExport';
import './RepositoryAnalysis.css';

type Mode = 'map' | 'changes' | 'impact' | 'propose' | 'workspace';
export type AnalysisResult = Record<string, unknown>;

export default function RepositoryAnalysis() {
  const [mode, setMode] = useState<Mode>('changes');
  const [root, setRoot] = useState('examples/commerce');
  const [targets, setTargets] = useState('');
  const [description, setDescription] = useState('');
  const [base, setBase] = useState('HEAD');
  const [head, setHead] = useState('worktree');
  const [service, setService] = useState('');
  const [confirm, setConfirm] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setResult(null);
    try {
      const response = await fetch(`/api/analysis/${mode}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root, targets: targets.split(',').map(t => t.trim()).filter(Boolean), description, base, head, service: service || null, confirm }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check analysis inputs');
      setResult(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Analysis failed'); }
    finally { setBusy(false); }
  }

  return <section className="repository-analysis" aria-label="Repository change analysis">
    <h2>Repository & change impact</h2>
    <p>Analyze local source without executing it. Results describe potential static impact and coverage gaps.</p>
    <form onSubmit={submit}>
      <label>Analysis mode<select value={mode} onChange={e => { setMode(e.target.value as Mode); setResult(null); setConfirm(false); }}>
        <option value="changes">Git changes</option><option value="map">Repository mapping</option>
        <option value="impact">Selected targets</option><option value="propose">Proposed change</option><option value="workspace">Service workspace</option>
      </select></label>
      <label>{mode === 'workspace' ? 'Workspace manifest path' : 'Repository path'}<input required value={root} onChange={e => setRoot(e.target.value)} /></label>
      {(mode === 'changes') && <><label>Base revision<input value={base} onChange={e => setBase(e.target.value)} /></label><label>Compare with<input value={head} onChange={e => setHead(e.target.value)} placeholder="worktree, index, or commit" /></label></>}
      {['impact', 'propose', 'workspace'].includes(mode) && <label>Qualified targets (comma separated)<input value={targets} onChange={e => { setTargets(e.target.value); setConfirm(false); }} placeholder="inventory.validate_stock" /></label>}
      {mode === 'workspace' && <label>Service ID (for target impact)<input value={service} onChange={e => setService(e.target.value)} /></label>}
      {mode === 'propose' && <><label>Describe the proposed change<textarea required value={description} onChange={e => { setDescription(e.target.value); setConfirm(false); }} /></label>
        <label><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />I confirm the explicit targets above</label></>}
      <button className="apple-btn" disabled={busy} type="submit">{busy ? 'Analyzing…' : 'Analyze repository'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div><button className="apple-btn" onClick={() => downloadFile(JSON.stringify(result, null, 2), 'repository-analysis.json', 'application/json')}>Export analysis JSON</button>
      <details open><summary>Analysis result and evidence</summary><pre>{JSON.stringify(result, null, 2)}</pre></details></div>}
  </section>;
}
