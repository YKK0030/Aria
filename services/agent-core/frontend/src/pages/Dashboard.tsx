import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import './Dashboard.css';

type MetricPoint = { labels: Record<string, string>; value: number };
type RuntimeStatus = {
  agent_name: string;
  enabled_channels: string[];
  model_provider: string;
  redis_enabled: boolean;
  short_term_memory_turns: number;
  long_term_memory_top_k: number;
};
type Skill = { name: string; description: string; category: string; loaded: boolean };
type Tool = { name: string; description: string; enabled: boolean; available: boolean };
type AuditEvent = { ts: string; event_type: string; payload: Record<string, unknown> };
type DashboardData = {
  status: RuntimeStatus;
  metrics: Record<string, MetricPoint[]>;
  skills: Skill[];
  tools: Tool[];
  events: AuditEvent[];
};

const NAV = [
  { label: 'Overview', href: '/dashboard', mark: '01' },
  { label: 'Chat', href: '/', mark: '02' },
  { label: 'Trace', href: '/aria-trace', mark: '03' },
  { label: 'Memory', href: '/memory', mark: '04' },
  { label: 'Metrics', href: '/metrics', mark: '05' },
];

async function getJson<T>(url: string, key?: string): Promise<T> {
  const response = await fetch(url, { headers: key ? { 'x-admin-api-key': key } : undefined });
  if (!response.ok) {
    const error = new Error(response.status === 401 ? 'That admin key was not accepted.' : `Request failed (${response.status}).`);
    Object.assign(error, { status: response.status });
    throw error;
  }
  return response.json() as Promise<T>;
}

