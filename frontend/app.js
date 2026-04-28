const state = {
  batchId: null,
  items: [],
  logs: [],
  poller: null,
};

const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const folderInput = document.getElementById('folderInput');
const resultsEl = document.getElementById('results');
const logsEl = document.getElementById('logs');
const globalStats = document.getElementById('globalStats');
const globalProgress = document.getElementById('globalProgress');
const searchInput = document.getElementById('searchInput');
const sortSelect = document.getElementById('sortSelect');

function fmtSec(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

function getFilesFromDrop(ev) {
  const files = [];
  for (const item of ev.dataTransfer.items) {
    const file = item.getAsFile();
    if (file && file.type.startsWith('image/')) files.push(file);
  }
  return files;
}

function attachInteractions() {
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('bg-white/20');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('bg-white/20'));
  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    dropzone.classList.remove('bg-white/20');
    await uploadFiles(getFilesFromDrop(e), []);
  });
  fileInput.addEventListener('change', async () => {
    await uploadFiles([...fileInput.files], []);
  });
  folderInput.addEventListener('change', async () => {
    const files = [...folderInput.files].filter((f) => f.type.startsWith('image/'));
    const rel = files.map((f) => f.webkitRelativePath || f.name);
    await uploadFiles(files, rel);
  });
  searchInput.addEventListener('input', renderResults);
  sortSelect.addEventListener('change', renderResults);
  document.querySelectorAll('.export-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (!state.batchId) return;
      window.open(`/api/batches/${state.batchId}/export/${btn.dataset.export}`, '_blank');
    });
  });
  document.getElementById('themeToggle').addEventListener('click', () => {
    document.body.classList.toggle('light');
  });
}

async function uploadFiles(files, relativePaths) {
  if (!files.length) return;
  showSkeletons();
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  form.append('relative_paths', relativePaths.join('||'));
  const res = await fetch('/api/batches', { method: 'POST', body: form });
  const payload = await res.json();
  state.batchId = payload.batch_id;
  if (state.poller) clearInterval(state.poller);
  await refreshBatch();
  state.poller = setInterval(refreshBatch, 1200);
}

async function refreshBatch() {
  if (!state.batchId) return;
  const res = await fetch(`/api/batches/${state.batchId}`);
  if (!res.ok) return;
  const payload = await res.json();
  state.items = payload.items;
  state.logs = payload.logs;
  renderSummary(payload.summary);
  renderResults();
  renderLogs();
}

function renderSummary(summary) {
  globalStats.innerHTML = [
    ['Total files', summary.total_files],
    ['Completed', summary.completed_files],
    ['Failed', summary.failed_files],
    ['ETA', fmtSec(summary.estimated_remaining_seconds)],
  ].map(([label, value]) => `
      <div class="rounded-xl border border-white/20 p-4">
        <p class="text-xs text-white/60">${label}</p>
        <p class="text-xl font-semibold">${value}</p>
      </div>
    `).join('');

  const progress = summary.total_files ? ((summary.completed_files + summary.failed_files) / summary.total_files) * 100 : 0;
  globalProgress.style.width = `${progress}%`;
}

function renderResults() {
  const query = searchInput.value.toLowerCase();
  const sortBy = sortSelect.value;
  let items = [...state.items].filter((item) =>
    item.filename.toLowerCase().includes(query) || item.visible_text.toLowerCase().includes(query)
  );
  items.sort((a, b) => {
    if (sortBy === 'importance') return b.importance_score - a.importance_score;
    if (sortBy === 'confidence') return b.confidence_score - a.confidence_score;
    return a.filename.localeCompare(b.filename);
  });

  resultsEl.innerHTML = items.map((item) => `
    <article class="rounded-xl border border-white/20 p-3 transition hover:bg-white/5">
      <div class="flex flex-col gap-3 md:flex-row">
        <img loading="lazy" src="${item.thumbnail_url}" alt="preview" class="h-24 w-24 rounded-lg object-cover"/>
        <div class="min-w-0 flex-1 space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="truncate-name font-medium">${escapeHtml(item.filename)}</h3>
            <span class="badge">${item.stage}</span>
            <span class="badge">Intent: ${item.marketing_intent}</span>
            <span class="badge">Importance: ${item.importance_score}</span>
            <span class="badge">Confidence: ${item.confidence_score}</span>
            ${item.duplicate_of ? '<span class="badge">Duplicate</span>' : ''}
          </div>
          <pre class="max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-2 text-xs">${escapeHtml(item.visible_text || '')}</pre>
          ${item.error_message ? `<p class="text-xs text-red-400">${escapeHtml(item.error_message)}</p>` : ''}
        </div>
        <div class="flex gap-2">
          <button data-retry="${item.id}" class="retry rounded-lg border border-white/30 px-3 py-2 text-xs">Retry</button>
          <button data-delete="${item.id}" class="remove rounded-lg border border-red-400/70 px-3 py-2 text-xs text-red-300">Delete</button>
        </div>
      </div>
    </article>
  `).join('');

  resultsEl.querySelectorAll('button.retry').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/items/${btn.dataset.retry}/retry`, { method: 'POST' });
      await refreshBatch();
    });
  });
  resultsEl.querySelectorAll('button.remove').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await fetch(`/api/items/${btn.dataset.delete}`, { method: 'DELETE' });
      await refreshBatch();
    });
  });
}

function renderLogs() {
  logsEl.innerHTML = state.logs.map((log) => `
    <div class="rounded-lg bg-white/5 p-2">
      <span class="mr-2 text-white/60">${new Date(log.timestamp).toLocaleTimeString()}</span>
      <span class="mr-2">[${log.level}]</span>
      <span>${escapeHtml(log.message)}</span>
      ${log.context ? `<pre class="mt-1 overflow-auto whitespace-pre-wrap text-[10px] text-white/60">${escapeHtml(log.context)}</pre>` : ''}
    </div>
  `).join('');
  logsEl.scrollTop = logsEl.scrollHeight;
}

function showSkeletons() {
  const tpl = document.getElementById('skeletonTemplate').content.firstElementChild.outerHTML;
  resultsEl.innerHTML = Array.from({ length: 5 }).map(() => tpl).join('');
}

function escapeHtml(str) {
  return str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

attachInteractions();
