/* ============================================================
   Parking Audit Builder — Frontend JavaScript
   ============================================================ */

/* ---- File input display ---- */
function setupFileInput(inputId, labelId) {
  const input = document.getElementById(inputId);
  const label = document.getElementById(labelId);
  if (!input || !label) return;
  input.addEventListener('change', () => {
    if (input.files && input.files[0]) {
      label.textContent = input.files[0].name;
      label.classList.add('has-file');
    } else {
      label.textContent = label.dataset.placeholder || 'Click to choose file or drag & drop';
      label.classList.remove('has-file');
    }
  });
  // Drag and drop
  const zone = input.closest('.file-drop-zone');
  if (zone) {
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) {
        const dt = new DataTransfer();
        dt.items.add(e.dataTransfer.files[0]);
        input.files = dt.files;
        input.dispatchEvent(new Event('change'));
      }
    });
  }
}

/* ---- Form submit loading state ---- */
function setupFormSubmit(formId, btnId, loadingText) {
  const form = document.getElementById(formId);
  const btn  = document.getElementById(btnId);
  if (!form || !btn) return;
  form.addEventListener('submit', () => {
    btn.disabled = true;
    btn.classList.add('loading');
    const origText = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span> ' + loadingText;
  });
}

/* ============================================================
   Dashboard
   ============================================================ */
let _dashboardData = [];
let _sortCol = 'room_number';
let _sortDir = 'asc';
let _pollTimer = null;
let _currentScope = 'full';

function initDashboard(sessionId, hasDepartures, scope) {
  _currentScope = scope || 'full';
  fetchAndRender(sessionId, hasDepartures);
  _pollTimer = setInterval(() => fetchAndRender(sessionId, hasDepartures), 5000);
  
  // Initialize map features
  initMapTabs();
  initMapRoomClick();

  // Search
  const search = document.getElementById('searchInput');
  if (search) search.addEventListener('input', () => renderTable(hasDepartures));

  // Checkboxes
  ['filterNotInSys', 'filterDueOut', 'filterStayover'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', () => renderTable(hasDepartures));
  });

  // Clear filters
  const clearBtn = document.getElementById('clearFilters');
  if (clearBtn) clearBtn.addEventListener('click', () => {
    if (search) search.value = '';
    ['filterNotInSys', 'filterDueOut', 'filterStayover'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.checked = false;
    });
    renderTable(hasDepartures);
  });

  // Sortable columns
  document.querySelectorAll('.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (_sortCol === col) {
        _sortDir = _sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        _sortCol = col;
        _sortDir = 'asc';
      }
      document.querySelectorAll('.sortable').forEach(h => {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(_sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      renderTable(hasDepartures);
    });
  });
}

function fetchAndRender(sessionId, hasDepartures) {
  fetch('/api/session/' + sessionId)
    .then(r => r.json())
    .then(data => {
      _dashboardData = data.records || [];
      _currentScope = data.session.scope || 'full';
      updateTiles(data.session);
      renderTable(hasDepartures);
      updateHotelMap(hasDepartures, _currentScope);
      const lu = document.getElementById('lastUpdated');
      if (lu) lu.textContent = 'Updated ' + new Date().toLocaleTimeString();
    })
    .catch(err => console.warn('Dashboard poll error:', err));
}

function updateTiles(session) {
  const set = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.textContent = val; };
  set('val-total',    session.total_rooms);
  set('val-vehicles', session.rooms_with_vehicles);
  set('val-notinsys', session.not_in_system);
  set('val-dueouts',  session.due_outs);
  set('val-stayovers',session.stayovers);
}

