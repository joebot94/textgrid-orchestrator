const state = {
  snapshot: null,
  ws: null,
};

const els = {
  tabs: Array.from(document.querySelectorAll('.tab')),
  panels: {
    config: document.getElementById('tab-config'),
    live: document.getElementById('tab-live'),
    commands: document.getElementById('tab-commands'),
  },
  healthBadge: document.getElementById('healthBadge'),
  deviceCount: document.getElementById('deviceCount'),
  deviceTableBody: document.querySelector('#deviceTable tbody'),
  deviceForm: document.getElementById('deviceForm'),
  commandForm: document.getElementById('commandForm'),
  commandTarget: document.getElementById('commandTarget'),
  commandLog: document.getElementById('commandLog'),
  liveGrid: document.getElementById('liveGrid'),
  livePreset: document.getElementById('livePreset'),
  liveBlank: document.getElementById('liveBlank'),
  revisionLabel: document.getElementById('revisionLabel'),
  liveDeviceTotal: document.getElementById('liveDeviceTotal'),
  liveDeviceOnline: document.getElementById('liveDeviceOnline'),
  liveDeviceOffline: document.getElementById('liveDeviceOffline'),
};

function parseCsvNumbers(v) {
  if (!v.trim()) return [];
  return v
    .split(',')
    .map((x) => Number.parseInt(x.trim(), 10))
    .filter((x) => Number.isInteger(x) && x >= 0);
}

function fmtTs(ms) {
  const d = new Date(ms);
  return d.toLocaleTimeString();
}

async function api(url, opts = {}) {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(txt || `HTTP ${resp.status}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function setHealth(text, ok) {
  els.healthBadge.textContent = text;
  els.healthBadge.style.color = ok ? '#48d66f' : '#ff4444';
}

function setTab(tab) {
  els.tabs.forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === tab));
  Object.entries(els.panels).forEach(([name, panel]) => panel.classList.toggle('active', name === tab));
}

function renderDevices(snapshot) {
  const devices = snapshot.devices || [];
  const maxDevices = 25;
  const onlineCount = devices.filter((d) => d.online).length;

  els.deviceCount.textContent = `${devices.length} / ${maxDevices}`;
  els.liveDeviceTotal.textContent = String(devices.length);
  els.liveDeviceOnline.textContent = String(onlineCount);
  els.liveDeviceOffline.textContent = String(devices.length - onlineCount);

  els.deviceTableBody.innerHTML = '';
  els.commandTarget.innerHTML = '<option value="broadcast">Broadcast to all</option>';

  devices.forEach((d) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${d.name}</td>
      <td>${d.device_type}</td>
      <td>${d.transport}</td>
      <td>${d.endpoint || '-'}</td>
      <td>${d.sync_mode}</td>
      <td><span class="status ${d.online ? 'online' : 'offline'}">${d.online ? 'ONLINE' : 'OFFLINE'}</span></td>
      <td>
        <div class="row-actions">
          <button class="action-btn" data-action="ping" data-id="${d.id}">PING</button>
          <button class="action-btn" data-action="toggle-sync" data-id="${d.id}">${d.sync_mode === 'follow' ? 'SET INDEP' : 'SET FOLLOW'}</button>
          <button class="action-btn" data-action="remove" data-id="${d.id}">REMOVE</button>
        </div>
      </td>
    `;
    els.deviceTableBody.appendChild(tr);

    const opt = document.createElement('option');
    opt.value = d.id;
    opt.textContent = `${d.name} (${d.device_type})`;
    els.commandTarget.appendChild(opt);
  });
}

function renderLive(snapshot) {
  const visual = snapshot.visual_state;
  els.liveGrid.textContent = visual.grid_profile;
  els.livePreset.textContent = visual.preset;
  els.liveBlank.textContent = `[${visual.blanked_cells.join(', ')}]`;
  els.revisionLabel.textContent = `rev ${visual.revision}`;

  const recent = snapshot.command_log || [];
  els.commandLog.innerHTML = '';
  for (const c of recent.slice(0, 18)) {
    const li = document.createElement('li');
    const target = c.scope === 'broadcast' ? 'all' : c.target_device_id;
    const p = c.payload;
    li.textContent = `${fmtTs(c.ts_ms)} | ${c.scope}(${target}) | grid=${p.grid_profile || '-'} preset=${p.preset || '-'} blank=[${p.blank_cells.join(',')}] unblank=[${p.unblank_cells.join(',')}] ${p.note ? `| ${p.note}` : ''}`;
    els.commandLog.appendChild(li);
  }
}

function renderSnapshot(snapshot) {
  state.snapshot = snapshot;
  renderDevices(snapshot);
  renderLive(snapshot);
}

async function refreshSnapshot() {
  const snapshot = await api('/api/state');
  renderSnapshot(snapshot);
}

function connectWs() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${proto}//${window.location.host}/ws`);
  state.ws = ws;

  ws.onopen = () => setHealth('live socket', true);
  ws.onclose = () => {
    setHealth('reconnecting...', false);
    setTimeout(connectWs, 1200);
  };
  ws.onerror = () => setHealth('socket error', false);

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.event === 'snapshot') {
      renderSnapshot(msg.data);
    }
  };
}

function bindEvents() {
  els.tabs.forEach((btn) => {
    btn.addEventListener('click', () => setTab(btn.dataset.tab));
  });

  els.deviceForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await api('/api/devices', {
        method: 'POST',
        body: JSON.stringify({
          name: document.getElementById('name').value,
          device_type: document.getElementById('deviceType').value,
          transport: document.getElementById('transport').value,
          endpoint: document.getElementById('endpoint').value,
          sync_mode: document.getElementById('syncMode').value,
          enabled: true,
        }),
      });
      e.target.reset();
    } catch (err) {
      alert(`Create device failed: ${err.message}`);
    }
  });

  els.deviceTableBody.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    const id = btn.dataset.id;

    try {
      if (action === 'remove') {
        await api(`/api/devices/${id}`, { method: 'DELETE' });
      } else if (action === 'ping') {
        await api(`/api/heartbeat/${id}`, { method: 'POST' });
      } else if (action === 'toggle-sync') {
        const dev = (state.snapshot.devices || []).find((d) => d.id === id);
        if (!dev) return;
        const next = dev.sync_mode === 'follow' ? 'independent' : 'follow';
        await api(`/api/devices/${id}`, {
          method: 'PUT',
          body: JSON.stringify({ sync_mode: next }),
        });
      }
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
  });

  els.commandForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const target = document.getElementById('commandTarget').value;
    const payload = {
      grid_profile: document.getElementById('cmdGrid').value || null,
      preset: document.getElementById('cmdPreset').value || null,
      blank_cells: parseCsvNumbers(document.getElementById('cmdBlank').value),
      unblank_cells: parseCsvNumbers(document.getElementById('cmdUnblank').value),
      note: document.getElementById('cmdNote').value || null,
    };

    try {
      if (target === 'broadcast') {
        await api('/api/commands/broadcast', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/api/commands/device/${target}`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }
      e.target.reset();
    } catch (err) {
      alert(`Command failed: ${err.message}`);
    }
  });
}

async function boot() {
  setHealth('loading', false);
  bindEvents();
  await refreshSnapshot();
  connectWs();
}

boot().catch((err) => {
  setHealth('boot failed', false);
  console.error(err);
});
