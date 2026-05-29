'use strict';

let _autoRefreshTimer = null;

// Authenticated identity resolved from the token via /api/whoami.
// principal = the resource owner; role = client|operator.
let _identity = { principal: null, role: null };

// ── Helpers ─────────────────────────────────────────────────────────────────

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

    tbody.innerHTML = resources.map(r => {
      const ports      = r.location.ports_any ? 'ANY' : (r.location.ports || []).join(', ');
      const statusCls  = `status-${r.status}`;
      const ownerCell  = r.owner ? `<span class="owner-cell">${esc(r.owner)}</span>` : '<span class="cell-muted">—</span>';
      const whoCell    = r.who ? esc(r.who) : '<span class="cell-muted">—</span>';
      // The owner is the authenticated principal; an operator may release any.
      const canRelease = _identity.role === 'operator' || r.owner === _identity.principal;
      let   actionCell = '';

      if (r.status === 'available') {
        actionCell = `<button class="btn btn-reserve"
          onclick="reserve(${esc(JSON.stringify(r.resource_class))},${esc(JSON.stringify(r.name))},${esc(JSON.stringify(r.enumerator))})">
          Reserve</button>`;
      } else if (canRelease) {
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
        <td>${whoCell}</td>
        <td>${actionCell}</td>
      </tr>`;
    }).join('');

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
