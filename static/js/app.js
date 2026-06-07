/**
 * app.js — shared utilities loaded on every page.
 *
 * Per-page logic lives inline in each template's {% block scripts %}.
 */

// ── Theme switcher ───────────────────────────────────────────────────────
const THEME_KEY = 'bapi-theme';
const THEME_ICONS = { system: 'bi-circle-half', light: 'bi-sun-fill', dark: 'bi-moon-stars-fill' };

function _getStoredTheme() {
  return localStorage.getItem(THEME_KEY) || 'system';
}

function _getEffectiveTheme(mode) {
  return mode === 'system'
    ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
    : mode;
}

function applyTheme(mode) {
  document.documentElement.setAttribute('data-bs-theme', _getEffectiveTheme(mode));
  const icon = document.getElementById('theme-icon');
  if (icon) icon.className = `bi ${THEME_ICONS[mode] || 'bi-circle-half'}`;
  document.querySelectorAll('[data-theme]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === mode);
  });
}

// Sync icon + active state on load (theme itself already applied by <head> script)
applyTheme(_getStoredTheme());

// Handle dropdown selection
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-theme]');
  if (!btn) return;
  const mode = btn.dataset.theme;
  localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
});

// Re-apply when OS preference changes (only matters in 'system' mode)
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (_getStoredTheme() === 'system') applyTheme('system');
});

// ── Connection status indicator ──────────────────────────────────────────
// Not a live health-check — just a visual hint that settings come from .env.
document.addEventListener('DOMContentLoaded', () => {
  const badge = document.getElementById('nav-connection-badge');
  if (!badge) return;
  // Attempt a lightweight probe — search for a known internal RFC
  fetch('/api/bapi/search?q=RFC_PING&max=1')
    .then(r => {
      if (r.ok) {
        badge.className = 'badge bg-success';
        badge.innerHTML = '<i class="bi bi-plug-fill me-1"></i>SAP Connected';
      } else {
        badge.className = 'badge bg-danger';
        badge.innerHTML = '<i class="bi bi-plug me-1"></i>SAP Error';
      }
    })
    .catch(() => {
      badge.className = 'badge bg-warning text-dark';
      badge.innerHTML = '<i class="bi bi-plug me-1"></i>SAP Unreachable';
    });
});
