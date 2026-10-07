/**
 * Campus Facility Maintenance Request Management System
 * Executive Management Console (management.js)
 * STRICTLY READ-ONLY!
 */

let categoryChartInstance = null;
let priorityChartInstance = null;
let mgmtTab = 'overview'; // 'overview', 'audit'

document.addEventListener('DOMContentLoaded', async () => {
  await loadManagementDashboard();
  setupMgmtNavigation();
});

function setupMgmtNavigation() {
  document.querySelectorAll('.mgmt-nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.mgmt-nav-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');

      const targetTab = item.dataset.tab;
      mgmtTab = targetTab;

      document.querySelectorAll('.mgmt-view-panel').forEach(p => p.style.display = 'none');
      const targetPanel = document.getElementById(`mgmt-panel-${targetTab}`);
      if (targetPanel) targetPanel.style.display = 'block';

      if (targetTab === 'overview') loadManagementDashboard();
      else if (targetTab === 'audit') loadManagementAuditLogs();
    });
  });
}

async function loadManagementDashboard() {
  const res = await apiFetch('/api/management/dashboard');
  if (!res.ok || !res.data) {
    showToast('Failed to load executive analytics.', 'error');
    return;
  }

  const d = res.data;

  // KPI Cards
  const kpiTotal = document.getElementById('kpi-total');
  const kpiOpen = document.getElementById('kpi-open');
  const kpiResolved = document.getElementById('kpi-resolved');
  const kpiSla = document.getElementById('kpi-sla');
  const kpiRating = document.getElementById('kpi-rating');
  const kpiCost = document.getElementById('kpi-cost');

  if (kpiTotal) kpiTotal.textContent = d.total_requests;
  if (kpiOpen) kpiOpen.textContent = d.open_requests;
  if (kpiResolved) kpiResolved.textContent = d.resolved_requests;
  if (kpiSla) kpiSla.textContent = `${d.sla_compliance_rate}%`;
  if (kpiRating) kpiRating.textContent = d.average_rating > 0 ? `⭐ ${d.average_rating}/5` : 'N/A';
  if (kpiCost) kpiCost.textContent = formatINR(d.total_materials_cost);

  // Render Charts
  renderCategoryChart(d.requests_by_category || []);
  renderPriorityChart(d.requests_by_priority || []);

  // Render Timeline
  renderMgmtTimeline(d.recent_timeline || []);
}

function renderCategoryChart(data) {
  const canvas = document.getElementById('mgmt-category-chart');
  if (!canvas) return;

  const labels = data.map(c => c.CategoryName);
  const counts = data.map(c => c.count);

  if (categoryChartInstance) {
    categoryChartInstance.destroy();
  }

  categoryChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: counts,
        backgroundColor: [
          '#16a34a', '#0284c7', '#ea580c', '#e11d48', '#8b5cf6', '#64748b'
        ],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 12 } } },
        tooltip: {
          callbacks: {
            label: function(context) {
              const item = data[context.dataIndex];
              const spend = formatINR(item.total_category_cost);
              return ` ${item.CategoryName}: ${item.count} tickets (Spend: ${spend})`;
            }
          }
        }
      }
    }
  });
}

function renderPriorityChart(data) {
  const canvas = document.getElementById('mgmt-priority-chart');
  if (!canvas) return;

  const labels = data.map(p => p.Label);
  const counts = data.map(p => p.count);

  if (priorityChartInstance) {
    priorityChartInstance.destroy();
  }

  priorityChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Request Volume',
        data: counts,
        backgroundColor: ['#e11d48', '#ea580c', '#0284c7', '#64748b'],
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderMgmtTimeline(timeline) {
  const container = document.getElementById('mgmt-timeline-container');
  if (!container) return;

  if (timeline.length === 0) {
    container.innerHTML = '<div class="text-muted text-center py-3">No status progression recorded.</div>';
    return;
  }

  container.innerHTML = timeline.map(t => `
    <div class="timeline-step">
      <div class="timeline-dot"></div>
      <div class="timeline-content">
        <div style="font-weight:600; font-size:13.5px;">
          Ticket #REQ-2026-${String(t.RequestID).padStart(3, '0')}: 
          <span style="color:var(--text-muted);">${escapeHtml(t.OldStatus || 'Created')}</span> ➔ 
          <span style="color:var(--primary);">${escapeHtml(t.NewStatus)}</span>
        </div>
        <div style="font-size:12.5px; color:var(--text-secondary); margin-top:2px;">
          ${escapeHtml(t.CategoryName)} in ${escapeHtml(t.BuildingName)} (${escapeHtml(t.RoomNo)})
        </div>
        <div class="text-muted" style="font-size:11.5px; margin-top:2px;">
          ${formatISTDate(t.ChangedOn)}
        </div>
      </div>
    </div>
  `).join('');
}

async function loadManagementAuditLogs() {
  const tbody = document.getElementById('mgmt-audit-tbody');
  if (!tbody) return;

  tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">Loading audit records...</td></tr>';

  const res = await apiFetch('/api/management/audit-logs');
  if (res.ok && Array.isArray(res.data)) {
    if (res.data.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No audit records found.</td></tr>';
      return;
    }

    tbody.innerHTML = res.data.map(l => `
      <tr>
        <td style="font-weight:700; color:var(--text-muted); font-size:12px;">#${l.LogID}</td>
        <td style="font-size:12px;">${formatISTDate(l.Timestamp)}</td>
        <td><span class="badge badge-assigned">${escapeHtml(l.Action)}</span></td>
        <td style="font-size:13px;">${escapeHtml(l.UserName || 'System')} <span class="text-muted" style="font-size:11px;">(${escapeHtml(l.UserRole || 'N/A')})</span></td>
        <td style="font-size:12.5px; max-width:340px; word-break:break-word;">${escapeHtml(l.Details || '')}</td>
        <td style="font-size:11.5px; font-family:monospace;">${escapeHtml(l.IP || '127.0.0.1')}</td>
      </tr>
    `).join('');
  }
}
