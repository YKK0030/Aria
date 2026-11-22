"""Modern, polished browser surfaces for local Aria chat, trace, command centre, memory, metrics, and dashboard."""

SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} · Aria</title><style>
:root{{
  --ink:#0f1713; --ink-muted:#4a5c53; --paper:#f5f3ed; --surface:#ffffff;
  --line:#e0ddcf; --line-strong:#d0cbc8; --brand:#2d5a45; --brand-light:#3d7a58;
  --brand-pale:#e8f2ed; --accent:#c97d3e; --accent-light:#d9935a;
  --danger:#b83a3a; --danger-pale:#fdeaea; --warning:#b8860b; --warning-pale:#fef3c7;
  --success:#2d5a45; --success-pale:#e8f2ed; --focus:#c97d3e;
  --shadow-sm:0 1px 2px rgba(15,23,19,0.06); --shadow:0 4px 12px rgba(15,23,19,0.08);
  --shadow-lg:0 12px 28px rgba(15,23,19,0.12); --radius:10px; --radius-sm:6px;
  --mono:ui-monospace,SFMono-Regular,'JetBrains Mono',Consolas,monospace;
  --sans:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  --heading:'PP Mori','Georgia Pro',Georgia,serif;
  --transition:180ms cubic-bezier(.2,.8,.2,1);
}}
@media (prefers-color-scheme: dark){{
  :root{{
    --ink:#f0efe8; --ink-muted:#a8b8ad; --paper:#0f1713; --surface:#161f1a;
    --line:#2a3830; --line-strong:#34433a; --brand:#78c8a0; --brand-light:#8fd4b8;
    --brand-pale:#123024; --accent:#e0a05a; --accent-light:#f0b87a;
    --danger:#e87a7a; --danger-pale:#3a1a1a; --warning:#f0c05a; --warning-pale:#3a2e0f;
    --success:#78c8a0; --success-pale:#123024;
    --shadow-sm:0 1px 2px rgba(0,0,0,0.3); --shadow:0 4px 12px rgba(0,0,0,0.4);
    --shadow-lg:0 12px 28px rgba(0,0,0,0.5);
  }}
}}
*{{box-sizing:border-box}}
@media (prefers-reduced-motion: reduce){{
  *,*::before,*::after{{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
}}
html{scroll-behavior:smooth}}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 var(--sans);letter-spacing:-.005em;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}}
.layout{min-height:100vh;display:grid;grid-template-columns:260px minmax(0,1fr)}}
aside{
  background:linear-gradient(180deg,var(--surface) 0%,var(--paper) 100%);
  border-right:1px solid var(--line);padding:32px 24px;
  display:flex;flex-direction:column;gap:40px;position:sticky;top:0;height:100vh;overflow-y:auto
}}
.brand{font:500 28px/1.05 var(--heading);letter-spacing:-.02em;color:var(--ink)}}
.brand small{display:block;margin-top:10px;color:var(--ink-muted);font:11px/1.4 var(--mono);letter-spacing:.15em;text-transform:uppercase;font-weight:600}}
nav{display:grid;gap:4px}}
nav a{color:var(--ink-muted);text-decoration:none;padding:12px 14px;border-radius:var(--radius-sm);font-weight:500;transition:all var(--transition)}}
nav a:hover,nav a:focus-visible{color:var(--ink);background:var(--brand-pale)}}
nav a[aria-current="page"]{background:var(--brand);color:#fff;box-shadow:var(--shadow-sm)}}
.metric-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:20px;transition:all var(--transition)}}
.metric-card:hover{box-shadow:var(--shadow);border-color:var(--brand)}}
.metric-card .label{font:11px/1.3 var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--ink-muted);margin-bottom:6px}}
.metric-card .value{font:28px/1.1 var(--heading);letter-spacing:-.02em;color:var(--ink)}}
.metric-card .sparkline{margin-top:12px;height:40px;background:var(--paper);border-radius:var(--radius-sm);position:relative}}
.metric-card .sparkline svg{width:100%;height:100%}}
.charts-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:16px 0}}
.chart-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:16px}}
.chart-card h4{margin:0 0 12px;font:500 14px/1.3 var(--sans);color:var(--ink)}}
.side-note{margin-top:auto;color:var(--ink-muted);font-size:12px;line-height:1.5;border-top:1px solid var(--line);padding-top:16px}}
main{min-width:0;padding:40px clamp(24px,6vw,96px) 80px}}
.toplines{display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:32px}}
.eyebrow{font:11px/1.4 var(--mono);letter-spacing:.15em;text-transform:uppercase;color:var(--ink-muted);font-weight:600}}
h1{font:400 clamp(38px,5.5vw,58px)/1.05 var(--heading);letter-spacing:-.03em;margin:28px 0 12px}}
h2{font:400 26px/1.2 var(--heading);letter-spacing:-.02em;margin:0 0 16px;color:var(--ink)}}
h3{font:500 17px/1.3 var(--sans);margin:0 0 8px}}
p{margin:0 0 14px;color:var(--ink-muted);max-width:72ch}}
.muted{color:var(--ink-muted)}} .meta{font:12px/1.5 var(--mono);color:var(--ink-muted)}}
.keybar{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end;max-width:720px;margin:24px 0 36px}}
label{display:grid;gap:8px;font-size:13px;color:var(--ink-muted);font-weight:500}}
input,textarea,select,button{font:inherit;font-size:15px}}
input,textarea,select{
  width:100%;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);
  border-radius:var(--radius-sm);padding:14px 16px;min-height:50px;transition:border-color var(--transition),box-shadow var(--transition)
}}
input:hover,textarea:hover,select:hover{border-color:var(--brand)}}
input:focus,textarea:focus,select:focus,button:focus-visible,a:focus-visible{
  outline:none;box-shadow:0 0 0 3px var(--brand-pale);border-color:var(--brand)
}}
button{min-height:50px;border:0;border-radius:var(--radius-sm);background:var(--ink);color:#fff;padding:12px 24px;font-weight:600;cursor:pointer;transition:all var(--transition)}}
button:hover{background:var(--brand);transform:translateY(-1px);box-shadow:var(--shadow)}}
button:active{transform:translateY(0)}}
button:disabled{opacity:.5;cursor:not-allowed;transform:none}}
button.secondary{background:var(--surface);color:var(--ink);border:1px solid var(--line-strong)}}
button.secondary:hover{background:var(--brand-pale);border-color:var(--brand);color:var(--brand)}}
button.ghost{background:transparent;color:var(--ink-muted);border:1px solid transparent}}
button.ghost:hover{background:var(--brand-pale);color:var(--brand)}}
.status{min-height:28px;font-size:14px;font-weight:500;transition:color var(--transition)}}
.status.error{color:var(--danger)}} .status.ok{color:var(--success)}} .status.info{color:var(--accent)}}
.thread{max-width:880px;display:grid;gap:20px;margin:32px 0}}
.message{max-width:85ch;padding:18px 22px;border-radius:var(--radius);white-space:pre-wrap;overflow-wrap:anywhere;animation:fadeIn var(--transition)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}}to{opacity:1;transform:none}}}}
.message.user{margin-left:auto;background:var(--brand-pale);border:1px solid var(--brand)}}
.message.assistant{background:var(--surface);border:1px solid var(--line)}}
.message .role{font:10px/1.3 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-muted);margin-bottom:8px;font-weight:600}}
.message .content{line-height:1.7}}
.composer{max-width:880px;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}}
textarea{resize:vertical;min-height:60px;max-height:200px;line-height:1.6}}
.filters{display:grid;grid-template-columns:minmax(160px,220px) minmax(180px,1fr) auto;gap:14px;align-items:end;margin:28px 0}}
.metrics{display:flex;gap:28px;flex-wrap:wrap;border-block:1px solid var(--line);padding:20px 0;margin:24px 0 32px}}
.metric{display:flex;flex-direction:column}}
.metric strong{font:32px/1.1 var(--heading);letter-spacing:-.02em;color:var(--ink)}}
.metric span{font:10px/1.3 var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--ink-muted);font-weight:600}}
.trace-grid{display:grid;grid-template-columns:minmax(320px,.8fr) minmax(0,1.4fr);gap:32px;align-items:start}}
.events{display:grid;gap:0;border-top:1px solid var(--line)}}
.event{padding:16px 14px;border-bottom:1px solid var(--line);cursor:pointer;transition:background var(--transition)}}
.event:hover,.event:focus-visible{background:var(--brand-pale);outline:none}}
.event.selected{background:var(--ink);color:#fff}}
.event.selected .meta{color:var(--accent-light)}}
.event-title{font-weight:600;overflow-wrap:anywhere;font-size:14px}}
.badge{display:inline-block;margin-left:10px;font:10px/1.2 var(--mono);text-transform:uppercase;letter-spacing:.05em;padding:3px 8px;border-radius:999px;background:var(--success-pale);color:var(--success);font-weight:600}}
.event.selected .badge{background:var(--accent);color:#fff}}
.detail{position:sticky;top:24px;min-height:180px;background:var(--surface);padding:24px;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow-sm)}}
pre{font:12px/1.6 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;max-height:70vh;overflow:auto;margin:16px 0 0;color:var(--ink-muted);background:var(--paper);padding:16px;border-radius:var(--radius-sm);border:1px solid var(--line)}}
.empty{padding:40px 20px;color:var(--ink-muted);text-align:center}}
.overview-grid{display:grid;grid-template-columns:1.3fr .85fr;gap:28px;margin-top:32px}}
.surface{background:var(--surface);padding:28px;border-radius:var(--radius);border:1px solid var(--line);transition:box-shadow var(--transition)}}
.surface:hover{box-shadow:var(--shadow)}}
.surface p{max-width:62ch}}
.quick-links{display:grid;gap:0;margin-top:20px}}
.quick-links a{padding:16px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none;display:flex;justify-content:space-between;align-items:center;gap:16px;transition:color var(--transition)}}
.quick-links a:hover{color:var(--brand)}}
.runtime-list{display:grid;gap:14px;margin-top:22px}}
.runtime-row{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding-bottom:12px}}
.runtime-row span:first-child{color:var(--ink-muted)}}
.memory-filters{grid-template-columns:repeat(2,minmax(140px,1fr)) auto auto}}
.memory-list{max-width:960px;border-top:1px solid var(--line)}}
.memory-item{padding:20px 14px;border-bottom:1px solid var(--line);transition:background var(--transition)}}
.memory-item:hover{background:var(--brand-pale)}}
.memory-item p{white-space:pre-wrap;overflow-wrap:anywhere;margin:10px 0 0;line-height:1.7}}
.memory-item .meta{display:flex;gap:16px;flex-wrap:wrap;font-size:12px}}
.graph-wrap{margin:28px 0 36px;background:var(--ink);color:#fff;padding:28px;border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow-lg)}}
.graph-head{display:flex;justify-content:space-between;align-items:start;gap:16px;flex-wrap:wrap}}
.graph-head .meta{color:var(--ink-muted)}}
.graph-viewport{overflow:auto;margin-top:20px;scrollbar-color:var(--brand) var(--surface);scrollbar-width:thin}}
.graph-viewport svg{display:block;min-width:100%;height:280px}}
.graph-edge{stroke:var(--line);stroke-width:1.5;opacity:.6;transition:stroke var(--transition)}}
.graph-node{cursor:pointer;transition:transform var(--transition)}}
.graph-node:hover{transform:scale(1.1)}}
.graph-node circle{stroke:var(--ink);stroke-width:3;transition:stroke var(--transition)}}
.graph-node.user circle{fill:var(--accent)}} .graph-node.assistant circle{fill:var(--brand)}}
.graph-node:focus-visible{outline:3px solid var(--accent);outline-offset:4px}}
.graph-node text{fill:#fff;font:11px/1.2 var(--mono);text-anchor:middle}}
.graph-detail{min-height:36px;margin-top:14px;color:var(--ink-muted);font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--paper);color:var(--ink);padding:16px;border-radius:var(--radius-sm);border:1px solid var(--line)}}
.trace-list{display:grid;gap:14px}}
.trace-card{width:100%;text-align:left;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:var(--radius);padding:20px;min-height:0;transition:all var(--transition)}}
.trace-card:hover,.trace-card:focus-visible{background:var(--brand-pale);border-color:var(--brand);box-shadow:var(--shadow);transform:translateY(-2px)}}
.trace-card[aria-pressed="true"]{border-color:var(--brand);box-shadow:inset 4px 0 var(--brand),var(--shadow);background:var(--surface)}}
.trace-card-head{display:flex;justify-content:space-between;gap:16px;align-items:start;flex-wrap:wrap}}
.trace-card h3{font-size:15px;margin:0;font-weight:600;line-height:1.3}}
.trace-chip{font:10px/1.2 var(--mono);padding:4px 10px;border-radius:999px;background:var(--brand-pale);color:var(--brand);font-weight:600;white-space:nowrap}}
.trace-chip.running{background:var(--warning-pale);color:var(--warning)}}
.trace-chip.failed{background:var(--danger-pale);color:var(--danger)}}
.trace-chip.success{background:var(--success-pale);color:var(--success)}}
.trace-card p{margin:10px 0 0;overflow-wrap:anywhere;font-size:14px}}
.trace-meta{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px;font:11px/1.4 var(--mono);color:var(--ink-muted)}}
.trace-detail h3{font:400 24px/1.2 var(--heading);margin:16px 0}}
.trace-detail .trace-error{padding:16px;background:var(--danger-pale);color:var(--danger);border-radius:var(--radius-sm);overflow-wrap:anywhere;border:1px solid var(--danger)}}
.trace-detail pre{max-height:45vh}}
.trace-section{margin:28px 0}}
.trace-section h2{font:400 22px/1.2 var(--heading);margin:0 0 16px}}
.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin:24px 0}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:24px;transition:all var(--transition)}}
.card:hover{box-shadow:var(--shadow);transform:translateY(-2px);border-color:var(--brand)}}
.card h3{margin:0 0 12px;font:500 17px/1.3 var(--sans);color:var(--ink)}}
.card p{margin:0;color:var(--ink-muted);font-size:14px}}
.badge-pill{display:inline-flex;align-items:center;gap:6px;font:10px/1.2 var(--mono);padding:4px 10px;border-radius:999px;background:var(--brand-pale);color:var(--brand);font-weight:600}}
.badge-pill.warning{background:var(--warning-pale);color:var(--warning)}}
.badge-pill.danger{background:var(--danger-pale);color:var(--danger)}}
.badge-pill.success{background:var(--success-pale);color:var(--success)}}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:16px 0 24px}}
.toolbar .keybar{margin:0}}
@media(max-width:900px){
  .layout{grid-template-columns:1fr}}
  aside{padding:18px 20px;gap:16px;flex-direction:row;align-items:center;justify-content:space-between;flex-wrap:wrap;position:static;height:auto}}
  .brand{font-size:22px}} .brand small{display:none}}
  nav{display:flex;flex-wrap:wrap;gap:4px}}
  .side-note{display:none}}
  main{padding:28px 18px 56px}}
  .trace-grid,.overview-grid{grid-template-columns:1fr}}
  .detail{position:static}}
  .filters,.memory-filters{grid-template-columns:1fr 1fr}} .filters button{grid-column:1/-1}}
  .keybar{grid-template-columns:1fr}} .composer{grid-template-columns:1fr}}
  .composer button{width:100%}}
  .metrics{gap:20px}}
}}
@media(max-width:520px){
  aside{align-items:flex-start;flex-direction:column}}
  .filters,.memory-filters{grid-template-columns:1fr}} .filters button{grid-column:auto}}
  .metrics{flex-direction:column;gap:16px}}
  .thread,.composer{max-width:100%}}
  .message{max-width:92%}}
  h1{font-size:32px}}
  .graph-viewport svg{height:220px}}
}}
</style></head><body><div class="layout"><aside><div class="brand">ARIA<small>Local assistant · runtime</small></div><nav aria-label="Main navigation"><a href="/command-center" {home_current}}>Command centre</a><a href="/" {chat_current}}>Chat</a><a href="/dashboard" {dashboard_current}}>Dashboard</a><a href="/aria-trace" {trace_current}}>Trace</a><a href="/memory" {memory_current}}>Memory</a><a href="/metrics" {metrics_current}}>Metrics</a></nav><div class="side-note">Private local interface · API stays on this machine</div></aside><main>{content}}</main></div></body></html>"""


def _render_page(title: str, content: str, **active_nav: str) -> str:
    page = SHELL.replace("{{", "{").replace("}}", "}")
    content = content.replace("{{", "{").replace("}}", "}")
    values = {"title": title, "home_current": "", "chat_current": "", "dashboard_current": "",
              "trace_current": "", "memory_current": "", "metrics_current": "", **active_nav}
    for key, value in values.items():
        page = page.replace("{" + key + "}", value)
    return page.replace("{content}", content)


def chat_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Personal workspace</span><span id="session" class="meta"></span></div>
<h1>Talk to Aria.</h1><p class="muted">Your local assistant. Messages stay in your Aria history.</p>
<form id="connect" class="keybar"><label for="key">Local admin key<input id="key" type="password" autocomplete="current-password" required placeholder="Enter admin key"></label><button>Connect</button></form>
<div id="status" class="status" role="status" aria-live="polite">Connect with your local admin key to load this session.</div>
<section id="thread" class="thread" aria-label="Conversation" aria-live="polite"></section>
<form id="composer" class="composer"><label for="message">Message<textarea id="message" maxlength="12000" placeholder="Ask Aria anything…" required></textarea></label><button id="send">Send</button></form>
<p class="meta" style="margin-top:14px">Enter sends · Shift+Enter adds a line · <a id="traceLink" href="/aria-trace">Open trace</a> · <a id="memoryLink" href="/memory">Inspect memory</a></p>
<script>
const $=id=>document.getElementById(id), status=$('status'), thread=$('thread');
const keyName='aria-admin-key', sessionName='aria-web-session';
let key=sessionStorage.getItem(keyName)||'', session=sessionStorage.getItem(sessionName)||crypto.randomUUID();
sessionStorage.setItem(sessionName,session); $('session').textContent='SESSION '+session.slice(0,8); $('traceLink').href='/aria-trace?channel=web&chat_id='+encodeURIComponent(session);$('memoryLink').href='/memory?channel=web&chat_id='+encodeURIComponent(session);
function setStatus(text,kind=''){status.textContent=text;status.className='status '+kind}}
function addMessage(role,text){const item=document.createElement('article');item.className='message '+role;const label=document.createElement('div');label.className='role';label.textContent=role==='user'?'You':'Aria';const body=document.createElement('div');body.className='content';body.textContent=text;item.append(label,body);thread.append(item);thread.scrollTop=thread.scrollHeight}}
async function request(path,options={}}){const response=await fetch(path,{...options,headers:{'x-admin-api-key':key,...(options.headers||{}})}}}});if(!response.ok)throw Error((await response.text())||`HTTP ${response.status}}`);return response.json()}}
async function loadHistory(){if(!key)return;try{const data=await request('/admin/history/web/'+encodeURIComponent(session)+'?limit=100');thread.replaceChildren();for(const item of data.history||[])addMessage(item.direction==='inbound'?'user':'aria',item.text||'');setStatus('Connected · local web session','ok')}}catch(error){setStatus('Could not load session. Check the key and web channel. '+error.message,'error')}}}}
$('connect').addEventListener('submit',async event=>{event.preventDefault();key=$('key').value.trim();if(!key)return;sessionStorage.setItem(keyName,key);await loadHistory();$('message').focus()}});
$('composer').addEventListener('submit',async event=>{event.preventDefault();const text=$('message').value.trim();if(!text||!key){setStatus('Connect with your admin key first.','error');return}}const button=$('send');button.disabled=true;setStatus('Aria is thinking…','info');addMessage('user',text);$('message').value='';try{const data=await request('/chat',{method:'POST',headers:{'content-type':'application/json'}},body:JSON.stringify({text,session_id:session}})}});addMessage('aria',data.response_text||'No response returned.');setStatus('Response received','ok')}}catch(error){setStatus('Message failed. '+error.message,'error')}}finally{button.disabled=false;$('message').focus()}}}});
$('message').addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('composer').requestSubmit()}}}});
$('key').value=key;if(key)loadHistory();
</script>"""
    return _render_page("Chat", content, chat_current='aria-current="page"')


