'use strict';

// --- Tab switching ---
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + target).classList.add('active');
    if (target === 'search') loadCollectionsIntoSelect();
    if (target === 'collections') loadCollections();
  });
});

// --- Helpers ---
function appendLog(msg, type = '') {
  const log = document.getElementById('progress-log');
  const line = document.createElement('p');
  line.className = 'log-line' + (type ? ' ' + type : '');
  line.textContent = msg;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

function setStatusBadge(status) {
  const badge = document.getElementById('gather-status');
  badge.textContent = status.replace(/_/g, ' ');
  badge.className = 'status-badge ' + status;
}

// --- Gather (two-step) ---
let gatherPollInterval = null;
let lastProgressIndex = 0;
let currentTaskId = null;

document.getElementById('btn-gather').addEventListener('click', async () => {
  const baseUrl = document.getElementById('base-url').value.trim();
  const searchQuery = document.getElementById('search-query').value.trim();
  const collectionName = document.getElementById('collection-name').value.trim();
  const maxPages = parseInt(document.getElementById('max-pages').value, 10) || 10;
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  if (!baseUrl || !searchQuery || !collectionName) {
    alert('Please fill in Base URL, Search Query, and Collection Name.');
    return;
  }

  const btn = document.getElementById('btn-gather');
  btn.disabled = true;
  btn.textContent = 'Opening browser...';

  const progressCard = document.getElementById('progress-card');
  document.getElementById('progress-log').innerHTML = '';
  document.getElementById('process-action').classList.add('hidden');
  lastProgressIndex = 0;
  currentTaskId = null;
  progressCard.classList.remove('hidden');
  setStatusBadge('pending');

  try {
    const resp = await fetch('/api/gather', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        base_url: baseUrl, search_query: searchQuery,
        collection_name: collectionName, max_pages: maxPages,
        username, password,
      }),
    });
    if (!resp.ok) throw new Error(await resp.text());
    const { task_id } = await resp.json();
    currentTaskId = task_id;

    if (gatherPollInterval) clearInterval(gatherPollInterval);
    gatherPollInterval = setInterval(() => pollGather(task_id, btn), 2000);
  } catch (err) {
    appendLog('Error: ' + err.message, 'error');
    setStatusBadge('error');
    btn.disabled = false;
    btn.textContent = 'Open Browser';
  }
});

// "Process Current Page" button — visible only while waiting_for_user
document.getElementById('btn-process').addEventListener('click', async () => {
  if (!currentTaskId) return;
  const btn = document.getElementById('btn-process');
  btn.disabled = true;
  btn.textContent = 'Processing...';
  document.getElementById('process-action').classList.add('hidden');

  try {
    const resp = await fetch(`/api/gather/${currentTaskId}/process`, { method: 'POST' });
    if (!resp.ok) {
      const msg = await resp.text();
      appendLog('Could not trigger processing: ' + msg, 'error');
      btn.disabled = false;
      btn.textContent = 'Process Current Page';
      document.getElementById('process-action').classList.remove('hidden');
    }
  } catch (err) {
    appendLog('Error: ' + err.message, 'error');
    btn.disabled = false;
    btn.textContent = 'Process Current Page';
    document.getElementById('process-action').classList.remove('hidden');
  }
});

async function pollGather(taskId, openBtn) {
  try {
    const resp = await fetch('/api/gather/' + taskId);
    if (!resp.ok) return;
    const data = await resp.json();

    const newLines = (data.progress || []).slice(lastProgressIndex);
    newLines.forEach(msg => appendLog(msg));
    lastProgressIndex = (data.progress || []).length;

    setStatusBadge(data.status);

    // Show/hide the "Process Current Page" action
    const processAction = document.getElementById('process-action');
    if (data.status === 'waiting_for_user') {
      processAction.classList.remove('hidden');
      openBtn.textContent = 'Browser open';
    } else {
      processAction.classList.add('hidden');
    }

    if (data.status === 'done' || data.status === 'error') {
      clearInterval(gatherPollInterval);
      openBtn.disabled = false;
      openBtn.textContent = 'Open Browser';
      if (data.status === 'done') {
        appendLog(`✓ Stored ${data.total_paragraphs} paragraphs.`, 'done');
      }
      if (data.error) appendLog('Error: ' + data.error, 'error');
    }
  } catch (_) {}
}

