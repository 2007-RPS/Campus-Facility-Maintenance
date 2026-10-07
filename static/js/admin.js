/**
 * Campus Facility Maintenance Request Management System
 * Facility Admin Console (admin.js)
 */

let allAdminRequests = [];
let adminFilter = { status: 'all', category_id: '', search: '' };
let currentTab = 'requests'; // 'requests', 'users', 'audit'

document.addEventListener('DOMContentLoaded', async () => {
  await loadAdminRequests();
  setupAdminNavigation();
  setupAdminForms();
});

function setupAdminNavigation() {
  document.querySelectorAll('.admin-nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.admin-nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      const targetTab = item.dataset.tab;
      currentTab = targetTab;

      document.querySelectorAll('.admin-view-panel').forEach(p => p.style.display = 'none');
      const targetPanel = document.getElementById(`panel-${targetTab}`);
      if (targetPanel) targetPanel.style.display = 'block';

      if (targetTab === 'requests') loadAdminRequests();
      else if (targetTab === 'users') loadAdminUsers();
      else if (targetTab === 'audit') loadAdminAuditLogs();
    });
  });

  // Filter change listeners
  const statusFilter = document.getElementById('filter-status');
  if (statusFilter) {
    statusFilter.addEventListener('change', () => {
      adminFilter.status = statusFilter.value;
      loadAdminRequests();
    });
  }

  const searchInput = document.getElementById('filter-search');
  if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        adminFilter.search = searchInput.value;
        loadAdminRequests();
      }, 300);
    });
  }
}

