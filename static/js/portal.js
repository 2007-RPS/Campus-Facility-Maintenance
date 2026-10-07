/**
 * Campus Facility Maintenance Request Management System
 * Student & Staff Requester Portal (portal.js)
 */

let portalMetadata = { categories: [], buildings: [], facilities: [], priorities: [] };
let myRequests = [];
let activeFilter = 'all';

document.addEventListener('DOMContentLoaded', async () => {
  await loadMetadata();
  await loadMyRequests();
  setupEventListeners();
});

async function loadMetadata() {
  const res = await apiFetch('/api/portal/metadata');
  if (res.ok && res.data) {
    portalMetadata = res.data;
    populateDropdowns();
  }
}

function populateDropdowns() {
  const catSelect = document.getElementById('category-select');
  const bldgSelect = document.getElementById('building-select');
  const prioSelect = document.getElementById('priority-select');

  if (catSelect) {
    catSelect.innerHTML = '<option value="">Select Category...</option>' +
      portalMetadata.categories.map(c => `<option value="${c.CategoryID}">${escapeHtml(c.CategoryName)}</option>`).join('');
  }

  if (bldgSelect) {
    bldgSelect.innerHTML = '<option value="">Select Building...</option>' +
      portalMetadata.buildings.map(b => `<option value="${b.BuildingID}">${escapeHtml(b.BuildingName)}</option>`).join('');
  }

  if (prioSelect) {
    prioSelect.innerHTML = portalMetadata.priorities.map(p =>
      `<option value="${p.PriorityID}" ${p.Label === 'Medium' ? 'selected' : ''}>${escapeHtml(p.Label)} (SLA: ${p.SLAHours}h)</option>`
    ).join('');
  }
}

