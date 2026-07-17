/**
 * =========================================================================
 *  Sazón Caribeño POS — App Controller
 *  Vanilla JS SPA with FastAPI backend + sidebar layout
 * =========================================================================
 */

const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000/api/v1'
  : `${location.origin}/api/v1`;

/* =========================================================================
   State
   ========================================================================= */
const state = {
  token: localStorage.getItem('pos_token') || null,
  user: JSON.parse(localStorage.getItem('pos_user') || 'null'),
  currentScreen: 'salon',
  selectedMesa: null,
  currentOrder: { mesaId: null, items: [] },
  tables: [],
  zonas: [],
  menuItems: [],
  cierreData: null,
  categories: [],
  insumos: [],
  insumoAlerts: [],
  categoriasInsumo: [],
  unidadesMedida: [],
  activeInsumoCatFilter: null,
  allGastos: [],
  activeGastoFilter: null,
  turnos: [],
  empleados: [],
  nominaActual: null,
  currentAsistencia: JSON.parse(localStorage.getItem('pos_asistencia') || 'null'),
  currentOcupada: null,
  heartbeatInterval: null,
};

/* =========================================================================
   API Helpers
   ========================================================================= */
async function api(endpoint, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    if (res.status === 401) { logout(); throw new Error('Sesión expirada'); }
    if (res.status === 403) {
      const err = await res.json().catch(() => ({ detail: 'Acceso denegado' }));
      showIPBlockModal(err.detail || 'Acceso denegado');
      throw new Error(err.detail || 'Acceso denegado');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error del servidor' }));
      let msg = err.detail || `Error ${res.status}`;
      if (Array.isArray(msg)) {
        msg = msg.map(e => e.msg || JSON.stringify(e)).join('; ');
      }
      throw new Error(msg);
    }
    return res.status === 204 ? null : await res.json();
  } catch (e) {
    if (e.message !== 'Sesión expirada') showToast(e.message, 'error');
    throw e;
  }
}

/* =========================================================================
   Toast
   ========================================================================= */
function showToast(message, type = 'success', duration = 3000) {
  const t = document.getElementById('toast');
  t.textContent = type === 'success' ? `✓ ${message}` : `✗ ${message}`;
  t.className = `toast ${type} show`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('show'), duration);
}

/* =========================================================================
   Shell Visibility
   ========================================================================= */
function showLogin() {
  document.getElementById('app-shell').classList.remove('visible');
  document.getElementById('screen-login').classList.add('active');
}

function showApp() {
  document.getElementById('screen-login').classList.remove('active');
  document.getElementById('app-shell').classList.add('visible');
}

/* =========================================================================
   Navigation (SPA)
   ========================================================================= */
function navigateTo(screenId) {
  document.querySelectorAll('.main-content .screen').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(`screen-${screenId}`);
  if (target) target.classList.add('active');

  document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.screen === screenId);
  });

  // Sync bottom nav active state
  document.querySelectorAll('.bottom-nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.screen === screenId);
  });

  state.currentScreen = screenId;

  // Close mobile sidebar if open
  document.getElementById('sidebar')?.classList.remove('open');
  document.getElementById('sidebar-backdrop')?.classList.remove('show');
  document.getElementById('sidebar-toggle')?.classList.remove('open');

  if (screenId === 'salon') loadTables();
  if (screenId === 'comandero') loadCocinaOrdenes();
  if (screenId === 'menu-view') loadMenuBrowse();
  if (screenId === 'menu-mgmt') loadMenuManagement();
  if (screenId === 'inventory') loadInventory();
  if (screenId === 'personal') loadPersonal();
  if (screenId === 'cuenta') {
    loadCierreReportes('diario');
    loadHistorialOrdenesDia();
  }
  if (screenId === 'gastos') { state.activeGastoFilter = null; loadGastos(); }
}

/* =========================================================================
   Role-Based Nav Restrictions
   ========================================================================= */
function applyRoleRestrictions() {
  const rol = state.user?.rol || '';
  const isElevated = rol === 'Administrador' || rol === 'Gerente';

  document.body.classList.remove('role-administrador', 'role-gerente', 'role-vendedor');
  if (rol === 'Administrador') document.body.classList.add('role-administrador');
  else if (rol === 'Gerente') document.body.classList.add('role-gerente');
  else if (rol === 'Vendedor') document.body.classList.add('role-vendedor');

  document.querySelectorAll('.nav-item-admin').forEach(btn => {
    const allowedRoles = (btn.dataset.roles || '').split(',');
    if (!isElevated) {
      btn.classList.add('nav-locked');
      btn.title = 'Requiere rol de Administrador o Gerente';
    } else {
      btn.classList.remove('nav-locked');
      btn.title = '';
    }
  });
}

/* =========================================================================
   Auth
   ========================================================================= */
async function login(username, password) {
  const data = await api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  state.token = data.access_token;
  localStorage.setItem('pos_token', data.access_token);

  const payload = JSON.parse(atob(data.access_token.split('.')[1]));
  state.user = { id: parseInt(payload.sub), username: payload.username, rol: payload.rol };
  localStorage.setItem('pos_user', JSON.stringify(state.user));

  updateUserBadges();
  applyRoleRestrictions();
  showApp();
  showAttendancePanel();
  loadTurnos();
  navigateTo('salon');
  showToast(`Bienvenido, ${state.user.username}`);
}

function logout() {
  if (state.heartbeatInterval) { clearInterval(state.heartbeatInterval); state.heartbeatInterval = null; }
  state.token = null;
  state.user = null;
  state.currentAsistencia = null;
  state.turnos = [];
  localStorage.removeItem('pos_token');
  localStorage.removeItem('pos_user');
  localStorage.removeItem('pos_asistencia');
  hideAttendancePanel();
  showLogin();
}

function updateUserBadges() {
  const initial = (state.user?.username || 'U')[0].toUpperCase();
  const name = state.user?.username || 'Usuario';
  const rol = state.user?.rol || 'Rol';

  document.getElementById('sidebar-avatar').textContent = initial;
  document.getElementById('sidebar-username').textContent = name;
  document.getElementById('sidebar-role').textContent = rol;

  const roleBadge = document.getElementById('cuenta-role-badge');
  if (roleBadge) roleBadge.textContent = rol;
}

/* =========================================================================
   Attendance — IP Validation & Shift Control
   ========================================================================= */
async function iniciarTurno(turnoId) {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

    const res = await fetch(`${API_BASE}/asistencia/turnos/iniciar/${turnoId}`, {
      method: 'POST',
      headers,
    });

    if (res.status === 403) {
      const err = await res.json().catch(() => ({ detail: 'IP no autorizada' }));
      showIPBlockModal(err.detail || 'IP no autorizada');
      return null;
    }

    if (res.status === 401) {
      logout();
      throw new Error('Sesión expirada');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error del servidor' }));
      throw new Error(err.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    state.currentAsistencia = data;
    localStorage.setItem('pos_asistencia', JSON.stringify(data));
    renderAttendanceStatus();
    showToast('Turno iniciado con éxito', 'success');
    return data;
  } catch (e) {
    if (e.message !== 'Sesión expirada') showToast(e.message, 'error');
    throw e;
  }
}

async function finalizarTurno() {
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

    const res = await fetch(`${API_BASE}/asistencia/check-out`, {
      method: 'POST',
      headers,
    });

    if (res.status === 403) {
      const err = await res.json().catch(() => ({ detail: 'Acceso denegado' }));
      showIPBlockModal(err.detail || 'Acceso denegado');
      return null;
    }

    if (res.status === 401) {
      logout();
      throw new Error('Sesión expirada');
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Error del servidor' }));
      throw new Error(err.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    state.currentAsistencia = null;
    localStorage.removeItem('pos_asistencia');
    renderAttendanceStatus();
    showToast('Turno finalizado con éxito', 'success');
    return data;
  } catch (e) {
    if (e.message !== 'Sesión expirada') showToast(e.message, 'error');
    throw e;
  }
}

/* --- Attendance Panel UI --- */
function showAttendancePanel() {
  const panel = document.getElementById('attendance-panel');
  if (panel) panel.style.display = 'block';
  renderAttendanceStatus();
}

function hideAttendancePanel() {
  const panel = document.getElementById('attendance-panel');
  if (panel) panel.style.display = 'none';
}

function renderAttendanceStatus() {
  const statusEl = document.getElementById('attendance-status');
  const btnIniciar = document.getElementById('btn-iniciar-turno');
  const btnFinalizar = document.getElementById('btn-finalizar-turno');
  const select = document.getElementById('turno-select');

  if (state.currentAsistencia) {
    if (statusEl) {
      const hora = new Date(state.currentAsistencia.hora_entrada_real).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
      statusEl.innerHTML = `🟢 Turno activo — entrada ${hora}`;
      statusEl.style.color = '#2A9D8F';
    }
    if (btnIniciar) { btnIniciar.style.opacity = '0.4'; btnIniciar.style.pointerEvents = 'none'; }
    if (btnFinalizar) { btnFinalizar.style.opacity = '1'; btnFinalizar.style.pointerEvents = 'auto'; }
    if (select) { select.disabled = true; select.value = state.currentAsistencia.turno_id; }
  } else {
    if (statusEl) { statusEl.innerHTML = '⚪ Sin turno activo'; statusEl.style.color = '#6b7280'; }
    if (btnIniciar) { btnIniciar.style.opacity = '1'; btnIniciar.style.pointerEvents = 'auto'; }
    if (btnFinalizar) { btnFinalizar.style.opacity = '0.4'; btnFinalizar.style.pointerEvents = 'none'; }
    if (select) { select.disabled = false; }
  }
}

async function loadTurnos() {
  try {
    const data = await api('/asistencia/turnos');
    state.turnos = data;
    const select = document.getElementById('turno-select');
    if (!select) return;
    const current = select.value;
    select.innerHTML = '<option value="">Seleccionar turno…</option>';
    data.forEach(t => {
      select.innerHTML += `<option value="${t.id}">${t.nombre} (${t.hora_entrada}–${t.hora_salida})</option>`;
    });
    if (current) select.value = current;
  } catch {
    state.turnos = [];
  }
}

/* --- Heartbeat (keepalive cada 2 min, solo Vendedor con turno activo) --- */
async function enviarHeartbeat() {
  if (!state.token || !state.user) return;
  if (state.user.rol !== 'Vendedor') return;
  if (!state.currentAsistencia) return;
  try {
    const headers = { 'Content-Type': 'application/json' };
    headers['Authorization'] = `Bearer ${state.token}`;
    await fetch(`${API_BASE}/asistencia/turnos/heartbeat/${state.currentAsistencia.id}`, {
      method: 'POST', headers,
    });
  } catch { /* silent — intentionally ignored */ }
}

/* =========================================================================
   Gastos — CRUD
   ========================================================================= */
const CATEGORIA_LABELS = {
  OPERATIVO: '🔧 Operativo',
  MANTENIMIENTO: '🛠️ Mantenimiento',
  SUMINISTROS: '📦 Suministros',
  SERVICIOS: '⚙️ Servicios',
  IMPUESTOS: '🏛️ Impuestos',
  OTROS: '📋 Otros',
};

async function loadGastos() {
  const tbody = document.getElementById('gastos-table-body');
  if (!tbody) return;
  try {
    state.allGastos = await api('/gastos/');
    renderGastoFilters();
    renderGastosTable();
  } catch {
    tbody.innerHTML = '<tr><td colspan="6" style="padding:32px;text-align:center;color:#E63946;">Error al cargar gastos</td></tr>';
  }
}

function renderGastoFilters() {
  const container = document.getElementById('gastos-cat-filters');
  if (!container) return;
  const cats = Object.keys(CATEGORIA_LABELS);
  container.innerHTML = `<button class="chip ${state.activeGastoFilter === null ? 'active' : ''}" onclick="applyGastoFilter(null)">Todos</button>`
    + cats.map(c => `<button class="chip ${state.activeGastoFilter === c ? 'active' : ''}" onclick="applyGastoFilter('${c}')">${CATEGORIA_LABELS[c]}</button>`).join('');
}

function applyGastoFilter(cat) {
  state.activeGastoFilter = cat;
  renderGastoFilters();
  renderGastosTable();
}

function renderGastosTable() {
  const tbody = document.getElementById('gastos-table-body');
  if (!tbody) return;
  const filtered = state.activeGastoFilter
    ? state.allGastos.filter(g => g.categoria === state.activeGastoFilter)
    : state.allGastos;
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="padding:32px;text-align:center;color:#9ca3af;">No hay gastos registrados</td></tr>';
    return;
  }
  tbody.innerHTML = filtered.map(g => `
    <tr style="border-bottom:1px solid #f1f5f9;transition:background .15s;" onmouseenter="this.style.background='#f8fafc'" onmouseleave="this.style.background=''">
      <td style="padding:12px 16px;font-weight:600;color:var(--azul-marino);">#${g.id}</td>
      <td style="padding:12px 16px;color:#374151;">${new Date(g.fecha).toLocaleDateString('es-CO', { day:'2-digit', month:'short', year:'numeric' })}</td>
      <td style="padding:12px 16px;"><span style="display:inline-block;background:#f1f5f9;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;">${CATEGORIA_LABELS[g.categoria] || g.categoria}</span></td>
      <td style="padding:12px 16px;color:#374151;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${g.concepto}</td>
      <td style="padding:12px 16px;text-align:right;font-weight:700;color:var(--rojo-cangrejo);">C$${parseFloat(g.monto).toFixed(2)}</td>
      <td style="padding:12px 16px;color:#6b7280;font-size:13px;">${g.registrado_por ? 'Usuario #' + g.registrado_por : '—'}</td>
    </tr>
  `).join('');
}

function openGastosModal() {
  document.getElementById('gasto-form')?.reset();
  document.getElementById('modal-registrar-gasto')?.classList.add('show');
}

function closeGastosModal() {
  document.getElementById('modal-registrar-gasto')?.classList.remove('show');
}

async function guardarGasto() {
  const categoria = document.getElementById('gasto-categoria')?.value;
  const monto = parseFloat(document.getElementById('gasto-monto')?.value);
  const concepto = document.getElementById('gasto-descripcion')?.value.trim();

  if (!categoria) return showToast('Selecciona una categoría', 'warning');
  if (!monto || monto <= 0) return showToast('Ingresa un monto válido', 'warning');
  if (!concepto) return showToast('Ingresa una descripción', 'warning');

  const btn = document.getElementById('save-gasto-btn');
  btn.disabled = true;
  btn.textContent = 'Guardando…';
  try {
    await api('/gastos/', {
      method: 'POST',
      body: JSON.stringify({ categoria, monto, concepto }),
    });
    closeGastosModal();
    showToast('Gasto registrado con éxito', 'success');
    loadGastos();
  } catch { /* handled by api() */ }
  finally {
    btn.disabled = false;
    btn.textContent = 'Guardar Gasto';
  }
}

function showIPBlockModal(detail) {
  const modal = document.getElementById('modal-ip-block');
  const detailEl = document.getElementById('ip-block-detail');
  if (detailEl && detail) detailEl.textContent = detail;
  modal.style.display = 'flex';
  modal.classList.add('show');
  blockPOSAccess();
}

function closeIPBlockModal() {
  const modal = document.getElementById('modal-ip-block');
  modal.style.display = 'none';
  modal.classList.remove('show');
  logout();
}

function blockPOSAccess() {
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => {
    btn.classList.add('nav-locked');
    btn.title = 'Bloqueado — verifique su conexión a la red';
    btn.style.pointerEvents = 'none';
    btn.style.opacity = '0.5';
  });

  document.querySelectorAll('.btn-add').forEach(b => { b.disabled = true; b.style.opacity = '0.4'; b.style.pointerEvents = 'none'; });
  document.querySelectorAll('.btn-turquoise, .btn-primary').forEach(b => { b.disabled = true; b.style.opacity = '0.4'; b.style.pointerEvents = 'none'; });
}

