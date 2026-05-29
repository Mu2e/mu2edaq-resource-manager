'use strict';

let _autoRefreshTimer = null;

// Authenticated identity resolved from the token via /api/whoami.
// principal = the resource owner; role = client|operator.
let _identity = { principal: null, role: null };

// Per-category collapse state; persisted in sessionStorage.
let _collapsed = {};

// ── Helpers ─────────────────────────────────────────────────────────────────

// Display port list as "first-last" (or just the single port if only one).
function formatPorts(ports) {
  if (!ports || ports.length === 0) return '';
  const sorted = [...ports].sort((a, b) => a - b);
  return sorted.length === 1 ? `${sorted[0]}` : `${sorted[0]}-${sorted[sorted.length - 1]}`;
}

// Strip trailing numeric suffix so "CALO-1" and "CALO-8" share category "CALO".
function categoryKey(cls) {
  return cls.replace(/-\d+$/, '');
}

function loadCollapsed() {
  try { _collapsed = JSON.parse(sessionStorage.getItem('rm_collapsed') || '{}'); }
  catch (_) { _collapsed = {}; }
}

function saveCollapsed() {
  sessionStorage.setItem('rm_collapsed', JSON.stringify(_collapsed));
}

function toggleCategory(key) {
  _collapsed[key] = !_collapsed[key];
  saveCollapsed();
  // Toggle visibility of all data rows belonging to this category.
  document.querySelectorAll(`tr[data-category="${CSS.escape(key)}"]`).forEach(row => {
    row.style.display = _collapsed[key] ? 'none' : '';
  });
  // Flip the arrow on the header row.
  const hdr = document.querySelector(`tr.group-header[data-key="${CSS.escape(key)}"]`);
  if (hdr) hdr.querySelector('.group-arrow').textContent = _collapsed[key] ? '▶' : '▼';
}

// Free-text operator annotation (the "Operator" field / "Who" column).
function operatorLabel() {
  return document.getElementById('operator-input').value.trim();
}

function authToken() {
  return document.getElementById('token-input').value.trim();
}

