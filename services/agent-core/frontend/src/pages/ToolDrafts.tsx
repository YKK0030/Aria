import { useCallback, useEffect, useState, type FormEvent } from 'react';
import './Dashboard.css';
import './ToolDrafts.css';

type TestResult = { case: number; passed: boolean; actual?: string; error?: string };
type Proposal = {
  id: string; name: string; description: string; source: string; tests: Array<{ args: Record<string, unknown>; expected: unknown }>;
  status: string; sha256: string; created_at: string; test_count?: number; case_count: number;
  test_run?: { passed: boolean; tests: number; results: TestResult[]; error: string; finished_at: string };
  review?: { approved: boolean; summary: string; findings: string[] };
};

const NAV = [
  ['01', 'Overview', '/dashboard'], ['02', 'Chat', '/'], ['03', 'Trace', '/aria-trace'],
  ['04', 'Memory', '/memory'], ['05', 'Metrics', '/metrics'], ['06', 'Tool drafts', '/tool-drafts'],
];

async function request<T>(path: string, key: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'x-admin-api-key': key, ...(init.body ? { 'content-type': 'application/json' } : {}), ...init.headers },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try { detail = (await response.json()).detail || detail; } catch { /* keep status message */ }
    const error = new Error(detail);
    Object.assign(error, { status: response.status });
    throw error;
  }
  return response.json() as Promise<T>;
}

