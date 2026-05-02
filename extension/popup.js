/**
 * Autoflow Bridge — Popup UI
 */

let _manualDisconnect = false;

function formatTokenAge(ms) {
  if (ms === null || ms === undefined) return 'none';
  const s = Math.floor(ms / 1000);
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function render(status) {
  if (!status) return;

  _manualDisconnect = status.manualDisconnect;

  // Status pill
  const pill = document.getElementById('status-pill');
  const txt  = document.getElementById('status-text');
  if (status.manualDisconnect || !status.connected) {
    pill.className = 'status-pill offline';
    txt.textContent = 'Offline';
  } else if (status.state === 'running') {
    pill.className = 'status-pill running';
    txt.textContent = 'Running';
  } else {
    pill.className = 'status-pill connected';
    txt.textContent = 'Connected';
  }

  // Token
  document.getElementById('token-row').textContent =
    status.flowKeyPresent ? formatTokenAge(status.tokenAge) : 'none';

  // Stats
  const m = status.metrics || {};
  document.getElementById('stats-row').textContent = m.requestCount || 0;
  document.getElementById('stats-sf').innerHTML =
    `✓ ${m.successCount || 0} &nbsp; ✗ ${m.failedCount || 0}`;

  // Error
  const errSection = document.getElementById('error-section');
  if (m.lastError) {
    errSection.style.display = 'flex';
    document.getElementById('error-row').textContent = m.lastError;
  } else {
    errSection.style.display = 'none';
  }

  // Toggle button
  const btn = document.getElementById('btn-toggle');
  if (status.manualDisconnect) {
    btn.textContent = 'Reconnect';
    btn.className   = 'success';
  } else {
    btn.textContent = 'Disconnect';
    btn.className   = 'danger';
  }
}

function fetchStatus() {
  chrome.runtime.sendMessage({ type: 'STATUS' }, (reply) => {
    if (chrome.runtime.lastError) return;
    render(reply);
  });
}

// Sync icon to system color scheme
function syncIcon() {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = isDark ? 'light' : 'dark';
  const path = {
    '16':  `icons/icon-${theme}-16.png`,
    '32':  `icons/icon-${theme}-32.png`,
    '48':  `icons/icon-${theme}-48.png`,
    '128': `icons/icon-${theme}-128.png`,
  };
  chrome.action.setIcon({ path });
  const logo = document.getElementById('logo-img');
  if (logo) logo.src = `icons/icon-${theme}-32.png`;
}

syncIcon();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', syncIcon);

// Initial fetch + poll
fetchStatus();
setInterval(fetchStatus, 1500);

// Re-render on push from background
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'STATUS_PUSH') fetchStatus();
});

// Buttons
document.getElementById('btn-flow-tab').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'OPEN_FLOW_TAB' });
});

document.getElementById('btn-refresh').addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'REFRESH_TOKEN' });
});

document.getElementById('btn-toggle').addEventListener('click', () => {
  const type = _manualDisconnect ? 'RECONNECT' : 'DISCONNECT';
  chrome.runtime.sendMessage({ type }, () => {
    if (chrome.runtime.lastError) return;
    fetchStatus();
  });
});