// Authorization header for state-changing requests, when a token is set.
function authHeaders() {
  const t = authToken();
  return t ? { 'Authorization': `Bearer ${t}` } : {};
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

// ── Identity (client ID + token role) ────────────────────────────────────────

function updateOperatorDisplay() {
  document.getElementById('identity-operator').textContent = operatorLabel() || '—';
}

// Resolve the token's principal and role from the server (these live in the
// auth config, not the token itself). Updates _identity, the role badge, the
// first-load hint, and re-renders the table so the Release buttons reflect the
// authenticated principal.
async function updateRoleDisplay() {
  const roleEl = document.getElementById('identity-role');
  const hint = document.getElementById('auth-hint');

  if (!authToken()) {
    _identity = { principal: null, role: null };
    roleEl.textContent = '—';
    hint.style.display = 'block';
    loadResources();
    return;
  }
  try {
    const who = await apiFetch('/api/whoami', { headers: authHeaders() });
    _identity = { principal: who.principal, role: who.role };
    roleEl.textContent = who.role;
    hint.style.display = 'none';
  } catch (err) {
    _identity = { principal: null, role: null };
    roleEl.textContent = (err && err.status === 401) ? 'invalid token' : '—';
    hint.style.display = 'block';
  }
  loadResources();
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

  try {
    const resources = await apiFetch(url);

    if (resources.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="cell-center cell-muted">No resources found.</td></tr>';
      return;
    }

    // Group resources by category key, preserving server order within each group.
    const groups = new Map();
    for (const r of resources) {
      const key = categoryKey(r.resource_class);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(r);
    }

    const rows = [];
    for (const [key, members] of groups) {
      const collapsed = !!_collapsed[key];
      const arrow = collapsed ? '▶' : '▼';
      const total = members.length;
      const avail = members.filter(r => r.status === 'available').length;
      const resvd = total - avail;
      const summary = `${total} resource${total !== 1 ? 's' : ''} — `
        + `<span class="status-available">${avail} available</span>, `
        + `<span class="status-reserved">${resvd} reserved</span>`;
      rows.push(`<tr class="group-header" data-key="${esc(key)}" onclick="toggleCategory(${esc(JSON.stringify(key))})">
        <td colspan="10">
          <span class="group-arrow">${arrow}</span>
          <span class="group-label">${esc(key)}</span>
          <span class="group-summary">${summary}</span>
        </td>
      </tr>`);

      for (const r of members) {
        const ports      = r.location.ports_any ? 'ANY' : formatPorts(r.location.ports);
        const statusCls  = `status-${r.status}`;
        const ownerCell  = r.owner ? `<span class="owner-cell">${esc(r.owner)}</span>` : '<span class="cell-muted">—</span>';
        const whoCell    = r.who ? esc(r.who) : '<span class="cell-muted">—</span>';
        const canRelease = _identity.role === 'operator' || r.owner === _identity.principal;
        let   actionCell = '';
        if (r.status === 'available') {
          actionCell = `<button class="btn btn-reserve"
            onclick="event.stopPropagation();reserve(${esc(JSON.stringify(r.resource_class))},${esc(JSON.stringify(r.name))},${esc(JSON.stringify(r.enumerator))})">
            Reserve</button>`;
        } else if (canRelease) {
          actionCell = `<button class="btn btn-release"
            onclick="event.stopPropagation();release(${esc(JSON.stringify(r.resource_class))},${esc(JSON.stringify(r.name))},${esc(JSON.stringify(r.enumerator))})">
            Release</button>`;
        }
        rows.push(`<tr data-category="${esc(key)}"${collapsed ? ' style="display:none"' : ''}>
          <td>${esc(r.resource_class)}</td>
          <td>${esc(r.name)}</td>
          <td>${esc(r.enumerator)}</td>
          <td class="node-cell">${esc(r.location.node)}</td>
          <td>${esc(r.location.user)}</td>
          <td class="ports-cell">${esc(ports)}</td>
          <td class="${statusCls}">${esc(r.status)}</td>
          <td>${ownerCell}</td>
          <td>${whoCell}</td>
          <td>${actionCell}</td>
        </tr>`);
      }
    }
    tbody.innerHTML = rows.join('');

    document.getElementById('last-updated').textContent =
      'Updated: ' + new Date().toLocaleTimeString();
  } catch (err) {
    const msg = (err.data && err.data.detail) ? err.data.detail : 'Connection error';
    tbody.innerHTML = `<tr><td colspan="10" class="cell-center" style="color:var(--red);padding:20px">
      Failed to load resources: ${esc(msg)}</td></tr>`;
  }
}

// ── Reserve / Release ────────────────────────────────────────────────────────

async function reserve(resourceClass, name, enumerator) {
  try {
    await apiFetch('/api/reserve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        who: operatorLabel() || null,
        resources: [{ resource_class: resourceClass, name, enumerator }],
      }),
    });
    flash(`Reserved ${resourceClass}:${name}:${enumerator}`, 'success');
    await refresh();
  } catch (err) {
    const detail = err.data && err.data.detail;
    const msg = detail ? (detail.message || detail) : 'Failed to reserve resource';
    flash(msg, 'error');
  }
}

async function release(resourceClass, name, enumerator) {
  try {
    await apiFetch('/api/release', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
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
  loadCollapsed();
  // Restore and persist the bearer token across reloads (sessionStorage so it
  // is cleared when the tab closes).
  const tokenInput = document.getElementById('token-input');
  tokenInput.value = sessionStorage.getItem('rm_token') || '';
  tokenInput.addEventListener('input', () => {
    sessionStorage.setItem('rm_token', tokenInput.value.trim());
    updateRoleDisplay();
  });

  // Restore and persist the operator label; keep its badge in sync.
  const opInput = document.getElementById('operator-input');
  opInput.value = sessionStorage.getItem('rm_operator') || '';
  opInput.addEventListener('input', () => {
    sessionStorage.setItem('rm_operator', opInput.value.trim());
    updateOperatorDisplay();
  });

  // Draw attention to the token field on first load when it is empty.
  if (!tokenInput.value) tokenInput.focus();

  updateOperatorDisplay();
  updateRoleDisplay();
  refresh();
  _autoRefreshTimer = setInterval(refresh, 5000);
});
