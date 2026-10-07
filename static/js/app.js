/**
 * Campus Facility Maintenance Request Management System (Campus FMS)
 * Review 1 Frontend Controller
 * Interacts strictly with normalized MySQL schema, live 5s polling, Chart.js, and DB triggers.
 */

// Application State
const AppState = {
  currentUser: null,
  activeView: 'student', // 'student' | 'admin' | 'technician' | 'management'
  categories: [],
  buildings: [],
  facilities: [],
  priorities: [],
  filters: {
    status: 'All',
    category_id: '',
    priority_id: 'All',
    building_id: '',
    search: ''
  },
  pollingInterval: 5000,
  pollingTimer: null,
  isModalOpen: false,
  charts: {
    category: null,
    priority: null
  }
};

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadMetadata();
  await checkAuth();
  await checkSystemStatus();
  startLivePolling();
});

// =====================================================================
// 1. Initial Data & Metadata Loaders
// =====================================================================
async function loadMetadata() {
  try {
    const [catRes, buildRes, facRes, prioRes] = await Promise.all([
      fetch('/api/categories'),
      fetch('/api/buildings'),
      fetch('/api/facilities'),
      fetch('/api/priorities')
    ]);

    AppState.categories = await catRes.json();
    AppState.buildings = await buildRes.json();
    AppState.facilities = await facRes.json();
    AppState.priorities = await prioRes.json();

    populateMetadataDropdowns();
  } catch (err) {
    console.error('Error loading metadata:', err);
    showToast('Failed to load facility metadata', 'error');
  }
}

function populateMetadataDropdowns() {
  // Categories (Modal & Filter)
  const reqCatSelect = document.getElementById('reqCategory');
  const filterCatSelect = document.getElementById('filterCategory');

  if (reqCatSelect) {
    reqCatSelect.innerHTML = '<option value="">Select Category...</option>' + 
      AppState.categories.map(c => `<option value="${c.CategoryID}">${escapeHtml(c.CategoryName)}</option>`).join('');
  }
  if (filterCatSelect) {
    filterCatSelect.innerHTML = '<option value="">All Categories</option>' + 
      AppState.categories.map(c => `<option value="${c.CategoryID}">${escapeHtml(c.CategoryName)}</option>`).join('');
  }

  // Priorities (Modal & Filter)
  const reqPrioSelect = document.getElementById('reqPriority');
  const filterPrioSelect = document.getElementById('filterPriority');

  if (reqPrioSelect && AppState.priorities.length > 0) {
    reqPrioSelect.innerHTML = AppState.priorities.map(p => 
      `<option value="${p.PriorityID}" ${p.Label === 'Medium' ? 'selected' : ''}>${escapeHtml(p.Label)} (${p.SLAHours}h SLA)</option>`
    ).join('');
  }
  if (filterPrioSelect && AppState.priorities.length > 0) {
    filterPrioSelect.innerHTML = '<option value="All">All Priorities</option>' + 
      AppState.priorities.map(p => `<option value="${p.PriorityID}">${escapeHtml(p.Label)}</option>`).join('');
  }

  // Buildings (Modal & Filter)
  const reqBuildSelect = document.getElementById('reqBuilding');
  const filterBuildSelect = document.getElementById('filterBuilding');

  if (reqBuildSelect) {
    reqBuildSelect.innerHTML = '<option value="">Select Building...</option>' + 
      AppState.buildings.map(b => `<option value="${b.BuildingID}">${escapeHtml(b.BuildingName)}</option>`).join('');
  }
  if (filterBuildSelect) {
    filterBuildSelect.innerHTML = '<option value="">All Buildings</option>' + 
      AppState.buildings.map(b => `<option value="${b.BuildingID}">${escapeHtml(b.BuildingName)}</option>`).join('');
  }
}

async function checkSystemStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const syncLabel = document.getElementById('syncEngineLabel');
    if (syncLabel) {
      syncLabel.textContent = `Polling every 5s • MySQL 8.0 (${data.database})`;
    }
  } catch (err) {
    console.warn('Status check failed:', err);
  }
}

// =====================================================================
// 2. Authentication & User Profile Management
// =====================================================================
async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.authenticated && data.user) {
      AppState.currentUser = data.user;
      updateUserUI(data.user);

      const roleViewMap = {
        'student_staff': 'student',
        'facility_admin': 'admin',
        'technician': 'technician',
        'management': 'management'
      };
      switchView(roleViewMap[data.user.Role] || 'student');
    }
  } catch (err) {
    console.error('Auth verification error:', err);
  }
}

function updateUserUI(user) {
  const avatarEl = document.getElementById('userAvatar');
  const nameEl = document.getElementById('userName');
  const roleBadgeEl = document.getElementById('userRoleBadge');

  if (avatarEl) {
    const initials = user.Name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    avatarEl.textContent = initials;
  }
  if (nameEl) nameEl.textContent = user.Name;
  if (roleBadgeEl) {
    const roleLabels = {
      'student_staff': 'Student / Staff',
      'facility_admin': 'Facility Admin',
      'technician': 'Technician',
      'management': 'Management'
    };
    roleBadgeEl.textContent = roleLabels[user.Role] || user.Role;
  }
}