/*    =========================================================================
   Tables (Salón)
   ========================================================================= */
let activeEstadoFilter = 'all';
let activeZonaFilter = 'all';
let activeMgmtCatFilter = 'all';
let activeCartaCatFilter = 'all';

async function loadTables() {
  try {
    const [zonas, mesasFlat] = await Promise.all([
      api('/salon/zonas'),
      api('/salon/mesas'),
    ]);
    state.zonas = zonas;
    state.tables = mesasFlat.map(m => {
      const zona = zonas.find(z => z.id === m.zona_id);
      return { ...m, zona_nombre: zona?.nombre || 'Zona ' + m.zona_id };
    });
    renderZonasFilters(zonas);
    applyTableFilters();
  } catch { state.tables = []; renderTables([]); }
}

function renderZonasFilters(zonas) {
  const container = document.getElementById('zona-filters');
  if (!container) return;
  container.innerHTML = `
    <button class="chip active" data-zona="all" role="tab" aria-selected="true">🗺️ Todas las Zonas</button>
    ${zonas.map(z => `<button class="chip" data-zona="${z.id}" role="tab">📍 ${z.nombre}</button>`).join('')}
  `;
  container.querySelectorAll('.chip[data-zona]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip[data-zona]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeZonaFilter = chip.dataset.zona;
      applyTableFilters();
    });
  });
}

function applyTableFilters() {
  let filtered = state.tables;
  if (activeEstadoFilter !== 'all') {
    filtered = filtered.filter(t => t.estado === activeEstadoFilter);
  }
  if (activeZonaFilter !== 'all') {
    filtered = filtered.filter(t => String(t.zona_id) === activeZonaFilter);
  }
  renderTables(filtered);
}

function renderTables(mesas) {
  const grid = document.getElementById('table-grid');
  if (!mesas || mesas.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:32px;">No hay mesas configuradas</p>';
    return;
  }
  grid.innerHTML = mesas.map(m => {
    const estado = m.estado || 'LIBRE';
    const el = estado.toLowerCase();
    return `
      <article class="table-card border-${el} animate-in" data-mesa-id="${m.id}" data-estado="${estado}" data-zona-id="${m.zona_id}"
               role="button" tabindex="0" aria-label="Mesa ${m.numero}, ${estado}">
        <span class="status-dot status-${el}" aria-hidden="true"></span>
        <div class="table-number">${m.numero}</div>
        <div class="table-zone">${m.zona_nombre || 'Zona ' + m.zona_id}</div>
        <div class="table-capacity">👥 ${m.capacidad} personas</div>
      </article>`;
  }).join('');

  grid.querySelectorAll('.table-card').forEach(card => {
    card.addEventListener('click', () => {
      const mesaId = parseInt(card.dataset.mesaId);
      const estado = card.dataset.estado;
      const mesa = state.tables.find(t => t.id === mesaId);
      if (estado === 'LIBRE') {
        openOrderModal(mesaId, mesa?.numero || '?');
      } else if (estado === 'OCUPADA') {
        openDetalleMesaOcupada(mesaId);
      } else {
        showToast(`Mesa ${mesa?.numero || '?'} está ${estado.toLowerCase()}`, 'warning');
      }
    });
  });
}

/* =========================================================================
   Table Filtering (Estado)
   ========================================================================= */
document.querySelectorAll('.chip[data-filter]').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip[data-filter]').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeEstadoFilter = chip.dataset.filter;
    applyTableFilters();
  });
});

/* =========================================================================
   Salon Management (Gestionar Mesas)
   ========================================================================= */
function openGestionMesas() {
  document.getElementById('gestion-mesa-id').value = '';
  document.getElementById('gestion-mesa-numero').value = '';
  document.getElementById('gestion-mesa-capacidad').value = '4';
  document.getElementById('gestion-form-title').textContent = 'Nueva Mesa';
  document.getElementById('gestion-cancelar-edicion').style.display = 'none';
  const panel = document.getElementById('zonas-panel');
  if (panel) panel.style.display = 'none';
  document.getElementById('modal-gestion-mesas').classList.add('show');
  loadGestionMesas();
}

function closeGestionMesas() {
  document.getElementById('modal-gestion-mesas').classList.remove('show');
}

async function loadGestionMesas() {
  try {
    const zonas = await api('/salon/zonas');
    state.zonas = zonas;
    const zonaSelect = document.getElementById('gestion-mesa-zona');
    zonaSelect.innerHTML = zonas.map(z =>
      `<option value="${z.id}">${z.nombre}</option>`
    ).join('');

    renderZonasList(zonas);

    const mesas = await api('/salon/mesas');
    renderGestionMesasList(mesas);
  } catch { /* handled by api() */ }
}

function renderZonasList(zonas) {
  const list = document.getElementById('zonas-list');
  if (!list) return;
  if (!zonas || zonas.length === 0) {
    list.innerHTML = '<p style="font-size:12px;color:#9ca3af;text-align:center;padding:8px;">No hay zonas creadas</p>';
    return;
  }
  list.innerHTML = zonas.map(z => {
    const count = (z.mesas || []).length;
    return `
      <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:4px;">
        <span style="flex:1;font-size:13px;font-weight:600;">📍 ${z.nombre}</span>
        <span style="font-size:11px;color:#9ca3af;">${count} mesa(s)</span>
        <button class="btn btn-secondary" style="font-size:11px;padding:3px 8px;color:#E63946;${count > 0 ? 'opacity:0.4;pointer-events:none;' : ''}" onclick="eliminarZona(${z.id}, '${z.nombre.replace(/'/g, "\\'")}')" title="${count > 0 ? 'Tiene mesas — no se puede eliminar' : 'Eliminar zona'}">🗑</button>
      </div>`;
  }).join('');
}

function renderGestionMesasList(mesas) {
  const list = document.getElementById('gestion-mesas-list');
  if (!mesas || mesas.length === 0) {
    list.innerHTML = '<p class="text-center text-muted" style="padding:16px;">No hay mesas registradas</p>';
    return;
  }
  const estadoColors = {
    LIBRE: 'background:#dcfce7;color:#166534;',
    OCUPADA: 'background:#fee2e2;color:#991b1b;',
    RESERVADA: 'background:#fef9c3;color:#854d0e;',
    MANTENIMIENTO: 'background:#e5e7eb;color:#374151;',
  };
  list.innerHTML = mesas.map(m => `
    <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid #e5e7eb;border-radius:10px;margin-bottom:6px;">
      <div style="flex:1;">
        <span style="font-weight:600;font-size:14px;">Mesa ${m.numero}</span>
        <span style="font-size:12px;color:#6b7280;margin-left:6px;">ID: ${m.id}</span>
      </div>
      <span style="font-size:12px;padding:2px 8px;border-radius:999px;${estadoColors[m.estado] || ''}">${m.estado}</span>
      <span style="font-size:12px;color:#6b7280;">👥 ${m.capacidad}</span>
      <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px;" onclick="editarMesa(${m.id})">✏️</button>
      <button class="btn btn-secondary" style="font-size:12px;padding:4px 10px;color:#E63946;" onclick="eliminarMesa(${m.id}, ${m.numero})">🗑</button>
    </div>`).join('');
}

async function editarMesa(mesaId) {
  try {
    const mesas = await api('/salon/mesas');
    const mesa = mesas.find(m => m.id === mesaId);
    if (!mesa) return showToast('Mesa no encontrada', 'error');

    document.getElementById('gestion-mesa-id').value = mesa.id;
    document.getElementById('gestion-mesa-numero').value = mesa.numero;
    document.getElementById('gestion-mesa-capacidad').value = mesa.capacidad;
    document.getElementById('gestion-form-title').textContent = `Editar Mesa #${mesa.numero}`;
    document.getElementById('gestion-cancelar-edicion').style.display = '';

    const zonaSelect = document.getElementById('gestion-mesa-zona');
    if (zonaSelect.querySelector(`option[value="${mesa.zona_id}"]`)) {
      zonaSelect.value = mesa.zona_id;
    }
  } catch { /* handled */ }
}

async function eliminarMesa(mesaId, numero) {
  if (!confirm(`¿Eliminar la Mesa ${numero}?`)) return;
  try {
    await api(`/salon/mesas/${mesaId}`, { method: 'DELETE' });
    showToast(`Mesa ${numero} eliminada`, 'success');
    await loadGestionMesas();
    await loadTables();
  } catch { /* handled by api() */ }
}

