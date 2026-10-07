/**
 * Campus Facility Maintenance Request Management System
 * Shared Utilities & Layered Security Core (common.js)
 */

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute('content') : '';
}

/**
 * Robust fetch wrapper that automatically:
 * - Attaches X-CSRF-Token header on mutating requests (POST, PUT, DELETE, PATCH)
 * - Sets JSON headers
 * - Handles 401 session expiry and redirects
 * - Handles 403 access control denials
 */
async function apiFetch(url, options = {}) {
  const opts = { ...options };
  opts.headers = { ...(opts.headers || {}) };

  const method = (opts.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const token = getCsrfToken();
    if (token) {
      opts.headers['X-CSRF-Token'] = token;
    }
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
  }

  try {
    const response = await fetch(url, opts);

    if (response.status === 401) {
      const data = await response.json().catch(() => ({}));
      if (data.expired) {
        showToast('Your session has expired due to 30 minutes of inactivity.', 'error');
        setTimeout(() => { window.location.href = '/?expired=1'; }, 1500);
      }
      return { ok: false, status: 401, data };
    }

    if (response.status === 403) {
      const data = await response.json().catch(() => ({}));
      showToast(data.error || 'Access denied (403 Forbidden).', 'error');
      return { ok: false, status: 403, data };
    }

    const contentType = response.headers.get('content-type') || '';
    let data = null;
    if (contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return {
      ok: response.ok,
      status: response.status,
      data
    };
  } catch (err) {
    console.error('Fetch error:', err);
    showToast('Network error or server unreachable.', 'error');
    return { ok: false, status: 0, error: err };
  }
}

/**
 * Currency formatter strictly in Indian Rupees (₹)
 * Example: ₹1,25,000.00
 */
function formatINR(val) {
  const num = parseFloat(val) || 0;
  return '₹' + num.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

/**
 * Date formatter in DD-MM-YYYY hh:mm A IST format
 */
function formatISTDate(dateVal) {
  if (!dateVal) return 'N/A';
  try {
    const d = new Date(dateVal);
    if (isNaN(d.getTime())) return String(dateVal);

    const pad = (n) => String(n).padStart(2, '0');
    const day = pad(d.getDate());
    const month = pad(d.getMonth() + 1);
    const year = d.getFullYear();

    let hours = d.getHours();
    const minutes = pad(d.getMinutes());
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12; // hour '0' should be '12'

    return `${day}-${month}-${year} ${pad(hours)}:${minutes} ${ampm} IST`;
  } catch (e) {
    return String(dateVal);
  }
}

/**
 * Output escaping to prevent XSS
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Toast notifications
 */
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'error' : ''}`;
  toast.innerHTML = `
    <span>${type === 'error' ? '⚠️' : '✓'}</span>
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/**
 * Status Badge HTML generator
 */
function getStatusBadge(status) {
  const s = String(status || 'Open').toLowerCase().replace(/\s+/g, '');
  let badgeClass = 'badge-status-open';
  if (s === 'assigned') badgeClass = 'badge-status-assigned';
  else if (s === 'inprogress') badgeClass = 'badge-status-inprogress';
  else if (s === 'resolved') badgeClass = 'badge-status-resolved';
  else if (s === 'closed') badgeClass = 'badge-status-closed';

  return `<span class="badge ${badgeClass}">${escapeHtml(status)}</span>`;
}

/**
 * Priority Badge HTML generator
 */
function getPriorityBadge(priority) {
  const p = String(priority || 'Medium').toLowerCase();
  let badgeClass = 'badge-prio-medium';
  if (p === 'urgent') badgeClass = 'badge-prio-urgent';
  else if (p === 'high') badgeClass = 'badge-prio-high';
  else if (p === 'low') badgeClass = 'badge-prio-low';

  return `<span class="badge ${badgeClass}">${escapeHtml(priority)}</span>`;
}


/**
 * Global Modal Helpers
 */
function openModal(target) {
  const modal = typeof target === 'string' ? document.getElementById(target) : target;
  if (modal) {
    modal.style.display = 'flex';
    // Focus first input if available
    const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
    if (firstInput) setTimeout(() => firstInput.focus(), 100);
  }
}

function closeModal(target) {
  const modal = typeof target === 'string' ? document.getElementById(target) : target;
  if (modal) {
    modal.style.display = 'none';
  }
}

// Close modal when clicking on overlay background or pressing ESC
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
  }
});

/**
 * Logout handler
 */
async function handleLogout() {
  const res = await apiFetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/';
}