// =====================================================================
// 3. View Switching
// =====================================================================
function switchView(viewName) {
  AppState.activeView = viewName;

  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  const targetPanel = document.getElementById('view' + capitalize(viewName));
  if (targetPanel) targetPanel.classList.add('active');

  const titleMap = {
    'student': {
      title: 'My Maintenance Requests',
      sub: 'Track facility issues, monitor service updates, and rate completed work',
      label: 'Student / Staff'
    },
    'admin': {
      title: 'Dispatch & Campus Requests',
      sub: 'Review maintenance tickets, assign technicians by skill, and manage lifecycle',
      label: 'Facility Admin'
    },
    'technician': {
      title: 'Assigned Work Orders',
      sub: 'View assigned jobs, record labor hours, log materials/cost, and mark resolved',
      label: 'Technician'
    },
    'management': {
      title: 'Executive Facilities Dashboard',
      sub: 'High-level KPI metrics, SLA compliance, customer ratings, and trigger audit log',
      label: 'Management'
    }
  };

  const info = titleMap[viewName] || titleMap['student'];
  document.getElementById('pageTitle').textContent = info.title;
  document.getElementById('pageSubtitle').textContent = info.sub;
  document.getElementById('currentViewLabel').textContent = info.label;

  fetchActiveViewData();
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// =====================================================================
// 4. Live Polling (5 Seconds)
// =====================================================================
function startLivePolling() {
  if (AppState.pollingTimer) clearInterval(AppState.pollingTimer);

  AppState.pollingTimer = setInterval(async () => {
    if (!AppState.isModalOpen) {
      await fetchActiveViewData(true);
      await updateNavCounts();
    }
  }, AppState.pollingInterval);
}

async function fetchActiveViewData(silent = false) {
  switch (AppState.activeView) {
    case 'student':
      await loadStudentRequests(silent);
      break;
    case 'admin':
      await loadAdminRequests(silent);
      break;
    case 'technician':
      await loadTechnicianJobs(silent);
      break;
    case 'management':
      await loadManagementDashboard(silent);
      break;
  }
}

async function updateNavCounts() {
  try {
    if (AppState.currentUser) {
      const res = await fetch(`/api/requests?user_id=${AppState.currentUser.UserID}`);
      const myReqs = await res.json();
      const badgeMy = document.getElementById('countMyRequests');
      if (badgeMy) badgeMy.textContent = myReqs.length;

      const adminRes = await fetch('/api/requests');
      const allReqs = await adminRes.json();
      const badgeAdmin = document.getElementById('countAdminRequests');
      if (badgeAdmin) badgeAdmin.textContent = allReqs.length;

      if (AppState.currentUser.Role === 'technician') {
        const techRes = await fetch(`/api/requests?tech_user_id=${AppState.currentUser.UserID}`);
        const techReqs = await techRes.json();
        const badgeTech = document.getElementById('countTechJobs');
        if (badgeTech) badgeTech.textContent = techReqs.filter(r => !['Resolved', 'Closed'].includes(r.Status)).length;
      }
    }
  } catch (err) {}
}

// =====================================================================
// 5. Student / Staff View Logic
// =====================================================================
async function loadStudentRequests(silent = false) {
  if (!AppState.currentUser) return;
  try {
    const res = await fetch(`/api/requests?user_id=${AppState.currentUser.UserID}`);
    const requests = await res.json();

    const tbody = document.getElementById('studentRequestsBody');
    if (!tbody) return;

    const total = requests.length;
    const open = requests.filter(r => ['Open', 'Assigned', 'In Progress'].includes(r.Status)).length;
    const resolved = requests.filter(r => ['Resolved', 'Closed'].includes(r.Status)).length;

    document.getElementById('studentTotalCount').textContent = total;
    document.getElementById('studentOpenCount').textContent = open;
    document.getElementById('studentResolvedCount').textContent = resolved;
    document.getElementById('countMyRequests').textContent = total;

    if (requests.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-4 text-muted">
            <i class="bi bi-inbox" style="font-size: 24px; display: block; margin-bottom: 8px;"></i>
            You have not submitted any maintenance requests yet.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = requests.map(r => {
      const reqId = r.RequestID || r.id;
      const ticketLabel = r.ticket_number || (`#REQ-${reqId}`);
      const catName = r.CategoryName || r.category_name || 'General';
      const locStr = `${r.BuildingName || r.building_name || 'Campus'} - ${r.RoomNo || r.room || 'General'}`;
      const prio = r.PriorityLabel || r.priority || 'Medium';
      const status = r.Status || r.status || 'Open';
      const reqDate = r.RequestDate || r.created_at;
      const techName = r.AssignedTechnicians || r.technician_name || '';
      const ratingVal = r.Rating || r.rating;
      const feedbackStr = r.FeedbackComments || r.feedback || r.rating_feedback || '';

      let actionHtml = '';
      if (['Resolved', 'Closed'].includes(status)) {
        if (ratingVal) {
          actionHtml = `<span class="badge badge-light" title="${escapeHtml(feedbackStr)}">
            <i class="bi bi-star-fill text-warning"></i> ${ratingVal}/5 Rated
          </span>`;
        } else {
          actionHtml = `<button class="btn btn-xs btn-primary" onclick="openRatingModal(${reqId}, '${escapeHtml(ticketLabel)}')">
            <i class="bi bi-star"></i> Rate Service
          </button>`;
        }
      } else {
        actionHtml = `<button class="btn btn-xs btn-outline" onclick="openDetailsModal(${reqId})">
          <i class="bi bi-eye"></i> Details
        </button>`;
      }

      return `
        <tr>
          <td><strong class="text-primary">${escapeHtml(ticketLabel)}</strong></td>
          <td>${escapeHtml(catName)}</td>
          <td>${escapeHtml(locStr)}</td>
          <td>${getPriorityBadge(prio)}</td>
          <td>${getStatusBadge(status)}</td>
          <td>${formatDate(reqDate)}</td>
          <td>${techName ? `<strong>${escapeHtml(techName)}</strong>` : '<span class="text-muted">Unassigned</span>'}</td>
          <td>${actionHtml}</td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    if (!silent) console.error('Error fetching student requests:', err);
  }
}

// =====================================================================
// 6. Facility Admin View Logic
// =====================================================================
async function loadAdminRequests(silent = false) {
  try {
    const params = new URLSearchParams();
    if (AppState.filters.status && AppState.filters.status !== 'All') {
      params.append('status', AppState.filters.status);
    }
    if (AppState.filters.category_id) {
      params.append('category_id', AppState.filters.category_id);
    }
    if (AppState.filters.priority_id && AppState.filters.priority_id !== 'All') {
      params.append('priority_id', AppState.filters.priority_id);
    }
    if (AppState.filters.building_id) {
      params.append('building_id', AppState.filters.building_id);
    }
    if (AppState.filters.search) {
      params.append('search', AppState.filters.search);
    }

    const res = await fetch(`/api/requests?${params.toString()}`);
    const requests = await res.json();

    const tbody = document.getElementById('adminRequestsBody');
    const badge = document.getElementById('adminTotalBadge');
    if (badge) badge.textContent = `${requests.length} tickets`;
    if (!tbody) return;

    if (requests.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" class="text-center py-4 text-muted">
            No maintenance requests match the selected filters.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = requests.map(r => {
      const reqId = r.RequestID || r.id;
      const catId = r.CategoryID || r.category_id || 1;
      const ticketLabel = r.ticket_number || (`#REQ-${reqId}`);
      const reqName = r.RequesterName || r.requester_name || 'Requester';
      const reqPhone = r.RequesterPhone || r.requester_phone || '';
      const catName = r.CategoryName || r.category_name || 'General';
      const locStr = `${r.BuildingName || r.building_name || 'Campus'} - ${r.RoomNo || r.room || 'General'}`;
      const prio = r.PriorityLabel || r.priority || 'Medium';
      const status = r.Status || r.status || 'Open';
      const techName = r.AssignedTechnicians || r.technician_name || '';
      const slaDue = r.SLADueDate || r.sla_due_at;

      return `
        <tr>
          <td>
            <a href="javascript:void(0)" onclick="openDetailsModal(${reqId})" style="text-decoration:none;">
              <strong>${escapeHtml(ticketLabel)}</strong>
            </a>
          </td>
          <td>
            <div>${escapeHtml(reqName)}</div>
            <small class="text-muted">${escapeHtml(reqPhone)}</small>
          </td>
          <td>${escapeHtml(catName)}</td>
          <td>${escapeHtml(locStr)}</td>
          <td>${getPriorityBadge(prio)}</td>
          <td>${getStatusBadge(status)}</td>
          <td>
            ${techName ? `<strong>${escapeHtml(techName)}</strong>` : '<span class="text-muted">Unassigned</span>'}
          </td>
          <td>
            <small class="${isSlaBreached(r) ? 'text-danger font-weight-bold' : 'text-muted'}">
              ${slaDue ? formatDate(slaDue) : 'N/A'}
            </small>
          </td>
          <td>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-xs btn-primary" title="Assign Technician" onclick="openAssignModal(${reqId}, ${catId}, '${escapeHtml(ticketLabel)}', '${escapeHtml(catName)}')">
                <i class="bi bi-person-plus"></i> Assign
              </button>
              <button class="btn btn-xs btn-outline" title="Change Status" onclick="openChangeStatusModal(${reqId}, '${escapeHtml(status)}')">
                <i class="bi bi-arrow-repeat"></i> Status
              </button>
              <button class="btn btn-xs btn-ghost" title="View Details" onclick="openDetailsModal(${reqId})">
                <i class="bi bi-eye"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    if (!silent) console.error('Error fetching admin requests:', err);
  }
}

// =====================================================================
// 7. Technician View Logic
// =====================================================================
async function loadTechnicianJobs(silent = false) {
  if (!AppState.currentUser) return;
  try {
    const isTech = AppState.currentUser.Role === 'technician';
    const url = isTech ? `/api/requests?tech_user_id=${AppState.currentUser.UserID}` : '/api/requests';

    const res = await fetch(url);
    const jobs = await res.json();

    const tbody = document.getElementById('techJobsBody');
    if (!tbody) return;

    const assigned = jobs.filter(j => j.Status === 'Assigned').length;
    const inProgress = jobs.filter(j => j.Status === 'In Progress').length;
    const resolved = jobs.filter(j => ['Resolved', 'Closed'].includes(j.Status)).length;

    document.getElementById('techAssignedCount').textContent = assigned;
    document.getElementById('techInProgressCount').textContent = inProgress;
    document.getElementById('techResolvedCount').textContent = resolved;

    if (jobs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-4 text-muted">
            <i class="bi bi-check2-circle" style="font-size: 24px; display: block; margin-bottom: 8px;"></i>
            No active jobs currently assigned.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = jobs.map(j => {
      const jId = j.RequestID || j.id;
      const ticketLabel = j.ticket_number || (`#REQ-${jId}`);
      const catName = j.CategoryName || j.category_name || 'General';
      const locStr = `${j.BuildingName || j.building_name || 'Campus'} - ${j.RoomNo || j.room || 'General'}`;
      const prio = j.PriorityLabel || j.priority || 'Medium';
      const status = j.Status || j.status || 'Open';
      const desc = j.Description || j.description || '';
      const reqName = j.RequesterName || j.requester_name || 'Requester';
      const reqPhone = j.RequesterPhone || j.requester_phone || '';
      const roomStr = j.RoomNo || j.room || 'General';

      return `
        <tr>
          <td><strong class="text-primary">${escapeHtml(ticketLabel)}</strong></td>
          <td>${escapeHtml(catName)}</td>
          <td>${escapeHtml(locStr)}</td>
          <td>${getPriorityBadge(prio)}</td>
          <td>${getStatusBadge(status)}</td>
          <td style="max-width: 220px;" class="text-truncate">${escapeHtml(desc)}</td>
          <td>
            <div>${escapeHtml(reqName)}</div>
            <small class="text-muted">${escapeHtml(reqPhone)}</small>
          </td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-xs btn-primary" title="Add Work Log & Materials" onclick="openWorkLogModal(${jId}, '${escapeHtml(ticketLabel)}', '${escapeHtml(roomStr)}')">
                <i class="bi bi-journal-plus"></i> Work Log
              </button>
              ${!['Resolved', 'Closed'].includes(status) ? `
                <button class="btn btn-xs btn-outline" style="color: var(--primary); border-color: var(--primary);" title="Mark Resolved" onclick="markJobResolved(${jId})">
                  <i class="bi bi-check-lg"></i> Resolve
                </button>
              ` : `
                <button class="btn btn-xs btn-ghost" onclick="openDetailsModal(${jId})">
                  <i class="bi bi-eye"></i> Details
                </button>
              `}
            </div>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    if (!silent) console.error('Error loading technician jobs:', err);
  }
}

// =====================================================================
// 8. Management Dashboard & Analytics Logic
// =====================================================================
async function loadManagementDashboard(silent = false) {
  try {
    const res = await fetch('/api/analytics/dashboard');
    const data = await res.json();

    document.getElementById('mgmtTotalReq').textContent = data.total_requests;
    document.getElementById('mgmtOpenReq').textContent = data.open_requests;
    document.getElementById('mgmtResolvedReq').textContent = data.resolved_requests;
    document.getElementById('mgmtSlaPct').textContent = `${data.sla_compliance_rate}%`;
    document.getElementById('mgmtAvgRating').textContent = `${data.average_rating} / 5`;
    document.getElementById('mgmtRatingCount').textContent = `${data.ratings_count} review${data.ratings_count === 1 ? '' : 's'}`;
    document.getElementById('mgmtTotalCost').textContent = formatCurrency(data.total_materials_cost);

    renderCategoryChart(data.requests_by_category);
    renderPriorityChart(data.requests_by_priority);
    renderStatusHistoryTimeline(data.recent_timeline);

  } catch (err) {
    if (!silent) console.error('Error fetching management analytics:', err);
  }
}

function renderCategoryChart(catData) {
  const canvas = document.getElementById('categoryChart');
  if (!canvas) return;

  const labels = catData.map(c => c.CategoryName);
  const values = catData.map(c => c.count);

  const colors = ['#16a34a', '#059669', '#0284c7', '#f59e0b', '#8b5cf6', '#e11d48'];

  if (AppState.charts.category) {
    AppState.charts.category.data.labels = labels;
    AppState.charts.category.data.datasets[0].data = values;
    AppState.charts.category.update('none');
    return;
  }

  AppState.charts.category = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            boxWidth: 12,
            font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' }
          }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = catData[context.dataIndex] || {};
              const count = context.parsed || 0;
              const cost = Number(item.total_category_cost || 0);
              return ` ${context.label}: ${count} tickets • Total Spend: ${formatCurrency(cost)}`;
            }
          }
        }
      },
      cutout: '65%'
    }
  });
}

function renderPriorityChart(prioData) {
  const canvas = document.getElementById('priorityChart');
  if (!canvas) return;

  const labels = prioData.map(p => p.Label);
  const values = prioData.map(p => p.count);
  const colors = ['#64748b', '#0284c7', '#ea580c', '#e11d48'];

  if (AppState.charts.priority) {
    AppState.charts.priority.data.labels = labels;
    AppState.charts.priority.data.datasets[0].data = values;
    AppState.charts.priority.update('none');
    return;
  }

  AppState.charts.priority = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Tickets',
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: { stepSize: 1 }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderStatusHistoryTimeline(timelineItems) {
  const container = document.getElementById('statusHistoryTimeline');
  if (!container) return;

  if (!timelineItems || timelineItems.length === 0) {
    container.innerHTML = '<div class="text-center py-4 text-muted">No recent status transitions logged yet.</div>';
    return;
  }

  container.innerHTML = timelineItems.map(item => {
    return `
      <div class="timeline-item">
        <span class="timeline-node"></span>
        <div class="timeline-header">
          <span class="timeline-ticket">#REQ-${item.RequestID}</span>
          <span class="timeline-transition">
            ${item.OldStatus ? getStatusBadge(item.OldStatus) + ' ➔ ' : ''}
            ${getStatusBadge(item.NewStatus)}
          </span>
          <span class="timeline-meta ms-auto">${formatDate(item.ChangedOn)}</span>
        </div>
        <div class="timeline-notes">
          <i class="bi bi-info-circle"></i> 
          ${escapeHtml(item.CategoryName)} in ${escapeHtml(item.BuildingName)} (${escapeHtml(item.RoomNo)})
          • <em>MySQL Trigger Audit</em>
        </div>
      </div>
    `;
  }).join('');
}

// =====================================================================
// 9. Modals & Actions
// =====================================================================
function openNewRequestModal() {
  const modal = document.getElementById('modalNewRequest');
  const form = document.getElementById('formNewRequest');
  if (form) form.reset();
  openModal(modal);
}

// Assign Technician Modal (Matching Skill Only)
async function openAssignModal(reqId, categoryId, ticketLabel, categoryName) {
  document.getElementById('assignRequestId').value = reqId;
  const summaryEl = document.getElementById('assignTicketSummary');
  summaryEl.innerHTML = `
    <strong>Ticket:</strong> ${escapeHtml(ticketLabel)} 
    <span class="badge badge-light ms-2">Category: ${escapeHtml(categoryName)}</span>
  `;

  const select = document.getElementById('assignTechSelect');
  select.innerHTML = '<option value="">Loading qualified technicians...</option>';

  openModal(document.getElementById('modalAssignTech'));

  try {
    const res = await fetch(`/api/technicians/available?category_id=${categoryId}`);
    const techs = await res.json();

    if (techs.length === 0) {
      select.innerHTML = '<option value="">No available technicians with matching skill</option>';
      return;
    }

    select.innerHTML = '<option value="">Select Technician...</option>' + 
      techs.map(t => {
        const tid = t.TechID || t.tech_id || t.id;
        const tname = t.Name || t.name;
        const tskill = t.Skill || t.skill;
        const ajobs = t.active_jobs !== undefined ? t.active_jobs : 0;
        return `<option value="${tid}">${escapeHtml(tname)} (${escapeHtml(tskill)}) - ${ajobs} active job${ajobs === 1 ? '' : 's'}</option>`;
      }).join('');

  } catch (err) {
    console.error('Error fetching technicians:', err);
    select.innerHTML = '<option value="">Failed to load technicians</option>';
  }
}

const VALID_STATUS_TRANSITIONS = {
  'Open': ['Assigned'],
  'Assigned': ['In Progress'],
  'In Progress': ['Resolved'],
  'Resolved': ['Closed'],
  'Closed': []
};

function openChangeStatusModal(reqId, currentStatus) {
  document.getElementById('statusRequestId').value = reqId;
  const select = document.getElementById('selectNewStatus');
  const allowed = VALID_STATUS_TRANSITIONS[currentStatus] || [];
  if (select) {
    if (allowed.length === 0) {
      select.innerHTML = '<option value="">Closed (Terminal State)</option>';
      select.disabled = true;
    } else {
      select.disabled = false;
      select.innerHTML = allowed.map(st => `<option value="${st}">${st}</option>`).join('');
      select.value = allowed[0];
    }
  }
  openModal(document.getElementById('modalChangeStatus'));
}

function openWorkLogModal(reqId, ticketLabel, room) {
  document.getElementById('workLogRequestId').value = reqId;
  document.getElementById('workLogTicketSummary').innerHTML = `
    <strong>Ticket:</strong> ${escapeHtml(ticketLabel)} • <strong>Location:</strong> ${escapeHtml(room)}
  `;
  const form = document.getElementById('formWorkLog');
  if (form) form.reset();
  openModal(document.getElementById('modalWorkLog'));
}

function openRatingModal(reqId, ticketLabel) {
  document.getElementById('ratingRequestId').value = reqId;
  document.getElementById('ratingScoreInput').value = 5;
  setStarDisplay(5);
  openModal(document.getElementById('modalRating'));
}

// Request Details Modal
async function openDetailsModal(reqId) {
  const modal = document.getElementById('modalDetails');
  const body = document.getElementById('detailsModalBody');
  body.innerHTML = '<div class="text-center py-4">Loading request details...</div>';
  openModal(modal);

  try {
    const res = await fetch(`/api/requests/${reqId}`);
    const data = await res.json();

    document.getElementById('detailsTicketTitle').textContent = `Request #REQ-${data.RequestID} Details & Audit`;

    body.innerHTML = `
      <div class="ticket-summary-pill mb-3" style="display:flex; justify-content:space-between; flex-wrap:wrap;">
        <div>
          <span style="font-size: 16px; font-weight:800; color:var(--primary);">#REQ-${data.RequestID}</span>
          <span class="ms-2">${getStatusBadge(data.Status)}</span>
          <span class="ms-2">${getPriorityBadge(data.PriorityLabel)}</span>
        </div>
        <div>
          <span class="text-muted">Submitted:</span> ${formatDate(data.RequestDate)}
        </div>
      </div>

      <div class="row" style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:16px;">
        <div style="background:#f8fafc; padding:12px; border-radius:10px;">
          <h5 style="font-size:12px; text-transform:uppercase; color:var(--text-muted); margin-bottom:4px;">Requester</h5>
          <strong>${escapeHtml(data.RequesterName)}</strong><br>
          <small class="text-muted">${escapeHtml(data.RequesterEmail)} • ${escapeHtml(data.RequesterPhone || '')} (${escapeHtml(data.RequesterDept || '')})</small>
        </div>
        <div style="background:#f8fafc; padding:12px; border-radius:10px;">
          <h5 style="font-size:12px; text-transform:uppercase; color:var(--text-muted); margin-bottom:4px;">Location & Category</h5>
          <strong>${escapeHtml(data.BuildingName)}</strong> - Room ${escapeHtml(data.RoomNo)} (${escapeHtml(data.FacilityType || 'General')})<br>
          <small class="text-muted">Category: ${escapeHtml(data.CategoryName)} • SLA: ${data.SLAHours}h</small>
        </div>
      </div>

      <div class="form-group">
        <label>Issue Description</label>
        <div style="background:#ffffff; border:1px solid #e2e8f0; padding:10px 14px; border-radius:8px;">
          ${escapeHtml(data.Description)}
        </div>
      </div>

      <!-- Assignments -->
      <h4 style="font-size:14px; font-weight:700; margin: 18px 0 8px;">
        <i class="bi bi-people-fill text-primary"></i> Assigned Technicians
      </h4>
      ${data.assignments && data.assignments.length > 0 ? `
        <div style="display:flex; flex-wrap:wrap; gap:8px;">
          ${data.assignments.map(a => `
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; padding:8px 12px; font-size:13px;">
              <strong>${escapeHtml(a.TechnicianName)}</strong> (${escapeHtml(a.Skill)})<br>
              <small class="text-muted">Assigned: ${formatDate(a.AssignedOn)} • ${escapeHtml(a.TechnicianPhone || '')}</small>
            </div>
          `).join('')}
        </div>
      ` : '<p class="text-muted" style="font-size:13px;">No technicians assigned yet.</p>'}

      <!-- Work Logs & Materials -->
      <h4 style="font-size:14px; font-weight:700; margin: 20px 0 8px;">
        <i class="bi bi-tools text-primary"></i> Work Logs & Materials Consumed
      </h4>
      ${data.work_logs && data.work_logs.length > 0 ? `
        <div style="display:flex; flex-direction:column; gap:10px;">
          ${data.work_logs.map(log => `
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 14px;">
              <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <strong>${escapeHtml(log.TechnicianName)} (${escapeHtml(log.Skill)})</strong>
                <span class="text-muted" style="font-size:11.5px;">${formatDate(log.WorkDate)}</span>
              </div>
              <p style="font-size:13px; margin-bottom:6px;">${escapeHtml(log.WorkDescription)}</p>
              ${log.materials && log.materials.length > 0 ? `
                <div style="background:white; border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; margin-top:6px;">
                  <strong style="font-size:12px; color:var(--text-secondary);">Materials:</strong>
                  <ul style="padding-left:18px; font-size:12px; margin:4px 0 0;">
                    ${log.materials.map(m => `
                      <li>${escapeHtml(m.MaterialName)} × ${m.Qty} @ ${formatCurrency(m.Cost)} = <strong>${formatCurrency(m.TotalCost)}</strong></li>
                    `).join('')}
                  </ul>
                  <div style="font-size:12px; text-align:right; font-weight:700; color:var(--primary); margin-top:4px;">
                    Total Materials Cost: ${formatCurrency(log.total_cost)}
                  </div>
                </div>
              ` : ''}
            </div>
          `).join('')}
        </div>
      ` : '<p class="text-muted" style="font-size:13px;">No work logs recorded yet.</p>'}

      <!-- Status History (Triggered) -->
      <h4 style="font-size:14px; font-weight:700; margin: 20px 0 8px;">
        <i class="bi bi-clock-history text-primary"></i> Status History Audit Trail (MySQL Trigger)
      </h4>
      <div class="timeline-container" style="padding-left:20px;">
        ${data.status_history && data.status_history.length > 0 ? data.status_history.map(h => `
          <div class="timeline-item">
            <span class="timeline-node"></span>
            <div class="timeline-header">
              <span>${h.OldStatus ? getStatusBadge(h.OldStatus) + ' ➔ ' : ''}${getStatusBadge(h.NewStatus)}</span>
              <span class="timeline-meta ms-auto">${formatDate(h.ChangedOn)}</span>
            </div>
          </div>
        `).join('') : '<p class="text-muted">No history transitions found.</p>'}
      </div>

      <!-- Feedback -->
      ${data.Rating ? `
        <div style="margin-top:20px; background:#fef9c3; border:1px solid #fde047; padding:12px; border-radius:10px;">
          <h5 style="color:#854d0e; font-size:13px; font-weight:700; margin-bottom:4px;">
            <i class="bi bi-star-fill"></i> Requester Feedback: ${data.Rating} / 5 Stars
          </h5>
          <p style="font-size:13px; color:#713f12; margin:0;">"${escapeHtml(data.FeedbackComments || 'No written feedback.')}"</p>
        </div>
      ` : ''}
    `;

  } catch (err) {
    console.error('Error fetching request details:', err);
    body.innerHTML = '<div class="text-danger text-center py-4">Failed to load request details.</div>';
  }
}

// Demo User Switcher Modal
async function openUserSwitcherModal() {
  const modal = document.getElementById('modalUserSwitcher');
  const list = document.getElementById('demoUserList');
  list.innerHTML = '<div class="text-center py-3">Loading demo accounts...</div>';
  openModal(modal);

  try {
    const res = await fetch('/api/auth/demo-users');
    const users = await res.json();

    const roleBadges = {
      'student_staff': '<span class="badge badge-primary">Student/Staff</span>',
      'facility_admin': '<span class="badge badge-status-assigned">Facility Admin</span>',
      'technician': '<span class="badge badge-status-inprogress">Technician</span>',
      'management': '<span class="badge badge-status-resolved">Management</span>'
    };

    list.innerHTML = users.map(u => {
      const uId = u.UserID || u.id;
      const uName = u.Name || u.name;
      const uEmail = u.Email || u.email;
      const uRole = u.Role || u.role;
      const uDept = u.Dept || u.dept;
      const isCurrent = AppState.currentUser && (AppState.currentUser.UserID === uId || AppState.currentUser.id === uId);
      return `
        <div class="user-switch-item ${isCurrent ? 'active' : ''}" onclick="switchDemoUser(${uId})">
          <div>
            <strong>${escapeHtml(uName)}</strong>
            <div style="font-size: 12px; color: var(--text-muted);">${escapeHtml(uEmail)}${uDept ? ` (${escapeHtml(uDept)})` : ''}</div>
          </div>
          <div>
            ${roleBadges[uRole] || uRole}
            ${isCurrent ? '<i class="bi bi-check2 text-success ms-2" style="font-size: 18px;"></i>' : ''}
          </div>
        </div>
      `;
    }).join('');

  } catch (err) {
    console.error('Error loading demo users:', err);
  }
}

async function switchDemoUser(userId) {
  try {
    const res = await fetch('/api/auth/switch-user', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });
    const data = await res.json();
    if (res.ok) {
      AppState.currentUser = data.user;
      updateUserUI(data.user);
      closeAllModals();
      showToast(`Switched user to ${data.user.Name}`);

      const roleViewMap = {
        'student_staff': 'student',
        'facility_admin': 'admin',
        'technician': 'technician',
        'management': 'management'
      };
      switchView(roleViewMap[data.user.Role] || 'student');
    }
  } catch (err) {
    showToast('Failed to switch user', 'error');
  }
}

async function markJobResolved(reqId) {
  if (!confirm('Mark this maintenance request as Resolved?')) return;
  try {
    const res = await fetch(`/api/requests/${reqId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Resolved' })
    });
    if (res.ok) {
      showToast('Maintenance request marked as Resolved!');
      fetchActiveViewData();
    } else {
      const err = await res.json();
      showToast(err.error || 'Failed to update status', 'error');
    }
  } catch (err) {
    showToast('Network error while marking resolved', 'error');
  }
}

// =====================================================================
// 10. Event Listeners Setup
// =====================================================================
function setupEventListeners() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      if (view) switchView(view);
    });
  });

  const btnOpenNew = document.getElementById('btnOpenNewRequestModal');
  const btnStudentNew = document.getElementById('btnStudentNewReq');
  if (btnOpenNew) btnOpenNew.addEventListener('click', openNewRequestModal);
  if (btnStudentNew) btnStudentNew.addEventListener('click', openNewRequestModal);

  const btnUserModal = document.getElementById('btnOpenUserModal');
  const btnQuickDemo = document.getElementById('btnQuickDemo');
  if (btnUserModal) btnUserModal.addEventListener('click', openUserSwitcherModal);
  if (btnQuickDemo) btnQuickDemo.addEventListener('click', openUserSwitcherModal);

  const btnRefresh = document.getElementById('btnManualRefresh');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      btnRefresh.innerHTML = '<i class="bi bi-arrow-repeat spin"></i> Syncing...';
      await fetchActiveViewData();
      await updateNavCounts();
      setTimeout(() => {
        btnRefresh.innerHTML = '<i class="bi bi-arrow-repeat"></i> Sync';
      }, 500);
      showToast('Synced latest data');
    });
  }

  const btnLogout = document.getElementById('btnLogout');
  if (btnLogout) {
    btnLogout.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      showToast('Logged out. Reconnecting demo session...');
      checkAuth();
    });
  }

  // Filters
  const filterStatus = document.getElementById('filterStatus');
  const filterCat = document.getElementById('filterCategory');
  const filterPrio = document.getElementById('filterPriority');
  const filterBuild = document.getElementById('filterBuilding');
  const filterSearch = document.getElementById('filterSearch');
  const btnClearFilters = document.getElementById('btnClearFilters');

  const onFilterChange = () => {
    AppState.filters.status = filterStatus ? filterStatus.value : 'All';
    AppState.filters.category_id = filterCat ? filterCat.value : '';
    AppState.filters.priority_id = filterPrio ? filterPrio.value : 'All';
    AppState.filters.building_id = filterBuild ? filterBuild.value : '';
    AppState.filters.search = filterSearch ? filterSearch.value : '';
    loadAdminRequests();
  };

  if (filterStatus) filterStatus.addEventListener('change', onFilterChange);
  if (filterCat) filterCat.addEventListener('change', onFilterChange);
  if (filterPrio) filterPrio.addEventListener('change', onFilterChange);
  if (filterBuild) filterBuild.addEventListener('change', onFilterChange);
  if (filterSearch) filterSearch.addEventListener('input', debounce(onFilterChange, 300));

  if (btnClearFilters) {
    btnClearFilters.addEventListener('click', () => {
      if (filterStatus) filterStatus.value = 'All';
      if (filterCat) filterCat.value = '';
      if (filterPrio) filterPrio.value = 'All';
      if (filterBuild) filterBuild.value = '';
      if (filterSearch) filterSearch.value = '';
      onFilterChange();
    });
  }

  // Modal Close buttons
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', closeAllModals);
  });

  document.querySelectorAll('.modal-backdrop').forEach(bd => {
    bd.addEventListener('click', (e) => {
      if (e.target === bd) closeAllModals();
    });
  });

  // Star Rating Picker
  const starBtns = document.querySelectorAll('.star-btn');
  starBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const val = parseInt(btn.dataset.value);
      document.getElementById('ratingScoreInput').value = val;
      setStarDisplay(val);
    });
    btn.addEventListener('mouseenter', () => {
      const val = parseInt(btn.dataset.value);
      setStarDisplay(val, true);
    });
  });

  const starPicker = document.getElementById('starRatingPicker');
  if (starPicker) {
    starPicker.addEventListener('mouseleave', () => {
      const cur = parseInt(document.getElementById('ratingScoreInput').value || 5);
      setStarDisplay(cur);
    });
  }

  setupFormSubmissions();
}

function setupFormSubmissions() {
  // 1. Submit Request Form
  const formNewReq = document.getElementById('formNewRequest');
  if (formNewReq) {
    formNewReq.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        category_id: document.getElementById('reqCategory').value,
        building_id: document.getElementById('reqBuilding').value,
        room_no: document.getElementById('reqRoom').value,
        priority_id: document.getElementById('reqPriority').value,
        description: document.getElementById('reqDescription').value
      };

      try {
        const res = await fetch('/api/requests', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          closeAllModals();
          showToast(`Request submitted! Ticket #REQ-${data.request_id}`);
          fetchActiveViewData();
        } else {
          showToast(data.error || 'Submission failed', 'error');
        }
      } catch (err) {
        showToast('Network error on submission', 'error');
      }
    });
  }

  // 2. Assign Tech Form
  const formAssign = document.getElementById('formAssignTech');
  if (formAssign) {
    formAssign.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = document.getElementById('assignRequestId').value;
      const techId = document.getElementById('assignTechSelect').value;

      if (!techId) {
        showToast('Please select an available technician', 'error');
        return;
      }

      try {
        const res = await fetch(`/api/requests/${reqId}/assign`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            TechID: parseInt(techId, 10),
            tech_id: parseInt(techId, 10)
          })
        });
        const data = await res.json();
        if (res.ok) {
          closeAllModals();
          showToast('Technician assigned successfully!');
          fetchActiveViewData();
        } else {
          showToast(data.error || 'Failed to assign technician', 'error');
        }
      } catch (err) {
        showToast('Network error while assigning technician', 'error');
      }
    });
  }

  // 3. Update Status Form
  const formStatus = document.getElementById('formChangeStatus');
  if (formStatus) {
    formStatus.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = document.getElementById('statusRequestId').value;
      const newStatus = document.getElementById('selectNewStatus').value;

      try {
        const res = await fetch(`/api/requests/${reqId}/status`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (res.ok) {
          closeAllModals();
          showToast(`Status updated to ${newStatus}`);
          fetchActiveViewData();
        } else {
          showToast(data.error || 'Status update failed', 'error');
        }
      } catch (err) {
        showToast('Network error on status update', 'error');
      }
    });
  }

  // 4. Add Work Log + Materials Form
  const formWork = document.getElementById('formWorkLog');
  if (formWork) {
    formWork.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = document.getElementById('workLogRequestId').value;
      const payload = {
        work_description: document.getElementById('workDescription').value,
        material_name: document.getElementById('workMatName').value,
        qty: parseInt(document.getElementById('workMatQty').value || 1),
        cost: parseFloat(document.getElementById('workMatCost').value || 0.0)
      };

      try {
        const res = await fetch(`/api/requests/${reqId}/work-logs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          closeAllModals();
          showToast('Work log and materials saved successfully!');
          fetchActiveViewData();
        } else {
          showToast(data.error || 'Failed to save work log', 'error');
        }
      } catch (err) {
        showToast('Network error saving work log', 'error');
      }
    });
  }

  // 5. Submit Rating / Feedback Form
  const formRating = document.getElementById('formRating');
  if (formRating) {
    formRating.addEventListener('submit', async (e) => {
      e.preventDefault();
      const reqId = document.getElementById('ratingRequestId').value;
      const rating = parseInt(document.getElementById('ratingScoreInput').value || 5);
      const comments = document.getElementById('ratingFeedback').value;

      try {
        const res = await fetch(`/api/requests/${reqId}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rating, comments })
        });
        const data = await res.json();
        if (res.ok) {
          closeAllModals();
          showToast('Thank you for rating the service!');
          fetchActiveViewData();
        } else {
          showToast(data.error || 'Failed to submit rating', 'error');
        }
      } catch (err) {
        showToast('Network error submitting rating', 'error');
      }
    });
  }
}