/* --- Zonas CRUD (within Gestionar Mesas modal) --- */
function toggleZonasPanel() {
  const panel = document.getElementById('zonas-panel');
  if (!panel) return;
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

async function guardarZona() {
  const input = document.getElementById('zona-nueva-nombre');
  const nombre = input?.value.trim();
  if (!nombre) return showToast('Ingresa un nombre para la zona', 'warning');
  try {
    await api('/salon/zonas', {
      method: 'POST',
      body: JSON.stringify({ nombre }),
    });
    input.value = '';
    showToast(`Zona '${nombre}' creada`, 'success');
    await loadGestionMesas();
    await loadTables();
  } catch { /* handled by api() */ }
}

async function eliminarZona(zonaId, nombre) {
  if (!confirm(`¿Eliminar la zona "${nombre}"? Solo se puede si no tiene mesas.`)) return;
  try {
    await api(`/salon/zonas/${zonaId}`, { method: 'DELETE' });
    showToast(`Zona '${nombre}' eliminada`, 'success');
    await loadGestionMesas();
    await loadTables();
  } catch { /* handled by api() */ }
}

async function guardarMesa() {
  const id = document.getElementById('gestion-mesa-id').value;
  const numero = parseInt(document.getElementById('gestion-mesa-numero').value);
  const capacidad = parseInt(document.getElementById('gestion-mesa-capacidad').value) || 4;
  const zona_id = parseInt(document.getElementById('gestion-mesa-zona').value);

  if (!numero || numero <= 0) return showToast('Ingresa un número válido', 'warning');
  if (!zona_id) return showToast('Selecciona una zona', 'warning');

  try {
    if (id) {
      await api(`/salon/mesas/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ numero, capacidad, zona_id }),
      });
      showToast('Mesa actualizada', 'success');
    } else {
      await api('/salon/mesas', {
        method: 'POST',
        body: JSON.stringify({ numero, capacidad, zona_id }),
      });
      showToast('Mesa creada', 'success');
    }
    document.getElementById('gestion-mesa-id').value = '';
    document.getElementById('gestion-mesa-numero').value = '';
    document.getElementById('gestion-mesa-capacidad').value = '4';
    document.getElementById('gestion-form-title').textContent = 'Nueva Mesa';
    document.getElementById('gestion-cancelar-edicion').style.display = 'none';
    await loadGestionMesas();
    await loadTables();
  } catch { /* handled by api() */ }
}

/* =========================================================================
   KDS — Kitchen Display System
   ========================================================================= */
let cocinaTab = 'cocina';
let cocinaOrdenes = [];

const ESTADO_BORDER_KDS = {
  PENDIENTE: 'kc-border-pendiente',
  PREPARANDO: 'kc-border-preparando',
  ENTREGADA: 'kc-border-entregada',
  PAGADA: 'kc-border-pagada',
  CANCELADA: 'kc-border-cancelada',
};

async function loadCocinaOrdenes() {
  const grid = document.getElementById('cocina-grid');
  if (!grid) return;
  try {
    const ordenes = await api('/ordenes/');
    cocinaOrdenes = ordenes;
    renderCocinaCards();
  } catch {
    grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:#E63946;padding:32px;">Error al cargar órdenes</p>';
  }
}

function renderCocinaCards() {
  const grid = document.getElementById('cocina-grid');
  if (!grid) return;

  let filtered;
  if (cocinaTab === 'cocina') {
    filtered = cocinaOrdenes.filter(o => o.estado === 'PENDIENTE' || o.estado === 'PREPARANDO');
  } else if (cocinaTab === 'lista') {
    filtered = cocinaOrdenes.filter(o => o.estado === 'ENTREGADA');
  } else {
    filtered = cocinaOrdenes.filter(o => o.estado === 'PAGADA' || o.estado === 'CANCELADA');
  }

  if (!filtered.length) {
    const emptyMsg = cocinaTab === 'cocina'
      ? 'No hay órdenes en cocina'
      : cocinaTab === 'lista'
        ? 'No hay órdenes listas para servir'
        : 'No hay historial de órdenes';
    grid.innerHTML = `<p style="grid-column:1/-1;text-align:center;color:#9ca3af;padding:32px;">${emptyMsg}</p>`;
    return;
  }

  grid.innerHTML = filtered.map(o => {
    const zona = o.mesa?.zona?.nombre || '—';
    const mesaNum = o.mesa?.numero || o.mesa_id;
    const mesero = o.mesero?.username || `Usuario #${o.mesero_id}`;
    const tiempo = getTiempoTranscurrido(o.fecha_creacion);
    const minutos = getMinutosTranscurrido(o.fecha_creacion);
    const tiempoClass = minutos > 15 ? 'kc-tiempo-urgente' : minutos > 8 ? 'kc-tiempo-ok' : 'kc-tiempo-calmado';
    const borderClass = ESTADO_BORDER_KDS[o.estado] || '';
    const showActions = o.estado === 'PENDIENTE' || o.estado === 'PREPARANDO';

    const itemsHtml = (o.detalles || []).map(d => {
      const nombre = d.producto_nombre || `Producto #${d.producto_id}`;
      const notas = d.notas ? `<div class="kc-notas">${d.notas}</div>` : '';
      return `<li><span><span class="kc-qty">${d.cantidad}x</span> ${nombre}</span>${notas}</li>`;
    }).join('');

    const actionsHtml = showActions ? (() => {
      if (o.estado === 'PENDIENTE') {
        return `<div class="kc-actions">
          <button class="kc-btn-entregar" onclick="cambiarEstadoKDS(${o.id}, 'PREPARANDO')" title="Empezar a preparar">🍳 Empezar a Preparar</button>
          <button class="kc-btn-cancelar" onclick="cambiarEstadoKDS(${o.id}, 'CANCELADA')" title="Cancelar orden">✕ Cancelar</button>
        </div>`;
      }
      return `<div class="kc-actions">
        <button class="kc-btn-entregar" onclick="cambiarEstadoKDS(${o.id}, 'ENTREGADA')" title="Marcar como entregada">✔ Entregar / Listo</button>
        <button class="kc-btn-cancelar" onclick="cambiarEstadoKDS(${o.id}, 'CANCELADA')" title="Cancelar orden">✕ Cancelar</button>
      </div>`;
    })() : '';

    return `
      <div class="cocina-card ${borderClass} animate-in">
        <div class="kc-header">
          <span class="kc-orden-id">Orden #${o.id}</span>
          <span class="kc-tiempo ${tiempoClass}">⏱ ${tiempo}</span>
        </div>
        <div class="kc-meta">
          <span>🪑 Mesa ${mesaNum}</span>
          <span>📍 ${zona}</span>
          <span>🧑‍🍳 ${mesero}</span>
          <span>💰 C$${parseFloat(o.total).toFixed(2)}</span>
        </div>
        <ul class="kc-items">${itemsHtml}</ul>
        ${actionsHtml}
      </div>`;
  }).join('');
}

function getTiempoTranscurrido(fechaCreacion) {
  const diff = Date.now() - new Date(fechaCreacion).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Ahora';
  if (mins < 60) return `${mins}min`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}min`;
}

function getMinutosTranscurrido(fechaCreacion) {
  return Math.floor((Date.now() - new Date(fechaCreacion).getTime()) / 60000);
}

async function cambiarEstadoKDS(ordenId, nuevoEstado) {
  if (nuevoEstado === 'CANCELADA' && !confirm(`¿Cancelar la Orden #${ordenId}?`)) return;
  try {
    await api(`/ordenes/${ordenId}/estado`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: nuevoEstado }),
    });
    showToast(`Orden #${ordenId} → ${nuevoEstado}`, 'success');
    await loadCocinaOrdenes();
  } catch { /* handled by api() */ }
}

function getCategoryEmoji(nombre) {
  const n = (nombre || '').toLowerCase();
  if (n.includes('bebida'))    return '🥤';
  if (n.includes('ceviche') || n.includes('marisco')) return '🐟';
  if (n.includes('fuerte') || n.includes('plato') || n.includes('carne') || n.includes('pollo')) return '🍛';
  if (n.includes('postre'))    return '🍰';
  if (n.includes('entrada'))   return '🥗';
  return '🍽️';
}

function renderMenuItems(items, containerId) {
  const grid = document.getElementById(containerId);
  if (!items || items.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:32px;">No hay productos disponibles</p>';
    return;
  }
  grid.innerHTML = items.map(item => {
    const emoji = getCategoryEmoji(item.categoria?.nombre);
    return `
      <article class="menu-item animate-in" data-item-id="${item.id}">
        <div class="item-emoji" aria-hidden="true">${emoji}</div>
        <div class="item-name">${item.nombre}</div>
        <div class="item-price">C$${parseFloat(item.precio).toFixed(2)}</div>
      </article>`;
  }).join('');
}

/* =========================================================================
   Order Modal (Tomar Comanda)
   ========================================================================= */
let orderModalCategory = 'all';
let orderModalSearch = '';

function openOrderModal(mesaId, mesaNumero) {
  state.currentOrder = { mesaId, items: [] };
  state.selectedMesa = mesaId;
  orderModalCategory = 'all';
  orderModalSearch = '';

  document.getElementById('order-modal-mesa').textContent = mesaNumero;
  document.getElementById('order-modal-count').textContent = '0';
  document.getElementById('order-modal-subtotal').textContent = 'C$0.00';
  document.getElementById('order-modal-total').textContent = 'C$0.00';

  const searchInput = document.getElementById('order-modal-search');
  if (searchInput) searchInput.value = '';

  document.querySelectorAll('#order-modal-categories .category-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.omCat === 'all');
  });

  document.getElementById('order-modal-cart').innerHTML =
    '<p style="text-align:center;color:#9ca3af;padding:16px;font-size:13px;">Vacío — toca + para agregar</p>';
  document.getElementById('order-modal-menu').innerHTML =
    '<p class="text-center text-muted" style="grid-column:1/-1;padding:24px;">Cargando menú…</p>';

  document.getElementById('modal-order').classList.add('show');
  loadOrderModalMenu();
}

function closeOrderModal() {
  document.getElementById('modal-order').classList.remove('show');
  state.currentOrder = { mesaId: null, items: [], _addToExisting: false, _ordenId: null };
}

async function loadOrderModalMenu() {
  try {
    state.menuItems = await api('/menu/items');
    renderOrderModalMenu(state.menuItems);
  } catch {
    document.getElementById('order-modal-menu').innerHTML =
      '<p class="text-center text-muted" style="grid-column:1/-1;padding:24px;">Error al cargar menú</p>';
  }
}

function renderOrderModalMenu(items) {
  const grid = document.getElementById('order-modal-menu');
  let filtered = items || [];

  if (orderModalCategory !== 'all') {
    filtered = filtered.filter(i => {
      const cat = (i.categoria?.nombre || '').toLowerCase();
      return cat.includes(orderModalCategory);
    });
  }

  if (orderModalSearch) {
    const q = orderModalSearch.toLowerCase();
    filtered = filtered.filter(i => i.nombre.toLowerCase().includes(q));
  }

  if (filtered.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:24px;">No hay productos disponibles</p>';
    return;
  }

  const emojis = { bebidas: '🥤', ceviches: '🐟', fuertes: '🍛', postres: '🍰', default: '🍽️' };
  grid.innerHTML = filtered.map(item => {
    const cat = (item.categoria?.nombre || '').toLowerCase();
    let emoji = emojis.default;
    if (cat.includes('bebida')) emoji = emojis.bebidas;
    else if (cat.includes('ceviche')) emoji = emojis.bebidas;
    else if (cat.includes('fuerte') || cat.includes('plato')) emoji = emojis.fuertes;
    else if (cat.includes('postre')) emoji = emojis.postres;

    const inOrder = state.currentOrder.items.find(i => i.producto_id === item.id);
    const qty = inOrder ? inOrder.cantidad : 0;

    return `
      <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;border:1px solid #e5e7eb;border-radius:12px;">
        <span style="font-size:24px;">${emoji}</span>
        <div style="flex:1;">
          <div style="font-weight:600;font-size:14px;">${item.nombre}</div>
          <div style="font-size:13px;color:#6b7280;">C$${parseFloat(item.precio).toFixed(2)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          <button class="qty-btn" onclick="changeOrderModalQty(${item.id}, -1)" style="width:30px;height:30px;font-size:16px;">−</button>
          <span style="min-width:24px;text-align:center;font-weight:700;font-size:15px;">${qty}</span>
          <button class="qty-btn" onclick="changeOrderModalQty(${item.id}, 1)" style="width:30px;height:30px;font-size:16px;">+</button>
        </div>
      </div>`;
  }).join('');
}

function changeOrderModalQty(itemId, delta) {
  const item = state.menuItems.find(i => i.id === itemId);
  if (!item) return;

  const existing = state.currentOrder.items.find(i => i.producto_id === itemId);
  if (existing) {
    existing.cantidad += delta;
    if (existing.cantidad <= 0) {
      state.currentOrder.items = state.currentOrder.items.filter(i => i.producto_id !== itemId);
    }
  } else if (delta > 0) {
    state.currentOrder.items.push({
      producto_id: itemId, nombre: item.nombre,
      precio_unitario: parseFloat(item.precio), cantidad: 1, notas: null,
    });
  }

  renderOrderModalMenu(state.menuItems);
  renderOrderModalCart();
  updateOrderModalTotals();
}

function renderOrderModalCart() {
  const cart = document.getElementById('order-modal-cart');
  const items = state.currentOrder.items;

  if (items.length === 0) {
    cart.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:16px;font-size:13px;">Vacío — toca + para agregar</p>';
    return;
  }

  cart.innerHTML = items.map((item, idx) => `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f3f4f6;">
      <div style="flex:1;min-width:0;">
        <div style="font-weight:500;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.nombre}</div>
        <div style="font-size:12px;color:#6b7280;">C$${item.precio_unitario.toFixed(2)}</div>
      </div>
      <div style="display:flex;align-items:center;gap:4px;flex-shrink:0;">
        <button class="qty-btn" onclick="changeOrderModalQty(${item.producto_id}, -1)" style="width:26px;height:26px;font-size:14px;">−</button>
        <span style="min-width:20px;text-align:center;font-weight:600;font-size:13px;">${item.cantidad}</span>
        <button class="qty-btn" onclick="changeOrderModalQty(${item.producto_id}, 1)" style="width:26px;height:26px;font-size:14px;">+</button>
        <button onclick="deleteOrderItem(${idx})" style="background:none;border:none;color:#E63946;font-size:14px;cursor:pointer;padding:2px 4px;" title="Eliminar">🗑</button>
      </div>
    </div>`).join('');
}

function deleteOrderItem(idx) {
  state.currentOrder.items.splice(idx, 1);
  renderOrderModalMenu(state.menuItems);
  renderOrderModalCart();
  updateOrderModalTotals();
}

function updateOrderModalTotals() {
  const items = state.currentOrder.items;
  const count = items.reduce((s, i) => s + i.cantidad, 0);
  const subtotal = items.reduce((s, i) => s + i.precio_unitario * i.cantidad, 0);
  document.getElementById('order-modal-count').textContent = count;
  document.getElementById('order-modal-subtotal').textContent = `C$${subtotal.toFixed(2)}`;
  document.getElementById('order-modal-total').textContent = `C$${subtotal.toFixed(2)}`;
}

function filterOrderModalByCategory(cat) {
  orderModalCategory = cat;
  document.querySelectorAll('#order-modal-categories .category-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.omCat === cat);
  });
  renderOrderModalMenu(state.menuItems);
}

function filterOrderModalBySearch(query) {
  orderModalSearch = query.trim();
  renderOrderModalMenu(state.menuItems);
}

async function submitOrder() {
  const items = state.currentOrder.items;
  if (!items.length) return showToast('Agrega al menos un producto', 'warning');
  if (!state.currentOrder.mesaId) return showToast('Selecciona una mesa primero', 'error');

  const btn = document.getElementById('confirm-order-modal');
  btn.disabled = true;
  btn.textContent = '⏳ Enviando…';

  try {
    if (state.currentOrder._addToExisting && state.currentOrder._ordenId) {
      await api(`/ordenes/${state.currentOrder._ordenId}/items`, {
        method: 'POST',
        body: JSON.stringify({
          items: items.map(i => ({ producto_id: i.producto_id, cantidad: i.cantidad, notas: i.notas })),
        }),
      });
      showToast('Ítems agregados a la orden existente', 'success');
    } else {
      await api('/ordenes/', {
        method: 'POST',
        body: JSON.stringify({
          mesa_id: state.currentOrder.mesaId,
          detalles: items.map(i => ({ producto_id: i.producto_id, cantidad: i.cantidad, notas: i.notas })),
        }),
      });
      showToast('¡Comanda enviada a cocina con éxito!', 'success');
    }

    const mesaId = state.currentOrder.mesaId;
    closeOrderModal();

    const mesa = state.tables.find(t => t.id === mesaId);
    if (mesa) {
      mesa.estado = 'OCUPADA';
      const card = document.querySelector(`.table-card[data-mesa-id="${mesaId}"]`);
      if (card) {
        card.dataset.estado = 'OCUPADA';
        card.classList.remove('border-libre');
        card.classList.add('border-ocupada');
        const dot = card.querySelector('.status-dot');
        if (dot) {
          dot.classList.remove('status-libre');
          dot.classList.add('status-ocupada');
        }
        const label = card.querySelector('.table-capacity');
        if (label) label.innerHTML = '🔴 Ocupada';
      }
    }
  } catch { /* api() already shows the specific error toast */ }
  finally {
    btn.disabled = false;
    btn.textContent = '📤 Confirmar';
  }
}