// --- Collections ---
async function loadCollections() {
  const list = document.getElementById('collections-list');
  list.innerHTML = '<li style="color:var(--text-muted);font-size:.9rem;">Loading...</li>';
  try {
    const resp = await fetch('/api/collections');
    const { collections } = await resp.json();
    if (!collections.length) {
      list.innerHTML = '<li style="color:var(--text-muted);font-size:.9rem;">No collections yet.</li>';
      return;
    }
    list.innerHTML = '';
    collections.forEach(name => {
      const li = document.createElement('li');
      li.innerHTML = `<span>${name}</span>
        <button class="danger" data-name="${name}">Delete</button>`;
      li.querySelector('button').addEventListener('click', () => deleteCollection(name));
      list.appendChild(li);
    });
  } catch (err) {
    list.innerHTML = `<li style="color:var(--error);">Error: ${err.message}</li>`;
  }
}

async function deleteCollection(name) {
  if (!confirm(`Delete collection "${name}"? This cannot be undone.`)) return;
  try {
    const resp = await fetch('/api/collections/' + encodeURIComponent(name), { method: 'DELETE' });
    if (!resp.ok) throw new Error(await resp.text());
    await loadCollections();
  } catch (err) {
    alert('Delete failed: ' + err.message);
  }
}

document.getElementById('btn-refresh-collections').addEventListener('click', loadCollections);

async function loadCollectionsIntoSelect() {
  const sel = document.getElementById('search-collection');
  const current = sel.value;
  try {
    const resp = await fetch('/api/collections');
    const { collections } = await resp.json();
    sel.innerHTML = '<option value="">— select a collection —</option>';
    collections.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      if (name === current) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (_) {}
}

// --- Chat ---
let chatHistory = [];
let isChatStreaming = false;

async function sendChatMessage() {
  if (isChatStreaming) return;

  const collection = document.getElementById('search-collection').value;
  const inputEl = document.getElementById('chat-input');
  const query = inputEl.value.trim();

  if (!collection) { alert('Please select a collection.'); return; }
  if (!query) return;

  const messagesEl = document.getElementById('chat-messages');
  const emptyEl = messagesEl.querySelector('.chat-empty');
  if (emptyEl) emptyEl.remove();

  // User bubble
  chatHistory.push({ role: 'user', content: query });
  const userBubble = document.createElement('div');
  userBubble.className = 'message user';
  userBubble.textContent = query;
  messagesEl.appendChild(userBubble);
  inputEl.value = '';
  inputEl.style.height = 'auto';
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // Assistant bubble
  const assistantBubble = document.createElement('div');
  assistantBubble.className = 'message assistant';
  const textSpan = document.createElement('span');
  const cursorSpan = document.createElement('span');
  cursorSpan.className = 'cursor';
  assistantBubble.appendChild(textSpan);
  assistantBubble.appendChild(cursorSpan);
  messagesEl.appendChild(assistantBubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  isChatStreaming = true;
  const sendBtn = document.getElementById('btn-send');
  sendBtn.disabled = true;
  sendBtn.textContent = '…';

  const nResults = parseInt(document.getElementById('n-results').value, 10) || 5;
  let assistantText = '';
  let sources = null;

  try {
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ collection_name: collection, messages: chatHistory, n_results: nResults }),
    });
    if (!resp.ok) throw new Error(await resp.text());

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6);
        if (raw === '[DONE]') break;
        try {
          const msg = JSON.parse(raw);
          if (msg.type === 'text') {
            assistantText += msg.content;
            textSpan.textContent = assistantText;
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (msg.type === 'sources') {
            sources = msg.content;
          }
        } catch (_) {}
      }
    }
  } catch (err) {
    textSpan.textContent = 'Error: ' + err.message;
  }

  cursorSpan.remove();
  chatHistory.push({ role: 'assistant', content: assistantText });

  if (sources && sources.length) {
    const sourcesEl = document.createElement('div');
    sourcesEl.className = 'message-sources';
    const label = document.createElement('div');
    label.className = 'message-sources-label';
    label.textContent = 'Sources:';
    sourcesEl.appendChild(label);
    sources.forEach(chunk => {
      const a = document.createElement('a');
      a.className = 'source-chip';
      a.href = chunk.source_url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML = `${chunk.page_title || chunk.source_url} <span class="score-badge">${(chunk.score * 100).toFixed(0)}%</span>`;
      sourcesEl.appendChild(a);
    });
    assistantBubble.appendChild(sourcesEl);
  }

  messagesEl.scrollTop = messagesEl.scrollHeight;
  isChatStreaming = false;
  sendBtn.disabled = false;
  sendBtn.textContent = 'Send';
}

document.getElementById('btn-send').addEventListener('click', sendChatMessage);

document.getElementById('chat-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
});

document.getElementById('chat-input').addEventListener('input', function () {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 150) + 'px';
});

document.getElementById('btn-new-chat').addEventListener('click', () => {
  chatHistory = [];
  const messagesEl = document.getElementById('chat-messages');
  messagesEl.innerHTML = '<div class="chat-empty">Select a collection above and ask a question to start chatting.</div>';
});

// --- Init ---
loadCollections();