def trace_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Operations · local only</span><span id="updated" class="meta">Waiting for connection</span></div>
<h1>Aria, in the open.</h1><p class="muted">Follow requests from arrival to response: model, tools, specialists, reviewer results, and delivery status. This is an operational trace, not hidden chain-of-thought.</p>
<form id="connect" class="keybar"><label for="key">Local admin key<input id="key" type="password" autocomplete="current-password" required placeholder="Enter admin key"></label><button>Connect</button></form>
<div id="status" class="status" role="status" aria-live="polite">Trace data requires your local admin key.</div>
<div class="metrics" aria-label="Trace summary"><div class="metric"><strong id="requests">—</strong><span>Requests</span></div><div class="metric"><strong id="tools">—</strong><span>Tool calls</span></div><div class="metric"><strong id="delegates">—</strong><span>Specialist runs</span></div><div class="metric"><strong id="reviews">—</strong><span>Review outcomes</span></div></div>
<form id="filters" class="filters"><label for="channel">Channel<select id="channel"><option value="">All channels</option><option>web</option><option>cli</option><option>telegram</option><option>whatsapp</option></select></label><label for="chatId">Chat or session ID<input id="chatId" autocomplete="off" placeholder="Filter by chat"></label><button>Refresh</button></form>
<div class="trace-grid"><section><h2>Requests & activity</h2><div id="events" class="trace-list" aria-live="polite"><div class="empty">Connect to load traces.</div></div></section><section id="detailPanel" class="detail trace-detail" aria-label="Selected request details"><div class="eyebrow">Request details</div><div id="detailTitle" class="muted" style="margin-top:8px">Select a request or review.</div><div id="detail"></div></section></div>
<script>
const $=id=>document.getElementById(id), keyName='aria-admin-key';let key=sessionStorage.getItem(keyName)||'', rows=[], refreshBusy=false, selectedTraceKey='';
const params=new URLSearchParams(location.search);$('channel').value=params.get('channel')||'';$('chatId').value=params.get('chat_id')||'';$('key').value=key;
function setStatus(text,error=false){$('status').textContent=text;$('status').className='status '+(error?'error':error?'':'ok')}}
function payload(row){return row.payload||{}}}}function result(row){return payload(row).result||{}}}}
function requestKey(row){const p=payload(row),e=result(row).event||{}};return [p.channel||e.channel||'',p.chat_id||e.chat_id||'',p.message_id||e.message_id||''].join('|')}}
function traceKey(row){const p=payload(row),type=row.event_type||'';return type.startsWith('inbound_')||type.startsWith('agent_run_')?'request:'+requestKey(row):[type,row.ts||'',p.proposal_id||'',p.path||'',p.name||''].join('|')}}
function isDone(row){return (row.event_type||'').startsWith('inbound_')&&(row.event_type||'').endsWith('_processed')}}
async function refresh(){if(refreshBusy)return;if(!key){setStatus('Enter the local admin key to read trace data.',true);return}}refreshBusy=true;const query=new URLSearchParams({limit:'300'}});if($('channel').value)query.set('channel',$('channel').value);if($('chatId').value.trim())query.set('chat_id',$('chatId').value.trim());try{const response=await fetch('/admin/audit?'+query,{headers:{'x-admin-api-key':key}}}});if(!response.ok)throw Error((await response.text())||`HTTP ${response.status}}`);const data=await response.json();rows=data.events||[];render();$('updated').textContent='Updated '+new Date().toLocaleTimeString();setStatus(rows.length?'Live trace connected. Auto-refreshes every 3s.':'No audit records match these filters.')}}catch(error){setStatus('Could not load trace. Check the key and Aria status. '+error.message,true)}}finally{refreshBusy=false}}}}
function render(){const root=$('events');root.replaceChildren();let toolCount=0,delegateCount=0,reviewCount=0;const requests=new Map();for(const row of rows){const type=row.event_type||'';if(['specialist_started','specialist_completed','specialist_failed'].includes(type))delegateCount++;if(type==='task_tool_reviewed'||type==='code_change_reviewed')reviewCount++;if(isDone(row)){const p=payload(row),r=result(row);toolCount+=(r.used_tools||[]).length;requests.set(requestKey(row),{done:row,start:null,agent:null}})}}else if(type==='inbound_request_started'){const id=requestKey(row),existing=requests.get(id)||{done:null,start:null,agent:null}};existing.start=row;requests.set(id,existing)}}else if(type.startsWith('agent_run_')){const id=requestKey(row),existing=requests.get(id)||{done:null,start:null,agent:null}};existing.agent=row;requests.set(id,existing)}}}}
const groups=[...requests.values()].filter(group=>group.done||group.start);
const activities=rows.filter(row=>row.event_type.startsWith('specialist_')||row.event_type.startsWith('task_tool_review')||row.event_type.startsWith('code_change_review')||row.event_type.startsWith('workspace_'));const entries=[...groups.map(group=>({row:group.done||group.start,element:makeRequestCard(group)}})),...activities.map(row=>({row,element:makeCard(row)}}))];entries.sort((a,b)=>(b.row.ts||'').localeCompare(a.row.ts||''));for(const entry of entries)root.append(entry.element);if(!root.children.length){const empty=document.createElement('div');empty.className='empty';empty.textContent='No request activity yet. Send Aria a message and this view will update automatically.';root.append(empty)}}if(selectedTraceKey){const selected=[...root.querySelectorAll('.trace-card')].find(item=>item.dataset.traceKey===selectedTraceKey);if(selected)selected.click()}}$('requests').textContent=groups.filter(group=>group.done).length+' / '+groups.length;$('tools').textContent=toolCount;$('delegates').textContent=delegateCount;$('reviews').textContent=reviewCount}}
function card(titleText,subtitle,chip,kind,time,details,row){const button=document.createElement('button');button.type='button';button.className='trace-card';button.dataset.traceKey=traceKey(row);button.setAttribute('aria-pressed','false');const head=document.createElement('div');head.className='trace-card-head';const title=document.createElement('h3');title.textContent=titleText;const status=document.createElement('span');status.className='trace-chip '+kind;status.textContent=chip;head.append(title,status);const text=document.createElement('p');text.textContent=subtitle;const meta=document.createElement('div');meta.className='trace-meta';meta.textContent=[time,details].filter(Boolean).join(' · ');button.append(head,text,meta);button.addEventListener('click',()=>select(button,titleText,row));return button}}
function makeRequestCard(group){const row=group.done||group.start,p=payload(row),r=result(row),event=r.event||{}},running=!group.done,tools=(r.used_tools||[]).map(item=>item.name).filter(Boolean),files=r.file_changes||[],error=r.delivery_error||r.error_message;let subtitle=(event.text||p.task||'Request received').slice(0,240);let action=tools.length?'Tools: '+tools.join(', '):files.length?'Files: '+files.join(', '):'Text response only';if(running&&group.agent)action='Model running: '+(payload(group.agent).model||'selected model');if(error)action='Delivery/processing issue: '+error;return card(subtitle,r.response_text|| (running?'Aria is processing this request…':'Response recorded; expand for details.'),error?'Failed':running?'In progress':'Completed',error?'failed':running?'running':'success',row.ts,(r.selected_model|| (group.agent&&payload(group.agent).model)||'' )+' · '+action,row)}}
function makeCard(row){const p=payload(row),type=row.event_type||'Activity',review=type.includes('review'),workspaceEvent=type.startsWith('workspace_'),failed=type.endsWith('failed')||p.status==='failed';const name=p.name||p.role||(review?'Code reviewer':'Specialist');const title=workspaceEvent?'Workspace · '+(p.path||p.name||'file activity'):(review?'Review · ':'Specialist · ')+name;const subtitle=workspaceEvent?(type==='workspace_file_written'?'File saved · '+(p.bytes||0)+' bytes':type==='workspace_file_read'?'File read':type==='workspace_project_activated'?'Project selected · brief saved':'Workspace folder inspected'):p.summary||p.result||p.error|| (type==='specialist_started'?'Independent specialist started; result pending.':'Activity recorded.');return card(title,String(subtitle).slice(0,420),p.status||type.replaceAll('_',' '),failed?'failed':type.endsWith('started')?'running':'success',row.ts,[p.model||'',p.findings?`${p.findings.length}} findings`:'' ].filter(Boolean).join(' · '),row)}}
function select(button,title,row){document.querySelectorAll('.trace-card[aria-pressed=true]').forEach(item=>item.setAttribute('aria-pressed','false'));button.setAttribute('aria-pressed','true');$('detailTitle').textContent=title+' · '+(row.ts||'');const root=$('detail');root.replaceChildren();const p=payload(row),r=result(row);if((row.event_type||'').startsWith('workspace_')){const action=document.createElement('p');action.textContent='Action: '+(row.event_type==='workspace_file_written'?'File saved':row.event_type==='workspace_file_read'?'File read':row.event_type==='workspace_project_activated'?'Project selected':'Folder listed');root.append(action);const path=document.createElement('p');path.textContent='Path: .data/agent-core/workspace/'+(p.path||'');root.append(path);if(p.bytes){const size=document.createElement('p');size.textContent='Size: '+p.bytes+' bytes';root.append(size)}}const note=document.createElement('p');note.className='muted';note.textContent=row.event_type==='workspace_project_activated'?'Only a short project goal is stored locally, per channel and chat.':'File contents are intentionally not copied into the operational trace.';root.append(note)}}else if(row.event_type&&row.event_type.includes('review')){if(p.description){const description=document.createElement('p');description.textContent='Reviewed item: '+p.description;root.append(description)}}if(p.model){const model=document.createElement('p');model.textContent='Reviewer model: '+p.model;root.append(model)}}const summary=document.createElement('p');summary.textContent=p.summary|| (row.event_type.endsWith('started')?'Review started; waiting for the independent reviewer result.':'No reviewer summary was recorded.');root.append(summary);if(Array.isArray(p.findings)&&p.findings.length){const heading=document.createElement('h3');heading.textContent='Findings';const list=document.createElement('ul');for(const finding of p.findings){const item=document.createElement('li');item.textContent=typeof finding===
'string'?finding:JSON.stringify(finding);list.append(item)}}root.append(list)}}const details=document.createElement('pre');details.textContent=JSON.stringify({payload:p,result:r}},null,2);root.append(details)}}else{const details=document.createElement('pre');details.textContent=JSON.stringify({payload:p,result:r}},null,2);root.append(details)}}selectedTraceKey=traceKey(row)}}
$('connect').addEventListener('submit',event=>{event.preventDefault();key=$('key').value.trim();if(key){sessionStorage.setItem(keyName,key);refresh()}}}});$('filters').addEventListener('submit',event=>{event.preventDefault();refresh()}});if(key)refresh();document.addEventListener('visibilitychange',()=>{if(!document.hidden&&key)refresh()}});setInterval(()=>{if(!document.hidden&&key)refresh()}},3000);
</script>"""
    return _render_page("Trace", content, trace_current='aria-current="page"')


def command_center_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Aria · local command centre</span><span id="updated" class="meta">Not connected</span></div>
<h1>Command centre.</h1><p class="muted">A clear view of Aria's runtime, conversations, memory, and review activity.</p>
<form id="connect" class="keybar"><label for="key">Local admin key<input id="key" type="password" autocomplete="current-password" required placeholder="Enter admin key"></label><button>Connect</button></form>
<div id="status" class="status" role="status" aria-live="polite">Connect to load local operational data.</div>
<div class="metrics"><div class="metric"><strong id="channels">—</strong><span>Channels on</span></div><div class="metric"><strong id="tools">—</strong><span>Available tools</span></div><div class="metric"><strong id="drafts">—</strong><span>Tool drafts</span></div><div class="metric"><strong id="events">—</strong><span>Recent trace events</span></div></div>
<div class="card-grid"><section class="card"><h3>Workspace</h3><p>Create, edit, and inspect files in your bounded workspace.</p><div class="quick-links" style="margin-top:16px"><a href="/">Open local chat <span aria-hidden="true">→</span></a><a href="/aria-trace">Inspect trace & reviewer activity <span aria-hidden="true">→</span></a><a href="/memory">Explore short- and long-term memory <span aria-hidden="true">→</span></a></div></section>
<section class="card"><h3>Runtime</h3><div id="runtime" class="runtime-list"><p class="muted">Runtime details appear after connecting.</p></div></section>
<section class="card"><h3>Skills</h3><p>Manage adaptive skills and view learning preferences.</p><div class="quick-links" style="margin-top:16px"><button id="viewSkills" class="secondary" style="width:100%;text-align:left;padding:12px;background:none;border:none;cursor:pointer;font:inherit;color:var(--brand);border-top:1px solid var(--line)">View skills & learning <span aria-hidden="true">→</span></button></div></section>
<section class="card"><h3>Consolidation</h3><p>Nightly memory consolidation and pattern detection.</p><div class="quick-links" style="margin-top:16px"><button id="runConsolidation" class="secondary" style="width:100%;text-align:left;padding:12px;background:none;border:none;cursor:pointer;font:inherit;color:var(--brand);border-top:1px solid var(--line)">Run consolidation now <span aria-hidden="true">→</span></button></div></section>
<section class="card"><h3>Metrics</h3><p>Prometheus metrics dashboard with real-time charts.</p><div class="quick-links" style="margin-top:16px"><a href="/metrics/ui" style="width:100%;text-align:left;padding:12px;background:none;border:none;cursor:pointer;font:inherit;color:var(--brand);border-top:1px solid var(--line);text-decoration:none">Open metrics dashboard <span aria-hidden="true">→</span></a></div></section></div>
<script>
const $=id=>document.getElementById(id), keyName='aria-admin-key';let key=sessionStorage.getItem(keyName)||'';$('key').value=key;
async function get(path){const response=await fetch(path,{headers:{'x-admin-api-key':key}}}});if(!response.ok)throw Error(`Request failed (${response.status}})`);return response.json()}}
function row(name,value){const item=document.createElement('div');item.className='runtime-row';const a=document.createElement('span'),b=document.createElement('strong');a.textContent=name;b.textContent=value;item.append(a,b);return item}}
async function refresh(){if(!key)return;const status=$('status');status.textContent='Loading runtime overview…';status.className='status';try{const [runtime,tools,drafts,audit]=await Promise.all([get('/admin/status'),get('/admin/tools'),get('/admin/tool-proposals'),get('/admin/audit?limit=100')]);$('channels').textContent=runtime.enabled_channels.length;$('tools').textContent=tools.tools.filter(item=>item.available).length;$('drafts').textContent=drafts.proposals.length;$('events').textContent=audit.events.length;const panel=$('runtime');panel.replaceChildren(row('Agent',runtime.agent_name),row('Provider',runtime.model_provider||'Configured locally'),row('Channels',runtime.enabled_channels.join(', ')||'None'),row('Short memory',runtime.redis_enabled?'Valkey / Redis':'Disabled'),row('Long memory','SQLite graph'));$('updated').textContent='Updated '+new Date().toLocaleTimeString();status.textContent='Connected · local runtime';status.className='status ok'}}catch(error){status.textContent='Could not load command centre. Check the admin key and that Aria is running. '+error.message;status.className='status error'}}}}
$('connect').addEventListener('submit',event=>{event.preventDefault();key=$('key').value.trim();if(key){sessionStorage.setItem(keyName,key);refresh()}}}});
$('viewSkills')?.addEventListener('click',()=>window.open('/admin/skills','_blank'));
$('runConsolidation')?.addEventListener('click',async()=>{const btn=$('runConsolidation');btn.disabled=true;btn.textContent='Running…';try{const res=await fetch('/admin/consolidation/run',{method:'POST',headers:{'x-admin-api-key':key,'content-type':'application/json'}}}});const data=await res.json();alert('Consolidation complete: '+JSON.stringify(data.result));}}catch(e){alert('Failed: '+e.message)}}finally{btn.disabled=false;btn.textContent='Run consolidation now →'}}}});
if(key)refresh();document.addEventListener('visibilitychange',()=>{if(!document.hidden&&key)refresh()}});setInterval(()=>{if(!document.hidden&&key)refresh()}},15000);
</script>"""
    return _render_page("Command centre", content, home_current='aria-current="page"')