/* =========================================================================
   Menu Browse (Carta)
   ========================================================================= */
async function loadMenuBrowse() {
  await loadCategories();
  renderCartaCatFilters(state.categories);
  activeCartaCatFilter = 'all';
  try {
    state.menuItems = await api('/menu/items');
    applyCartaFilter();
  } catch { applyCartaFilter(); }
}

/* =========================================================================
   Menu Management (Admin/Gerente)
   ========================================================================= */
async function loadCategories() {
  try { state.categories = await api('/menu/categorias'); } catch { state.categories = []; }
}

async function loadMenuManagement() {
  await loadCategories();
  populateCategorySelect();
  renderMenuMgmtCatFilters(state.categories);
  try {
    state.menuItems = await api('/menu/items');
    applyMenuMgmtFilter();
  } catch { applyMenuMgmtFilter(); }
}

function populateCategorySelect() {
  const sel = document.getElementById('dish-category');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">Seleccionar…</option>';
  state.categories.forEach(c => {
    sel.innerHTML += `<option value="${c.id}">${c.nombre}</option>`;
  });
  if (current) sel.value = current;
}

function renderMenuMgmt(items) {
  const grid = document.getElementById('menu-mgmt-grid');
  if (!items || items.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:32px;">No hay platillos. Crea el primero.</p>';
    return;
  }
  grid.innerHTML = items.map(item => {
    const cat = item.categoria?.nombre || 'Sin categoría';
    const available = item.disponible !== false;
    const recipeCount = item.ingredientes_receta?.length || 0;
    return `
      <div class="data-card animate-in" data-dish-id="${item.id}">
        <div class="card-header">
          <div>
            <div class="card-title">${item.nombre}</div>
            <div class="card-subtitle">${cat}</div>
          </div>
          <span class="card-badge ${available ? 'badge-active' : 'badge-inactive'}">${available ? 'Activo' : 'Inactivo'}</span>
        </div>
        <div class="card-price">C$${parseFloat(item.precio).toFixed(2)}</div>
        ${item.descripcion ? `<div class="card-subtitle">${item.descripcion}</div>` : ''}
        ${recipeCount > 0 ? `<div class="card-subtitle" style="margin-top:2px;">🧾 ${recipeCount} ingrediente${recipeCount > 1 ? 's' : ''}</div>` : ''}
        <div class="card-actions">
          <button class="btn btn-secondary btn-sm" onclick="openEditDish(${item.id})">✏️ Editar</button>
          <button class="btn btn-secondary btn-sm" onclick="deleteDish(${item.id}, '${item.nombre.replace(/'/g, "\\'")}')" style="color:#E63946;">🗑️</button>
        </div>
      </div>`;
  }).join('');
}

function renderMenuMgmtCatFilters(categorias) {
  const container = document.getElementById('menu-mgmt-cat-filters');
  if (!container) return;
  container.innerHTML = `
    <button class="chip active" data-cat="all" role="tab" aria-selected="true">Todas</button>
    ${categorias.map(c => `<button class="chip" data-cat="${c.id}" role="tab">🍽️ ${c.nombre}</button>`).join('')}
  `;
  container.querySelectorAll('.chip[data-cat]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip[data-cat]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeMgmtCatFilter = chip.dataset.cat;
      applyMenuMgmtFilter();
    });
  });
}

function applyMenuMgmtFilter() {
  let filtered = state.menuItems;
  if (activeMgmtCatFilter !== 'all') {
    filtered = filtered.filter(i => String(i.categoria_id) === activeMgmtCatFilter);
  }
  renderMenuMgmt(filtered);
}

async function deleteDish(itemId, nombre) {
  if (!confirm(`¿Eliminar el platillo "${nombre}"?\nSe borrarán también sus recetas asociadas.`)) return;
  try {
    await api(`/menu/items/${itemId}`, { method: 'DELETE' });
    showToast(`"${nombre}" eliminado`);
    state.menuItems = state.menuItems.filter(i => i.id !== itemId);
    applyMenuMgmtFilter();
  } catch { /* handled by api() */ }
}

/* --- Carta (Menu Browse) Filters --- */
function renderCartaCatFilters(categorias) {
  const container = document.getElementById('carta-cat-filters');
  if (!container) return;
  container.innerHTML = `
    <button class="chip active" data-cat="all" role="tab" aria-selected="true">Todas</button>
    ${categorias.map(c => `<button class="chip" data-cat="${c.id}" role="tab">${getCategoryEmoji(c.nombre)} ${c.nombre}</button>`).join('')}
  `;
  container.querySelectorAll('.chip[data-cat]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip[data-cat]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeCartaCatFilter = chip.dataset.cat;
      applyCartaFilter();
    });
  });
}

function applyCartaFilter() {
  let filtered = state.menuItems;
  if (activeCartaCatFilter !== 'all') {
    filtered = filtered.filter(i => String(i.categoria_id) === activeCartaCatFilter);
  }
  renderMenuItems(filtered, 'menu-browse-grid');
}

/* --- Dish Modal --- */
async function openNewDishModal() {
  document.getElementById('dish-modal-title').textContent = 'Nuevo Platillo';
  document.getElementById('dish-form').reset();
  document.getElementById('dish-id').value = '';
  setDishToggle(true);
  clearRecipeRows();
  const catPanel = document.getElementById('cat-panel');
  if (catPanel) catPanel.style.display = 'none';
  await loadInsumosForRecipe();
  document.getElementById('modal-dish').classList.add('show');
}

async function openEditDish(itemId) {
  await Promise.all([loadCategories(), loadInsumosForRecipe()]);
  populateCategorySelect();
  const item = state.menuItems.find(i => i.id === itemId);
  if (!item) return;

  document.getElementById('dish-modal-title').textContent = 'Editar Platillo';
  document.getElementById('dish-id').value = item.id;
  document.getElementById('dish-name').value = item.nombre;
  document.getElementById('dish-price').value = item.precio;
  document.getElementById('dish-category').value = item.categoria_id || '';
  document.getElementById('dish-desc').value = item.descripcion || '';
  setDishToggle(item.disponible !== false);

  clearRecipeRows();
  if (item.ingredientes_receta && item.ingredientes_receta.length > 0) {
    item.ingredientes_receta.forEach(r => addRecipeRow(r.insumo_id, r.cantidad_necesaria));
  }

  const catPanel = document.getElementById('cat-panel');
  if (catPanel) catPanel.style.display = 'none';

  document.getElementById('modal-dish').classList.add('show');
}

function setDishToggle(active) {
  document.getElementById('dish-active-btn').classList.toggle('active', active);
  document.getElementById('dish-inactive-btn').classList.toggle('active', !active);
}

function clearRecipeRows() {
  document.getElementById('dish-recipe-rows').innerHTML = '';
}

function addRecipeRow(ingredienteId, cantidad) {
  const container = document.getElementById('dish-recipe-rows');
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px;';
  row.className = 'recipe-row';

  const options = state.insumos.map(i =>
    `<option value="${i.id}" ${i.id === ingredienteId ? 'selected' : ''}>${i.nombre} (${i.unidad_medida})</option>`
  ).join('');

  row.innerHTML = `
    <select class="form-input recipe-ingrediente" style="flex:2;height:36px;font-size:13px;">${options}</select>
    <input type="number" class="form-input recipe-cantidad" style="flex:1;height:36px;font-size:13px;" step="0.001" min="0.001" placeholder="Cant." value="${cantidad || ''}">
    <button type="button" class="btn-remove-recipe" style="background:none;border:none;color:#E63946;font-size:18px;cursor:pointer;padding:4px;" title="Quitar">🗑️</button>
  `;

  row.querySelector('.btn-remove-recipe').addEventListener('click', () => row.remove());
  container.appendChild(row);
}

function buildRecetaPayload() {
  const rows = document.querySelectorAll('#dish-recipe-rows .recipe-row');
  const receta = [];
  rows.forEach(row => {
    const sel = row.querySelector('.recipe-ingrediente');
    const rawId = sel ? sel.value : '';
    const insumo_id = parseInt(rawId, 10);
    const cantidad_necesaria = parseFloat(row.querySelector('.recipe-cantidad').value);
    if (Number.isInteger(insumo_id) && insumo_id > 0 && Number.isFinite(cantidad_necesaria) && cantidad_necesaria > 0) {
      receta.push({ insumo_id, cantidad_necesaria });
    }
  });
  return receta;
}

async function loadInsumosForRecipe() {
  if (state.insumos.length > 0) return;
  try { state.insumos = await api('/inventario/insumos'); } catch { state.insumos = []; }
}

function closeDishModal() {
  document.getElementById('modal-dish').classList.remove('show');
}