async function loadAdminRequests() {
  const tbody = document.getElementById('admin-requests-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">Loading maintenance requests...</td></tr>';

  let url = '/api/admin/requests?';
  if (adminFilter.status && adminFilter.status !== 'all') url += `status=${encodeURIComponent(adminFilter.status)}&`;
  if (adminFilter.search) url += `search=${encodeURIComponent(adminFilter.search)}&`;

  const res = await apiFetch(url);
  if (res.ok && Array.isArray(res.data)) {
    allAdminRequests = res.data;
    renderAdminRequestsTable();
  } else {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No requests found.</td></tr>';
  }
}

function renderAdminRequestsTable() {
  const tbody = document.getElementById('admin-requests-tbody');
  const countBadge = document.getElementById('admin-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${allAdminRequests.length} Total Requests`;

  if (allAdminRequests.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No maintenance requests match current filters.</td></tr>';
    return;
  }

  tbody.innerHTML = allAdminRequests.map(r => {
    const ticketNo = escapeHtml(r.ticket_number || `REQ-2026-${String(r.RequestID).padStart(3, '0')}`);
    const dateFormatted = formatISTDate(r.RequestDate);
    const category = escapeHtml(r.CategoryName || 'General');
    const location = `${escapeHtml(r.BuildingName || '')} - ${escapeHtml(r.RoomNo || '')}`;
    const requester = escapeHtml(r.RequesterName || 'N/A');
    const assignedTech = escapeHtml(r.AssignedTechnicians || 'Unassigned');

    let actionsHtml = `<button class="btn btn-secondary btn-sm" onclick="viewAdminRequestDetails(${r.RequestID})">Details</button>`;

    if (['Open', 'Assigned'].includes(r.Status)) {
      actionsHtml += ` <button class="btn btn-primary btn-sm" style="margin-left:4px;" onclick="openAssignModal(${r.RequestID}, ${r.CategoryID})">Assign</button>`;
    }

    if (r.Status !== 'Closed') {
      actionsHtml += ` <button class="btn btn-outline btn-sm" style="margin-left:4px;" onclick="openStatusModal(${r.RequestID}, '${r.Status}')">Status</button>`;
    }

    return `
      <tr>
        <td style="font-weight:600; color:var(--primary);">${ticketNo}</td>
        <td>${category}</td>
        <td>${location}</td>
        <td>${requester}</td>
        <td>${getPriorityBadge(r.PriorityLabel)}</td>
        <td>${getStatusBadge(r.Status)}</td>
        <td style="font-size:12.5px;">${assignedTech}</td>
        <td style="text-align:right;">${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

async function openAssignModal(reqId, categoryId) {
  const form = document.getElementById('assign-form');
  const select = document.getElementById('tech-select');
  if (!form || !select) return;

  form.dataset.requestId = reqId;
  select.innerHTML = '<option value="">Loading available technicians...</option>';
  openModal('assign-modal');

  const res = await apiFetch(`/api/admin/technicians?category_id=${categoryId}`);
  if (res.ok && Array.isArray(res.data)) {
    if (res.data.length === 0) {
      select.innerHTML = '<option value="">No available technicians</option>';
    } else {
      select.innerHTML = '<option value="">Select Technician...</option>' +
        res.data.map(t => `<option value="${t.TechID}">${escapeHtml(t.Name)} (${escapeHtml(t.Skill)}) - ${t.active_jobs || 0} active</option>`).join('');
    }
  }
}

async function openStatusModal(reqId, currentStatus) {
  const form = document.getElementById('status-update-form');
  const select = document.getElementById('new-status-select');
  const curSpan = document.getElementById('current-status-display');
  if (!form || !select) return;

  form.dataset.requestId = reqId;
  if (curSpan) curSpan.textContent = currentStatus;

  // Allowed forward status transitions
  const transitions = {
    'Open': ['Assigned'],
    'Assigned': ['In Progress'],
    'In Progress': ['Resolved'],
    'Resolved': ['Closed'],
    'Closed': []
  };

  const allowed = transitions[currentStatus] || [];
  if (allowed.length === 0) {
    showToast(`Request is in '${currentStatus}' status and cannot be advanced further.`, 'error');
    return;
  }

  select.innerHTML = allowed.map(s => `<option value="${s}">${s}</option>`).join('');
  openModal('status-modal');
}

function setupAdminForms() {
  // Assign Technician Submit
  const assignForm = document.getElementById('assign-form');
  if (assignForm) {
    assignForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = assignForm.dataset.requestId;
      const techId = document.getElementById('tech-select')?.value;

      if (!techId) {
        showToast('Please select a technician.', 'error');
        return;
      }

      const res = await apiFetch(`/api/admin/requests/${reqId}/assign`, {
        method: 'POST',
        body: { TechID: parseInt(techId) }
      });

      if (res.ok) {
        showToast('Technician assigned successfully!');
        closeModal('assign-modal');
        await loadAdminRequests();
      } else {
        showToast(res.data?.error || 'Failed to assign technician.', 'error');
      }
    });
  }

  // Status Update Submit
  const statusForm = document.getElementById('status-update-form');
  if (statusForm) {
    statusForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = statusForm.dataset.requestId;
      const newStatus = document.getElementById('new-status-select')?.value;

      if (!newStatus) return;

      const res = await apiFetch(`/api/admin/requests/${reqId}/status`, {
        method: 'PUT',
        body: { status: newStatus }
      });

      if (res.ok) {
        showToast(`Status updated to '${newStatus}'!`);
        closeModal('status-modal');
        await loadAdminRequests();
      } else {
        showToast(res.data?.error || 'Failed to update status.', 'error');
      }
    });
  }

  // Create User Form Submit (Admin Only)
  const createUserForm = document.getElementById('create-user-form');
  if (createUserForm) {
    createUserForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const name = document.getElementById('user-name').value.trim();
      const email = document.getElementById('user-email').value.trim();
      const phone = document.getElementById('user-phone').value.trim();
      const role = document.getElementById('user-role').value;
      const dept = document.getElementById('user-dept').value.trim();
      const password = document.getElementById('user-password').value;
      const skill = document.getElementById('user-skill')?.value.trim();

      if (!name || !email || !password || !role) {
        showToast('Name, email, role, and password are required.', 'error');
        return;
      }

      const submitBtn = createUserForm.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
      }

      const res = await apiFetch('/api/admin/users', {
        method: 'POST',
        body: { name, email, phone, role, dept, password, skill }
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Create User Account';
      }

      if (res.ok) {
        showToast(`User account created successfully!`);
        createUserForm.reset();
        closeModal('create-user-modal');
        await loadAdminUsers();
      } else {
        showToast(res.data?.error || 'Failed to create user.', 'error');
      }
    });
  }

  // Toggle skill field for technician role
  const roleSelect = document.getElementById('user-role');
  const skillGroup = document.getElementById('tech-skill-group');
  if (roleSelect && skillGroup) {
    roleSelect.addEventListener('change', () => {
      skillGroup.style.display = roleSelect.value === 'technician' ? 'block' : 'none';
    });
  }
}

async function loadAdminUsers() {
  const tbody = document.getElementById('admin-users-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Loading user accounts...</td></tr>';

  const res = await apiFetch('/api/admin/users');
  if (res.ok && Array.isArray(res.data)) {
    if (res.data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No users found.</td></tr>';
      return;
    }

    tbody.innerHTML = res.data.map(u => `
      <tr>
        <td style="font-weight:600;">${escapeHtml(u.Name)}</td>
        <td>${escapeHtml(u.Email)}</td>
        <td>${escapeHtml(u.Phone || 'N/A')}</td>
        <td><span class="role-badge-pill role-${escapeHtml(u.Role)}">${escapeHtml(u.Role)}</span></td>
        <td>${escapeHtml(u.Dept || 'Facilities')}</td>
        <td style="font-size:12.5px;">${u.Skill ? `<strong>${escapeHtml(u.Skill)}</strong>` : '-'}</td>
      </tr>
    `).join('');
  }
}

async function loadAdminAuditLogs() {
  const tbody = document.getElementById('admin-audit-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Loading audit trail...</td></tr>';

  const res = await apiFetch('/api/admin/audit-logs');
  if (res.ok && Array.isArray(res.data)) {
    if (res.data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No audit logs found.</td></tr>';
      return;
    }

    tbody.innerHTML = res.data.map(l => `
      <tr>
        <td style="font-weight:700; color:var(--text-muted); font-size:12px;">#${l.LogID}</td>
        <td style="font-size:12px;">${formatISTDate(l.Timestamp)}</td>
        <td><span class="badge badge-assigned">${escapeHtml(l.Action)}</span></td>
        <td style="font-size:13px;">${escapeHtml(l.UserName || 'System')} <span class="text-muted" style="font-size:11px;">(${escapeHtml(l.UserRole || 'N/A')})</span></td>
        <td style="font-size:12.5px; max-width:320px; word-break:break-word;">${escapeHtml(l.Details || '')}</td>
        <td style="font-size:11.5px; font-family:monospace;">${escapeHtml(l.IP || '127.0.0.1')}</td>
      </tr>
    `).join('');
  }
}

async function viewAdminRequestDetails(reqId) {
  const res = await apiFetch(`/api/admin/requests/${reqId}`);
  if (!res.ok) {
    showToast(res.data?.error || 'Failed to load details.', 'error');
    return;
  }

  const r = res.data;
  const content = document.getElementById('admin-details-content');
  if (!content) return;

  const ticketNo = escapeHtml(r.ticket_number || `REQ-2026-${String(r.RequestID).padStart(3, '0')}`);

  let logsHtml = '';
  if (r.work_logs && r.work_logs.length > 0) {
    logsHtml = r.work_logs.map(wl => {
      const matsList = (wl.materials || []).map(m =>
        `<li>${escapeHtml(m.MaterialName)} × ${m.Qty} @ ${formatINR(m.Cost)} = <strong>${formatINR(m.TotalCost)}</strong></li>`
      ).join('');

      return `
        <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:10px; padding:12px; margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong style="font-size:13px;">${escapeHtml(wl.TechnicianName)}</strong>
            <span class="text-muted" style="font-size:12px;">${formatISTDate(wl.WorkDate)}</span>
          </div>
          <div style="font-size:13.5px; margin-bottom:8px;">${escapeHtml(wl.WorkDescription)}</div>
          ${wl.materials && wl.materials.length > 0 ? `
            <div style="font-size:12.5px; border-top:1px dashed var(--border-color); padding-top:6px;">
              <strong>Materials:</strong>
              <ul style="margin:4px 0 0 16px;">${matsList}</ul>
              <div style="text-align:right; font-weight:700; color:var(--primary); margin-top:4px;">Total: ${formatINR(wl.total_cost)}</div>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  } else {
    logsHtml = '<div class="text-muted" style="font-size:13px;">No work logs recorded yet.</div>';
  }

  const historyHtml = (r.status_history || []).map(h => `
    <div class="timeline-step">
      <div class="timeline-dot"></div>
      <div class="timeline-content">
        <div style="font-weight:600; font-size:13px;">${escapeHtml(h.OldStatus || 'Created')} ➔ ${escapeHtml(h.NewStatus)}</div>
        <div class="text-muted" style="font-size:11.5px;">${formatISTDate(h.ChangedOn)}</div>
      </div>
    </div>
  `).join('');

  content.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
      <h3 style="font-size:18px; font-weight:700; color:var(--primary);">${ticketNo}</h3>
      <div>${getStatusBadge(r.Status)} ${getPriorityBadge(r.PriorityLabel)}</div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; font-size:13.5px;">
      <div><strong>Requester:</strong> ${escapeHtml(r.RequesterName)} (${escapeHtml(r.RequesterDept)})</div>
      <div><strong>Contact:</strong> ${escapeHtml(r.RequesterEmail)} | ${escapeHtml(r.RequesterPhone || 'N/A')}</div>
      <div><strong>Location:</strong> ${escapeHtml(r.BuildingName)} - ${escapeHtml(r.RoomNo)}</div>
      <div><strong>Category:</strong> ${escapeHtml(r.CategoryName)}</div>
      <div><strong>Created On:</strong> ${formatISTDate(r.RequestDate)}</div>
      <div><strong>SLA Target:</strong> ${formatISTDate(r.SLADueDate)}</div>
    </div>

    <div style="margin-bottom:16px;">
      <strong style="font-size:13.5px;">Description:</strong>
      <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:8px; padding:12px; margin-top:6px; font-size:13.5px;">
        ${escapeHtml(r.Description)}
      </div>
    </div>

    ${r.Rating ? `
      <div style="margin-bottom:16px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:12px;">
        <strong style="color:var(--primary); font-size:13.5px;">Requester Rating:</strong> ⭐ ${r.Rating}/5
        <p style="margin-top:4px; font-size:13px; color:var(--text-secondary);">${escapeHtml(r.FeedbackComments || 'No written comments.')}</p>
      </div>
    ` : ''}

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:20px;">
      <div>
        <strong style="font-size:13.5px;">Work Logs & Material Costs:</strong>
        <div style="margin-top:8px;">${logsHtml}</div>
      </div>
      <div>
        <strong style="font-size:13.5px;">Status History Audit:</strong>
        <div class="timeline-stepper" style="margin-top:8px;">${historyHtml || '<div class="text-muted" style="font-size:12px;">No progression recorded.</div>'}</div>
      </div>
    </div>
  `;

  openModal('admin-details-modal');
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'flex';
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'none';
}