def memory_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Personal data · local memory</span><span class="meta">Redis/Valkey · SQLite</span></div>
<h1>Memory, in context.</h1><p class="muted">Inspect the recent conversation cache or search durable graph memory. Both views are scoped to one channel and chat.</p>
<form id="connect" class="keybar"><label for="key">Local admin key<input id="key" type="password" autocomplete="current-password" required placeholder="Enter admin key"></label><button>Connect</button></form>
<div id="status" class="status" role="status" aria-live="polite">Connect before reading memory.</div>
<form id="filters" class="filters memory-filters"><label for="channel">Channel<select id="channel"><option>web</option><option>cli</option><option>telegram</option><option>whatsapp</option></select></label><label for="chatId">Chat or session ID<input id="chatId" autocomplete="off" required placeholder="Enter chat/session ID"></label><label for="kind">Memory type<select id="kind"><option value="short">Short-term · Redis/Valkey</option><option value="long">Long-term · SQLite graph</option></select></label><label for="query">Search long-term memory<input id="query" autocomplete="off" placeholder="Optional query"></label><button>Load memory</button></form>
<section id="graphSection" hidden><div class="graph-wrap"><div class="graph-head"><div><div class="eyebrow">Durable memory · relationship graph</div><p class="meta" style="margin-top:6px">User and assistant memories connected in conversation order · refreshes every 5 seconds</p></div><span id="graphCount" class="meta"></span></div><div id="graph" class="graph-viewport"></div><div id="graphDetail" class="graph-detail" role="status" aria-live="polite">Select a node to inspect its saved memory.</div></div></section>
<section aria-labelledby="memory-heading"><h2 id="memory-heading">Stored messages</h2><div id="results" class="memory-list"><div class="empty">Choose a channel and chat ID, then load memory.</div></div></section>
<script>
const $=id=>document.getElementById(id),keyName='aria-admin-key';let key=sessionStorage.getItem(keyName)||'';$('key').value=key;const params=new URLSearchParams(location.search);$('channel').value=params.get('channel')||'web';$('chatId').value=params.get('chat_id')||'';
function message(text,error=false){$('status').textContent=text;$('status').className='status '+(error?'error':'ok')}}
const svgNS='http://www.w3.org/2000/svg';let loading=false;
function drawGraph(graph){const nodes=[...(graph.nodes||[])].reverse(),edges=graph.edges||[],root=$('graph');root.replaceChildren();$('graphSection').hidden=false;$('graphCount').textContent=`${nodes.length}} memories · ${edges.length}} links`;if(!nodes.length){const empty=document.createElement('p');empty.className='meta';empty.textContent='No durable graph memories yet for this chat.';root.append(empty);return}}const width=Math.max(560,nodes.length*84+40),svg=document.createElementNS(svgNS,'svg');svg.setAttribute('viewBox',`0 0 ${width}} 280`);svg.setAttribute('role','group');svg.setAttribute('aria-label',`Memory graph with ${nodes.length}} nodes and ${edges.length}} links`);const positions=new Map(nodes.map((node,index)=>[node.id,{x:42+index*84,y:node.role==='user'?80:200}}]));for(const edge of edges){const from=positions.get(edge.from_node_id),to=positions.get(edge.to_node_id);if(!from||!to)continue;const line=document.createElementNS(svgNS,'line');line.setAttribute('x1',from.x);line.setAttribute('y1',from.y);line.setAttribute('x2',to.x);line.setAttribute('y2',to.y);line.setAttribute('class','graph-edge');svg.append(line)}}for(const node of nodes){const pos=positions.get(node.id),group=document.createElementNS(svgNS,'g');group.setAttribute('class','graph-node '+(node.role==='user'?'user':'assistant'));group.setAttribute('transform',`translate(${pos.x}} ${pos.y}})`);group.setAttribute('tabindex','0');group.setAttribute('role','button');group.setAttribute('aria-label',`${node.role}} memory ${node.id}}: ${(node.text||'').slice(0,100)}}`);const circle=document.createElementNS(svgNS,'circle');circle.setAttribute('r','14');const label=document.createElementNS(svgNS,'text');label.setAttribute('y','34');label.textContent=String(node.id);group.append(circle,label);const inspect=()=>{$('graphDetail').textContent=`${node.role}} · ${node.created_at||''}}\n${node.text||''}}`}};group.addEventListener('click',inspect);group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' ')inspect()}});svg.append(group)}}root.append(svg)}}
async function load(event,silent=false){event?.preventDefault();if(loading||!key)return;const channel=$('channel').value,chat=$('chatId').value.trim();if(!chat){if(!silent){message('Enter a chat or session ID.',true);$('chatId').focus()}}return}}loading=true;const query=new URLSearchParams({channel,chat_id:chat}});const kind=$('kind').value;if(kind==='short')query.set('limit','10');else{query.set('limit','50');query.set('query',$('query').value.trim())}}if(!silent)message('Loading memory…');try{let data,items;if(kind==='short'){const response=await fetch('/admin/memory/short-term?'+query,{headers:{'x-admin-api-key':key}}}});if(!response.ok)throw Error(`Request failed (${response.status}})`);data=await response.json();items=data.messages;$('graphSection').hidden=true}}else{const [searchResponse,graphResponse]=await Promise.all([fetch('/admin/graph/search?'+query,{headers:{'x-admin-api-key':key}}}}),fetch(`/admin/graph/chat/${encodeURIComponent(channel)}}/${encodeURIComponent(chat)}}?limit=50`,{headers:{'x-admin-api-key':key}}}})]);if(!searchResponse.ok||!graphResponse.ok)throw Error(`Request failed (${searchResponse.status||graphResponse.status}})`);data=await searchResponse.json();items=data.results;drawGraph(await graphResponse.json())}}const root=$('results');root.replaceChildren();if(!items?.length){const empty=document.createElement('div');empty.className='empty';empty.textContent=kind==='short'?'No recent messages for this channel and chat. Redis may be disabled or its retention window may have expired.':'No long-term memories match this chat and search.';root.append(empty)}}for(const item of items||[]){const article=document.createElement('article');article.className='memory-item';const meta=document.createElement('div');meta.className='meta';meta.textContent=[item.role||'memory',item.created_at||item.ts||'',item.source_message_id?'source '+item.source_message_id:''].filter(Boolean).join(' · ');const body=document.createElement('p');body.textContent=item.text||'';article.append(meta,body);root.append(article)}}if(!silent)message('Memory loaded','ok')}}catch(error){message('Load failed. '+error.message,true)}}finally{loading=false}}}}
$('connect').addEventListener('submit',event=>{event.preventDefault();key=$('key').value.trim();if(key){sessionStorage.setItem(keyName,key);load()}}}});$('filters').addEventListener('submit',load);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load(null,true)}});setInterval(()=>{if(!document.hidden&&key&&$('kind').value==='long')load(null,true)}},5000);
</script>"""
    return _render_page("Memory", content, memory_current='aria-current="page"')


def metrics_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Observability · local metrics</span><span id="updated" class="meta">Live</span></div>
<h1>Metrics dashboard.</h1><p class="muted">Real-time Prometheus metrics for Aria. Auto-refreshes every 10 seconds.</p>
<div id="status" class="status ok" role="status" aria-live="polite">Loading metrics…</div>
<div id="metricsGrid" class="charts-grid"></div>
<div class="charts-grid" id="chartsGrid"></div>
<script>
const $=id=>document.getElementById(id);
function setStatus(text,error=false){$('status').textContent=text;$('status').className='status '+(error?'error':'ok')}}
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toFixed(2)}}
function sparkline(points,color){if(!points||points.length<2)return'<svg></svg>';const w=280,h=40,pad=2;const min=Math.min(...points),max=Math.max(...points),range=max-min||1;const path=points.map((v,i)=>`${pad+i*(w-2*pad)/(points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');return`<svg viewBox="0 0 ${w}} ${h}}"><path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`}}
async function load(){
  setStatus('Loading metrics…');
  try{
    const res=await fetch('/metrics');
    if(!res.ok)throw Error(`HTTP ${res.status}}`);
    const text=await res.text();
    const metrics=parsePrometheus(text);
    render(metrics);
    setStatus('Metrics loaded · auto-refreshes every 10s','ok');
  }}catch(e){
    setStatus('Failed: '+e.message,true);
  }}
}}
function parsePrometheus(text){
  const lines=text.split('\n');
  const metrics={}};
  for(const line of lines){
    if(!line||line.startsWith('#'))continue;
    const match=line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}}]*)\}})?\s+([+-]?\d+(?:\.\d+)?)/);
    if(!match) continue;
    const name=match[1];
    const labelsStr=match[2]||'';
    const value=parseFloat(match[3]);
    const labels={}};
    if(labelsStr){
      for(const part of labelsStr.split(',')){
        const [k,v]=part.split('=');
        labels[k]=v.replace(/^"|"$/g,'');
      }}
    }}
    if(!metrics[name]) metrics[name]=[];
    metrics[name].push({labels,value}});
  }}
  return metrics;
}}
function render(metrics){
  const grid=$('metricsGrid');
  grid.style.display='grid';
  grid.replaceChildren();
  const important=['aria_http_requests_total','aria_agent_runs_total','aria_tool_calls_total','aria_memory_operations_total','aria_skill_activations_total','aria_consolidation_runs_total','aria_webhook_events_total'];
  let hasData=false;
  for(const name of important){
    const series=metrics[name];
    if(!series||!series.length) continue;
    hasData=true;
    const total=series.reduce((a,b)=>a+b.value,0);
    const card=document.createElement('div');
    card.className='metric-card';
    const points=series.slice(-20).map(s=>s.value);
    card.innerHTML=`<div class="label">${name}}</div><div class="value">${fmt(total)}}</div><div class="sparkline">${sparkline(points,'var(--brand)')}}</div>`;
    grid.appendChild(card);
  }}
  if(!hasData){
    grid.innerHTML='<p class="muted">No metrics data yet. Send some requests to generate data.</p>';
  }}
  renderCharts(metrics);
}}
function renderCharts(metrics){
  const grid=$('chartsGrid');
  grid.replaceChildren();
  const chartDefs=[{title:'HTTP Requests/sec',metric:'aria_http_requests_total',color:'var(--brand)'}},{title:'Agent Runs',metric:'aria_agent_runs_total',color:'var(--accent)'}},{title:'Tool Calls',metric:'aria_tool_calls_total',color:'var(--success)'}},{title:'Memory Ops',metric:'aria_memory_operations_total',color:'var(--warning)'}}];
  for(const defn of chartDefs){
    const series=metrics[defn.metric];
    if(!series||!series.length) continue;
    const card=document.createElement('div');
    card.className='chart-card';
    const byLabel={}};
    for(const s of series){
      for(const [k,v] of Object.entries(s.labels)){
        if(!byLabel[k]) byLabel[k]={}};
        byLabel[k][v]=(byLabel[k][v]||0)+s.value;
      }}
    }}
    const labels=Object.keys(byLabel).slice(0,10);
    const datasets=[];
    for(const label of labels){
      const points=[];
      // we only have one snapshot; just show current value
      const total=metrics[defn.metric].filter(s=>s.labels===label).reduce((a,b)=>a+b.value,0);
      datasets.push({label,points:[total]}});
    }}
    card.innerHTML=`<h4>${defn.title}}</h4><div class="sparkline" style="height:120px">${multiSparkline(datasets)}}</div>`;
    grid.appendChild(card);
  }}
}}
function multiSparkline(datasets){
  if(!datasets.length) return '<svg></svg>';
  const w=400,h=100,pad=20;
  const allPoints=datasets.flatMap(d=>d.points);
  const min=Math.min(...allPoints),max=Math.max(...allPoints),range=max-min||1;
  const colors=['var(--brand)','var(--accent)','var(--success)','var(--warning)','var(--danger)'];
  let svg=`<svg viewBox="0 0 ${w}} ${h}}">`;
  datasets.forEach((ds,i)=>{const color=colors[i%colors.length];const path=ds.points.map((v,j)=>`${pad+j*(w-2*pad)/(ds.points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');svg+=`<path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round"/>`;}});
  svg+=`</svg>`;
  return svg;
}}
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toFixed(2)}}
function sparkline(points,color){if(!points||points.length<2)return'<svg></svg>';const w=280,h=40,pad=2;const min=Math.min(...points),max=Math.max(...points),range=max-min||1;const path=points.map((v,i)=>`${pad+i*(w-2*pad)/(points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');return`<svg viewBox="0 0 ${w}} ${h}}"><path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
load();
setInterval(()=>{if(!document.hidden)load()}},10000);
</script>"""
    return _render_page("Metrics", content, metrics_current='aria-current="page"')