/* --- Categorías CRUD (within dish modal) --- */
function toggleCatPanel() {
  const panel = document.getElementById('cat-panel');
  if (!panel) return;
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function renderCatList() {
  const list = document.getElementById('cat-list');
  if (!list) return;
  if (!state.categories || state.categories.length === 0) {
    list.innerHTML = '<p style="font-size:12px;color:#9ca3af;text-align:center;padding:8px;">No hay categorías creadas</p>';
    return;
  }
  list.innerHTML = state.categories.map(c => {
    const count = state.menuItems.filter(i => i.categoria_id === c.id).length;
    return `
      <div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:#fff;border:1px solid #e5e7eb;border-radius:8px;margin-bottom:4px;">
        <span style="flex:1;font-size:13px;font-weight:600;">🍽️ ${c.nombre}</span>
        <span style="font-size:11px;color:#9ca3af;">${count} platillo(s)</span>
        <button class="btn btn-secondary" style="font-size:11px;padding:3px 8px;color:#E63946;${count > 0 ? 'opacity:0.4;pointer-events:none;' : ''}" onclick="eliminarCategoriaMenu(${c.id}, '${c.nombre.replace(/'/g, "\\'")}')" title="${count > 0 ? 'Tiene platillos — no se puede eliminar' : 'Eliminar categoría'}">🗑</button>
      </div>`;
  }).join('');
}

async function guardarCategoriaMenu() {
  const input = document.getElementById('cat-nueva-nombre');
  const nombre = input?.value.trim();
  if (!nombre) return showToast('Ingresa un nombre para la categoría', 'warning');
  try {
    await api('/menu/categorias', {
      method: 'POST',
      body: JSON.stringify({ nombre }),
    });
    input.value = '';
    showToast(`Categoría '${nombre}' creada`, 'success');
    await loadCategories();
    populateCategorySelect();
    renderMenuMgmtCatFilters(state.categories);
    renderCatList();
  } catch { /* handled by api() */ }
}

async function eliminarCategoriaMenu(catId, nombre) {
  if (!confirm(`¿Eliminar la categoría "${nombre}"? Solo se puede si no tiene platillos.`)) return;
  try {
    await api(`/menu/categorias/${catId}`, { method: 'DELETE' });
    showToast(`Categoría '${nombre}' eliminada`, 'success');
    await loadCategories();
    populateCategorySelect();
    renderMenuMgmtCatFilters(state.categories);
    renderCatList();
  } catch { /* handled by api() */ }
}

async function saveDish(e) {
  e.preventDefault();
  const id = document.getElementById('dish-id').value;
  const disponible = document.getElementById('dish-active-btn').classList.contains('active');
  const payload = {
    nombre: document.getElementById('dish-name').value.trim(),
    precio: parseFloat(document.getElementById('dish-price').value),
    categoria_id: parseInt(document.getElementById('dish-category').value),
    descripcion: document.getElementById('dish-desc').value.trim() || null,
    disponible,
  };

  if (!payload.nombre || !payload.precio || !payload.categoria_id) {
    return showToast('Completa nombre, precio y categoría', 'warning');
  }

  const receta = buildRecetaPayload();
  if (receta.length > 0) payload.receta = receta;

  try {
    if (id) {
      await api(`/menu/items/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Platillo actualizado');
    } else {
      await api('/menu/items', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Platillo creado');
    }
    closeDishModal();
    loadMenuManagement();
  } catch { /* handled */ }
}

/* =========================================================================
   Inventory (Insumos)
   ========================================================================= */
async function loadInventory() {
  await Promise.all([
    loadInsumos(),
    loadInsumoAlerts(),
    loadCategoriasInsumo(),
    loadUnidadesMedida(),
  ]);
}

async function loadCategoriasInsumo() {
  try {
    state.categoriasInsumo = await api('/inventario/categorias-insumo');
    renderInsumoCatFilters();
  } catch { state.categoriasInsumo = []; renderInsumoCatFilters(); }
}

async function loadUnidadesMedida() {
  try {
    state.unidadesMedida = await api('/inventario/unidades-medida');
  } catch { state.unidadesMedida = []; }
}

function renderInsumoCatFilters() {
  const container = document.getElementById('insumo-cat-filters');
  if (!container) return;
  const cats = state.categoriasInsumo;
  let html = `<button class="chip ${state.activeInsumoCatFilter === null ? 'active' : ''}" onclick="applyInsumoFilter(null)">Todos</button>`;
  html += cats.map(c =>
    `<button class="chip ${state.activeInsumoCatFilter === c.id ? 'active' : ''}" onclick="applyInsumoFilter(${c.id})">${c.nombre}</button>`
  ).join('');
  container.innerHTML = html;
}

function applyInsumoFilter(catId) {
  state.activeInsumoCatFilter = catId;
  renderInsumoCatFilters();
  const filtered = catId === null
    ? state.insumos
    : state.insumos.filter(i => i.categoria_id === catId);
  renderInsumos(filtered);
}

async function loadInsumos() {
  try {
    state.insumos = await api('/inventario/insumos');
    applyInsumoFilter(state.activeInsumoCatFilter);
  } catch { renderInsumos([]); }
}

async function loadInsumoAlerts() {
  try {
    state.insumoAlerts = await api('/inventario/insumos/alertas');
    renderAlerts(state.insumoAlerts);
  } catch { renderAlerts([]); }
}

function renderAlerts(alerts) {
  const strip = document.getElementById('inventory-alerts');
  if (!alerts || alerts.length === 0) {
    strip.innerHTML = '<div class="alerts-empty">✅ Todo en orden — no hay alertas de stock</div>';
    return;
  }
  strip.innerHTML = alerts.map(a => `
    <div class="alert-card animate-in" onclick="openStockModal(${a.id})" title="Ajustar stock de ${a.nombre}">
      <span class="alert-icon">⚠️</span>
      <div class="alert-info">
        <div class="alert-name">${a.nombre}</div>
        <div class="alert-stock">${a.cantidad_actual} ${a.unidad_medida} — mín: ${a.stock_minimo}</div>
      </div>
    </div>`).join('');
}

function renderInsumos(insumos) {
  const grid = document.getElementById('inventory-grid');
  if (!insumos || insumos.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:32px;">No hay insumos registrados</p>';
    return;
  }
  grid.innerHTML = insumos.map(i => {
    const pct = parseFloat(i.stock_minimo) > 0
      ? Math.min((parseFloat(i.cantidad_actual) / parseFloat(i.stock_minimo)) * 100, 100)
      : 100;
    const barClass = pct > 60 ? 'bar-ok' : pct > 30 ? 'bar-warn' : 'bar-crit';
    const badgeClass = pct > 60 ? 'badge-ok' : pct > 30 ? 'badge-warn' : 'badge-crit';
    const badgeText = pct > 60 ? 'OK' : pct > 30 ? 'Bajo' : 'Crítico';
    const catBadge = i.categoria_nombre ? `<span style="font-size:11px;background:#e0f2fe;color:var(--azul-marino);padding:2px 6px;border-radius:4px;">${i.categoria_nombre}</span>` : '';
    return `
      <div class="data-card animate-in">
        <div class="card-header">
          <div class="card-title">${i.nombre}</div>
          <span class="card-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:8px;">
          <span style="font-size:22px;font-weight:700;color:var(--azul-marino);">${i.cantidad_actual}</span>
          <span class="card-subtitle">${i.unidad_medida}</span>
          ${catBadge}
        </div>
        <div class="stock-bar-track"><div class="stock-bar-fill ${barClass}" style="width:${pct}%"></div></div>
        <div class="card-subtitle">Mínimo: ${i.stock_minimo} ${i.unidad_medida}</div>
        <div class="card-actions">
          <button class="btn btn-turquoise btn-sm" onclick="openStockModal(${i.id})">📦 Ajustar Stock</button>
        </div>
      </div>`;
  }).join('');
}

/* --- Stock Modal --- */
function openStockModal(insumoId) {
  const insumo = state.insumos.find(i => i.id === insumoId);
  if (!insumo) return;

  document.getElementById('stock-insumo-id').value = insumo.id;
  document.getElementById('stock-info').innerHTML = `
    <div class="stock-info-name">${insumo.nombre}</div>
    <div class="stock-info-qty">${insumo.cantidad_actual} ${insumo.unidad_medida}</div>
    <div class="stock-info-unit">Mínimo: ${insumo.stock_minimo} ${insumo.unidad_medida}</div>`;
  document.getElementById('stock-qty').value = '';
  document.getElementById('stock-motivo').value = 'Ajuste de inventario';
  setStockType('ENTRADA');
  document.getElementById('modal-stock').classList.add('show');
}

function setStockType(tipo) {
  document.getElementById('stock-entrada-btn').classList.toggle('active', tipo === 'ENTRADA');
  document.getElementById('stock-salida-btn').classList.toggle('active', tipo === 'SALIDA');
}

function closeStockModal() {
  document.getElementById('modal-stock').classList.remove('show');
}

async function saveStock(e) {
  e.preventDefault();
  const insumoId = document.getElementById('stock-insumo-id').value;
  const tipo = document.getElementById('stock-entrada-btn').classList.contains('ENTRADA') ||
               document.getElementById('stock-entrada-btn').classList.contains('active')
    ? 'ENTRADA' : 'SALIDA';
  const tipoFinal = document.getElementById('stock-entrada-btn').classList.contains('active') ? 'ENTRADA' : 'SALIDA';
  const payload = {
    cantidad: parseFloat(document.getElementById('stock-qty').value),
    tipo: tipoFinal,
    motivo: document.getElementById('stock-motivo').value.trim() || 'Ajuste de inventario',
  };

  if (!payload.cantidad || payload.cantidad <= 0) {
    return showToast('Ingresa una cantidad válida', 'warning');
  }

  try {
    await api(`/inventario/insumos/${insumoId}/stock`, {
      method: 'PATCH', body: JSON.stringify(payload),
    });
    showToast(`Stock ${tipoFinal === 'ENTRADA' ? 'incrementado' : 'reducido'}`);
    closeStockModal();
    loadInventory();
  } catch { /* handled */ }
}

/* --- Insumo Modal --- */
function openNewInsumoModal() {
  document.getElementById('insumo-form').reset();
  document.getElementById('insumo-qty').value = '0';
  document.getElementById('insumo-min').value = '5';
  populateUnidadSelect();
  populateCatInsumoSelect();
  document.getElementById('unidad-panel').style.display = 'none';
  document.getElementById('cat-insumo-panel').style.display = 'none';
  document.getElementById('modal-insumo').classList.add('show');
}

function populateUnidadSelect() {
  const sel = document.getElementById('insumo-unit');
  sel.innerHTML = state.unidadesMedida.map(u =>
    `<option value="${u.id}">${u.nombre} (${u.abreviatura})</option>`
  ).join('');
}

function populateCatInsumoSelect() {
  const sel = document.getElementById('insumo-cat');
  sel.innerHTML = '<option value="">Sin categoría</option>' +
    state.categoriasInsumo.map(c => `<option value="${c.id}">${c.nombre}</option>`).join('');
}

function closeInsumoModal() {
  document.getElementById('modal-insumo').classList.remove('show');
}

async function saveInsumo(e) {
  e.preventDefault();
  const payload = {
    nombre: document.getElementById('insumo-name').value.trim(),
    cantidad_actual: parseFloat(document.getElementById('insumo-qty').value) || 0,
    unidad_medida_id: parseInt(document.getElementById('insumo-unit').value),
    categoria_id: parseInt(document.getElementById('insumo-cat').value) || null,
    stock_minimo: parseFloat(document.getElementById('insumo-min').value) || 5,
  };
  if (!payload.nombre) return showToast('Ingresa el nombre del insumo', 'warning');
  if (!payload.unidad_medida_id) return showToast('Selecciona una unidad de medida', 'warning');

  try {
    await api('/inventario/insumos', { method: 'POST', body: JSON.stringify(payload) });
    showToast('Insumo creado');
    closeInsumoModal();
    loadInventory();
  } catch { /* handled */ }
}

/* --- Categoría Insumo Subpanel --- */
function toggleCatInsumoPanel() {
  const panel = document.getElementById('cat-insumo-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  if (panel.style.display === 'block') renderCatInsumoList();
}

function renderCatInsumoList() {
  const list = document.getElementById('cat-insumo-list');
  list.innerHTML = state.categoriasInsumo.map(c =>
    `<div class="inline-list-item">
      <span>${c.nombre}</span>
      <button type="button" class="btn-delete-inline" onclick="eliminarCategoriaInsumo(${c.id})" title="Eliminar">✕</button>
    </div>`
  ).join('') || '<span style="font-size:12px;color:var(--text-muted);">No hay categorías</span>';
}

async function guardarCategoriaInsumo() {
  const input = document.getElementById('new-cat-insumo-nombre');
  const nombre = input.value.trim();
  if (!nombre) return showToast('Ingresa el nombre', 'warning');
  try {
    await api('/inventario/categorias-insumo', { method: 'POST', body: JSON.stringify({ nombre }) });
    input.value = '';
    await loadCategoriasInsumo();
    populateCatInsumoSelect();
    renderCatInsumoList();
    showToast('Categoría creada');
  } catch { /* handled */ }
}

async function eliminarCategoriaInsumo(id) {
  if (!confirm('¿Eliminar esta categoría?')) return;
  try {
    await api(`/inventario/categorias-insumo/${id}`, { method: 'DELETE' });
    await loadCategoriasInsumo();
    populateCatInsumoSelect();
    renderCatInsumoList();
    loadInsumos();
  } catch { /* handled */ }
}

/* --- Unidad Medida Subpanel --- */
function toggleUnidadPanel() {
  const panel = document.getElementById('unidad-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  if (panel.style.display === 'block') renderUnidadList();
}

function renderUnidadList() {
  const list = document.getElementById('unidad-list');
  list.innerHTML = state.unidadesMedida.map(u =>
    `<div class="inline-list-item">
      <span>${u.nombre} (${u.abreviatura})</span>
      <button type="button" class="btn-delete-inline" onclick="eliminarUnidadMedida(${u.id})" title="Eliminar">✕</button>
    </div>`
  ).join('') || '<span style="font-size:12px;color:var(--text-muted);">No hay unidades</span>';
}

async function guardarUnidadMedida() {
  const nombreInput = document.getElementById('new-unidad-nombre');
  const abrevInput = document.getElementById('new-unidad-abrev');
  const nombre = nombreInput.value.trim();
  const abreviatura = abrevInput.value.trim();
  if (!nombre) return showToast('Ingresa el nombre', 'warning');
  if (!abreviatura) return showToast('Ingresa la abreviatura', 'warning');
  try {
    await api('/inventario/unidades-medida', { method: 'POST', body: JSON.stringify({ nombre, abreviatura }) });
    nombreInput.value = '';
    abrevInput.value = '';
    await loadUnidadesMedida();
    populateUnidadSelect();
    renderUnidadList();
    showToast('Unidad creada');
  } catch { /* handled */ }
}

async function eliminarUnidadMedida(id) {
  if (!confirm('¿Eliminar esta unidad de medida?')) return;
  try {
    await api(`/inventario/unidades-medida/${id}`, { method: 'DELETE' });
    await loadUnidadesMedida();
    populateUnidadSelect();
    renderUnidadList();
    loadInsumos();
  } catch { /* handled */ }
}

/* =========================================================================
   Personal & Nómina
   ========================================================================= */
async function loadPersonal() {
  try {
    const [empleados, usuarios] = await Promise.all([
      api('/personal/empleados'),
      api('/personal/usuarios'),
    ]);
    state.empleados = empleados;
    state.usuarios = usuarios;
    renderPersonalTable(empleados, usuarios);
  } catch { renderPersonalTable([]); }
}

function renderPersonalTable(empleados, usuarios) {
  const container = document.getElementById('personal-table-container');
  const userMap = {};
  (usuarios || []).forEach(u => { userMap[u.empleado_id] = u; });

  if (!empleados || empleados.length === 0) {
    container.innerHTML = '<p class="text-center text-muted" style="padding:32px;">No hay empleados registrados</p>';
    return;
  }
  container.innerHTML = `
    <table class="employee-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Nombre Completo</th>
          <th>Cédula</th>
          <th>Teléfono</th>
          <th>Puesto</th>
          <th>Salario Base</th>
          <th>Fecha Ingreso</th>
          <th>Estado</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${empleados.map(e => {
          const user = userMap[e.id];
          const username = user?.username || '';
          return `
          <tr>
            <td>${e.id}</td>
            <td style="font-weight:600;">${e.nombre} ${e.apellido}</td>
            <td>${e.cedula_identidad}</td>
            <td>${e.telefono || '—'}</td>
            <td>${e.puesto?.nombre || '—'}</td>
            <td class="salary-cell">C$${parseFloat(e.salario_base || e.puesto?.salario_base || 0).toFixed(2)}</td>
            <td>${e.fecha_ingreso || '—'}</td>
            <td>
              <span class="nh-status ${e.activo ? 'nh-status-pagado' : 'nh-status-pendiente'}">
                ${e.activo ? 'Activo' : 'Inactivo'}
              </span>
            </td>
            <td>
              <div style="display:flex;gap:4px;flex-wrap:wrap;">
                <button class="btn-action-action" onclick="openAsistenciasModal(${e.id}, '${(e.nombre + ' ' + e.apellido).replace(/'/g, "\\'")}')" title="Ver asistencias">🕒</button>
                ${user ? `<button class="btn-action-action" onclick="openResetPasswordModal(${user.id}, '${user.username}')" title="Restablecer contraseña">🔑</button>` : ''}
                <button class="btn-nomina" onclick="openNominaModal(${e.id}, '${(e.nombre + ' ' + e.apellido).replace(/'/g, "\\'")}')">
                  📊 Nómina
                </button>
              </div>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

let nominaModalEmpleadoId = null;

function openNominaModal(empleadoId, nombre) {
  nominaModalEmpleadoId = empleadoId;
  state.nominaActual = null;
  document.getElementById('nomina-employee-name').textContent = nombre;
  document.getElementById('nomina-fecha-inicio').value = '';
  document.getElementById('nomina-fecha-fin').value = '';
  document.getElementById('nomina-result').style.display = 'none';
  document.getElementById('modal-nomina').classList.add('show');
  loadNominaHistorial(empleadoId);
}

function closeNominaModal() {
  document.getElementById('modal-nomina').classList.remove('show');
  nominaModalEmpleadoId = null;
  state.nominaActual = null;
}

async function calcularNomina() {
  const fechaInicio = document.getElementById('nomina-fecha-inicio').value;
  const fechaFin = document.getElementById('nomina-fecha-fin').value;

  if (!fechaInicio || !fechaFin) return showToast('Selecciona ambas fechas', 'warning');
  if (!nominaModalEmpleadoId) return showToast('Error: no se identificó el empleado', 'error');

  const btn = document.getElementById('btn-calcular-nomina');
  btn.disabled = true;
  btn.textContent = '⏳ Calculando…';

  try {
    const result = await api('/nomina/calcular', {
      method: 'POST',
      body: JSON.stringify({
        empleado_id: nominaModalEmpleadoId,
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
      }),
    });

    state.nominaActual = result;
    renderNominaResult(result);
    showToast('Nómina calculada con éxito', 'success');
    loadNominaHistorial(nominaModalEmpleadoId);
  } catch { /* handled by api() */ }
  finally {
    btn.disabled = false;
    btn.textContent = '🧮 Calcular Nómina';
  }
}

function renderNominaResult(data) {
  const resultDiv = document.getElementById('nomina-result');
  resultDiv.style.display = 'block';

  document.getElementById('nomina-periodo-text').textContent =
    `${data.fecha_inicio} al ${data.fecha_fin}`;

  const horasNormales = parseFloat(data.salario_quincenal_teorico) > 0
    ? 'Ver cálculo detallado'
    : '0.00 h';

  document.getElementById('nomina-horas-normales').textContent = horasNormales;
  document.getElementById('nomina-pago-normales').textContent =
    `C$${(parseFloat(data.salario_quincenal_teorico) - parseFloat(data.pago_horas_extras)).toFixed(2)}`;
  document.getElementById('nomina-horas-extras').textContent =
    `${parseFloat(data.total_horas_extras).toFixed(2)} h`;
  document.getElementById('nomina-pago-extras').textContent =
    `C$${parseFloat(data.pago_horas_extras).toFixed(2)}`;

  document.getElementById('nomina-neto-display').textContent =
    `C$${parseFloat(data.pago_neto).toFixed(2)}`;

  document.getElementById('nomina-detalle-panel').style.display = 'none';
  document.getElementById('nomina-detalle-content').innerHTML = '';

  const payBtn = document.getElementById('btn-pagar-nomina');
  if (data.estado === 'PAGADO') {
    payBtn.disabled = true;
    payBtn.textContent = '✅ Ya Pagado';
  } else {
    payBtn.disabled = false;
    payBtn.textContent = '💵 Registrar Pago';
  }
}

async function toggleNominaDetalle() {
  const panel = document.getElementById('nomina-detalle-panel');
  if (panel.style.display === 'block') {
    panel.style.display = 'none';
    return;
  }

  const data = state.nominaActual;
  if (!data) return;

  const content = document.getElementById('nomina-detalle-content');
  content.innerHTML = '<span style="color:#6b7280;">Cargando detalle…</span>';
  panel.style.display = 'block';

  try {
    const asistencias = await api(
      `/asistencia/empleados/${data.empleado_id}/historial?fecha_inicio=${data.fecha_inicio}&fecha_fin=${data.fecha_fin}`
    );

    if (!asistencias || asistencias.length === 0) {
      content.innerHTML = '<span style="color:#6b7280;">Sin registros en este período.</span>';
      return;
    }

    let totalHoras = 0;
    let diasTrabajados = 0;
    const rows = asistencias.map(a => {
      const entrada = new Date(a.hora_entrada_real);
      const salida = a.hora_salida_real ? new Date(a.hora_salida_real) : null;
      let horasTrabajadas = 0;
      if (salida) {
        horasTrabajadas = (salida - entrada) / 3600000;
        totalHoras += horasTrabajadas;
        diasTrabajados++;
      }
      const he = parseFloat(a.horas_extras || 0);
      const hNorm = Math.max(0, horasTrabajadas - he);
      const fecha = a.fecha;
      return `<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #e5e7eb;">
        <span>${fecha}</span>
        <span>${hNorm.toFixed(1)}h norm + ${he.toFixed(1)}h ext = ${horasTrabajadas.toFixed(1)}h</span>
      </div>`;
    }).join('');

    content.innerHTML = `
      <div style="display:flex;gap:16px;margin-bottom:8px;font-weight:600;">
        <span>Días trabajados: <b>${diasTrabajados}</b></span>
        <span>Total horas: <b>${totalHoras.toFixed(2)}h</b></span>
      </div>
      <div style="max-height:160px;overflow-y:auto;">${rows}</div>
    `;
  } catch {
    content.innerHTML = '<span style="color:#E63946;">Error al cargar el detalle.</span>';
  }
}

async function pagarNomina() {
  if (!state.nominaActual) return showToast('No hay nómina seleccionada', 'error');

  const btn = document.getElementById('btn-pagar-nomina');
  btn.disabled = true;
  btn.textContent = '⏳ Procesando…';

  try {
    const result = await api(`/nomina/${state.nominaActual.id}/pagar`, {
      method: 'PUT',
    });
    state.nominaActual = result;
    renderNominaResult(result);
    showToast('Pago registrado con éxito', 'success');
    loadNominaHistorial(nominaModalEmpleadoId);
  } catch { /* handled by api() */ }
  finally {
    btn.disabled = false;
    btn.textContent = '💵 Registrar Pago';
  }
}

async function loadNominaHistorial(empleadoId) {
  const container = document.getElementById('nomina-history-list');
  container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:16px;">Cargando historial…</p>';

  try {
    const nominas = await api(`/nomina/empleado/${empleadoId}`);
    renderNominaHistorial(nominas);
  } catch {
    container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:16px;">Error al cargar historial</p>';
  }
}

function renderNominaHistorial(nominas) {
  const container = document.getElementById('nomina-history-list');

  if (!nominas || nominas.length === 0) {
    container.innerHTML = '<div class="nomina-empty">📋 Sin nóminas registradas para este empleado</div>';
    return;
  }

  container.innerHTML = nominas.map(n => {
    const esPagado = n.estado === 'PAGADO';
    const statusClass = esPagado ? 'nh-status-pagado' : 'nh-status-pendiente';
    const statusText = esPagado ? 'PAGADA' : 'PENDIENTE';
    const paidDate = n.fecha_pago
      ? `Pagado: ${new Date(n.fecha_pago).toLocaleDateString('es-CO')}`
      : '';

    return `
      <div class="nomina-history-item">
        <div class="nh-period">
          <div class="nh-dates">📅 ${n.fecha_inicio} — ${n.fecha_fin}</div>
          ${paidDate ? `<div class="nh-paid">${paidDate}</div>` : ''}
        </div>
        <div class="nh-amount">C$${parseFloat(n.pago_neto).toFixed(2)}</div>
        <span class="nh-status ${statusClass}">${statusText}</span>
      </div>`;
  }).join('');
}

/* =========================================================================
   Nuevo Empleado (Modal)
   ========================================================================= */
let puestosCache = [];

async function loadPuestos() {
  if (puestosCache.length > 0) return;
  try { puestosCache = await api('/personal/puestos'); } catch { puestosCache = []; }
}

function populatePuestoSelect() {
  const sel = document.getElementById('ne-puesto');
  if (!sel) return;
  sel.innerHTML = '<option value="">Seleccionar puesto…</option>';
  puestosCache.forEach(p => {
    sel.innerHTML += `<option value="${p.id}">${p.nombre}</option>`;
  });
}

function openNuevoEmpleadoModal() {
  document.getElementById('nuevo-empleado-form').reset();
  document.getElementById('modal-nuevo-empleado').classList.add('show');
}

function closeNuevoEmpleadoModal() {
  document.getElementById('modal-nuevo-empleado').classList.remove('show');
}

async function saveNuevoEmpleado(e) {
  e.preventDefault();
  const nombre = document.getElementById('ne-nombre').value.trim();
  const apellido = document.getElementById('ne-apellido').value.trim();
  const cedula = document.getElementById('ne-cedula').value.trim();
  const telefono = document.getElementById('ne-telefono').value.trim();
  const puesto_id = parseInt(document.getElementById('ne-puesto').value);
  const salario = parseFloat(document.getElementById('ne-salario').value);
  const username = document.getElementById('ne-username').value.trim();
  const password = document.getElementById('ne-password').value;
  const rol = document.getElementById('ne-rol').value;

  if (!nombre || !apellido || !cedula) return showToast('Completa nombre, apellido y cédula', 'warning');
  if (!puesto_id) return showToast('Selecciona un puesto', 'warning');
  if (!salario || salario <= 0) return showToast('Ingresa un salario válido', 'warning');
  if (!username || username.length < 3) return showToast('El usuario debe tener al menos 3 caracteres', 'warning');
  if (!password || password.length < 6) return showToast('La contraseña debe tener al menos 6 caracteres', 'warning');
  if (!rol) return showToast('Selecciona un rol', 'warning');

  try {
    const empleado = await api('/personal/empleados', {
      method: 'POST',
      body: JSON.stringify({ nombre, apellido, cedula_identidad: cedula, telefono: telefono || null, puesto_id, salario_base: salario }),
    });

    await api('/personal/usuarios', {
      method: 'POST',
      body: JSON.stringify({ username, password, rol, empleado_id: empleado.id }),
    });

    showToast('Empleado y usuario creados con éxito', 'success');
    closeNuevoEmpleadoModal();
    loadPersonal();
  } catch { /* handled by api() */ }
}

/* =========================================================================
   Restablecer Contraseña
   ========================================================================= */
let resetPwdUsuarioId = null;

function openResetPasswordModal(usuarioId, username) {
  resetPwdUsuarioId = usuarioId;
  document.getElementById('reset-pwd-username').textContent = username || `Usuario #${usuarioId}`;
  document.getElementById('reset-pwd-new').value = '';
  document.getElementById('modal-reset-password').classList.add('show');
}

function closeResetPasswordModal() {
  document.getElementById('modal-reset-password').classList.remove('show');
  resetPwdUsuarioId = null;
}

async function confirmResetPassword() {
  const nuevaPassword = document.getElementById('reset-pwd-new').value;
  if (!nuevaPassword || nuevaPassword.length < 6) {
    return showToast('La contraseña debe tener al menos 6 caracteres', 'warning');
  }
  if (!resetPwdUsuarioId) return showToast('Error: no se identificó el usuario', 'error');

  try {
    await api(`/personal/usuarios/${resetPwdUsuarioId}/reset-password`, {
      method: 'PUT',
      body: JSON.stringify({ nueva_password: nuevaPassword }),
    });
    showToast('Contraseña restablecida con éxito', 'success');
    closeResetPasswordModal();
  } catch { /* handled by api() */ }
}

/* =========================================================================
   Asistencias del Empleado
   ========================================================================= */
let asisEmpleadoId = null;

function openAsistenciasModal(empleadoId, nombre) {
  asisEmpleadoId = empleadoId;
  document.getElementById('asis-employee-name').textContent = nombre;
  document.getElementById('asis-table-container').innerHTML =
    '<p style="text-align:center;color:#9ca3af;padding:24px;">Cargando asistencias…</p>';
  document.getElementById('modal-asistencias').classList.add('show');
  loadAsistenciasEmpleado(empleadoId);
}

function closeAsistenciasModal() {
  document.getElementById('modal-asistencias').classList.remove('show');
  asisEmpleadoId = null;
}

async function loadAsistenciasEmpleado(empleadoId) {
  const container = document.getElementById('asis-table-container');
  try {
    const asistencias = await api(`/asistencia/empleados/${empleadoId}/historial`);
    renderAsistenciasTable(asistencias, container);
  } catch {
    container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:24px;">Error al cargar asistencias</p>';
  }
}

function renderAsistenciasTable(asistencias, container) {
  if (!asistencias || asistencias.length === 0) {
    container.innerHTML = '<div class="nomina-empty">📋 Sin registros de asistencia</div>';
    return;
  }
  container.innerHTML = `
    <table class="employee-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Fecha</th>
          <th>Entrada</th>
          <th>Salida</th>
          <th>Horas Extras</th>
          <th>Auditoría</th>
          <th>Turno</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        ${asistencias.map(a => {
          const entrada = new Date(a.hora_entrada_real).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
          const salida = a.hora_salida_real
            ? new Date(a.hora_salida_real).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
            : '<span style="color:#E63946;font-weight:600;">Activo</span>';
          const ot = parseFloat(a.horas_extras);
          const otBadge = ot > 0
            ? `<span style="background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;">${ot.toFixed(2)}h</span>`
            : '<span style="color:#9ca3af;">0.00h</span>';
          const auditInfo = a.horas_extras_originales != null
            ? `<span title="Original: ${parseFloat(a.horas_extras_originales).toFixed(2)}h\nMotivo: ${a.motivo_modificacion || '—'}\nModificado por: Usuario #${a.modificado_por}" style="cursor:help;background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:999px;font-size:11px;font-weight:600;">✏️ Auditado</span>`
            : '<span style="color:#9ca3af;font-size:11px;">—</span>';
          return `
            <tr>
              <td>${a.id}</td>
              <td>${a.fecha}</td>
              <td>${entrada}</td>
              <td>${salida}</td>
              <td>${otBadge}</td>
              <td>${auditInfo}</td>
              <td style="font-size:12px;color:#6b7280;">Turno #${a.turno_id}</td>
              <td>
                <button class="btn-action-action" onclick="openEditOTModal(${a.id}, '${a.fecha}', ${a.horas_extras})" title="Editar horas extras">🕒</button>
              </td>
            </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

/* =========================================================================
   Editar Horas Extras
   ========================================================================= */
let editOTAsistenciaId = null;

function openEditOTModal(asistenciaId, fecha, horasActuales) {
  editOTAsistenciaId = asistenciaId;
  document.getElementById('edit-ot-fecha').textContent = fecha;
  document.getElementById('edit-ot-current').textContent = parseFloat(horasActuales).toFixed(2);
  document.getElementById('edit-ot-valor').value = parseFloat(horasActuales).toFixed(2);
  document.getElementById('edit-ot-motivo').value = '';
  document.getElementById('confirm-edit-ot').disabled = true;
  document.getElementById('modal-edit-ot').classList.add('show');

  const motivoInput = document.getElementById('edit-ot-motivo');
  const handler = () => {
    document.getElementById('confirm-edit-ot').disabled = !motivoInput.value.trim();
  };
  motivoInput.removeEventListener('input', motivoInput._otHandler);
  motivoInput._otHandler = handler;
  motivoInput.addEventListener('input', handler);
}

function closeEditOTModal() {
  document.getElementById('modal-edit-ot').classList.remove('show');
  editOTAsistenciaId = null;
}

async function confirmEditOT() {
  const horas = parseFloat(document.getElementById('edit-ot-valor').value);
  const motivo = document.getElementById('edit-ot-motivo').value.trim();

  if (isNaN(horas) || horas < 0) return showToast('Ingresa un valor válido para horas extras', 'warning');
  if (!motivo) return showToast('El motivo es obligatorio para auditoría', 'warning');
  if (!editOTAsistenciaId) return showToast('Error: no se identificó la asistencia', 'error');

  try {
    await api(`/asistencia/${editOTAsistenciaId}/horas-extras`, {
      method: 'PUT',
      body: JSON.stringify({ horas_extras: horas, motivo }),
    });
    showToast('Horas extras actualizadas con auditoría registrada', 'success');
    closeEditOTModal();
    if (asisEmpleadoId) loadAsistenciasEmpleado(asisEmpleadoId);
  } catch { /* handled by api() */ }
}

/* =========================================================================
   Dashboard (Cierre de Caja) — Reportes Visuales
   ========================================================================= */
let pieChartInstance = null;
let barChartInstance = null;

const PERIODOS_MAP = {
  diario: 'Hoy',
  semanal: 'Esta Semana',
  quincenal: 'Quincenal',
  mensual: 'Este Mes',
};

async function loadCierreReportes(periodo) {
  if (!periodo) periodo = 'diario';
  const grid = document.getElementById('cierre-summary-grid');
  grid.style.opacity = '0.5';

  try {
    const data = await api(`/reportes/cierre?periodo=${periodo}`);
    state.cierreData = data;
    renderCierreReportes(data);
  } catch {
    renderCierreReportes(null);
  } finally {
    grid.style.opacity = '1';
  }
}

function renderCierreReportes(data) {
  if (!data) {
    ['cc-ingresos', 'cc-nomina', 'cc-insumos', 'cc-gastos-op', 'cc-utilidad'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'C$0.00';
    });
    document.getElementById('cierre-periodo-label').textContent = '';
    document.getElementById('cierre-ordenes-info').textContent = '';
    document.getElementById('cierre-top-list').innerHTML = '';
    destroyCharts();
    return;
  }

  const fmt = v => 'C$' + parseFloat(v).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const utilPositiva = data.utilidad_neta >= 0;

  document.getElementById('cc-ingresos').textContent = fmt(data.ingresos_totales);
  document.getElementById('cc-nomina').textContent = fmt(data.gastos_nomina);
  document.getElementById('cc-insumos').textContent = fmt(data.costo_insumos);
  document.getElementById('cc-gastos-op').textContent = fmt(data.gastos_operativos);

  const utilEl = document.getElementById('cc-utilidad');
  utilEl.textContent = fmt(data.utilidad_neta);
  const utilCard = document.querySelector('.cierre-card--utilidad');
  utilCard.classList.toggle('cierre-card--positive', utilPositiva);
  utilCard.classList.toggle('cierre-card--negative', !utilPositiva);

  document.getElementById('cierre-periodo-label').textContent =
    `${PERIODOS_MAP[data.periodo] || data.periodo} — ${data.fecha_inicio} al ${data.fecha_fin}`;
  document.getElementById('cierre-ordenes-info').textContent =
    `${data.ordenes_pagadas} pagadas · ${data.ordenes_canceladas} canceladas`;

  renderPieChart(data);
  renderBarChart(data.top_platillos || []);
  renderTopList(data.top_platillos || []);
}

function destroyCharts() {
  if (pieChartInstance) { pieChartInstance.destroy(); pieChartInstance = null; }
  if (barChartInstance) { barChartInstance.destroy(); barChartInstance = null; }
}

function renderPieChart(data) {
  const ctx = document.getElementById('chart-pie-costos');
  if (!ctx) return;
  if (pieChartInstance) pieChartInstance.destroy();

  const labels = ['Gastos Nómina', 'Costo Insumos', 'Gastos Operativos'];
  const values = [data.gastos_nomina, data.costo_insumos, data.gastos_operativos];
  const colors = ['#E63946', '#FFB703', '#FD7E14'];

  if (data.utilidad_neta > 0) {
    labels.push('Utilidad Neta');
    values.push(data.utilidad_neta);
    colors.push('#2A9D8F');
  }

  pieChartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values.map(v => Math.max(v, 0)),
        backgroundColor: colors,
        borderColor: '#ffffff',
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.label}: C$${parseFloat(ctx.parsed).toLocaleString('es-CO', { minimumFractionDigits: 2 })}`,
          },
        },
      },
    },
  });
}

function renderBarChart(topPlatillos) {
  const ctx = document.getElementById('chart-bar-platillos');
  if (!ctx) return;
  if (barChartInstance) barChartInstance.destroy();

  if (!topPlatillos.length) {
    barChartInstance = null;
    return;
  }

  const labels = topPlatillos.map(p => p.nombre.length > 18 ? p.nombre.slice(0, 16) + '…' : p.nombre);
  const quantities = topPlatillos.map(p => p.cantidad_vendida);
  const revenues = topPlatillos.map(p => p.ingresos_generados);

  barChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Unidades Vendidas',
          data: quantities,
          backgroundColor: '#003366',
          borderRadius: 6,
          yAxisID: 'y',
        },
        {
          label: 'Ingresos (C$)',
          data: revenues,
          backgroundColor: 'rgba(42, 157, 143, 0.7)',
          borderRadius: 6,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: ctx => {
              if (ctx.datasetIndex === 1) return `Ingresos: C$${parseFloat(ctx.parsed.y).toLocaleString('es-CO')}`;
              return `Vendidos: ${ctx.parsed.y}`;
            },
          },
        },
      },
      scales: {
        y: { beginAtZero: true, position: 'left', title: { display: true, text: 'Unidades' } },
        y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Ingresos ($)' } },
      },
    },
  });
}

function renderTopList(topPlatillos) {
  const container = document.getElementById('cierre-top-list');
  if (!topPlatillos.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = `
    <h4 class="cierre-top-title">🍽️ Top 5 Platillos</h4>
    <div class="cierre-top-items">
      ${topPlatillos.map((p, i) => `
        <div class="cierre-top-item">
          <span class="cierre-top-rank">#${i + 1}</span>
          <span class="cierre-top-name">${p.nombre}</span>
          <span class="cierre-top-qty">${p.cantidad_vendida} uds</span>
          <span class="cierre-top-rev">C$${parseFloat(p.ingresos_generados).toLocaleString('es-CO')}</span>
        </div>
      `).join('')}
    </div>`;
}

/* =========================================================================
   Occupied Table Detail — Modal + Pre-Cuenta + Cerrar Cuenta
   ========================================================================= */
function openDetalleMesaOcupada(mesaId) {
  const mesa = state.tables.find(t => t.id === mesaId);
  if (!mesa) return showToast('Mesa no encontrada', 'error');

  state.currentOcupada = { mesaId, orden: null };

  document.getElementById('oc-mesa-numero').textContent = mesa.numero;
  document.getElementById('oc-items-list').innerHTML =
    '<p style="text-align:center;color:#9ca3af;padding:16px;">Cargando orden…</p>';
  ['oc-subtotal', 'oc-total'].forEach(id => {
    document.getElementById(id).textContent = 'C$0.00';
  });

  document.getElementById('modal-detalle-mesa-ocupada').classList.add('show');
  loadOcupadaOrden(mesaId);
}

function closeDetalleMesaOcupada() {
  document.getElementById('modal-detalle-mesa-ocupada').classList.remove('show');
  state.currentOcupada = null;
}

async function loadOcupadaOrden(mesaId) {
  try {
    const ordenes = await api('/ordenes/?mesa_id=' + mesaId + '&estado=PENDIENTE');
    let orden = null;
    if (ordenes.length > 0) {
      orden = ordenes[0];
    } else {
      const ordPrep = await api('/ordenes/?mesa_id=' + mesaId + '&estado=PREPARANDO');
      if (ordPrep.length > 0) orden = ordPrep[0];
    }
    if (!orden) {
      const all = await api('/ordenes/?mesa_id=' + mesaId);
      const activa = all.find(o => !['PAGADA', 'CANCELADA'].includes(o.estado));
      orden = activa || null;
    }

    if (!orden) {
      document.getElementById('oc-items-list').innerHTML =
        '<p style="text-align:center;color:#9ca3af;padding:16px;">No se encontró orden activa para esta mesa.</p>';
      return;
    }

    state.currentOcupada.orden = orden;
    document.getElementById('oc-orden-id').textContent = orden.id;
    renderOcItems(orden);
  } catch {
    document.getElementById('oc-items-list').innerHTML =
      '<p style="text-align:center;color:#E63946;padding:16px;">Error al cargar la orden.</p>';
  }
}

function renderOcItems(orden) {
  const list = document.getElementById('oc-items-list');
  const detalles = orden.detalles || [];

  if (detalles.length === 0) {
    list.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:12px;">Sin ítems registrados.</p>';
  } else {
    list.innerHTML = detalles.map(d => {
      const producto = state.menuItems.find(mi => mi.id === d.producto_id);
      const nombre = producto ? producto.nombre : `#${d.producto_id}`;
      const subtotal = parseFloat(d.precio_unitario) * d.cantidad;
      return `
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f3f4f6;">
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;">${nombre}</div>
            <div style="font-size:12px;color:#6b7280;">${d.cantidad} × C$${parseFloat(d.precio_unitario).toFixed(2)}</div>
          </div>
          <div style="font-weight:600;font-size:14px;color:var(--azul-marino);">C$${subtotal.toFixed(2)}</div>
        </div>`;
    }).join('');
  }

  const total = parseFloat(orden.total || 0);
  document.getElementById('oc-subtotal').textContent = `C$${total.toFixed(2)}`;
  document.getElementById('oc-total').textContent = `C$${total.toFixed(2)}`;
}

async function agregarAlPedido() {
  const oc = state.currentOcupada;
  if (!oc || !oc.orden) return;

  closeDetalleMesaOcupada();
  const mesa = state.tables.find(t => t.id === oc.mesaId);
  openOrderModal(oc.mesaId, mesa?.numero || '?');
  state.currentOrder._addToExisting = true;
  state.currentOrder._ordenId = oc.orden.id;
}

function openPreCuenta() {
  const oc = state.currentOcupada;
  if (!oc || !oc.orden) return;

  const orden = oc.orden;
  const detalles = orden.detalles || [];
  const mesa = state.tables.find(t => t.id === oc.mesaId);
  const now = new Date();
  const fecha = now.toLocaleDateString('es-CO');
  const hora = now.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
  const total = parseFloat(orden.total || 0);

  let lines = [];
  lines.push('════════════════════════════════');
  lines.push('    🍽️  SAZÓN CARIBEÑO');
  lines.push('════════════════════════════════');
  lines.push(`Fecha: ${fecha}  Hora: ${hora}`);
  lines.push(`Mesa: ${mesa?.numero || '—'}   Orden: #${orden.id}`);
  lines.push('────────────────────────────────');

  detalles.forEach(d => {
    const producto = state.menuItems.find(mi => mi.id === d.producto_id);
    const nombre = producto ? producto.nombre : `#${d.producto_id}`;
    const lineTotal = parseFloat(d.precio_unitario) * d.cantidad;
    lines.push(`${d.cantidad}  ${nombre}`);
    lines.push(`    C$${parseFloat(d.precio_unitario).toFixed(2)} c/u = C$${lineTotal.toFixed(2)}`);
  });

  lines.push('────────────────────────────────');
  lines.push(`TOTAL:            C$${total.toFixed(2)}`);
  lines.push('════════════════════════════════');
  lines.push('    ¡Gracias por su preferencia!');

  const content = document.getElementById('pre-cuenta-content');
  content.innerHTML = `<pre style="margin:0;white-space:pre-wrap;font-family:monospace;font-size:13px;">${lines.join('\n')}</pre>`;
  document.getElementById('modal-pre-cuenta').classList.add('show');
}

function closePreCuenta() {
  document.getElementById('modal-pre-cuenta').classList.remove('show');
}

async function cerrarCuenta() {
  const oc = state.currentOcupada;
  if (!oc || !oc.orden) return;

  if (!confirm('¿Cerrar cuenta y liberar esta mesa?')) return;

  try {
    await api(`/ordenes/${oc.orden.id}/estado`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: 'PAGADA' }),
    });

    await api(`/salon/mesas/${oc.mesaId}`, {
      method: 'PUT',
      body: JSON.stringify({ estado: 'LIBRE' }),
    });

    const mesa = state.tables.find(t => t.id === oc.mesaId);
    if (mesa) mesa.estado = 'LIBRE';

    showToast('Cuenta cerrada y mesa liberada', 'success');
    closeDetalleMesaOcupada();
    renderTables(state.tables);
  } catch (err) {
    showToast(err.message || 'Error al cerrar cuenta', 'error');
  }
}

