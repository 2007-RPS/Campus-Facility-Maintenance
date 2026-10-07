/**
 * Campus Facility Maintenance Request Management System
 * Maintenance Technician Console (technician.js)
 */

let techJobs = [];
let activeTechFilter = 'all';

document.addEventListener('DOMContentLoaded', async () => {
  await loadTechJobs();
  setupTechEventListeners();
});

async function loadTechJobs() {
  const tbody = document.getElementById('tech-jobs-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Loading assigned jobs...</td></tr>';

  let url = '/api/technician/jobs';
  if (activeTechFilter !== 'all') {
    url += `?status=${encodeURIComponent(activeTechFilter)}`;
  }

  const res = await apiFetch(url);
  if (res.ok && Array.isArray(res.data)) {
    techJobs = res.data;
    renderTechJobsTable();
  } else {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No jobs assigned.</td></tr>';
  }
}

function renderTechJobsTable() {
  const tbody = document.getElementById('tech-jobs-tbody');
  const countBadge = document.getElementById('job-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${techJobs.length} Jobs`;

  if (techJobs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No assigned jobs found under this filter.</td></tr>';
    return;
  }

  tbody.innerHTML = techJobs.map(j => {
    const ticketNo = escapeHtml(j.ticket_number || `REQ-2026-${String(j.RequestID).padStart(3, '0')}`);
    const dateFormatted = formatISTDate(j.RequestDate);
    const category = escapeHtml(j.CategoryName || 'General');
    const location = `${escapeHtml(j.BuildingName || '')} - ${escapeHtml(j.RoomNo || '')}`;
    const requester = `${escapeHtml(j.RequesterName || '')} (${escapeHtml(j.RequesterPhone || 'No Phone')})`;

    let actionsHtml = `<button class="btn btn-secondary btn-sm" onclick="viewJobDetails(${j.RequestID})">View</button>`;

    if (['Assigned', 'In Progress'].includes(j.Status)) {
      actionsHtml += ` <button class="btn btn-primary btn-sm" style="margin-left:4px;" onclick="openWorkLogModal(${j.RequestID})">+ Log Work</button>`;
    }

    if (j.Status === 'In Progress') {
      actionsHtml += ` <button class="btn btn-success btn-sm" style="margin-left:4px;" onclick="resolveJob(${j.RequestID})">✓ Resolve</button>`;
    }

    return `
      <tr>
        <td style="font-weight:600; color:var(--primary);">${ticketNo}</td>
        <td>${category}</td>
        <td>${location}</td>
        <td style="font-size:13px;">${requester}</td>
        <td>${getPriorityBadge(j.PriorityLabel)}</td>
        <td>${getStatusBadge(j.Status)}</td>
        <td style="text-align:right;">${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

function setupTechEventListeners() {
  // Filter pills
  document.querySelectorAll('.tech-filter-pill').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tech-filter-pill').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      activeTechFilter = e.currentTarget.dataset.status || 'all';
      loadTechJobs();
    });
  });

  // Dynamic material row addition
  const addMatBtn = document.getElementById('add-material-row-btn');
  if (addMatBtn) {
    addMatBtn.addEventListener('click', () => {
      const container = document.getElementById('materials-inputs-container');
      if (!container) return;
      const row = document.createElement('div');
      row.className = 'material-input-row';
      row.style.cssText = 'display:grid; grid-template-columns: 2fr 1fr 1fr auto; gap:8px; margin-bottom:8px; align-items:center;';
      row.innerHTML = `
        <input type="text" class="form-input mat-name" placeholder="Item name (e.g. LED Bulb)">
        <input type="number" class="form-input mat-qty" placeholder="Qty" value="1" min="1">
        <input type="number" class="form-input mat-cost" placeholder="Cost in ₹" min="0" step="0.50">
        <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()" style="padding:6px 10px;">✕</button>
      `;
      container.appendChild(row);
    });
  }

  // Work Log Form Submit
  const workLogForm = document.getElementById('work-log-form');
  if (workLogForm) {
    workLogForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = workLogForm.dataset.requestId;
      const description = document.getElementById('work-desc-input').value.trim();

      if (!description) {
        showToast('Work description is required.', 'error');
        return;
      }

      // Collect materials
      const materials = [];
      document.querySelectorAll('.material-input-row').forEach(row => {
        const name = row.querySelector('.mat-name')?.value.trim();
        const qty = parseInt(row.querySelector('.mat-qty')?.value || '1');
        const cost = parseFloat(row.querySelector('.mat-cost')?.value || '0');
        if (name) {
          materials.push({ material_name: name, qty, cost });
        }
      });

      const submitBtn = workLogForm.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';
      }

      const res = await apiFetch(`/api/technician/jobs/${reqId}/work-logs`, {
        method: 'POST',
        body: { work_description: description, materials }
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Save Work Log & Advance to In Progress';
      }

      if (res.ok) {
        showToast('Work log and materials saved successfully!');
        closeModal('work-log-modal');
        await loadTechJobs();
      } else {
        showToast(res.data?.error || 'Failed to record work log.', 'error');
      }
    });
  }
}

async function resolveJob(reqId) {
  if (!confirm(`Are you sure you want to mark maintenance request #${reqId} as Resolved?`)) {
    return;
  }

  const res = await apiFetch(`/api/technician/jobs/${reqId}/resolve`, {
    method: 'POST'
  });

  if (res.ok) {
    showToast('Job marked as Resolved!');
    await loadTechJobs();
  } else {
    showToast(res.data?.error || 'Failed to resolve job.', 'error');
  }
}

async function viewJobDetails(reqId) {
  const res = await apiFetch(`/api/technician/jobs/${reqId}`);
  if (!res.ok) {
    showToast(res.data?.error || 'Failed to load details.', 'error');
    return;
  }

  const j = res.data;
  const content = document.getElementById('tech-details-content');
  if (!content) return;

  const ticketNo = escapeHtml(j.ticket_number || `REQ-2026-${String(j.RequestID).padStart(3, '0')}`);

  let logsHtml = '';
  if (j.work_logs && j.work_logs.length > 0) {
    logsHtml = j.work_logs.map(wl => {
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
              <strong>Materials Used:</strong>
              <ul style="margin:4px 0 0 16px;">${matsList}</ul>
              <div style="text-align:right; font-weight:700; color:var(--primary); margin-top:4px;">Total: ${formatINR(wl.total_cost)}</div>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
  } else {
    logsHtml = '<div class="text-muted" style="font-size:13px;">No work logs submitted yet.</div>';
  }

  content.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
      <h3 style="font-size:18px; font-weight:700; color:var(--primary);">${ticketNo}</h3>
      <div>${getStatusBadge(j.Status)} ${getPriorityBadge(j.PriorityLabel)}</div>
    </div>

    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; font-size:13.5px;">
      <div><strong>Requester:</strong> ${escapeHtml(j.RequesterName)}</div>
      <div><strong>Contact:</strong> ${escapeHtml(j.RequesterPhone || 'N/A')}</div>
      <div><strong>Category:</strong> ${escapeHtml(j.CategoryName)}</div>
      <div><strong>Location:</strong> ${escapeHtml(j.BuildingName)} - ${escapeHtml(j.RoomNo)}</div>
      <div><strong>Requested:</strong> ${formatISTDate(j.RequestDate)}</div>
      <div><strong>SLA Due:</strong> ${formatISTDate(j.SLADueDate)}</div>
    </div>

    <div style="margin-bottom:16px;">
      <strong style="font-size:13.5px;">Issue Description:</strong>
      <div style="background:#f8fafc; border:1px solid var(--border-color); border-radius:8px; padding:12px; margin-top:6px; font-size:13.5px;">
        ${escapeHtml(j.Description)}
      </div>
    </div>

    <div style="margin-top:20px;">
      <strong style="font-size:13.5px;">Work Logs & Materials:</strong>
      <div style="margin-top:10px;">${logsHtml}</div>
    </div>
  `;

  openModal('tech-details-modal');
}

function openWorkLogModal(reqId) {
  const form = document.getElementById('work-log-form');
  if (form) {
    form.dataset.requestId = reqId;
    form.reset();
    const container = document.getElementById('materials-inputs-container');
    if (container) {
      container.innerHTML = `
        <div class="material-input-row" style="display:grid; grid-template-columns: 2fr 1fr 1fr auto; gap:8px; margin-bottom:8px; align-items:center;">
          <input type="text" class="form-input mat-name" placeholder="Item name (e.g. LED Bulb)">
          <input type="number" class="form-input mat-qty" placeholder="Qty" value="1" min="1">
          <input type="number" class="form-input mat-cost" placeholder="Cost in ₹" min="0" step="0.50">
          <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.remove()" style="padding:6px 10px;">✕</button>
        </div>
      `;
    }
  }
  openModal('work-log-modal');
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'flex';
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'none';
}