def dashboard_page() -> str:
    content = """<div class="toplines"><span class="eyebrow">Aria Dashboard</span><span id="updated" class="meta">Live</span></div>
<h1>Welcome to Aria.</h1><p class="muted">Your adaptive, skill‑based assistant. Choose a skill, view live metrics, or start a conversation.</p>
<div class="metrics" aria-label="Quick stats"><div class="metric"><strong id="reqCount">—</strong><span>Requests</span></div><div class="metric"><strong id="toolCount">—</strong><span>Tool calls</span></div><div class="metric"><strong id="skillCount">—</strong><span>Active skills</span></div></div>
<section class="card-grid" id="skillsGrid"><div class="empty">Loading skills…</div></section>
<h2 style="margin-top:32px">Live Metrics</h2>
<div id="metricsGrid" class="charts-grid"></div>
<div class="charts-grid" id="chartsGrid"></div>
<script>
const $=id=>document.getElementById(id);
function setStatus(text){$('status').textContent=text;}}
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toFixed(2)}}
function sparkline(points,color){if(!points||points.length<2)return'<svg></svg>';const w=280,h=40,pad=2;const min=Math.min(...points),max=Math.max(...points),range=max-min||1;const path=points.map((v,i)=>`${pad+i*(w-2*pad)/(points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');return`<svg viewBox="0 0 ${w}} ${h}}"><path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`}}
async function loadAll(){
  try{
    const [skillsRes, metricsRes]=await Promise.all([fetch('/admin/skills'), fetch('/metrics')]);
    const skillsData=await skillsRes.json();
    const metricsText=await metricsRes.text();
    const metrics=parsePrometheus(metricsText);
    renderSkills(skillsData.skills);
    renderMetrics(metrics);
    renderCharts(metrics);
  }}catch(e){
    console.error(e);
    $('skillsGrid').innerHTML='<p class="muted">Failed to load dashboard.</p>';
  }}
}}
function parsePrometheus(text){
  const lines=text.split('\\n');
  const metrics={}};
  for(const line of lines){
    if(!line||line.startsWith('#'))continue;
    const match=line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\\{([^}}]*)\\}})?\\s+([+-]?\\d+(?:\\.\\d+)?)/);
    if(!match) continue;
    const name=match[1];
    const labelsStr=match[2]||'';
    const value=parseFloat(match[3]);
    const labels={}};
    if(labelsStr){
      for(const part of labelsStr.split(',')){
        const [k,v]=part.split('=');
        labels[k]=v.replace(/^"|"$/g,'');
      }}
    }}
    if(!metrics[name]) metrics[name]=[];
    metrics[name].push({labels,value}});
  }}
  return metrics;
}}
function renderSkills(skills){
  const grid=$('skillsGrid');
  grid.replaceChildren();
  if(!skills.length){grid.innerHTML='<p class="muted">No skills installed.</p>';return}}
  for(const s of skills){
    const card=document.createElement('div');
    card.className='card';
    const badge=s.loaded?'<span class="badge-pill success">Active</span>':'<span class="badge-pill">Inactive</span>';
    card.innerHTML=`<h3>${s.name}} ${badge}}</h3><p>${s.description}}</p><p class="meta">v${s.version}} • ${s.category}}</p>`;
    grid.appendChild(card);
  }}
}}
function renderMetrics(metrics){
  const grid=$('metricsGrid');
  grid.replaceChildren();
  const important=['aria_http_requests_total','aria_agent_runs_total','aria_tool_calls_total','aria_memory_operations_total','aria_skill_activations_total','aria_consolidation_runs_total','aria_webhook_events_total'];
  let hasData=false;
  for(const name of important){
    const series=metrics[name];
    if(!series||!series.length) continue;
    hasData=true;
    const total=series.reduce((a,b)=>a+b.value,0);
    const card=document.createElement('div');
    card.className='metric-card';
    const points=series.slice(-20).map(s=>s.value);
    card.innerHTML=`<div class="label">${name}}</div><div class="value">${fmt(total)}}</div><div class="sparkline">${sparkline(points,'var(--brand)')}}</div>`;
    grid.appendChild(card);
  }}
  if(!hasData){
    $('metricsGrid').innerHTML='<p class="muted">No metrics data yet.</p>';
  }}
}}
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toFixed(2)}}
function sparkline(points,color){if(!points||points.length<2)return'<svg></svg>';const w=280,h=40,pad=2;const min=Math.min(...points),max=Math.max(...points),range=max-min||1;const path=points.map((v,i)=>`${pad+i*(w-2*pad)/(points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');return`<svg viewBox="0 0 ${w}} ${h}}"><path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`}}
function renderCharts(metrics){
  const grid=$('chartsGrid');
  grid.replaceChildren();
  const chartDefs=[{title:'HTTP Requests/sec',metric:'aria_http_requests_total',color:'var(--brand)'}},{title:'Agent Runs',metric:'aria_agent_runs_total',color:'var(--accent)'}},{title:'Tool Calls',metric:'aria_tool_calls_total',color:'var(--success)'}},{title:'Memory Ops',metric:'aria_memory_operations_total',color:'var(--warning)'}}];
  for(const defn of chartDefs){
    const series=metrics[defn.metric];
    if(!series||!series.length) continue;
    const card=document.createElement('div');
    card.className='chart-card';
    const byLabel={}};
    for(const s of series){
      for(const [k,v] of Object.entries(s.labels)){
        if(!byLabel[k])byLabel[k]={}};
        byLabel[k][v]=(byLabel[k][v]||0)+s.value;
      }}
    }}
    const labels=Object.keys(byLabel).slice(0,10);
    const datasets=[];
    for(const label of labels){
      const points=[];
      const total=metrics[defn.metric].filter(s=>JSON.stringify(s.labels)===JSON.stringify({label}})).reduce((a,b)=>a+b.value,0);
      datasets.push({label,points:[total]}});
    }}
    card.innerHTML=`<h4>${defn.title}}</h4><div class="sparkline" style="height:120px">${multiSparkline(datasets)}}</div>`;
    grid.appendChild(card);
  }}
}}
function multiSparkline(datasets){
  if(!datasets.length)return'<svg></svg>';
  const w=400,h=100,pad=20;
  const allPoints=datasets.flatMap(d=>d.points);
  const min=Math.min(...allPoints),max=Math.max(...allPoints),range=max-min||1;
  const colors=['var(--brand)','var(--accent)','var(--success)','var(--warning)','var(--danger)'];
  let svg=`<svg viewBox="0 0 ${w}} ${h}}">`;
  datasets.forEach((ds,i)=>{const color=colors[i%colors.length];const path=ds.points.map((v,j)=>`${pad+j*(w-2*pad)/(ds.points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');svg+=`<path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round"/>`;}});
  svg+=`</svg>`;
  return svg;
}}
function fmt(n){if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return n.toFixed(2)}}
function sparkline(points,color){if(!points||points.length<2)return'<svg></svg>';const w=280,h=40,pad=2;const min=Math.min(...points),max=Math.max(...points),range=max-min||1;const path=points.map((v,i)=>`${pad+i*(w-2*pad)/(points.length-1)}},${h-pad-(v-min)/range*(h-2*pad)}}`).join(' ');return`<svg viewBox="0 0 ${w}} ${h}}"><path d="M${path}}" stroke="${color}}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
loadAll();
setInterval(()=>{if(!document.hidden)loadAll()}},10000);
</script>"""
    return _render_page("Dashboard", content, dashboard_current='aria-current="page"')