export default function ToolDrafts() {
  const [key, setKey] = useState(() => sessionStorage.getItem('aria-admin-key') || '');
  const [keyInput, setKeyInput] = useState('');
  const [drafts, setDrafts] = useState<Array<Omit<Proposal, 'source' | 'tests'>>>([]);
  const [selected, setSelected] = useState<Proposal | null>(null);
  const [testText, setTestText] = useState('');
  const [confirmName, setConfirmName] = useState('');
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async (adminKey: string, selectedId?: string) => {
    setLoading(true);
    setError('');
    try {
      const list = await request<{ proposals: Array<Omit<Proposal, 'source' | 'tests'>> }>('/admin/tool-proposals', adminKey);
      setDrafts(list.proposals);
      sessionStorage.setItem('aria-admin-key', adminKey);
      setKey(adminKey);
      const id = selectedId || selected?.id || list.proposals[0]?.id;
      if (id && list.proposals.some((item) => item.id === id)) {
        const detail = await request<{ proposal: Proposal }>(`/admin/tool-proposals/${id}`, adminKey);
        setSelected(detail.proposal);
        setTestText(JSON.stringify(detail.proposal.tests, null, 2));
      } else {
        setSelected(null);
        setTestText('');
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load tool drafts.');
      if ((cause as Error & { status?: number }).status === 401) {
        sessionStorage.removeItem('aria-admin-key'); setKey(''); setSelected(null);
      }
    } finally {
      setLoading(false);
    }
  }, [selected?.id]);

  useEffect(() => { if (key) void load(key); }, []); // load once from the existing dashboard session

  const action = async (label: string, run: () => Promise<void>) => {
    setBusy(label); setError(''); setNotice('');
    try { await run(); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Action failed.'); }
    finally { setBusy(''); }
  };

  const openDraft = (id: string) => { if (key) void load(key, id); };

  const saveTests = () => action('save', async () => {
    if (!selected) return;
    let tests: Proposal['tests'];
    try { tests = JSON.parse(testText); } catch { throw new Error('Tests must be valid JSON.'); }
    const result = await request<{ proposal: Proposal }>(`/admin/tool-proposals/${selected.id}/tests`, key, {
      method: 'PUT', body: JSON.stringify({ sha256: selected.sha256, tests }),
    });
    setNotice('Test suite saved. This revision must pass again before review.');
    await load(key, result.proposal.id);
  });

  const addTestCase = () => {
    try {
      const tests = JSON.parse(testText);
      if (!Array.isArray(tests) || tests.length >= 10) throw new Error('Test suite can contain at most 10 cases.');
      setTestText(JSON.stringify([...tests, { args: {}, expected: null }], null, 2));
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Fix test JSON before adding a case.');
    }
  };

  const runTests = () => action('test', async () => {
    if (!selected) return;
    const result = await request<{ proposal: Proposal }>(`/admin/tool-proposals/${selected.id}/tested`, key, {
      method: 'POST', body: JSON.stringify({ sha256: selected.sha256, test_count: selected.tests.length }),
    });
    setNotice(result.proposal.test_run?.passed ? 'All isolated tests passed.' : 'Test suite ran. Review the failed cases below.');
    await load(key, selected.id);
  });

  const review = () => action('review', async () => {
    if (!selected) return;
    await request(`/admin/tool-proposals/${selected.id}/review`, key, {
      method: 'POST', body: JSON.stringify({ sha256: selected.sha256, test_count: selected.tests.length }),
    });
    setNotice('Independent review finished.'); await load(key, selected.id);
  });

  const revise = () => action('revise', async () => {
    if (!selected) return;
    const result = await request<{ proposal: Proposal }>(`/admin/tool-proposals/${selected.id}/revise`, key, {
      method: 'POST', body: JSON.stringify({ sha256: selected.sha256 }),
    });
    setNotice('Aria created a revised draft. Run its tests before requesting review.'); await load(key, result.proposal.id);
  });

  const approve = () => action('approve', async () => {
    if (!selected || confirmName !== selected.name) throw new Error(`Type ${selected?.name} exactly to install this tool.`);
    await request(`/admin/tool-proposals/${selected.id}/approve`, key, { method: 'POST' });
    setNotice(`${selected.name} installed and attached to Aria.`); setConfirmName(''); await load(key, selected.id);
  });

  const connect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const value = keyInput.trim(); if (value) void load(value);
  };

  return <div className="mission-shell">
    <aside className="mission-rail">
      <a className="mission-brand" href="/dashboard" aria-label="Aria mission control home"><span className="brand-glyph">A<span>.</span></span><span><strong>ARIA</strong><small>MISSION CONTROL</small></span></a>
      <div className="rail-label">WORKSPACE</div>
      <nav className="mission-nav" aria-label="Main navigation">{NAV.map(([mark, label, href]) => <a key={href} className={`nav-item ${href === '/tool-drafts' ? 'is-current' : ''}`} href={href} aria-current={href === '/tool-drafts' ? 'page' : undefined}><span className="nav-mark">{mark}</span><span>{label}</span></a>)}</nav>
      <div className="rail-bottom"><span className="status-light is-online"/><span>Local runtime</span><small>TOOL REVIEW</small></div>
    </aside>
    <main className="mission-main">
      <header className="mission-topbar"><div><span className="crumb-muted">Workspace</span><span className="crumb-divider">/</span><span>Tool drafts</span></div><div className="topbar-actions"><span className="refresh-note">Human approval required</span>{key && <button className="quiet-button" onClick={() => void load(key)} disabled={!!busy}>Refresh</button>}</div></header>
      <div className="mission-content">
        {!key ? <section className="connect-panel"><div className="connect-intro"><span className="section-index">01 / ACCESS</span><h2>Connect to your workspace</h2><p>Use the same local admin key as Mission Control. It stays in this browser session.</p></div><form className="connect-form" onSubmit={connect}><label htmlFor="draft-admin-key">Admin key</label><div className="key-row"><input id="draft-admin-key" type="password" value={keyInput} onChange={(event) => setKeyInput(event.target.value)} autoComplete="current-password" required/><button type="submit" disabled={!!busy}>Connect</button></div></form></section> : <>
          <section className="drafts-hero"><div><p className="overline">ARIA · EXTENSION WORKFLOW</p><h1>Review before<br/><em>Aria learns.</em></h1><p>Inspect proposed tools, strengthen their test cases, run them in isolation, then review and approve the exact tested revision.</p></div><div className="drafts-count"><strong>{drafts.filter((draft) => draft.status !== 'approved').length.toString().padStart(2, '0')}</strong><span>OPEN DRAFTS</span></div></section>
          {error && <div className="inline-error draft-alert" role="alert">{error}</div>}{notice && <div className="draft-notice" role="status">{notice}</div>}
          {loading && drafts.length === 0 ? <section className="surface-panel draft-empty" role="status">Loading tool drafts…</section> : drafts.length === 0 ? <section className="surface-panel draft-empty"><span className="section-index">NO PROPOSALS</span><h2>Nothing waiting for review</h2><p>When Aria proposes a tool, it will appear here with its source and test suite.</p><a href="/">Return to chat ↗</a></section> : <div className="draft-layout">
            <section className="surface-panel draft-list" aria-label="Tool draft list"><div className="panel-heading"><div><span className="section-index">01 / QUEUE</span><h2>Tool proposals</h2></div><span className="queue-total">{drafts.length}</span></div>{drafts.map((draft) => <button key={draft.id} type="button" onClick={() => openDraft(draft.id)} className={`draft-row ${selected?.id === draft.id ? 'is-selected' : ''}`}><span className="draft-row-top"><strong>{draft.name}</strong><span className={`draft-status status-${draft.status}`}>{draft.status.split('_').join(' ')}</span></span><span className="draft-description">{draft.description}</span><span className="draft-meta">{draft.case_count} cases · {draft.test_count ?? 0} passed · {new Date(draft.created_at).toLocaleDateString()}</span></button>)}</section>
            {selected && <section className="surface-panel draft-detail" aria-labelledby="draft-title"><div className="panel-heading"><div><span className="section-index">02 / INSPECT</span><h2 id="draft-title">{selected.name}</h2></div><span className={`draft-status status-${selected.status}`}>{selected.status.split('_').join(' ')}</span></div><p className="draft-detail-description">{selected.description}</p>
              <details className="source-panel"><summary>Proposed source <span>{selected.source.split('\n').length} lines</span></summary><pre><code>{selected.source}</code></pre></details>
              <div className="draft-section-title"><div><span className="section-index">03 / TEST</span><h3>Test cases</h3></div><div className="case-count"><span>{selected.tests.length} / 10</span><button type="button" className="add-case" onClick={addTestCase} disabled={!!busy || !['pending', 'tested'].includes(selected.status)}>+ Add case</button></div></div>
              <p className="draft-help">Edit the JSON suite. Each case needs <code>args</code> and <code>expected</code>. Saving invalidates prior test and review results.</p>
              <label className="sr-only" htmlFor="draft-test-cases">Test cases JSON</label><textarea id="draft-test-cases" className="test-editor" value={testText} onChange={(event) => setTestText(event.target.value)} spellCheck={false} aria-describedby="draft-test-format"/><div id="draft-test-format" className="editor-hint">Example: [{'{'} "args": {'{'} "value": 2 {'}'}, "expected": 4 {'}'}]</div>
              <div className="draft-actions"><button type="button" className="draft-button draft-secondary" onClick={() => void saveTests()} disabled={!!busy || !['pending', 'tested'].includes(selected.status)}>{busy === 'save' ? 'Saving…' : 'Save test suite'}</button><button type="button" className="draft-button draft-primary" onClick={() => void runTests()} disabled={!!busy || selected.status !== 'pending'}>{busy === 'test' ? 'Running isolated suite…' : 'Run isolated tests'}</button></div>
              {selected.test_run && <div className={`test-results ${selected.test_run.passed ? 'results-pass' : 'results-fail'}`}><div className="result-heading"><strong>{selected.test_run.passed ? 'All cases passed' : 'Tests need attention'}</strong><time>{new Date(selected.test_run.finished_at).toLocaleString()}</time></div>{selected.test_run.error && <p className="result-error">{selected.test_run.error}</p>}{selected.test_run.results.map((result) => <div className="case-result" key={result.case}><span className={result.passed ? 'case-icon is-pass' : 'case-icon'}>{result.passed ? '✓' : '×'}</span><span>Case {result.case}</span><code>{result.error || result.actual || 'No returned value'}</code></div>)}</div>}
              {selected.review && <div className={`review-result ${selected.review.approved && !selected.review.findings.length ? 'results-pass' : 'results-fail'}`}><span className="section-index">INDEPENDENT REVIEW</span><p>{selected.review.summary}</p>{selected.review.findings.map((finding, index) => <div key={index}>• {finding}</div>)}</div>}
              {selected.status === 'needs_changes' && <div className="review-action"><p>Reviewer requested changes. Ask Aria to create a new draft revision, then test it again.</p><button className="draft-button draft-secondary" onClick={() => void revise()} disabled={!!busy}>{busy === 'revise' ? 'Revising…' : 'Ask Aria to revise'}</button></div>}
              {selected.status === 'tested' && <div className="review-action"><p>Current revision passed all isolated tests. Request an independent review before owner approval.</p><button className="draft-button draft-secondary" onClick={() => void review()} disabled={!!busy}>{busy === 'review' ? 'Reviewing…' : 'Run independent review'}</button></div>}
              {selected.status === 'reviewed' && <div className="approve-panel"><div><span className="section-index">OWNER APPROVAL</span><p>Review passed. Confirm the exact tool name to install it into Aria’s tool registry.</p></div><label htmlFor="approve-tool-name">Type <strong>{selected.name}</strong> to confirm</label><div className="approve-row"><input id="approve-tool-name" value={confirmName} onChange={(event) => setConfirmName(event.target.value)} autoComplete="off"/><button className="draft-button draft-primary" onClick={() => void approve()} disabled={!!busy || confirmName !== selected.name}>{busy === 'approve' ? 'Installing…' : 'Approve & install'}</button></div></div>}
            </section>}
          </div>}
        </>}
      </div>
    </main>
  </div>;
}
