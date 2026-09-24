const $ = id => document.getElementById(id);
const icons = () => window.lucide?.createIcons();
let thread = crypto.randomUUID(), busy = false, pendingApproval = null, timer, elapsed = 0;
$('thread-id').value = thread;
const welcome = $('welcome').cloneNode(true);
const text = (id, value) => { $(id).textContent = value; };
function toast(value) { text('toast', value); $('toast').hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').hidden = true, 2500); }
function status(id, label, good) { text(id, label); $(id).className = `status ${good ? 'good' : 'bad'}`; }
function renderPartners(partners) {
  const container = $('partner-connections'); container.replaceChildren();
  for (const partner of partners) {
    const row = document.createElement('div'); row.className = 'connection';
    const label = document.createElement('span'); label.textContent = `${partner.display_name} token`;
    const state = document.createElement('span'); state.className = `status ${partner.token_present ? 'good' : 'bad'}`;
    state.textContent = partner.token_present ? 'Saved' : 'Missing';
    row.append(label, state); container.append(row);
  }
}
async function refreshStatus() {
  $('refresh').disabled = true;
  try {
    const response = await fetch('/v1/status', {signal: AbortSignal.timeout(10000), cache: 'no-store'});
    if (!response.ok) throw new Error('Status unavailable');
    const data = await response.json();
    status('api-status', 'Online', true);
    status('openai-status', data.openai_configured ? 'Configured' : 'Missing', data.openai_configured);
    renderPartners(data.partners || []);
    text('model', data.model); text('environment', `${data.environment} workspace`);
    text('runtime-approval', data.require_write_approval ? 'Required' : 'Disabled');
    text('write-policy', data.require_write_approval ? 'Partner writes require approval' : 'Write approval is disabled on the server');
    text('runtime-limit', data.max_tool_calls); text('runtime-timeout', `${data.mcp_timeout_seconds}s`);
    text('endpoint', (data.partners || []).map(partner => `${partner.display_name}: ${partner.mcp_url}`).join('\n') || '--'); text('checked-at', `Checked ${new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`);
    const missing = [];
    if (!data.openai_configured) missing.push('OpenAI key missing. Set OPENAI_API_KEY in .env, then restart the server.');
    for (const partner of data.partners || []) if (!partner.token_present) missing.push(`${partner.display_name} authorization needed. Run: ${partner.auth_command}`);
    $('setup-alert').hidden = !missing.length; text('setup-alert', missing.join('\n'));
  } catch {
    status('api-status', 'Offline', false); status('openai-status', 'Unknown', false);
    $('setup-alert').hidden = false; text('setup-alert', 'Cannot reach the local API. Start the server and refresh connection status.');
  } finally { $('refresh').disabled = false; }
}
function syncControls() {
  $('send').disabled = busy || !!pendingApproval || !$('message').value.trim() || !$('user-id').value.trim();
  $('new-chat').disabled = busy; $('user-id').disabled = busy || !!pendingApproval;
  $('message').disabled = busy || !!pendingApproval;
  $('approve').disabled = busy; $('decline').disabled = busy;
  text('counter', `${$('message').value.length.toLocaleString()} / 12,000`);
}
function addMessage(role, content) {
  $('welcome')?.remove();
  const article = document.createElement('article'); article.className = `message ${role}`;
  const heading = document.createElement('div'); heading.className = 'message-heading';
  if (role !== 'user') { const mark = document.createElement('img'); mark.src = '/static/mark.svg'; mark.alt = ''; heading.append(mark); }
  const label = document.createElement('span'); label.textContent = role === 'user' ? 'You' : role === 'error' ? 'Request failed' : 'Partner Agent';
  const time = document.createElement('time'); time.textContent = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  heading.append(label, time);
  const body = document.createElement('div'); body.className = 'message-body'; body.textContent = content;
  article.append(heading, body); $('messages').append(article); scrollChat();
  return article;
}
function scrollChat() { $('messages').scrollTop = $('messages').scrollHeight; }
function details(label, value) {
  const el = document.createElement('details'); el.className = 'tool-entry';
  const summary = document.createElement('summary'); summary.textContent = label;
  const pre = document.createElement('pre'); pre.textContent = JSON.stringify(value, null, 2);
  el.append(summary, pre); return el;
}
function inspect(data) {
  text('detail-status', data.approval_required ? 'Approval required' : 'Completed');
  text('detail-intent', data.intent.replaceAll('_', ' ')); text('detail-partner', data.partner);
  text('detail-count', data.tool_calls.length); text('trace-id', data.trace_id);
  text('response-json', JSON.stringify(data, null, 2));
  $('tool-activity').replaceChildren();
  const calls = data.approval_required ? data.planned_tools : data.tool_calls;
  if (!calls?.length) $('tool-activity').textContent = 'No tools used for this response.';
  for (const [index, call] of (calls || []).entries()) {
    $('tool-activity').append(details(`${data.approval_required ? 'Proposed' : index + 1} · ${call.name}`, call.arguments));
  }
  for (const result of data.tool_results || []) $('tool-activity').append(details(`${result.isError ? 'Error' : 'Result'} · ${result.tool}`, result));
}
async function sendRequest(payload, approval = false) {
  if (busy) return;
  busy = true; pendingApproval = null; $('approval').hidden = true; syncControls();
  if (!approval) addMessage('user', payload.message);
  const waiting = addMessage('assistant', approval ? 'Processing approved request...' : 'Working on your request...'); waiting.classList.add('pending');
  text('detail-status', 'Running'); text('detail-intent', '--'); text('detail-count', '--'); text('trace-id', 'Pending');
  text('response-json', 'Waiting for response...'); $('tool-activity').textContent = 'Waiting for tool activity...';
  const start = performance.now();
  const tick = () => { elapsed = (performance.now() - start) / 1000; text('detail-duration', `${elapsed.toFixed(1)}s`); text('request-state', `Running · ${Math.floor(elapsed)}s`); };
  tick(); timer = setInterval(tick, 250);
  try {
    const response = await fetch('/v1/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await response.json().catch(() => ({detail: `Server returned HTTP ${response.status}`}));
    const duration = ((performance.now() - start) / 1000).toFixed(1);
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
    waiting.remove();
    const article = addMessage('assistant', data.approval_required ? `This request needs your approval before making changes to ${data.partner}.` : data.answer);
    const footer = document.createElement('div'); footer.className = 'message-footer';
    const info = document.createElement('span'); info.textContent = `${data.intent.replaceAll('_', ' ')} · ${data.tool_calls.length} tool calls`;
    const copy = document.createElement('button'); copy.className = 'icon-button'; copy.title = 'Copy response'; copy.setAttribute('aria-label','Copy response');
    copy.innerHTML = '<i data-lucide="copy"></i>'; copy.onclick = () => copyText(data.answer);
    const view = document.createElement('button'); view.className = 'secondary'; view.textContent = 'Details'; view.onclick = () => { inspect(data); text('detail-duration', `${duration}s`); document.querySelector('.inspector').scrollIntoView({behavior:'smooth',block:'nearest'}); };
    footer.append(info, copy, view); article.append(footer); inspect(data); icons();
    if (data.approval_required) {
      pendingApproval = {...payload, approve_write:true}; $('approval').hidden = false;
      text('approval-request', payload.message); text('approval-tools', JSON.stringify(data.planned_tools || [], null, 2));
    }
  } catch (error) {
    waiting.remove(); const article = addMessage('error', error.message);
    const note = document.createElement('p'); note.className = 'subtle'; note.textContent = 'For a write request, check the partner system before retrying; the operation may have completed before the error.'; article.append(note);
    if (!approval) $('message').value = payload.message;
    text('detail-status','Failed'); text('response-json', error.message);
  } finally {
    clearInterval(timer); text('detail-duration', `${((performance.now()-start)/1000).toFixed(1)}s`);
    busy = false; text('request-state', pendingApproval ? 'Awaiting approval' : 'Ready'); syncControls(); scrollChat(); refreshStatus();
    if (!pendingApproval) $('message').focus();
  }
}
async function copyText(value) { try { await navigator.clipboard.writeText(value); toast('Copied'); } catch { toast('Clipboard access unavailable'); } }
$('chat-form').addEventListener('submit', event => {
  event.preventDefault(); if ($('send').disabled) return;
  const payload = {message:$('message').value.trim(), thread_id:thread, user_id:$('user-id').value.trim(), approve_write:false};
  $('message').value = ''; sendRequest(payload);
});
$('message').addEventListener('input', syncControls); $('user-id').addEventListener('input', syncControls);
$('message').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('chat-form').requestSubmit(); } });
document.addEventListener('click', event => { const button = event.target.closest('[data-prompt]'); if (button && !busy && !pendingApproval) { $('message').value = button.dataset.prompt; syncControls(); $('message').focus(); } });
$('approve').onclick = () => { if (pendingApproval) sendRequest(pendingApproval, true); };
$('decline').onclick = () => { pendingApproval = null; $('approval').hidden = true; addMessage('assistant', 'Write request declined. No approved retry was sent.'); text('detail-status','Declined'); text('request-state','Ready'); syncControls(); };
$('new-chat').onclick = () => {
  if (busy) return; thread = crypto.randomUUID(); $('thread-id').value = thread; pendingApproval = null; $('approval').hidden = true;
  $('messages').replaceChildren(welcome.cloneNode(true)); $('message').value = '';
  for (const id of ['detail-intent','detail-duration','detail-count']) text(id, '--');
  text('detail-status','No requests yet'); text('trace-id','Awaiting request'); text('response-json','No response yet.'); text('tool-activity','No tool activity yet.'); text('request-state','Ready');
  syncControls(); icons(); $('message').focus();
};
$('copy-thread').onclick = () => copyText(thread); $('refresh').onclick = refreshStatus;
icons(); syncControls(); refreshStatus();