/* =========================================================================
   Daily Orders History — Caja Screen
   ========================================================================= */
async function loadHistorialOrdenesDia() {
  const container = document.getElementById('historial-ordenes-list');
  if (!container) return;
  container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:12px;">Cargando historial…</p>';

  try {
    const data = await api('/caja/historial-diario');
    renderHistorialOrdenesDia(data.ordenes || []);
  } catch {
    container.innerHTML = '<p style="text-align:center;color:#E63946;padding:12px;">Error al cargar historial.</p>';
  }
}

function renderHistorialOrdenesDia(ordenes) {
  const container = document.getElementById('historial-ordenes-list');
  if (!container) return;

  if (ordenes.length === 0) {
    container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:12px;">No hay órdenes pagadas hoy.</p>';
    return;
  }

  const sorted = [...ordenes].sort((a, b) => b.id - a.id);
  container.innerHTML = `
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr style="border-bottom:2px solid #e5e7eb;">
            <th style="text-align:left;padding:6px 8px;color:#6b7280;"># Orden</th>
            <th style="text-align:left;padding:6px 8px;color:#6b7280;">Mesa</th>
            <th style="text-align:left;padding:6px 8px;color:#6b7280;">Estado</th>
            <th style="text-align:right;padding:6px 8px;color:#6b7280;">Total</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map(o => {
            const mesa = state.tables.find(t => t.id === o.mesa_id);
            return `
              <tr style="border-bottom:1px solid #f3f4f6;">
                <td style="padding:6px 8px;font-weight:600;">#${o.id}</td>
                <td style="padding:6px 8px;">Mesa ${mesa?.numero || o.mesa_id}</td>
                <td style="padding:6px 8px;">
                  <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600;
                    ${o.estado === 'PAGADA' ? 'background:#d1fae5;color:#065f46;' : 'background:#fee2e2;color:#991b1b;'}">
                    ${o.estado}
                  </span>
                </td>
                <td style="padding:6px 8px;text-align:right;font-weight:700;color:var(--azul-marino);">C$${parseFloat(o.total).toFixed(2)}</td>
              </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;
}