function renderTable(hasDepartures) {
  const tbody = document.getElementById('tableBody');
  if (!tbody) return;

  const search  = (document.getElementById('searchInput')   || {}).value || '';
  const onlyNIS = (document.getElementById('filterNotInSys')|| {}).checked;
  const onlyDO  = (document.getElementById('filterDueOut')  || {}).checked;
  const onlySO  = (document.getElementById('filterStayover')|| {}).checked;
  const sq = search.toLowerCase();

  // Group records by room_number for rendering
  const roomMap = {};
  _dashboardData.forEach(rec => {
    const rn = rec.room_number;
    if (!roomMap[rn]) roomMap[rn] = [];
    roomMap[rn].push(rec);
  });

  // Build room summaries for filtering/sorting
  let rooms = Object.values(roomMap).map(recs => {
    const first = recs[0];
    const hasVehicle = recs.some(r => r.has_vehicle_info);
    return { room_number: first.room_number, vehicle_status: first.vehicle_status, recs, hasVehicle };
  });

  // Filter
  rooms = rooms.filter(r => {
    if (onlyNIS && r.hasVehicle) return false;
    if (onlyDO  && r.vehicle_status !== 'DUE_OUT') return false;
    if (onlySO  && r.vehicle_status !== 'STAYOVER') return false;
    if (sq) {
      const roomMatch = String(r.room_number).includes(sq);
      const plateMatch = r.recs.some(rec => (rec.plate || '').toLowerCase().includes(sq));
      if (!roomMatch && !plateMatch) return false;
    }
    return true;
  });

  // Sort
  rooms.sort((a, b) => {
    let va = a[_sortCol] ?? '', vb = b[_sortCol] ?? '';
    if (_sortCol === 'room_number') { va = Number(va); vb = Number(vb); }
    else { va = String(va).toLowerCase(); vb = String(vb).toLowerCase(); }
    if (va < vb) return _sortDir === 'asc' ? -1 : 1;
    if (va > vb) return _sortDir === 'asc' ?  1 : -1;
    return 0;
  });

  // Render
  if (rooms.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="table-loading">No matching records.</td></tr>';
    const rc = document.getElementById('rowCount');
    if (rc) rc.textContent = '0 rooms shown';
    return;
  }

  const rows = [];
  rooms.forEach(r => {
    const recs = r.recs;
    const hasVehicle = r.hasVehicle;
    const status = r.vehicle_status;

    if (!hasVehicle) {
      // Not in VM System
      const statusCell = hasDepartures
        ? `<td class="${status === 'DUE_OUT' ? 'status-due-out' : 'status-stayover'}">${status || 'STAYOVER'}</td>`
        : '';
      const colSpan = hasDepartures ? 5 : 6;
      rows.push(`<tr class="row-missing">
        <td><strong>${r.room_number}</strong></td>
        ${statusCell}
        <td colspan="${colSpan}" class="not-in-sys">Not In VM System</td>
      </tr>`);
    } else {
      recs.filter(rec => rec.has_vehicle_info).forEach((rec, i) => {
        const statusCell = hasDepartures
          ? `<td class="${status === 'DUE_OUT' ? 'status-due-out' : 'status-stayover'}">${i === 0 ? (status || 'STAYOVER') : ''}</td>`
          : '';
        const rowClass = status === 'DUE_OUT' ? 'row-dueout' : '';
        rows.push(`<tr class="${rowClass}">
          <td><strong>${i === 0 ? r.room_number : ''}</strong></td>
          ${statusCell}
          <td>${esc(rec.state)}</td>
          <td>${esc(rec.plate)}</td>
          <td>${esc(rec.make_model)}</td>
          <td>${esc(rec.year)}</td>
          <td>${esc(rec.comment)}</td>
          <td><span class="badge">Present</span></td>
        </tr>`);
      });
    }
  });

  tbody.innerHTML = rows.join('');
  const rc = document.getElementById('rowCount');
  if (rc) rc.textContent = `${rooms.length} room${rooms.length !== 1 ? 's' : ''} shown`;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ============================================================
   Hotel Map Visualization
   ============================================================ */

function updateHotelMap(hasDepartures, scope) {
  const roomCells = document.querySelectorAll('.room-cell[data-room]');
  if (!roomCells.length) return;

  // Build room data lookup
  const roomData = {};
  _dashboardData.forEach(rec => {
    const rn = rec.room_number;
    if (!roomData[rn]) {
      roomData[rn] = {
        room_number: rn,
        status: rec.vehicle_status,
        hasVehicle: false,
        vehicles: []
      };
    }
    if (rec.has_vehicle_info) {
      roomData[rn].hasVehicle = true;
      roomData[rn].vehicles.push({
        plate: rec.plate,
        state: rec.state,
        make_model: rec.make_model,
        year: rec.year
      });
    }
  });

  // Determine which rooms are in scope
  const inScope = (roomNum) => {
    if (scope === 'full') return true;
    if (roomNum === 501 || roomNum === 502) return true;
    if (scope === '100_200') return roomNum >= 100 && roomNum <= 299;
    if (scope === '300_400') return roomNum >= 300 && roomNum <= 499;
    return true;
  };

  roomCells.forEach(cell => {
    const roomNum = parseInt(cell.dataset.room, 10);
    const data = roomData[roomNum];
    
    // Clear existing classes
    cell.classList.remove('has-vehicle', 'not-in-system', 'due-out', 'stayover-vehicle', 'empty-room', 'not-in-scope');
    
    // Remove existing tooltip
    const existingTooltip = cell.querySelector('.room-tooltip');
    if (existingTooltip) existingTooltip.remove();

    // Check if in scope
    if (!inScope(roomNum)) {
      cell.classList.add('not-in-scope');
      cell.textContent = roomNum;
      return;
    }

    // If no data for this room, it's empty/not occupied
    if (!data) {
      cell.classList.add('empty-room');
      cell.textContent = roomNum;
      return;
    }

    // Determine styling based on status
    if (hasDepartures && data.status === 'DUE_OUT') {
      cell.classList.add('due-out');
    } else if (data.hasVehicle) {
      cell.classList.add('has-vehicle');
    } else {
      cell.classList.add('not-in-system');
    }

    cell.textContent = roomNum;

    // Build tooltip content
    let tooltipHtml = `<div class="tooltip-room">Room ${roomNum}</div>`;
    
    if (hasDepartures) {
      const statusText = data.status === 'DUE_OUT' ? 'Due Out' : 'Stayover';
      tooltipHtml += `<div class="tooltip-status">${statusText}</div>`;
    }

    if (data.hasVehicle && data.vehicles.length > 0) {
      data.vehicles.forEach(v => {
        const parts = [];
        if (v.state || v.plate) parts.push([v.state, v.plate].filter(Boolean).join(' '));
        if (v.make_model) parts.push(v.make_model);
        if (v.year) parts.push(v.year);
        if (parts.length) {
          tooltipHtml += `<div class="tooltip-vehicle">${esc(parts.join(' - '))}</div>`;
        }
      });
    } else {
      tooltipHtml += `<div class="tooltip-vehicle">Not In VM System</div>`;
    }

    const tooltip = document.createElement('div');
    tooltip.className = 'room-tooltip';
    tooltip.innerHTML = tooltipHtml;
    cell.appendChild(tooltip);
  });
}

function initMapTabs() {
  const tabs = document.querySelectorAll('.map-tab');
  const floors = document.querySelectorAll('.map-floor');
  
  if (!tabs.length || !floors.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetFloor = tab.dataset.floor;
      
      // Update active tab
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Show/hide floors
      floors.forEach(floor => {
        if (targetFloor === 'all') {
          floor.style.display = '';
        } else {
          floor.style.display = floor.dataset.floor === targetFloor ? '' : 'none';
        }
      });
    });
  });
}

// Add click handler to focus search on room
function initMapRoomClick() {
  document.querySelectorAll('.room-cell[data-room]').forEach(cell => {
    cell.addEventListener('click', () => {
      const roomNum = cell.dataset.room;
      const searchInput = document.getElementById('searchInput');
      if (searchInput && !cell.classList.contains('not-in-scope')) {
        searchInput.value = roomNum;
        searchInput.dispatchEvent(new Event('input'));
        // Scroll to table
        const tableWrapper = document.querySelector('.table-wrapper');
        if (tableWrapper) {
          tableWrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });
}