// =====================================================================
// 11. Helper Functions
// =====================================================================
function openModal(modalEl) {
  if (!modalEl) return;
  modalEl.classList.add('active');
  AppState.isModalOpen = true;
}

function closeAllModals() {
  document.querySelectorAll('.modal-backdrop').forEach(m => m.classList.remove('active'));
  AppState.isModalOpen = false;
}

function setStarDisplay(score, isHover = false) {
  const stars = document.querySelectorAll('.star-btn');
  const labels = ['', '1 - Poor', '2 - Fair', '3 - Average', '4 - Very Good', '5 - Excellent Service'];

  stars.forEach(s => {
    const val = parseInt(s.dataset.value);
    if (val <= score) {
      s.classList.add('active');
      s.classList.replace('bi-star', 'bi-star-fill');
    } else {
      s.classList.remove('active');
      s.classList.replace('bi-star-fill', 'bi-star');
    }
  });

  const labelEl = document.getElementById('ratingLabelDisplay');
  if (labelEl) labelEl.textContent = labels[score] || '';
}

function getStatusBadge(status) {
  const map = {
    'Open': { class: 'badge-status-open', icon: 'bi-inbox-fill' },
    'Assigned': { class: 'badge-status-assigned', icon: 'bi-person-check-fill' },
    'In Progress': { class: 'badge-status-inprogress', icon: 'bi-gear-wide-connected' },
    'Resolved': { class: 'badge-status-resolved', icon: 'bi-patch-check-fill' },
    'Closed': { class: 'badge-status-closed', icon: 'bi-check-all' }
  };
  const item = map[status] || { class: 'badge-light', icon: 'bi-circle' };
  return `<span class="badge ${item.class}"><i class="bi ${item.icon}"></i> ${escapeHtml(status)}</span>`;
}