async function loadMyRequests() {
  const tbody = document.getElementById('my-requests-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">Loading your requests...</td></tr>';

  let url = '/api/portal/requests';
  if (activeFilter !== 'all') {
    url += `?status=${encodeURIComponent(activeFilter)}`;
  }

  const res = await apiFetch(url);
  if (res.ok && Array.isArray(res.data)) {
    myRequests = res.data;
    renderRequestsTable();
  } else {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No requests found.</td></tr>';
  }
}

function renderRequestsTable() {
  const tbody = document.getElementById('my-requests-tbody');
  const countBadge = document.getElementById('request-count-badge');
  if (!tbody) return;

  if (countBadge) countBadge.textContent = `${myRequests.length} Requests`;

  if (myRequests.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No requests found. Click "Submit New Request" to create one.</td></tr>';
    return;
  }

  tbody.innerHTML = myRequests.map(r => {
    const ticketNo = escapeHtml(r.ticket_number || `REQ-2026-${String(r.RequestID).padStart(3, '0')}`);
    const dateFormatted = formatISTDate(r.RequestDate);
    const slaFormatted = formatISTDate(r.SLADueDate);
    const category = escapeHtml(r.CategoryName || 'General');
    const location = `${escapeHtml(r.BuildingName || '')} - ${escapeHtml(r.RoomNo || '')}`;
    const desc = escapeHtml(r.Description || '');
    const shortDesc = desc.length > 55 ? desc.substring(0, 55) + '...' : desc;

    let actionsHtml = `<button class="btn btn-secondary btn-sm" onclick="viewRequestDetails(${r.RequestID})">Details</button>`;

    if (['Resolved', 'Closed'].includes(r.Status)) {
      if (r.Rating) {
        actionsHtml += ` <span title="${escapeHtml(r.Comments || '')}" class="text-success" style="font-weight:700; margin-left:6px;">⭐ ${r.Rating}/5</span>`;
      } else {
        actionsHtml += ` <button class="btn btn-primary btn-sm" style="margin-left:6px;" onclick="openRatingModal(${r.RequestID})">Rate</button>`;
      }
    }

    return `
      <tr>
        <td style="font-weight:600; color:var(--primary);">${ticketNo}</td>
        <td>${category}</td>
        <td>${location}</td>
        <td>${getPriorityBadge(r.PriorityLabel)}</td>
        <td>${getStatusBadge(r.Status)}</td>
        <td style="font-size:12.5px;">${dateFormatted}</td>
        <td style="text-align:right;">${actionsHtml}</td>
      </tr>
    `;
  }).join('');
}

function setupEventListeners() {
  // New Request Form Submit
  const newReqForm = document.getElementById('new-request-form');
  if (newReqForm) {
    newReqForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const buildingId = document.getElementById('building-select').value;
      const roomNo = document.getElementById('room-input').value.trim();
      const categoryId = document.getElementById('category-select').value;
      const priorityId = document.getElementById('priority-select').value;
      const description = document.getElementById('desc-input').value.trim();

      if (!buildingId || !categoryId || !priorityId || !description) {
        showToast('Please fill in all required fields.', 'error');
        return;
      }

      const submitBtn = newReqForm.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';
      }

      const res = await apiFetch('/api/portal/requests', {
        method: 'POST',
        body: {
          building_id: buildingId,
          room_no: roomNo || 'General',
          category_id: categoryId,
          priority_id: priorityId,
          description: description
        }
      });

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Request';
      }

      if (res.ok) {
        showToast('Maintenance request submitted successfully!');
        newReqForm.reset();
        closeModal('new-request-modal');
        await loadMyRequests();
      } else {
        showToast(res.data?.error || 'Failed to submit request.', 'error');
      }
    });
  }

  // Filter Buttons
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-pill').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      activeFilter = e.currentTarget.dataset.status || 'all';
      loadMyRequests();
    });
  });

  // Rating Form Submit
  const ratingForm = document.getElementById('rating-form');
  if (ratingForm) {
    ratingForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = ratingForm.dataset.requestId;
      const rating = document.querySelector('input[name="rating_stars"]:checked')?.value;
      const comments = document.getElementById('feedback-comments')?.value.trim();

      if (!rating) {
        showToast('Please select a star rating.', 'error');
        return;
      }

      const res = await apiFetch(`/api/portal/requests/${reqId}/feedback`, {
        method: 'POST',
        body: { rating: parseInt(rating), comments }
      });

      if (res.ok) {
        showToast('Thank you! Feedback recorded.');
        closeModal('rating-modal');
        await loadMyRequests();
      } else {
        showToast(res.data?.error || 'Failed to record feedback.', 'error');
      }
    });
  }
}

async function viewRequestDetails(reqId) {
  const res = await apiFetch(`/api/portal/requests/${reqId}`);
  if (!res.ok) {
    showToast(res.data?.error || 'Failed to load details.', 'error');
    return;
  }

  const r = res.data;
  const content = document.getElementById('req-details-content');
  if (!content) return;

  const ticketNo = escapeHtml(r.ticket_number || `REQ-2026-${String(r.RequestID).padStart(3, '0')}`);
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
      <div><strong>Category:</strong> ${escapeHtml(r.CategoryName)}</div>
      <div><strong>Location:</strong> ${escapeHtml(r.BuildingName)} - ${escapeHtml(r.RoomNo)}</div>
      <div><strong>Submitted On:</strong> ${formatISTDate(r.RequestDate)}</div>
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
        <strong style="color:var(--primary); font-size:13.5px;">Your Feedback:</strong> ⭐ ${r.Rating}/5
        <p style="margin-top:4px; font-size:13px; color:var(--text-secondary);">${escapeHtml(r.FeedbackComments || 'No written comments.')}</p>
      </div>
    ` : ''}

    <div style="margin-top:20px;">
      <strong style="font-size:13.5px;">Status Progression History:</strong>
      <div class="timeline-stepper" style="margin-top:12px;">
        ${historyHtml || '<div class="text-muted" style="font-size:12px;">No progression recorded yet.</div>'}
      </div>
    </div>
  `;

  openModal('req-details-modal');
}

function openRatingModal(reqId) {
  const form = document.getElementById('rating-form');
  if (form) {
    form.dataset.requestId = reqId;
    form.reset();
  }
  openModal('rating-modal');
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'flex';
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.style.display = 'none';
}