function clearHistorialOrdenesDia() {
  const container = document.getElementById('historial-ordenes-list');
  if (container) container.innerHTML = '<p style="text-align:center;color:#9ca3af;padding:12px;">Historial limpiado tras cierre de caja.</p>';
}

/* =========================================================================
   Ejecutar Cierre de Caja
   ========================================================================= */
async function ejecutarCierreCaja() {
  if (!confirm('¿Estás seguro de cerrar la caja? Se archivarán todas las órdenes pagadas del día.')) return;

  const btn = document.getElementById('btn-cerrar-caja');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Cerrando…'; }

  try {
    const data = await api('/caja/cierre', { method: 'POST' });
    showToast(`Caja cerrada: ${data.total_ordenes} órdenes archivadas, C$${parseFloat(data.total_ventas).toFixed(2)} en ventas`, 'success');
    clearHistorialOrdenesDia();
    loadCierreReportes('diario');
  } catch {
    showToast('Error al cerrar la caja', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🔒 Cerrar Caja'; }
  }
}

/* =========================================================================
   Clock
   ========================================================================= */
function updateClock() {
  const now = new Date();
  const time = now.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
  const el1 = document.getElementById('comandero-clock');
  const el2 = document.getElementById('salon-clock');
  if (el1) el1.textContent = time;
  if (el2) el2.textContent = time;
}

/* =========================================================================
   Event Listeners
   ========================================================================= */
document.addEventListener('DOMContentLoaded', () => {
  // Login
  document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const user = document.getElementById('login-username').value.trim();
    const pass = document.getElementById('login-password').value;
    if (!user || !pass) return showToast('Ingresa usuario y contraseña', 'warning');
    await login(user, pass);
  });

  // Sidebar nav
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('nav-locked')) {
        return showToast('Acceso restringido — solo Gerente o Administrador', 'warning');
      }
      navigateTo(btn.dataset.screen);
    });
  });

  // Mobile sidebar toggle
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebarEl = document.getElementById('sidebar');
  sidebarToggle?.addEventListener('click', () => {
    sidebarEl.classList.toggle('open');
    sidebarBackdrop.classList.toggle('show');
    sidebarToggle.classList.toggle('open');
  });
  sidebarBackdrop?.addEventListener('click', () => {
    sidebarEl.classList.remove('open');
    sidebarBackdrop.classList.remove('show');
    sidebarToggle.classList.remove('open');
  });

  // Mobile bottom nav
  document.querySelectorAll('.bottom-nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const screen = btn.dataset.screen;
      if (screen) {
        navigateTo(screen);
      } else if (btn.id === 'bottom-nav-more') {
        const sEl = document.getElementById('sidebar');
        const bEl = document.getElementById('sidebar-backdrop');
        const tEl = document.getElementById('sidebar-toggle');
        sEl.classList.toggle('open');
        bEl.classList.toggle('show');
        tEl.classList.toggle('open');
      }
    });
  });

  // KDS tab filters
  document.querySelectorAll('[data-cocina-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-cocina-tab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      cocinaTab = btn.dataset.cocinaTab;
      renderCocinaCards();
    });
  });

  // KDS refresh
  document.getElementById('btn-refresh-cocina')?.addEventListener('click', loadCocinaOrdenes);

  // Logout
  document.getElementById('btn-logout')?.addEventListener('click', logout);

  // Attendance buttons
  document.getElementById('btn-iniciar-turno')?.addEventListener('click', async () => {
    const select = document.getElementById('turno-select');
    const turnoId = parseInt(select?.value);
    if (!turnoId) return showToast('Selecciona un turno primero', 'warning');
    const btn = document.getElementById('btn-iniciar-turno');
    btn.disabled = true;
    btn.textContent = '⏳ Iniciando…';
    try {
      await iniciarTurno(turnoId);
    } catch { /* handled by iniciarTurno */ }
    finally {
      btn.disabled = false;
      btn.textContent = '▶ Iniciar';
    }
  });
  document.getElementById('btn-finalizar-turno')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-finalizar-turno');
    btn.disabled = true;
    btn.textContent = '⏳ Finalizando…';
    try {
      await finalizarTurno();
    } catch { /* handled by finalizarTurno */ }
    finally {
      btn.disabled = false;
      btn.textContent = '⏹ Finalizar';
    }
  });

  // Cierre de Caja — Period tabs
  document.querySelectorAll('#screen-cuenta .period-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('#screen-cuenta .period-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      loadCierreReportes(tab.dataset.periodo);
      loadHistorialOrdenesDia();
    });
  });

  // Cierre de Caja — Botón cerrar
  document.getElementById('btn-cerrar-caja')?.addEventListener('click', ejecutarCierreCaja);

  // Menu Management
  document.getElementById('btn-new-dish')?.addEventListener('click', async () => {
    await loadCategories();
    populateCategorySelect();
    openNewDishModal();
  });
  document.getElementById('close-dish-modal')?.addEventListener('click', closeDishModal);
  document.getElementById('cancel-dish-modal')?.addEventListener('click', closeDishModal);
  document.getElementById('dish-form')?.addEventListener('submit', saveDish);

  // Dish toggle
  document.getElementById('dish-active-btn')?.addEventListener('click', () => setDishToggle(true));
  document.getElementById('dish-inactive-btn')?.addEventListener('click', () => setDishToggle(false));

  // Add recipe row
  document.getElementById('btn-add-recipe-row')?.addEventListener('click', () => addRecipeRow());

  // Categorías panel toggle + CRUD
  document.getElementById('btn-toggle-cat-panel')?.addEventListener('click', () => { renderCatList(); toggleCatPanel(); });
  document.getElementById('btn-guardar-cat')?.addEventListener('click', guardarCategoriaMenu);
  document.getElementById('cat-nueva-nombre')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarCategoriaMenu(); } });

  // Inventory
  document.getElementById('btn-new-insumo')?.addEventListener('click', openNewInsumoModal);
  document.getElementById('close-insumo-modal')?.addEventListener('click', closeInsumoModal);
  document.getElementById('cancel-insumo-modal')?.addEventListener('click', closeInsumoModal);
  document.getElementById('insumo-form')?.addEventListener('submit', saveInsumo);

  // Inventory subpanels
  document.getElementById('btn-toggle-cat-insumo-panel')?.addEventListener('click', toggleCatInsumoPanel);
  document.getElementById('btn-save-cat-insumo')?.addEventListener('click', guardarCategoriaInsumo);
  document.getElementById('new-cat-insumo-nombre')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarCategoriaInsumo(); } });
  document.getElementById('btn-toggle-unidad-panel')?.addEventListener('click', toggleUnidadPanel);
  document.getElementById('btn-save-unidad')?.addEventListener('click', guardarUnidadMedida);
  document.getElementById('new-unidad-nombre')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarUnidadMedida(); } });
  document.getElementById('new-unidad-abrev')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarUnidadMedida(); } });

  // Stock modal
  document.getElementById('close-stock-modal')?.addEventListener('click', closeStockModal);
  document.getElementById('cancel-stock-modal')?.addEventListener('click', closeStockModal);
  document.getElementById('stock-form')?.addEventListener('submit', saveStock);
  document.getElementById('stock-entrada-btn')?.addEventListener('click', () => setStockType('ENTRADA'));
  document.getElementById('stock-salida-btn')?.addEventListener('click', () => setStockType('SALIDA'));

  // Order modal
  document.getElementById('close-order-modal')?.addEventListener('click', closeOrderModal);
  document.getElementById('cancel-order-modal')?.addEventListener('click', closeOrderModal);
  document.getElementById('confirm-order-modal')?.addEventListener('click', submitOrder);

  // Order modal search
  document.getElementById('order-modal-search')?.addEventListener('input', (e) => {
    filterOrderModalBySearch(e.target.value);
  });

  // Order modal category tabs
  document.querySelectorAll('#order-modal-categories .category-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      filterOrderModalByCategory(tab.dataset.omCat);
    });
  });

  // Gestionar Mesas modal
  document.getElementById('btn-gestion-mesas')?.addEventListener('click', openGestionMesas);
  document.getElementById('close-gestion-mesas')?.addEventListener('click', closeGestionMesas);
  document.getElementById('gestion-guardar-mesa')?.addEventListener('click', guardarMesa);

  // Zonas panel toggle + CRUD
  document.getElementById('btn-toggle-zonas-panel')?.addEventListener('click', toggleZonasPanel);
  document.getElementById('btn-guardar-zona')?.addEventListener('click', guardarZona);
  document.getElementById('zona-nueva-nombre')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); guardarZona(); } });
  document.getElementById('gestion-cancelar-edicion')?.addEventListener('click', () => {
    document.getElementById('gestion-mesa-id').value = '';
    document.getElementById('gestion-mesa-numero').value = '';
    document.getElementById('gestion-mesa-capacidad').value = '4';
    document.getElementById('gestion-form-title').textContent = 'Nueva Mesa';
    document.getElementById('gestion-cancelar-edicion').style.display = 'none';
  });

  // Nómina modal
  document.getElementById('close-nomina-modal')?.addEventListener('click', closeNominaModal);
  document.getElementById('btn-calcular-nomina')?.addEventListener('click', calcularNomina);
  document.getElementById('btn-pagar-nomina')?.addEventListener('click', pagarNomina);

  // Nuevo Empleado modal
  document.getElementById('btn-new-empleado')?.addEventListener('click', async () => {
    await loadPuestos();
    populatePuestoSelect();
    openNuevoEmpleadoModal();
  });
  document.getElementById('close-nuevo-empleado')?.addEventListener('click', closeNuevoEmpleadoModal);
  document.getElementById('cancel-nuevo-empleado')?.addEventListener('click', closeNuevoEmpleadoModal);
  document.getElementById('nuevo-empleado-form')?.addEventListener('submit', saveNuevoEmpleado);

  // Reset Password modal
  document.getElementById('close-reset-password')?.addEventListener('click', closeResetPasswordModal);
  document.getElementById('cancel-reset-password')?.addEventListener('click', closeResetPasswordModal);
  document.getElementById('confirm-reset-password')?.addEventListener('click', confirmResetPassword);

  // Asistencias modal
  document.getElementById('close-asistencias')?.addEventListener('click', closeAsistenciasModal);

  // Editar Horas Extras modal
  document.getElementById('close-edit-ot')?.addEventListener('click', closeEditOTModal);
  document.getElementById('cancel-edit-ot')?.addEventListener('click', closeEditOTModal);
  document.getElementById('confirm-edit-ot')?.addEventListener('click', confirmEditOT);

  // Gastos modal
  document.getElementById('btn-new-gasto')?.addEventListener('click', openGastosModal);
  document.getElementById('close-gasto-modal')?.addEventListener('click', closeGastosModal);
  document.getElementById('cancel-gasto-modal')?.addEventListener('click', closeGastosModal);
  document.getElementById('gasto-form')?.addEventListener('submit', (e) => { e.preventDefault(); guardarGasto(); });

  // Detalle Mesa Ocupada modal
  document.getElementById('close-detalle-mesa-ocupada')?.addEventListener('click', closeDetalleMesaOcupada);
  document.getElementById('btn-agregar-pedido')?.addEventListener('click', agregarAlPedido);
  document.getElementById('btn-pre-cuenta')?.addEventListener('click', openPreCuenta);
  document.getElementById('btn-cerrar-cuenta')?.addEventListener('click', cerrarCuenta);

  // Pre-Cuenta modal
  document.getElementById('close-pre-cuenta')?.addEventListener('click', closePreCuenta);
  document.getElementById('close-pre-cuenta-btn')?.addEventListener('click', closePreCuenta);

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('show');
    });
  });

  // Clock
  updateClock();
  setInterval(updateClock, 30000);

  // Restore session
  if (state.token && state.user) {
    updateUserBadges();
    applyRoleRestrictions();
    showApp();
    showAttendancePanel();
    loadTurnos();
    navigateTo('salon');
    state.heartbeatInterval = setInterval(enviarHeartbeat, 120_000);
  } else {
    showLogin();
  }
});