function totalMetric(metrics: DashboardData['metrics'], name: string): number {
  return (metrics[name] ?? []).reduce((sum, point) => sum + point.value, 0);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function humanize(value: string): string {
  return value.split('_').join(' ');
}

function eventDescription(event: AuditEvent): string {
  const task = event.payload.task;
  if (typeof task === 'string' && task.trim()) return task;
  const channel = event.payload.channel;
  return typeof channel === 'string' ? `Activity from ${channel}` : 'Aria runtime activity';
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Time unavailable' : new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date);
}

export default function Dashboard() {
  const [keyInput, setKeyInput] = useState('');
  const [adminKey, setAdminKey] = useState('');
  const [data, setData] = useState<DashboardData | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const loadDashboard = useCallback(async (key: string, quiet = false) => {
    if (!quiet) setBusy(true);
    setError('');
    try {
      const [status, metrics, skills, tools, audit] = await Promise.all([
        getJson<RuntimeStatus>('/admin/status', key),
        getJson<{ metrics: DashboardData['metrics'] }>('/admin/metrics/json', key),
        getJson<{ skills: Skill[] }>('/admin/skills', key),
        getJson<{ tools: Tool[] }>('/admin/tools', key),
        getJson<{ events: AuditEvent[] }>('/admin/audit?limit=8', key),
      ]);
      setData({ status, metrics: metrics.metrics, skills: skills.skills, tools: tools.tools, events: audit.events });
      sessionStorage.setItem('aria-admin-key', key);
      setAdminKey(key);
      setUpdatedAt(new Date());
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : 'Could not load Aria data.';
      setError(message);
      if ((cause as Error & { status?: number }).status === 401) {
        sessionStorage.removeItem('aria-admin-key');
        setAdminKey('');
        setData(null);
      }
    } finally {
      if (!quiet) setBusy(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    const checkHealth = async () => {
      try {
        await getJson('/health');
        if (alive) setOnline(true);
      } catch {
        if (alive) setOnline(false);
      }
    };
    void checkHealth();
    const timer = window.setInterval(checkHealth, 15000);
    return () => { alive = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => {
    const savedKey = sessionStorage.getItem('aria-admin-key');
    if (savedKey) void loadDashboard(savedKey, true);
  }, [loadDashboard]);

  useEffect(() => {
    if (!adminKey) return;
    const timer = window.setInterval(() => void loadDashboard(adminKey, true), 15000);
    return () => window.clearInterval(timer);
  }, [adminKey, loadDashboard]);

  const requestCount = useMemo(() => data ? totalMetric(data.metrics, 'aria_http_requests_total') : 0, [data]);
  const toolCount = useMemo(() => data ? totalMetric(data.metrics, 'aria_tool_calls_total') : 0, [data]);
  const readyTools = data?.tools.filter((tool) => tool.enabled && tool.available).length ?? 0;

  const connect = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = keyInput.trim();
    if (value) void loadDashboard(value);
  };

  const disconnect = () => {
    sessionStorage.removeItem('aria-admin-key');
    setAdminKey('');
    setData(null);
    setKeyInput('');
    setError('');
  };

  return (
    <div className="mission-shell">
      <aside className="mission-rail">
        <a className="mission-brand" href="/dashboard" aria-label="Aria mission control home">
          <span className="brand-glyph">A<span>.</span></span>
          <span><strong>ARIA</strong><small>MISSION CONTROL</small></span>
        </a>
        <div className="rail-label">WORKSPACE</div>
        <nav className="mission-nav" aria-label="Main navigation">
          {NAV.map((item) => (
            <a key={item.href} className={item.href === '/dashboard' ? 'nav-item is-current' : 'nav-item'} href={item.href} aria-current={item.href === '/dashboard' ? 'page' : undefined}>
              <span className="nav-mark">{item.mark}</span><span>{item.label}</span>
            </a>
          ))}
        </nav>
        <div className="rail-bottom">
          <span className={online ? 'status-light is-online' : 'status-light'} />
          <span>{online ? 'Local runtime online' : online === false ? 'Runtime unavailable' : 'Checking runtime'}</span>
          <small>127.0.0.1:8001</small>
        </div>
      </aside>

      <main className="mission-main">
        <header className="mission-topbar">
          <div><span className="crumb-muted">Workspace</span><span className="crumb-divider">/</span><span>Overview</span></div>
          <div className="topbar-actions">
            <span className="refresh-note">{updatedAt ? `Updated ${formatTime(updatedAt.toISOString())}` : 'Live local view'}</span>
            {adminKey && <button className="quiet-button" type="button" onClick={() => void loadDashboard(adminKey)} disabled={busy}>{busy ? 'Refreshing…' : 'Refresh'}</button>}
          </div>
        </header>

        <div className="mission-content">
          <section className="welcome-panel">
            <div className="welcome-copy">
              <p className="overline">PERSONAL AI · LOCAL INSTANCE</p>
              <h1>Your Aria,<br /><em>at a glance.</em></h1>
              <p className="welcome-description">A clear view of Aria’s runtime, tools, skills and recent work.</p>
            </div>
            <div className="welcome-status">
              <span className={online ? 'pulse-dot is-online' : 'pulse-dot'} />
              <div><strong>{online ? 'Runtime online' : online === false ? 'Runtime offline' : 'Checking runtime'}</strong><span>Local service · port 8001</span></div>
              <span className="welcome-orbit" aria-hidden="true" />
            </div>
          </section>

          {!data ? (
            <section className="connect-panel" aria-labelledby="connect-title">
              <div className="connect-intro">
                <span className="section-index">01 / ACCESS</span>
                <h2 id="connect-title">Connect to your workspace</h2>
                <p>Use the local admin key to load live runtime details. The key stays in this browser session.</p>
              </div>
              <form className="connect-form" onSubmit={connect}>
                <label htmlFor="admin-key">Admin key</label>
                <div className="key-row"><input id="admin-key" type="password" value={keyInput} onChange={(event) => setKeyInput(event.target.value)} autoComplete="current-password" placeholder="Enter your admin key" required /><button type="submit" disabled={busy}>{busy ? 'Connecting…' : 'Connect'}</button></div>
                {error && <p className="inline-error" role="alert">{error}</p>}
              </form>
            </section>
          ) : (
            <>
              {error && <div className="inline-error page-error" role="alert">Refresh issue: {error}</div>}
              <section className="overview-strip" aria-label="Runtime overview">
                <div className="overview-stat"><span className="stat-label">REQUESTS</span><strong>{formatNumber(requestCount)}</strong><span className="stat-foot">Recorded by this runtime</span></div>
                <div className="overview-stat"><span className="stat-label">TOOL CALLS</span><strong>{formatNumber(toolCount)}</strong><span className="stat-foot">Successful and failed calls</span></div>
                <div className="overview-stat"><span className="stat-label">AVAILABLE TOOLS</span><strong>{readyTools}<small> / {data.tools.length}</small></strong><span className="stat-foot">Enabled in Aria’s registry</span></div>
                <div className="overview-stat"><span className="stat-label">MODEL PROVIDER</span><strong className="provider-value">{data.status.model_provider}</strong><span className="stat-foot">Configured for inference</span></div>
              </section>

              <div className="dashboard-grid">
                <section className="surface-panel activity-panel" aria-labelledby="activity-title">
                  <div className="panel-heading"><div><span className="section-index">02 / ACTIVITY</span><h2 id="activity-title">Recent activity</h2></div><a href="/aria-trace">Open trace <span aria-hidden="true">↗</span></a></div>
                  {data.events.length ? <ol className="activity-list">{data.events.slice(0, 6).map((item, index) => (
                    <li className="activity-row" key={`${item.ts}-${item.event_type}-${index}`}>
                      <span className="activity-marker" aria-hidden="true" />
                      <div className="activity-copy"><strong>{humanize(item.event_type)}</strong><span>{eventDescription(item)}</span></div>
                      <time dateTime={item.ts}>{formatTime(item.ts)}</time>
                    </li>
                  ))}</ol> : <div className="empty-state"><strong>No activity recorded yet.</strong><span>New requests and tool calls will appear here.</span><a href="/">Start a conversation ↗</a></div>}
                </section>

                <section className="runtime-panel" aria-labelledby="runtime-title">
                  <div className="panel-heading"><div><span className="section-index">03 / RUNTIME</span><h2 id="runtime-title">Configuration</h2></div></div>
                  <dl className="runtime-details">
                    <div><dt>Assistant</dt><dd>{data.status.agent_name}</dd></div>
                    <div><dt>Short-term memory</dt><dd>{data.status.redis_enabled ? `Valkey · ${data.status.short_term_memory_turns} turns` : 'Disabled'}</dd></div>
                    <div><dt>Long-term recall</dt><dd>Top {data.status.long_term_memory_top_k} results</dd></div>
                  </dl>
                  <div className="channel-block"><span className="stat-label">ENABLED CHANNELS</span><div className="channel-list">{data.status.enabled_channels.map((channel) => <span key={channel} className="channel-chip">{channel}</span>)}</div></div>
                </section>
              </div>

              <div className="dashboard-grid lower-grid">
                <section className="surface-panel" aria-labelledby="tools-title">
                  <div className="panel-heading"><div><span className="section-index">04 / CAPABILITIES</span><h2 id="tools-title">Tools</h2></div><a href="/command-center">Manage <span aria-hidden="true">↗</span></a></div>
                  {data.tools.length ? <ul className="capability-list">{data.tools.slice(0, 6).map((tool) => <li key={tool.name}><span className="capability-mark" aria-hidden="true">⌘</span><div><strong>{tool.name}</strong><span>{tool.description}</span></div><span className={tool.available && tool.enabled ? 'availability is-ready' : 'availability'}>{tool.available && tool.enabled ? 'Ready' : 'Off'}</span></li>)}</ul> : <div className="empty-state"><strong>No tools registered.</strong><span>Approved tools will appear here.</span></div>}
                </section>
                <section className="surface-panel skills-panel" aria-labelledby="skills-title">
                  <div className="panel-heading"><div><span className="section-index">05 / SKILLS</span><h2 id="skills-title">Skills library</h2></div><a href="/command-center">View <span aria-hidden="true">↗</span></a></div>
                  {data.skills.length ? <ul className="skill-list">{data.skills.slice(0, 5).map((skill) => <li key={skill.name}><div><strong>{humanize(skill.name)}</strong><span>{skill.description}</span></div><span className={skill.loaded ? 'availability is-ready' : 'availability'}>{skill.loaded ? 'Loaded' : skill.category || 'Available'}</span></li>)}</ul> : <div className="empty-state"><strong>No skills installed.</strong><span>Aria will show available skills when they are added.</span></div>}
                </section>
              </div>
              <footer className="mission-footer"><span>ARIA · LOCAL MISSION CONTROL</span><button type="button" onClick={disconnect}>Disconnect session</button></footer>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