function getPriorityBadge(priority) {
  const map = {
    'Urgent': 'badge-prio-urgent',
    'High': 'badge-prio-high',
    'Medium': 'badge-prio-medium',
    'Low': 'badge-prio-low'
  };
  return `<span class="badge ${map[priority] || 'badge-light'}">${escapeHtml(priority)}</span>`;
}

function isSlaBreached(request) {
  if (['Resolved', 'Closed'].includes(request.Status)) return false;
  return request.SLADueDate && (new Date() > new Date(request.SLADueDate));
}

function formatCurrency(amount) {
  const val = Number(amount) || 0;
  return '₹' + val.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatDate(dateStr, includeTime = true) {
  if (!dateStr) return 'N/A';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return String(dateStr);

    const parts = new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    }).formatToParts(d);

    let day = '', month = '', year = '', hour = '', minute = '', dayPeriod = '';
    for (const p of parts) {
      if (p.type === 'day') day = p.value;
      if (p.type === 'month') month = p.value;
      if (p.type === 'year') year = p.value;
      if (p.type === 'hour') hour = p.value;
      if (p.type === 'minute') minute = p.value;
      if (p.type === 'dayPeriod') dayPeriod = p.value.toUpperCase();
    }

    const dateFormatted = `${day}-${month}-${year}`;
    if (!includeTime) {
      return dateFormatted;
    }
    return `${dateFormatted} ${hour}:${minute} ${dayPeriod} IST`;
  } catch (e) {
    return String(dateStr);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'error' : ''}`;
  const icon = type === 'error' ? 'bi-exclamation-circle-fill text-danger' : 'bi-check-circle-fill text-primary';
  toast.innerHTML = `<i class="bi ${icon}" style="font-size:18px;"></i> <span>${escapeHtml(message)}</span>`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease-out';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
