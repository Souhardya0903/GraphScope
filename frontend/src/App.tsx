import React from 'react';

export default function App() {
  return (
    <div className="app-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header className="glass-toolbar" style={{ padding: '0.75rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--accent-blue)', boxShadow: '0 0 10px var(--accent-blue)' }} />
          <h1 style={{ fontSize: '1.05rem', fontWeight: 600, letterSpacing: '-0.02em' }}>GraphScope</h1>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '0.25rem' }}>Impact Intelligence</span>
        </div>
      </header>
      <main style={{ flex: 1, padding: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-secondary)' }}>Split Command Center initialized.</p>
      </main>
    </div>
  );
}
