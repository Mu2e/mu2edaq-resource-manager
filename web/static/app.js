'use strict';

let _autoRefreshTimer = null;

// ── Helpers ─────────────────────────────────────────────────────────────────

function clientId() {
  return document.getElementById('client-id-input').value.trim() || 'web-client';
}

async function apiFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) throw { status: res.status, data };
  return data;
}

function flash(msg, type = 'success') {
  const el = document.getElementById('flash');
  el.textContent = msg;
  el.className = `flash flash-${type}`;
  el.style.display = 'block';
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.style.display = 'none'; }, 6000);
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Status badges ────────────────────────────────────────────────────────────

async function loadStatus() {
  try {
    const s = await apiFetch('/api/status');
    document.getElementById('badge-total').textContent     = s.total;
    document.getElementById('badge-available').textContent = s.available;
    document.getElementById('badge-reserved').textContent  = s.reserved;
  } catch (_) {}
}

// ── Resource table ───────────────────────────────────────────────────────────

async function loadResources() {
  const filter = document.getElementById('filter-select').value;
  const url    = filter ? `/api/resources?status=${filter}` : '/api/resources';
  const tbody  = document.getElementById('resources-tbody');
  const cid    = clientId();

  try {
    const resources = await apiFetch(url);

    if (resources.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="cell-center cell-muted">No resources found.</td></tr>';
      return;
    }

    tbody.innerHTML = resources.map(r => {
      const ports      = (r.location.ports || []).join(', ');
      const statusCls  = `status-${r.status}`;
      const ownerCell  = r.owner ? `<span class="owner-cell">${esc(r.owner)}</span>` : '<span class="cell-muted">—</span>';
      let   actionCell = '';

      if (r.status === 'available') {
        actionCell = `<button class="btn btn-reserve"
          onclick="reserve(${esc(JSON.stringify(r.resource_class))},${esc(JSON.stringify(r.name))},${esc(JSON.stringify(r.enumerator))})">
          Reserve</button>`;
      } else if (r.owner === cid) {
        actionCell = `<button class="btn btn-release"
          onclick="release(${esc(JSON.stringify(r.resource_class))},${esc(JSON.stringify(r.name))},${esc(JSON.stringify(r.enumerator))})">
          Release</button>`;
      }

      return `<tr>
        <td>${esc(r.resource_class)}</td>
        <td>${esc(r.name)}</td>
        <td>${esc(r.enumerator)}</td>
        <td class="node-cell">${esc(r.location.node)}</td>
        <td>${esc(r.location.user)}</td>
        <td class="ports-cell">${esc(ports)}</td>
        <td class="${statusCls}">${esc(r.status)}</td>
        <td>${ownerCell}</td>
        <td>${actionCell}</td>
      </tr>`;
    }).join('');

    document.getElementById('last-updated').textContent =
      'Updated: ' + new Date().toLocaleTimeString();
  } catch (err) {
    const msg = (err.data && err.data.detail) ? err.data.detail : 'Connection error';
    tbody.innerHTML = `<tr><td colspan="9" class="cell-center" style="color:var(--red);padding:20px">
      Failed to load resources: ${esc(msg)}</td></tr>`;
  }
}

// ── Reserve / Release ────────────────────────────────────────────────────────

async function reserve(resourceClass, name, enumerator) {
  const cid = clientId();
  try {
    const data = await apiFetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: cid,
        resources: [{ resource_class: resourceClass, name, enumerator }],
      }),
    });
    flash(`Reserved ${resourceClass}:${name}:${enumerator} for '${cid}'`, 'success');
    await refresh();
  } catch (err) {
    const detail = err.data && err.data.detail;
    const msg = detail ? (detail.message || detail) : 'Failed to reserve resource';
    flash(msg, 'error');
  }
}

async function release(resourceClass, name, enumerator) {
  const cid = clientId();
  try {
    await apiFetch('/api/release', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: cid,
        resources: [{ resource_class: resourceClass, name, enumerator }],
      }),
    });
    flash(`Released ${resourceClass}:${name}:${enumerator}`, 'success');
    await refresh();
  } catch (err) {
    const msg = (err.data && err.data.detail) ? err.data.detail : 'Failed to release resource';
    flash(msg, 'error');
  }
}

// ── Auto-refresh ─────────────────────────────────────────────────────────────

async function refresh() {
  await Promise.all([loadStatus(), loadResources()]);
}

function toggleAutoRefresh() {
  const on = document.getElementById('auto-refresh-chk').checked;
  clearInterval(_autoRefreshTimer);
  if (on) _autoRefreshTimer = setInterval(refresh, 5000);
}

// ── Init ─────────────────────────────────────────────────────────────────────

window.addEventListener('load', () => {
  refresh();
  _autoRefreshTimer = setInterval(refresh, 5000);
});
