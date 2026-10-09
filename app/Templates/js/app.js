/**
 * =========================================================================
 *  Sazón Caribeño POS — App Controller
 *  Vanilla JS SPA with FastAPI backend + sidebar layout
 * =========================================================================
 */

const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000/api/v1'
  : `${location.origin}/api/v1`;

function escHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/* =========================================================================
   State
   ========================================================================= */
const state = {
  token: localStorage.getItem('pos_token') || null,
  user: JSON.parse(localStorage.getItem('pos_user') || 'null'),
  currentScreen: 'salon',
  errorReturnScreen: null,
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
  attendanceSynced: false,
  currentOcupada: null,
  paymentOrder: null,
  paymentBusy: false,
  heartbeatInterval: null,
  sessionPollInterval: null,
  attendanceReminderInterval: null,
  calendarMonth: new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  calendarSelectedDay: calendarDateKey(new Date()),
  calendarMultiSelecting: false,
  calendarSelectedDays: new Set(),
  calendarPressTimer: null,
  calendarSuppressClickDate: null,
  calendarBulkDates: [],
  calendarEvents: [],
  calendarAttendances: [],
  calendarMenuItems: [],
  calendarInsumos: [],
  calendarProveedores: [],
  calendarCatalogsLoaded: false,
  cameras: [],
  cameraUsers: [],
  cameraPeers: new Map(),
  cameraRecordings: new Map(),
  cameraClips: [],
  cameraClipObjectUrl: null,
  notificationsLoading: false,
};

/* =========================================================================
   Date/Time Helpers
   ========================================================================= */
function formatLocalTime(isoStr) {
  if (!isoStr) return '';
  const timePart = String(isoStr).split('T')[1] || '';
  const [h, m] = timePart.split(':').map(Number);
  if (Number.isNaN(h)) return '';
  const ap = h >= 12 ? 'PM' : 'AM';
  const hh = h % 12 || 12;
  return `${String(hh).padStart(2, '0')}:${String(m || 0).padStart(2, '0')} ${ap}`;
}

/* =========================================================================
   Operational notifications
   ========================================================================= */
function actualizarContadoresNotificaciones(count) {
  document.querySelectorAll('button[aria-label="Notificaciones"]').forEach(button => {
    let badge = button.querySelector('.notification-count');
    if (!badge) {
      button.querySelector('span.absolute')?.remove();
      badge = document.createElement('span');
      badge.className = 'notification-count';
      button.appendChild(badge);
    }
    badge.textContent = count > 99 ? '99+' : String(count);
    badge.hidden = count === 0;
    button.setAttribute('aria-expanded', String(!document.getElementById('notifications-panel')?.hidden));
    button.setAttribute('aria-haspopup', 'dialog');
  });
}

function renderNotifications(notifications, errors = []) {
  const list = document.getElementById('notifications-list');
  const summary = document.getElementById('notifications-summary');
  if (!list || !summary) return;

  const count = notifications.length;
  summary.textContent = count
    ? `${count} aviso${count === 1 ? '' : 's'} para revisar`
    : 'Todo tranquilo por ahora';
  actualizarContadoresNotificaciones(count);

  const errorMarkup = errors.map(error => `
    <div class="notification-entry notification-entry-error" role="status">
      <span class="notification-entry-icon material-symbols-outlined" aria-hidden="true">cloud_off</span>
      <span class="notification-entry-copy">
        <strong>${escHtml(error.title)}</strong>
        <span>${escHtml(error.message)}</span>
      </span>
    </div>`).join('');
  const noticesMarkup = notifications.map(item => `
    <button class="notification-entry ${item.urgent ? 'notification-entry-urgent' : ''}" type="button"
            data-notification-screen="${item.screen}">
      <span class="notification-entry-icon material-symbols-outlined" aria-hidden="true">${item.icon}</span>
      <span class="notification-entry-copy">
        <strong>${escHtml(item.title)}</strong>
        <span>${escHtml(item.description)}</span>
      </span>
      <span class="material-symbols-outlined notification-entry-arrow" aria-hidden="true">chevron_right</span>
    </button>`).join('');

  list.innerHTML = errorMarkup + (noticesMarkup || (!errors.length
    ? `<div class="notifications-empty">
         <span class="material-symbols-outlined" aria-hidden="true">task_alt</span>
         <strong>Todo en orden</strong>
         <span>No hay comandas pendientes ni alertas de inventario.</span>
       </div>`
    : ''));
}

async function cargarNotificaciones() {
  const list = document.getElementById('notifications-list');
  if (!list || state.notificationsLoading) return;
  state.notificationsLoading = true;
  const refreshButton = document.getElementById('notifications-refresh');
  if (refreshButton) refreshButton.disabled = true;
  list.setAttribute('aria-busy', 'true');
  list.innerHTML = `
    <div class="notifications-loading" role="status">
      <span class="notification-spinner" aria-hidden="true"></span>
      Cargando avisos del turno…
    </div>`;

  const esGestor = ['Administrador', 'Gerente'].includes(state.user?.rol);
  const requests = [
    ['pending', api('/ordenes/?estado=PENDIENTE')],
    ['preparing', api('/ordenes/?estado=PREPARANDO')],
    ['ready', api('/ordenes/?estado=ENTREGADA')],
  ];
  if (esGestor) requests.push(['stock', api('/inventario/insumos/alertas')]);

  const results = await Promise.allSettled(requests.map(([, request]) => request));
  const data = {};
  const errors = [];
  results.forEach((result, index) => {
    const [key] = requests[index];
    if (result.status === 'fulfilled') {
      data[key] = result.value;
    } else {
      const title = key === 'stock' ? 'No se pudo consultar el inventario' : 'No se pudieron consultar las comandas';
      if (!errors.some(error => error.title === title)) errors.push({
        title,
        message: result.reason?.message || 'Intenta actualizar de nuevo.',
      });
    }
  });

  const notifications = [];
  [['pending', 'Nueva comanda', 'schedule'], ['preparing', 'Comanda en preparación', 'soup_kitchen'], ['ready', 'Lista para servir', 'room_service']]
    .forEach(([key, title, icon]) => {
      (data[key] || []).forEach(order => {
        const mesa = order.mesa_id ? `Mesa ${order.mesa?.numero || order.mesa_id}` : 'Para llevar';
        const minutes = getMinutosTranscurrido(order.fecha_creacion);
        notifications.push({
          screen: 'comandero',
          title: `${title} #${order.id} · ${mesa}`,
          description: `Hace ${getTiempoTranscurrido(order.fecha_creacion)} · ${order.detalles?.length || 0} artículo${order.detalles?.length === 1 ? '' : 's'}`,
          icon,
          urgent: key !== 'ready' && minutes >= 20,
        });
      });
    });
  (data.stock || []).forEach(item => {
    notifications.push({
      screen: 'inventory',
      title: `Stock bajo: ${item.nombre}`,
      description: `${item.cantidad_actual} ${item.unidad_medida} · mínimo ${item.stock_minimo}`,
      icon: 'inventory_2',
      urgent: Number(item.cantidad_actual) <= 0,
    });
  });
  notifications.sort((a, b) => Number(b.urgent) - Number(a.urgent));

  renderNotifications(notifications, errors);
  list.setAttribute('aria-busy', 'false');
  state.notificationsLoading = false;
  if (refreshButton) refreshButton.disabled = false;
}

function cerrarNotificaciones({ devolverFoco = false } = {}) {
  const panel = document.getElementById('notifications-panel');
  if (!panel || panel.hidden) return;
  panel.hidden = true;
  actualizarContadoresNotificaciones(
    panel.querySelectorAll('.notification-entry[data-notification-screen]').length
  );
  if (devolverFoco) {
    [...document.querySelectorAll('button[aria-label="Notificaciones"]')]
      .find(button => button.offsetParent !== null)
      ?.focus();
  }
}

function alternarNotificaciones() {
  const panel = document.getElementById('notifications-panel');
  if (!panel) return;
  if (!panel.hidden) {
    cerrarNotificaciones();
    return;
  }
  panel.hidden = false;
  actualizarContadoresNotificaciones(panel.querySelectorAll('.notification-entry[data-notification-screen]').length);
  void cargarNotificaciones();
  document.getElementById('notifications-close')?.focus();
}

/* =========================================================================
   API Helpers
   ========================================================================= */
const ERRORES_SESION = ['Sesión expirada', 'TURNO_DESHABILITADO', 'USUARIO_DESACTIVADO'];
const ERROR_INTERNO = 'ERROR_INTERNO';

function mostrarPantallaError() {
  const screen = document.getElementById('app-error-screen');
  if (!screen || !screen.hidden) return;
  state.errorReturnScreen = state.currentScreen;
  screen.hidden = false;
  document.getElementById('app-error-back')?.focus();
}

function volverDePantallaError() {
  const screen = document.getElementById('app-error-screen');
  if (!screen || screen.hidden) return;
  screen.hidden = true;
  const returnScreen = state.errorReturnScreen;
  state.errorReturnScreen = null;
  if (returnScreen && document.getElementById(`screen-${returnScreen}`)) {
    navigateTo(returnScreen);
  }
}

function _jwtExpirado(token) {
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' && payload.exp * 1000 <= Date.now();
  } catch {
    return false;
  }
}

async function api(endpoint, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = { ...options.headers };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  if (!isFormData && headers['Content-Type'] === undefined) {
    headers['Content-Type'] = 'application/json';
  }
  Object.keys(headers).forEach(k => { if (headers[k] === undefined) delete headers[k]; });

  const forzarCierreSesion = (err) => {
    if (err.detail === 'TURNO_DESHABILITADO') {
      showToast('Tu turno ha sido finalizado/deshabilitado por gerencia.', 'error', 5000);
      logout();
      return new Error('TURNO_DESHABILITADO');
    }
    if (err.detail === 'USUARIO_DESACTIVADO') {
      showToast('Tu usuario fue desactivado. Contacta a gerencia.', 'error', 5000);
      logout();
      return new Error('USUARIO_DESACTIVADO');
    }
    return null;
  };

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      cache: 'no-store',
    });
    if (!res.ok) {
      if (res.status >= 500) {
        mostrarPantallaError();
        throw new Error(ERROR_INTERNO);
      }
      let err;
      try {
        err = await res.json();
      } catch {
        const raw = await res.text().catch(() => '');
        err = { detail: `Error del servidor (HTTP ${res.status})${raw ? `: ${raw.slice(0, 200)}` : ''}` };
      }
      // 401: solo cierra sesión si el 401 es REALMENTE de nuestra API (JSON con
      // `detail`) o si el token ya expiró localmente. Portales cautivos/proxies
      // del WiFi también responden 401 con HTML → se trata como pérdida de
      // conexión (sin logout) para no matar la sesión durante una caída.
      if (res.status === 401 && !endpoint.startsWith('/auth/login')) {
        const esApiPropia = err && typeof err.detail === 'string' && err.detail.length > 0;
        if (esApiPropia || _jwtExpirado(state.token)) {
          logout();
          throw new Error('Sesión expirada');
        }
        throw new Error('SIN_CONEXION');
      }
      const sesion = forzarCierreSesion(err);
      if (sesion) throw sesion;
      let msg = err.detail || `Error ${res.status}`;
      if (Array.isArray(msg)) {
        msg = msg.map(e => e.msg || JSON.stringify(e)).join('; ');
      }
      throw new Error(msg);
    }
    return res.status === 204 ? null : await res.json();
  } catch (e) {
    const esRed = e.name === 'TypeError'
      || e.message === 'SIN_CONEXION'
      || /fetch|network|load failed|net::/i.test(e.message || '');
    if (!options.silent) {
      if (esRed) {
        showToast('Sin conexión a internet — reintentando…', 'error');
      } else if (!ERRORES_SESION.includes(e.message) && e.message !== ERROR_INTERNO) {
        showToast(e.message, 'error');
      }
    }
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
  if (state.currentScreen === 'cameras' && screenId !== 'cameras') {
    void cerrarTodasCamaras();
  }
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
  if (screenId === 'calendario') loadCalendario();
  if (screenId === 'cameras') loadCameras();
}

/* =========================================================================
   Cameras
   ========================================================================= */
function cameraEsGestor() {
  return ['Administrador', 'Gerente'].includes(state.user?.rol);
}

function formatearBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

async function loadCameras() {
  const grid = document.getElementById('camera-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="camera-empty">Cargando cámaras…</div>';
  try {
    const [cameras, clips] = await Promise.all([
      api('/cameras/'),
      api('/cameras/clips'),
    ]);
    state.cameras = cameras;
    state.cameraClips = clips;
    if (cameraEsGestor()) {
      const [usersResult, storageResult] = await Promise.allSettled([
        api('/cameras/eligible-users'),
        api('/cameras/storage'),
      ]);
      state.cameraUsers = usersResult.status === 'fulfilled' ? usersResult.value : [];
      if (usersResult.status === 'rejected') {
        showToast(`No se pudieron cargar los usuarios para permisos: ${usersResult.reason.message}`, 'error');
      }
      if (storageResult.status === 'fulfilled') {
        renderCameraStorage(storageResult.value);
      } else {
        const storage = document.getElementById('camera-storage-status');
        if (storage) storage.textContent = `No se pudo consultar el almacenamiento: ${storageResult.reason.message}`;
      }
    } else {
      state.cameraUsers = [];
    }
    renderCameras();
  } catch {
    grid.innerHTML = '<div class="camera-empty">No se pudieron cargar las cámaras. Revisa tu conexión y vuelve a intentarlo.</div>';
  }
}

function renderCameraStorage(storage) {
  const target = document.getElementById('camera-storage-status');
  if (!target) return;
  const total = Number(storage.bytes_totales) || 0;
  const used = Number(storage.bytes_usados) || 0;
  const free = Number(storage.bytes_libres) || 0;
  const usedPercent = total > 0 ? Math.min(100, Math.max(0, (used / total) * 100)) : 0;
  target.innerHTML = `<div class="camera-storage-copy">
      <span class="camera-storage-icon"><span class="material-symbols-outlined">cloud_done</span></span>
      <div><strong>Almacenamiento de clips</strong><span>${storage.clips} momentos guardados · ${formatearBytes(used)} utilizados</span></div>
    </div>
    <div class="camera-storage-capacity">
      <div class="camera-storage-capacity-label"><span>Espacio disponible</span><strong>${formatearBytes(free)}</strong></div>
      <div class="camera-storage-track" role="progressbar" aria-label="Espacio utilizado" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(usedPercent)}"><span style="width:${usedPercent}%"></span></div>
    </div>`;
}

function updateCameraStats() {
  const totalStat = document.getElementById('camera-stat-total');
  const activeStat = document.getElementById('camera-stat-active');
  const clipsStat = document.getElementById('camera-stat-clips');
  if (totalStat) totalStat.textContent = state.cameras.length;
  if (activeStat) activeStat.textContent = state.cameras.filter(camera => camera.activa).length;
  if (clipsStat) clipsStat.textContent = state.cameraClips.length;
}

function renderCameras() {
  const grid = document.getElementById('camera-grid');
  if (!grid) return;
  updateCameraStats();
  if (!state.cameras.length) {
    grid.innerHTML = cameraEsGestor()
      ? '<div class="camera-empty"><span class="camera-empty-icon"><span class="material-symbols-outlined">videocam_off</span></span><strong>Aún no hay cámaras</strong><span>Configura el puente seguro y agrega tu primera cámara para comenzar el monitoreo.</span></div>'
      : '<div class="camera-empty"><span class="camera-empty-icon"><span class="material-symbols-outlined">lock</span></span><strong>No tienes cámaras asignadas</strong><span>Solicita a Gerencia acceso a las cámaras que necesitas consultar.</span></div>';
    return;
  }
  grid.innerHTML = state.cameras.map(camera => {
    const clips = state.cameraClips.filter(clip => clip.camara_id === camera.id);
    const users = cameraEsGestor()
      ? `<details class="camera-access"><summary><span class="material-symbols-outlined">group</span><span>Acceso del equipo</span><span class="camera-access-count">${camera.usuario_ids.length}</span><span class="material-symbols-outlined camera-access-chevron">expand_more</span></summary>
        <p class="camera-access-hint">Selecciona los vendedores que podrán ver esta cámara.</p>
        <div class="camera-user-list">${state.cameraUsers.length
          ? state.cameraUsers.map(user => `<label><input type="checkbox" data-camera-access="${camera.id}" value="${user.id}" ${camera.usuario_ids.includes(user.id) ? 'checked' : ''}>
              <span>${escHtml(user.nombre_completo)} <small>@${escHtml(user.username)}</small></span></label>`).join('')
          : '<p>No hay vendedores activos para autorizar.</p>'}
        </div>
        <button type="button" class="camera-secondary-btn camera-save-access" onclick="guardarAccesosCamara(${camera.id})"><span class="material-symbols-outlined">save</span> Guardar accesos</button>
      </details>
      <div class="camera-admin-actions">
        <button type="button" class="camera-secondary-btn" onclick="editarCamara(${camera.id})"><span class="material-symbols-outlined">edit</span> Editar</button>
        <button type="button" class="camera-secondary-btn ${camera.activa ? 'camera-disable-action' : ''}" onclick="cambiarEstadoCamara(${camera.id}, ${!camera.activa})"><span class="material-symbols-outlined">${camera.activa ? 'videocam_off' : 'videocam'}</span> ${camera.activa ? 'Desactivar' : 'Activar'}</button>
      </div>`
      : '';
    return `<article class="camera-card" data-camera-card="${camera.id}">
      <div class="camera-card-heading">
      <div class="camera-card-title">
        <span class="camera-card-icon"><span class="material-symbols-outlined">videocam</span></span>
        <div><h3>${escHtml(camera.nombre)}</h3><p><span class="material-symbols-outlined">link</span> ${escHtml(camera.slug)}</p></div>
      </div>
      <span class="camera-state ${camera.activa ? 'is-active' : 'is-disabled'}"><i></i>${camera.activa ? 'Activa' : 'Desactivada'}</span>
      </div>
      <div class="camera-feed${state.cameraPeers.has(camera.id) ? ' is-live' : ''}" id="camera-feed-${camera.id}">
      <div class="camera-feed-placeholder" id="camera-placeholder-${camera.id}">
        <span class="camera-feed-placeholder-icon"><span class="material-symbols-outlined">${camera.activa && camera.stream_url ? 'videocam' : 'videocam_off'}</span></span>
        <strong>${!camera.activa ? 'Cámara desactivada' : camera.stream_url ? 'Vista en espera' : 'Puente pendiente de configurar'}</strong>
        <span>${!camera.activa ? 'Actívala para volver a conectarla.' : camera.stream_url ? 'Conéctate para iniciar la transmisión en vivo.' : 'Configura CAMERA_BRIDGE_BASE_URL para habilitar el video.'}</span>
      </div>
      <video id="camera-video-${camera.id}" class="camera-video" controls autoplay muted playsinline hidden></video>
      <span class="camera-live-badge" id="camera-live-${camera.id}" hidden><i></i> EN VIVO</span>
      </div>
      <div class="camera-stream-row"><span class="material-symbols-outlined">sensors</span><p class="camera-stream-status" id="camera-status-${camera.id}" aria-live="polite">${!camera.activa ? 'Cámara desactivada' : camera.stream_url ? 'Lista para conectar' : 'Puente sin configurar'}</p></div>
      <div class="camera-actions">
      ${camera.activa && camera.stream_url
        ? `<button type="button" class="camera-primary-btn" id="camera-connect-${camera.id}" onclick="conectarCamara(${camera.id})"><span class="material-symbols-outlined">play_arrow</span> Ver en vivo</button>
           <button type="button" class="camera-secondary-btn" id="camera-record-${camera.id}" onclick="alternarGrabacionCamara(${camera.id})" disabled><span class="material-symbols-outlined">radio_button_checked</span> Grabar momento</button>
           <button type="button" class="camera-secondary-btn camera-disconnect-btn" id="camera-disconnect-${camera.id}" onclick="desconectarCamara(${camera.id})" hidden><span class="material-symbols-outlined">stop</span> Desconectar</button>`
        : ''}
      </div>
      ${users}
      ${cameraClipsMarkup(clips)}
    </article>`;
  }).join('');
}

function cameraClipsMarkup(clips) {
  return `<section class="camera-clips"><h3>Momentos guardados <span>(${clips.length})</span></h3>
    ${clips.length ? `<ul>${clips.map(clip => {
      const puedeEliminar = cameraEsGestor() || clip.usuario_nombre === state.user?.username;
      return `<li><div><strong>${escHtml(new Date(clip.creado_en).toLocaleString('es-NI'))}</strong>
          <small>${escHtml(clip.usuario_nombre)} · ${formatearBytes(clip.bytes_guardados)}</small></div>
        <div class="camera-clip-actions">
          <button type="button" class="camera-secondary-btn" onclick="verClipCamara('${escHtml(clip.id)}')"><span class="material-symbols-outlined">play_arrow</span> Ver</button>
          ${puedeEliminar ? `<button type="button" class="camera-danger-btn" onclick="eliminarClipCamara('${escHtml(clip.id)}')"><span class="material-symbols-outlined">delete</span> Borrar</button>` : ''}
        </div></li>`;
    }).join('')}</ul>` : '<p class="camera-clips-empty">Todavía no hay momentos guardados. Conéctate y pulsa “Grabar momento” para conservar uno.</p>'}
  </section>`;
}

async function guardarCamara(event) {
  event.preventDefault();
  const cameraId = document.getElementById('camera-id').value;
  const nombre = document.getElementById('camera-name').value.trim();
  const slug = document.getElementById('camera-slug').value.trim().toLowerCase();
  try {
    if (cameraId && state.cameraPeers.has(Number(cameraId))) {
      await desconectarCamara(Number(cameraId));
    }
    await api(cameraId ? `/cameras/${cameraId}` : '/cameras/', {
      method: cameraId ? 'PATCH' : 'POST',
      body: JSON.stringify({ nombre, slug }),
    });
    resetCameraForm();
    showToast(cameraId ? 'Cámara actualizada' : 'Cámara agregada');
    await loadCameras();
  } catch { /* api() shows the error */ }
}

function editarCamara(cameraId) {
  const camera = state.cameras.find(item => item.id === cameraId);
  if (!camera) return showToast('Cámara no encontrada', 'error');
  document.getElementById('camera-id').value = camera.id;
  document.getElementById('camera-name').value = camera.nombre;
  document.getElementById('camera-slug').value = camera.slug;
  document.getElementById('camera-form-title').textContent = `Editar cámara: ${camera.nombre}`;
  document.getElementById('camera-submit').textContent = 'Guardar cambios';
  document.getElementById('camera-cancel-edit').hidden = false;
  document.getElementById('camera-form').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function resetCameraForm() {
  document.getElementById('camera-form').reset();
  document.getElementById('camera-id').value = '';
  document.getElementById('camera-form-title').textContent = 'Configurar una cámara';
  document.getElementById('camera-submit').textContent = 'Agregar cámara';
  document.getElementById('camera-cancel-edit').hidden = true;
}

async function guardarAccesosCamara(cameraId) {
  const usuario_ids = [...document.querySelectorAll(`[data-camera-access="${cameraId}"]:checked`)]
    .map(input => Number(input.value));
  try {
    await api(`/cameras/${cameraId}/access`, {
      method: 'PUT',
      body: JSON.stringify({ usuario_ids }),
    });
    showToast('Accesos actualizados');
    await loadCameras();
  } catch { /* api() shows the error */ }
}

async function cambiarEstadoCamara(cameraId, activa) {
  const accion = activa ? 'activar' : 'desactivar';
  if (!confirm(`¿Deseas ${accion} esta cámara?`)) return;
  try {
    await api(`/cameras/${cameraId}`, {
      method: 'PATCH',
      body: JSON.stringify({ activa }),
    });
    if (!activa) await desconectarCamara(cameraId);
    showToast(`Cámara ${activa ? 'activada' : 'desactivada'}`);
    await loadCameras();
  } catch { /* api() shows the error */ }
}

function setCameraStatus(cameraId, message, isError = false) {
  const target = document.getElementById(`camera-status-${cameraId}`);
  if (target) {
    target.textContent = message;
    target.classList.toggle('is-error', isError);
  }
  const isLive = message === 'En vivo';
  const feed = document.getElementById(`camera-feed-${cameraId}`);
  const liveBadge = document.getElementById(`camera-live-${cameraId}`);
  const placeholder = document.getElementById(`camera-placeholder-${cameraId}`);
  if (feed) feed.classList.toggle('is-live', isLive);
  if (liveBadge) liveBadge.hidden = !isLive;
  if (placeholder && isLive) placeholder.hidden = true;
  if (placeholder && !isLive && !state.cameraPeers.has(cameraId)) placeholder.hidden = false;
}

function esperarFinIce(peer) {
  if (peer.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise(resolve => {
    const terminar = () => {
      clearTimeout(timeout);
      peer.removeEventListener('icegatheringstatechange', alCambiar);
      resolve();
    };
    const alCambiar = () => {
      if (peer.iceGatheringState === 'complete') {
        terminar();
      }
    };
    const timeout = setTimeout(terminar, 8000);
    peer.addEventListener('icegatheringstatechange', alCambiar);
    alCambiar();
  });
}

async function conectarCamara(cameraId) {
  const camera = state.cameras.find(item => item.id === cameraId);
  if (!camera?.stream_url || !camera.activa) return;
  if (state.cameraPeers.has(cameraId)) return;
  const video = document.getElementById(`camera-video-${cameraId}`);
  const connectButton = document.getElementById(`camera-connect-${cameraId}`);
  try {
    setCameraStatus(cameraId, 'Conectando al puente…');
    connectButton.disabled = true;
    const streamToken = await api(`/cameras/${cameraId}/stream-token`, { method: 'POST' });
    const authorization = `Basic ${btoa(`${camera.slug}:${streamToken.token}`)}`;
    const peer = new RTCPeerConnection({ iceServers: streamToken.ice_servers });
    const connection = { peer, authorization, resourceUrl: null, stream: null };
    state.cameraPeers.set(cameraId, connection);
    peer.ontrack = event => {
      const stream = event.streams[0] || new MediaStream([event.track]);
      connection.stream = stream;
      video.srcObject = stream;
      video.hidden = false;
      const placeholder = document.getElementById(`camera-placeholder-${cameraId}`);
      if (placeholder) placeholder.hidden = true;
      document.getElementById(`camera-record-${cameraId}`).disabled = false;
      setCameraStatus(cameraId, 'En vivo');
    };
    peer.onconnectionstatechange = () => {
      if (peer.connectionState === 'failed' || peer.connectionState === 'disconnected') {
        setCameraStatus(cameraId, 'Conexión interrumpida. Verifica el puente y la red.', true);
      }
    };
    peer.addTransceiver('video', { direction: 'recvonly' });
    await peer.setLocalDescription(await peer.createOffer());
    await esperarFinIce(peer);
    const response = await fetch(camera.stream_url, {
      method: 'POST',
      headers: {
        Authorization: authorization,
        'Content-Type': 'application/sdp',
        Accept: 'application/sdp',
      },
      body: peer.localDescription.sdp,
    });
    if (!response.ok) {
      throw new Error(`El puente rechazó la conexión (HTTP ${response.status})`);
    }
    const answer = await response.text();
    const location = response.headers.get('Location');
    if (!location) {
      throw new Error('El puente no expuso la cabecera Location necesaria para cerrar la sesión WHEP');
    }
    const resourceUrl = new URL(location, camera.stream_url);
    if (resourceUrl.origin !== new URL(camera.stream_url).origin) {
      throw new Error('El puente devolvió una URL de sesión en otro origen');
    }
    connection.resourceUrl = resourceUrl.toString();
    await peer.setRemoteDescription({ type: 'answer', sdp: answer });
    document.getElementById(`camera-disconnect-${cameraId}`).hidden = false;
  } catch (error) {
    await desconectarCamara(cameraId, false);
    setCameraStatus(cameraId, error.message || 'No se pudo conectar al puente', true);
    showToast(error.message || 'No se pudo conectar al puente', 'error', 5000);
  } finally {
    const button = document.getElementById(`camera-connect-${cameraId}`);
    if (button) button.disabled = state.cameraPeers.has(cameraId);
  }
}

function mimeGrabacionDisponible() {
  if (typeof MediaRecorder === 'undefined') return '';
  return [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
    'video/mp4',
  ].find(type => MediaRecorder.isTypeSupported(type)) || '';
}

async function alternarGrabacionCamara(cameraId) {
  if (state.cameraRecordings.has(cameraId)) {
    await detenerGrabacionCamara(cameraId);
  } else {
    await iniciarGrabacionCamara(cameraId);
  }
}

async function iniciarGrabacionCamara(cameraId) {
  const connection = state.cameraPeers.get(cameraId);
  if (!connection?.stream) return showToast('Conecta la cámara antes de grabar', 'warning');
  const mimeType = mimeGrabacionDisponible();
  if (!mimeType) return showToast('Este navegador no permite grabar video', 'error');
  let clip;
  let recording;
  try {
    clip = await api(`/cameras/${cameraId}/clips`, {
      method: 'POST',
      body: JSON.stringify({ mime_type: mimeType }),
    });
    const recorder = new MediaRecorder(connection.stream, { mimeType });
    const authHeaders = { Authorization: `Bearer ${state.token}` };
    let resolveFinished;
    recording = {
      clipId: clip.id,
      recorder,
      sequence: 0,
      uploadQueue: Promise.resolve(),
      authHeaders,
      finished: new Promise(resolve => { resolveFinished = resolve; }),
    };
    state.cameraRecordings.set(cameraId, recording);
    recorder.ondataavailable = event => {
      if (!event.data.size || recording.error) return;
      const sequence = recording.sequence++;
      recording.uploadQueue = recording.uploadQueue.then(() => api(
        `/cameras/${cameraId}/clips/${recording.clipId}/chunks/${sequence}`,
        {
          method: 'PUT',
          headers: { ...authHeaders, 'Content-Type': 'application/octet-stream' },
          body: event.data,
          silent: true,
        },
      )).catch(error => {
        recording.error = error;
        showToast(`La grabación se interrumpió: ${error.message}`, 'error', 6000);
        if (recorder.state === 'recording') recorder.stop();
      });
    };
    recorder.onstop = async () => {
      try {
        if (recording.error) throw recording.error;
        await recording.uploadQueue;
        await api(`/cameras/${cameraId}/clips/${recording.clipId}/finish`, {
          method: 'POST',
          headers: authHeaders,
          silent: true,
        });
        showToast('Clip guardado; se conservará 7 días');
      } catch (error) {
        try {
          await api(`/cameras/clips/${recording.clipId}`, {
            method: 'DELETE',
            headers: authHeaders,
            silent: true,
          });
        } catch (deleteError) {
          showToast(`No se pudo finalizar ni limpiar el clip: ${deleteError.message}`, 'error', 6000);
        }
        if (!recording.error) {
          showToast(`No se pudo guardar el clip: ${error.message}`, 'error', 6000);
        }
      } finally {
        state.cameraRecordings.delete(cameraId);
        updateCameraRecordButton(cameraId);
        resolveFinished();
        await loadCameraClips();
      }
    };
    recorder.start(5000);
    updateCameraRecordButton(cameraId);
    showToast('Grabación iniciada. Deténla para guardar el clip.');
  } catch (error) {
    if (recording) {
      state.cameraRecordings.delete(cameraId);
      updateCameraRecordButton(cameraId);
    }
    if (clip?.id) {
      try {
        await api(`/cameras/clips/${clip.id}`, { method: 'DELETE', silent: true });
      } catch (cleanupError) {
        showToast(`No se pudo limpiar la grabación incompleta: ${cleanupError.message}`, 'error', 6000);
      }
    }
    showToast(`No se pudo iniciar la grabación: ${error.message}`, 'error', 5000);
  }
}

function updateCameraRecordButton(cameraId) {
  const button = document.getElementById(`camera-record-${cameraId}`);
  if (!button) return;
  const recording = state.cameraRecordings.has(cameraId);
  button.innerHTML = recording
    ? '<span class="material-symbols-outlined">stop_circle</span> Detener y guardar'
    : '<span class="material-symbols-outlined">radio_button_checked</span> Grabar momento';
  button.classList.toggle('is-recording', recording);
}

async function detenerGrabacionCamara(cameraId) {
  const recording = state.cameraRecordings.get(cameraId);
  if (!recording) return;
  if (recording.recorder.state !== 'inactive') recording.recorder.stop();
  await recording.finished;
}

async function desconectarCamara(cameraId, stopRecording = true) {
  if (stopRecording && state.cameraRecordings.has(cameraId)) {
    await detenerGrabacionCamara(cameraId);
  }
  const connection = state.cameraPeers.get(cameraId);
  if (connection) {
    connection.peer.close();
    connection.stream?.getTracks().forEach(track => track.stop());
    if (connection.resourceUrl) {
      try {
        const response = await fetch(connection.resourceUrl, {
          method: 'DELETE',
          headers: { Authorization: connection.authorization },
        });
        if (!response.ok && response.status !== 404) {
          showToast(`El puente no pudo cerrar la sesión (HTTP ${response.status})`, 'error');
        }
      } catch {
        showToast('Se cerró el video localmente, pero no se confirmó el cierre en el puente.', 'error');
      }
    }
    state.cameraPeers.delete(cameraId);
  }
  const video = document.getElementById(`camera-video-${cameraId}`);
  if (video) {
    video.pause();
    video.srcObject = null;
    video.hidden = true;
  }
  const connectButton = document.getElementById(`camera-connect-${cameraId}`);
  if (connectButton) connectButton.disabled = false;
  const disconnectButton = document.getElementById(`camera-disconnect-${cameraId}`);
  if (disconnectButton) disconnectButton.hidden = true;
  const recordButton = document.getElementById(`camera-record-${cameraId}`);
  if (recordButton) recordButton.disabled = true;
  updateCameraRecordButton(cameraId);
  const liveBadge = document.getElementById(`camera-live-${cameraId}`);
  const feed = document.getElementById(`camera-feed-${cameraId}`);
  const placeholder = document.getElementById(`camera-placeholder-${cameraId}`);
  if (liveBadge) liveBadge.hidden = true;
  if (feed) feed.classList.remove('is-live');
  if (placeholder) placeholder.hidden = false;
  setCameraStatus(cameraId, 'Desconectada');
}

async function cerrarTodasCamaras() {
  const cameraIds = new Set([
    ...state.cameraPeers.keys(),
    ...state.cameraRecordings.keys(),
  ]);
  for (const cameraId of cameraIds) {
    await desconectarCamara(cameraId);
  }
}

async function loadCameraClips() {
  if (!state.token) return;
  try {
    state.cameraClips = await api('/cameras/clips');
    updateCameraStats();
    document.querySelectorAll('[data-camera-card]').forEach(card => {
      const camera = state.cameras.find(item => item.id === Number(card.dataset.cameraCard));
      if (!camera) return;
      const clips = state.cameraClips.filter(clip => clip.camara_id === camera.id);
      const section = card.querySelector('.camera-clips');
      if (section) section.outerHTML = cameraClipsMarkup(clips);
    });
  } catch { /* api() reports the error */ }
}

async function verClipCamara(clipId) {
  try {
    const response = await fetch(`${API_BASE}/cameras/clips/${encodeURIComponent(clipId)}/video`, {
      headers: { Authorization: `Bearer ${state.token}` },
      cache: 'no-store',
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Error ${response.status}`);
    }
    const blob = await response.blob();
    if (state.cameraClipObjectUrl) URL.revokeObjectURL(state.cameraClipObjectUrl);
    state.cameraClipObjectUrl = URL.createObjectURL(blob);
    document.getElementById('camera-clip-player').src = state.cameraClipObjectUrl;
    document.getElementById('camera-clip-modal').classList.add('show');
  } catch (error) {
    showToast(`No se pudo abrir el clip: ${error.message}`, 'error');
  }
}

async function eliminarClipCamara(clipId) {
  if (!confirm('¿Eliminar este clip permanentemente?')) return;
  try {
    await api(`/cameras/clips/${encodeURIComponent(clipId)}`, { method: 'DELETE' });
    showToast('Clip eliminado');
    await loadCameraClips();
  } catch { /* api() shows the error */ }
}

function cerrarClipModal() {
  const player = document.getElementById('camera-clip-player');
  player.pause();
  player.removeAttribute('src');
  player.load();
  document.getElementById('camera-clip-modal').classList.remove('show');
  if (state.cameraClipObjectUrl) {
    URL.revokeObjectURL(state.cameraClipObjectUrl);
    state.cameraClipObjectUrl = null;
  }
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
  try {
    const data = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
      silent: true,
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
    iniciarIntervalosSesion();
    showToast(`Bienvenido, ${state.user.username}`);
  } catch (e) {
    const esErrorDeConexion = e?.name === 'TypeError'
      || e?.message === 'SIN_CONEXION'
      || /fetch|network|load failed|net::/i.test(e?.message || '');
    if (esErrorDeConexion) {
      showToast('No se pudo conectar con el sistema. Revisa tu conexión e inténtalo de nuevo.', 'error');
      return;
    }
    const serverMsg = e && typeof e.message === 'string'
      && e.message !== 'Error del servidor'
      ? e.message : null;
    showToast(serverMsg || 'Usuario o contraseña incorrectos', 'error');
    return;
  }
}

function logout() {
  void cerrarTodasCamaras();
  if (state.cameraClipObjectUrl) cerrarClipModal();
  if (state.heartbeatInterval) { clearInterval(state.heartbeatInterval); state.heartbeatInterval = null; }
  if (state.sessionPollInterval) { clearInterval(state.sessionPollInterval); state.sessionPollInterval = null; }
  if (state.attendanceReminderInterval) { clearInterval(state.attendanceReminderInterval); state.attendanceReminderInterval = null; }
  state.token = null;
  state.user = null;
  state.currentAsistencia = null;
  state.attendanceSynced = false;
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

  document.getElementById('user-avatar').textContent = initial;
  document.getElementById('user-name').textContent = name;
  document.getElementById('user-role').textContent = rol;

  const roleBadge = document.getElementById('cuenta-role-badge');
  if (roleBadge) roleBadge.textContent = rol;
}

/* =========================================================================
   Attendance — Shift Control
   ========================================================================= */
async function iniciarTurno(turnoId) {
  try {
    const data = await api(`/asistencia/turnos/iniciar/${turnoId}`, {
      method: 'POST',
      silent: true,
    });
    state.currentAsistencia = data;
    localStorage.setItem('pos_asistencia', JSON.stringify(data));
    marcarInicioTurnoNotificado(turnoId);
    renderAttendanceStatus();
    showToast('Turno iniciado con éxito', 'success');
    enviarHeartbeat();
    verificarAvisosTurno();
    return data;
  } catch (e) {
    if (!ERRORES_SESION.includes(e.message)) showToast(e.message, 'error');
    throw e;
  }
}

async function finalizarTurno() {
  try {
    await api('/asistencia/check-out', {
      method: 'POST',
      silent: true,
    });
    state.currentAsistencia = null;
    localStorage.removeItem('pos_asistencia');
    renderAttendanceStatus();
    showToast('Turno finalizado con éxito', 'success');
    verificarAvisosTurno();
    return null;
  } catch (e) {
    const msg = (e && typeof e.message === 'string') ? e.message : '';
    if (msg.includes('no tiene un turno activo')) {
      state.currentAsistencia = null;
      localStorage.removeItem('pos_asistencia');
      renderAttendanceStatus();
    }
    if (!ERRORES_SESION.includes(msg)) showToast(msg, 'error');
    throw e;
  }
}

/* --- Attendance Panel UI --- */
function showAttendancePanel() {
  const panel = document.getElementById('attendance-panel');
  if (panel) panel.style.display = 'flex';
  renderAttendanceStatus();
}

function hideAttendancePanel() {
  const panel = document.getElementById('attendance-panel');
  if (panel) panel.style.display = 'none';
}

function renderAttendanceStatus() {
  const statusEl = document.getElementById('attendance-status');
  const toggle = document.getElementById('btn-attendance-toggle');
  const select = document.getElementById('turno-select');

  if (state.currentAsistencia) {
    if (statusEl) {
      const hora = formatLocalTime(state.currentAsistencia.hora_entrada_real);
      statusEl.innerHTML = `🟢 Turno activo — entrada ${hora}`;
      statusEl.style.color = '#5EEAD4';
    }
    if (toggle) {
      toggle.classList.add('btn-stop');
      toggle.classList.remove('btn-turquoise');
      toggle.innerHTML = '<span class="material-symbols-outlined text-sm">stop</span> Finalizar Turno';
      toggle.disabled = false;
    }
    if (select) { select.disabled = true; select.value = state.currentAsistencia.turno_id; }
  } else {
    if (statusEl) { statusEl.innerHTML = '⚪ Sin turno activo'; statusEl.style.color = '#94a3b8'; }
    if (toggle) {
      toggle.classList.add('btn-turquoise');
      toggle.classList.remove('btn-stop');
      toggle.innerHTML = '<span class="material-symbols-outlined text-sm">schedule</span> Iniciar Turno';
      toggle.disabled = false;
    }
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
    const savedTurno = localStorage.getItem(`pos_turno_seleccionado_${state.user?.id}`);
    select.value = current || savedTurno || '';
    verificarAvisosTurno();
  } catch {
    state.turnos = [];
  }
}

function leerHoraTurno(value) {
  const [hours, minutes] = String(value || '').split(':').map(Number);
  if (!Number.isInteger(hours) || !Number.isInteger(minutes)
      || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) return null;
  return hours * 60 + minutes;
}

function obtenerAhoraManagua() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Managua',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  const fecha = `${values.year}-${values.month}-${values.day}`;
  const minutos = Number(values.hour) * 60 + Number(values.minute);
  const [year, month, day] = fecha.split('-').map(Number);
  return {
    fecha,
    minutos,
    absoluto: Math.floor(Date.UTC(year, month - 1, day) / 60_000) + minutos,
  };
}

function desplazarFecha(fecha, dias) {
  const [year, month, day] = fecha.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day + dias)).toISOString().slice(0, 10);
}

function fechaInicioTurnoActual(turno, ahora) {
  const entrada = leerHoraTurno(turno.hora_entrada);
  const salida = leerHoraTurno(turno.hora_salida);
  if (entrada === null || salida === null) return ahora.fecha;
  const cruzaMedianoche = salida <= entrada;
  return cruzaMedianoche && ahora.minutos < entrada && ahora.minutos < salida
    ? desplazarFecha(ahora.fecha, -1)
    : ahora.fecha;
}

function claveAvisoInicio(turnoId, fecha) {
  return `pos_aviso_inicio_turno_${state.user?.id}_${turnoId}_${fecha}`;
}

function marcarInicioTurnoNotificado(turnoId) {
  const turno = state.turnos.find(item => item.id === turnoId);
  if (!turno) return;
  const fecha = fechaInicioTurnoActual(turno, obtenerAhoraManagua());
  localStorage.setItem(claveAvisoInicio(turnoId, fecha), '1');
}

function emitirAvisoTurno(key, title, body) {
  if (localStorage.getItem(key)) return;
  new Notification(title, { body, tag: key });
  localStorage.setItem(key, '1');
}

function verificarAvisosTurno() {
  if (!state.token || !state.user || !state.attendanceSynced
      || typeof Notification === 'undefined' || Notification.permission !== 'granted') return;

  const ahora = obtenerAhoraManagua();
  if (state.currentAsistencia) {
    const asistencia = state.currentAsistencia;
    const turno = state.turnos.find(item => item.id === asistencia.turno_id);
    const entrada = leerHoraTurno(turno?.hora_entrada);
    const salida = leerHoraTurno(turno?.hora_salida);
    const fechaEntrada = String(asistencia.hora_entrada_real || '').slice(0, 10);
    if (turno && entrada !== null && salida !== null && /^\d{4}-\d{2}-\d{2}$/.test(fechaEntrada)) {
      const fechaSalida = desplazarFecha(fechaEntrada, salida <= entrada ? 1 : 0);
      const [year, month, day] = fechaSalida.split('-').map(Number);
      const salidaAbsoluta = Math.floor(Date.UTC(year, month - 1, day) / 60_000) + salida;
      const key = `pos_aviso_salida_turno_${state.user.id}_${asistencia.id}`;
      if (ahora.absoluto >= salidaAbsoluta) {
        emitirAvisoTurno(
          key,
          'Es hora de finalizar tu turno',
          `El turno ${turno.nombre} terminó a las ${String(turno.hora_salida).slice(0, 5)}. Recuerda registrar tu salida.`,
        );
      }
    }
    return;
  }

  const select = document.getElementById('turno-select');
  const turno = state.turnos.find(item => item.id === Number(select?.value));
  const entrada = leerHoraTurno(turno?.hora_entrada);
  const salida = leerHoraTurno(turno?.hora_salida);
  if (!turno || entrada === null || salida === null) return;

  let fechaInicio = ahora.fecha;
  let inicioAbsoluto = Math.floor(Date.UTC(
    Number(fechaInicio.slice(0, 4)),
    Number(fechaInicio.slice(5, 7)) - 1,
    Number(fechaInicio.slice(8, 10)),
  ) / 60_000) + entrada;
  if (inicioAbsoluto > ahora.absoluto) {
    fechaInicio = desplazarFecha(fechaInicio, -1);
    inicioAbsoluto -= 24 * 60;
  }
  const duracion = (salida - entrada + 24 * 60) % (24 * 60) || 24 * 60;
  const transcurrido = ahora.absoluto - inicioAbsoluto;
  if (transcurrido >= 0 && transcurrido < duracion) {
    const key = claveAvisoInicio(turno.id, fechaInicio);
    emitirAvisoTurno(
      key,
      'Tu turno ya comenzó',
      `El turno ${turno.nombre} inicia a las ${String(turno.hora_entrada).slice(0, 5)}. Recuerda registrar tu entrada.`,
    );
  }
}

function actualizarBotonAvisosTurno() {
  const button = document.getElementById('btn-enable-attendance-notifications');
  if (!button) return;
  if (typeof Notification === 'undefined') {
    button.hidden = true;
    return;
  }
  button.hidden = false;
  if (Notification.permission === 'granted') {
    button.textContent = 'Avisos de turno activados';
    button.disabled = true;
  } else {
    button.textContent = Notification.permission === 'denied'
      ? 'Permite avisos en el navegador'
      : 'Activar avisos de turno';
    button.disabled = false;
  }
}

async function activarAvisosTurno() {
  if (typeof Notification === 'undefined') {
    showToast('Este navegador no admite notificaciones del sistema.', 'error');
    return;
  }
  if (Notification.permission === 'denied') {
    showToast('Los avisos están bloqueados. Permítelos desde la configuración del navegador para este sitio.', 'warning', 5000);
    return;
  }
  try {
    const permission = Notification.permission === 'granted'
      ? 'granted'
      : await Notification.requestPermission();
    actualizarBotonAvisosTurno();
    if (permission === 'granted') {
      showToast('Avisos de turno activados', 'success');
      verificarAvisosTurno();
    } else {
      showToast('No se activaron los avisos de turno.', 'warning');
    }
  } catch (error) {
    showToast(`No se pudieron activar los avisos: ${error.message}`, 'error', 5000);
  }
}

/* --- Turnos CRUD (Gestión de Turnos modal) --- */
function calcularHoraSalida() {
  const entrada = document.getElementById('turno-entrada').value;
  const horas = parseInt(document.getElementById('turno-horas').value) || 0;
  if (!entrada || horas <= 0) return;
  const [h, m] = entrada.split(':').map(Number);
  const totalMin = ((h * 60 + m) + horas * 60) % (24 * 60);
  const sh = String(Math.floor(totalMin / 60)).padStart(2, '0');
  const sm = String(totalMin % 60).padStart(2, '0');
  document.getElementById('turno-salida').value = `${sh}:${sm}`;
}

function openTurnosModal() {
  document.getElementById('turno-edit-id').value = '';
  document.getElementById('turno-form-title').textContent = 'Nuevo Turno';
  document.getElementById('turno-save-btn').textContent = 'Crear Turno';
  document.getElementById('turno-cancel-edit').style.display = 'none';
  document.getElementById('turno-nombre').value = '';
  document.getElementById('turno-entrada').value = '08:00';
  document.getElementById('turno-salida').value = '16:00';
  document.getElementById('turno-horas').value = '8';
  calcularHoraSalida();
  renderTurnosTable();
  document.getElementById('modal-turnos').classList.add('show');
}

function renderTurnosTable() {
  const container = document.getElementById('turnos-table-container');
  if (!state.turnos.length) {
    container.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:13px;padding:16px 0;">No hay turnos registrados</div>';
    return;
  }
  container.innerHTML = `<table class="data-table"><thead><tr>
    <th>Nombre</th><th>Entrada</th><th>Salida</th><th>Horas</th><th style="width:80px;"></th>
  </tr></thead><tbody>${state.turnos.map(t => `<tr>
    <td style="font-weight:600;">${t.nombre}</td>
    <td>${t.hora_entrada}</td>
    <td>${t.hora_salida}</td>
    <td>${t.horas_teoricas}h</td>
    <td style="text-align:right;">
      <button class="btn-icon-sm" onclick="editTurno(${t.id})" title="Editar">✏️</button>
      <button class="btn-icon-sm" onclick="deleteTurno(${t.id}, '${t.nombre}')" title="Eliminar">🗑️</button>
    </td>
  </tr>`).join('')}</tbody></table>`;
}

function editTurno(id) {
  const t = state.turnos.find(x => x.id === id);
  if (!t) return;
  document.getElementById('turno-edit-id').value = t.id;
  document.getElementById('turno-form-title').textContent = `Editar: ${t.nombre}`;
  document.getElementById('turno-save-btn').textContent = 'Guardar Cambios';
  document.getElementById('turno-cancel-edit').style.display = '';
  document.getElementById('turno-nombre').value = t.nombre;
  document.getElementById('turno-entrada').value = t.hora_entrada;
  document.getElementById('turno-horas').value = t.horas_teoricas;
  calcularHoraSalida();
}

async function deleteTurno(id, nombre) {
  if (!confirm(`¿Eliminar el turno "${nombre}"?`)) return;
  try {
    await api(`/asistencia/turnos/${id}`, { method: 'DELETE' });
    showToast('Turno eliminado');
    await loadTurnos();
    renderTurnosTable();
  } catch { /* handled */ }
}

async function saveTurno() {
  const editId = document.getElementById('turno-edit-id').value;
  const payload = {
    nombre: document.getElementById('turno-nombre').value.trim(),
    hora_entrada: document.getElementById('turno-entrada').value + ':00',
    hora_salida: document.getElementById('turno-salida').value + ':00',
    horas_teoricas: parseInt(document.getElementById('turno-horas').value) || 8,
  };
  if (!payload.nombre) return showToast('Ingresa el nombre del turno', 'warning');
  try {
    if (editId) {
      await api(`/asistencia/turnos/${editId}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Turno actualizado');
    } else {
      await api('/asistencia/turnos', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Turno creado');
    }
    await loadTurnos();
    renderTurnosTable();
    document.getElementById('turno-edit-id').value = '';
    document.getElementById('turno-form-title').textContent = 'Nuevo Turno';
    document.getElementById('turno-save-btn').textContent = 'Crear Turno';
    document.getElementById('turno-cancel-edit').style.display = 'none';
    document.getElementById('turno-nombre').value = '';
    document.getElementById('turno-entrada').value = '08:00';
    document.getElementById('turno-horas').value = '8';
    calcularHoraSalida();
  } catch { /* handled */ }
}

/* --- Heartbeat (keepalive cada 2 min, solo Vendedor con turno activo) --- */
async function enviarHeartbeat() {
  if (!state.token || !state.user) return;
  if (state.user.rol !== 'Vendedor') return;
  if (!state.currentAsistencia) return;
  try {
    await api(`/asistencia/turnos/heartbeat/${state.currentAsistencia.id}`, {
      method: 'POST',
      keepalive: true,
      silent: true,
    });
  } catch (e) {
    const msg = (e && typeof e.message === 'string') ? e.message : '';
    const cerrado = msg.includes('salida') || msg.includes('No se encontró la asistencia');
    if (cerrado) {
      state.currentAsistencia = null;
      localStorage.removeItem('pos_asistencia');
      renderAttendanceStatus();
      showToast('Tu turno se cerró automáticamente. Contacta a gerencia.', 'warning');
    }
  }
}

/* --- Realineación del turno activo contra la BD (login/restore/foco) --- */
async function syncAsistenciaActiva() {
  if (!state.token || !state.user) return;
  try {
    const data = await api('/asistencia/activa', { silent: true });
    if (data) {
      state.currentAsistencia = data;
      localStorage.setItem('pos_asistencia', JSON.stringify(data));
    } else {
      state.currentAsistencia = null;
      localStorage.removeItem('pos_asistencia');
    }
    state.attendanceSynced = true;
    renderAttendanceStatus();
    verificarAvisosTurno();
  } catch { /* el interceptor ya maneja 403/401; silencio */ }
}

/* --- Verificación de sesión (polling cada 60s) ---
   Consulta GET /auth/me; si la gerencia deshabilitó el turno (403
   TURNO_DESHABILITADO) o el usuario fue desactivado (403
   USUARIO_DESACTIVADO), el interceptor de api() hace logout automático. */
async function verificarSesionTurno() {
  if (!state.token || !state.user) return;
  try {
    await api('/auth/me', { silent: true });
  } catch { /* el interceptor ya manejó el cierre de sesión */ }
}

/* --- Intervalos de sesión: heartbeat + poll de validez + sync inicial --- */
function iniciarIntervalosSesion() {
  if (state.heartbeatInterval) clearInterval(state.heartbeatInterval);
  if (state.sessionPollInterval) clearInterval(state.sessionPollInterval);
  if (state.attendanceReminderInterval) clearInterval(state.attendanceReminderInterval);
  state.attendanceSynced = false;
  state.heartbeatInterval = setInterval(enviarHeartbeat, 120_000);
  state.sessionPollInterval = setInterval(verificarSesionTurno, 60_000);
  state.attendanceReminderInterval = setInterval(verificarAvisosTurno, 30_000);
  actualizarBotonAvisosTurno();
  syncAsistenciaActiva();
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
  const tbody = document.getElementById('gastos-tbody');
  if (!tbody) return;
  try {
    state.allGastos = await api('/gastos/');
    renderGastoFilters();
    renderGastosTable();
  } catch {
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-10 text-center text-[#E63946]">Error al cargar gastos</td></tr>';
  }
}

const CATEGORIA_BADGE = {
  OPERATIVO: 'bg-[#FFE8E3] text-[#B42318]',
  MANTENIMIENTO: 'bg-sky-100 text-sky-800',
  SUMINISTROS: 'bg-amber-100 text-amber-800',
  SERVICIOS: 'bg-teal-100 text-teal-800',
  IMPUESTOS: 'bg-indigo-100 text-indigo-800',
  OTROS: 'bg-slate-200 text-slate-700',
};

function renderGastoFilters() {
  const container = document.getElementById('gasto-cat-filters');
  if (!container) return;
  const cats = Object.keys(CATEGORIA_LABELS);
  container.innerHTML = `<button class="chip ${state.activeGastoFilter === null ? 'active' : ''}" data-cat="all" onclick="applyGastoFilter(null)">Todos</button>`
    + cats.map(c => `<button class="chip ${state.activeGastoFilter === c ? 'active' : ''}" data-cat="${c}" onclick="applyGastoFilter('${c}')">${CATEGORIA_LABELS[c]}</button>`).join('');
}

function applyGastoFilter(cat) {
  state.activeGastoFilter = cat;
  renderGastoFilters();
  renderGastosTable();
}

function renderGastoResumen() {
  if (!state.allGastos) return;
  let totalHoy = 0;
  const hoyKey = new Date().toLocaleDateString('en-CA');
  state.allGastos.forEach(g => {
    if (new Date(g.fecha).toLocaleDateString('en-CA') === hoyKey) totalHoy += parseFloat(g.monto);
  });
  const elTotal = document.getElementById('gasto-total-hoy');
  const elMov = document.getElementById('gasto-movimientos');
  if (elTotal) elTotal.textContent = 'C$' + totalHoy.toFixed(2);
  if (elMov) elMov.textContent = state.allGastos.length;
}

function renderGastosTable() {
  const tbody = document.getElementById('gastos-tbody');
  if (!tbody) return;
  const filtered = state.activeGastoFilter
    ? state.allGastos.filter(g => g.categoria === state.activeGastoFilter)
    : state.allGastos;
  renderGastoResumen();
  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-10 text-center text-slate-400">No hay gastos registrados</td></tr>';
    return;
  }
  tbody.innerHTML = filtered.map(g => `
    <tr style="border-bottom:1px solid #f1f5f9;" onmouseenter="this.style.background='#f8fafc'" onmouseleave="this.style.background=''">
      <td style="padding:12px 16px;font-weight:600;color:#0F3B66;white-space:nowrap;">#${g.id}</td>
      <td style="padding:12px 16px;color:#374151;white-space:nowrap;">${new Date(g.fecha).toLocaleDateString('es-NI', { day:'2-digit', month:'short', year:'numeric' })}</td>
      <td style="padding:12px 16px;"><span class="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold ${CATEGORIA_BADGE[g.categoria] || 'bg-slate-100 text-slate-600'}">${CATEGORIA_LABELS[g.categoria] || g.categoria}</span></td>
      <td style="padding:12px 16px;color:#374151;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${g.concepto}</td>
      <td style="padding:12px 16px;text-align:right;font-weight:700;color:#E63946;white-space:nowrap;">C$${parseFloat(g.monto).toFixed(2)}</td>
      <td style="padding:12px 16px;color:#6b7280;font-size:13px;white-space:nowrap;">${g.registrado_por ? 'Usuario #' + g.registrado_por : '—'}</td>
    </tr>
  `).join('');
}

function openGastosModal() {
  document.getElementById('gasto-form')?.reset();
  const fechaInput = document.getElementById('gasto-fecha');
  if (fechaInput) {
    const today = new Date();
    fechaInput.value = today.toISOString().slice(0, 10);
  }
  document.getElementById('modal-registrar-gasto')?.classList.add('show');
}

function closeGastosModal() {
  document.getElementById('modal-registrar-gasto')?.classList.remove('show');
}

/* =========================================================================
   Calendar — planning events + real attendance
   ========================================================================= */
function calendarDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function calendarDateFromKey(key) {
  const [year, month, day] = key.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function calendarTimeLabel(value) {
  if (!value) return '';
  return formatLocalTime(`2000-01-01T${value}`);
}

function calendarManager() {
  return ['Administrador', 'Gerente'].includes(state.user?.rol);
}

function calendarEventColor(event) {
  const colors = ['azul', 'turquesa', 'ambar', 'rosa', 'violeta', 'gris'];
  return colors.includes(event.color_etiqueta)
    ? event.color_etiqueta
    : event.tipo === 'LLEGADA_INSUMO' ? 'ambar' : 'azul';
}

function toggleCalendarSelectedDate(dateKey) {
  if (state.calendarSelectedDays.has(dateKey)) {
    state.calendarSelectedDays.delete(dateKey);
  } else {
    state.calendarSelectedDays.add(dateKey);
  }
  state.calendarSelectedDay = dateKey;
}

function exitCalendarMultiSelect() {
  clearTimeout(state.calendarPressTimer);
  state.calendarMultiSelecting = false;
  state.calendarSelectedDays.clear();
  state.calendarBulkDates = [];
  renderCalendario();
}

function calendarGridRange(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(first.getFullYear(), first.getMonth(), first.getDate() - offset);
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const endOffset = 6 - ((last.getDay() + 6) % 7);
  const end = new Date(last.getFullYear(), last.getMonth(), last.getDate() + endOffset);
  return { start, end };
}

async function loadCalendario() {
  const grid = document.getElementById('calendar-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="calendar-loading">Cargando calendario…</div>';
  const { start, end } = calendarGridRange(state.calendarMonth);
  const params = new URLSearchParams({
    desde: calendarDateKey(start),
    hasta: calendarDateKey(end),
  });
  try {
    const data = await api(`/calendario/?${params}`);
    state.calendarEvents = data.eventos || [];
    state.calendarAttendances = data.asistencias || [];
    renderCalendario();
  } catch {
    grid.innerHTML = '<div class="calendar-empty calendar-load-error">No se pudo cargar el calendario. Intenta actualizarlo.</div>';
  }
}

function renderCalendario() {
  const title = document.getElementById('calendar-month-title');
  const grid = document.getElementById('calendar-grid');
  const summary = document.getElementById('calendar-summary');
  if (!grid || !title || !summary) return;

  title.textContent = state.calendarMonth.toLocaleDateString('es-NI', {
    month: 'long',
    year: 'numeric',
  });
  const manager = calendarManager();
  const readOnlyNotice = document.getElementById('calendar-readonly-notice');
  if (readOnlyNotice) readOnlyNotice.hidden = manager;
  const dayEvents = new Map();
  const dayAttendances = new Map();
  state.calendarEvents.forEach(event => {
    const start = calendarDateFromKey(event.fecha_inicio);
    const end = calendarDateFromKey(event.fecha_fin || event.fecha_inicio);
    for (let day = new Date(start); day <= end; day.setDate(day.getDate() + 1)) {
      const key = calendarDateKey(day);
      if (!dayEvents.has(key)) dayEvents.set(key, []);
      dayEvents.get(key).push(event);
    }
  });
  state.calendarAttendances.forEach(attendance => {
    if (!dayAttendances.has(attendance.fecha)) dayAttendances.set(attendance.fecha, []);
    dayAttendances.get(attendance.fecha).push(attendance);
  });

  const range = calendarGridRange(state.calendarMonth);
  const rangeStart = calendarDateKey(range.start);
  const rangeEnd = calendarDateKey(range.end);
  if (state.calendarSelectedDay < rangeStart || state.calendarSelectedDay > rangeEnd) {
    state.calendarSelectedDay = calendarDateKey(new Date(
      state.calendarMonth.getFullYear(),
      state.calendarMonth.getMonth(),
      1,
    ));
  }
  const dayHeaders = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    .map(day => `<div class="calendar-weekday">${day}</div>`).join('');
  const dayCells = [];
  for (const day = new Date(range.start); day <= range.end; day.setDate(day.getDate() + 1)) {
    const key = calendarDateKey(day);
    const isCurrentMonth = day.getMonth() === state.calendarMonth.getMonth();
    const isToday = key === calendarDateKey(new Date());
    const events = dayEvents.get(key) || [];
    const attendances = dayAttendances.get(key) || [];
    const eventMarkup = events.slice(0, 3).map(event => {
      const kind = event.tipo === 'LLEGADA_INSUMO' ? 'delivery' : 'dish';
      const color = calendarEventColor(event);
      const related = event.tipo === 'LLEGADA_INSUMO' ? event.insumo_nombre : event.menu_item_nombre;
      const time = event.hora_inicio ? `${calendarTimeLabel(event.hora_inicio)} ` : '';
      const status = event.estado === 'CANCELADO' ? ' · Cancelado' : event.estado === 'REALIZADO' ? ' · Realizado' : '';
      const text = `${time}${event.titulo}${related ? ` · ${related}` : ''}${status}`;
      const safeText = escHtml(text);
      return manager
        ? `<button type="button" class="calendar-event-chip ${kind} color-${color} ${event.estado.toLowerCase()}" data-calendar-event="${event.id}" title="${safeText}">${safeText}</button>`
        : `<div class="calendar-event-chip ${kind} color-${color} ${event.estado.toLowerCase()}" title="${safeText}">${safeText}</div>`;
    }).join('');
    const attendanceMarkup = attendances.slice(0, 2).map(attendance => {
      const time = formatLocalTime(attendance.hora_entrada_real);
      const text = `${time} ${attendance.empleado_nombre} · ${attendance.turno_nombre}`;
      return `<div class="calendar-attendance-chip" title="${escHtml(text)}">${escHtml(text)}</div>`;
    }).join('');
    const hiddenCount = Math.max(0, events.length - 3) + Math.max(0, attendances.length - 2);
    const more = hiddenCount
      ? `<span class="calendar-more">+${hiddenCount} más</span>` : '';
    const dayAction = manager
      ? `<button type="button" class="calendar-day-add" data-calendar-date="${key}" aria-label="Crear evento el ${key}">+</button>`
      : '';
    const isSelected = state.calendarMultiSelecting
      ? state.calendarSelectedDays.has(key)
      : key === state.calendarSelectedDay;
    dayCells.push(`
      <div class="calendar-day ${isCurrentMonth ? '' : 'outside-month'} ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''} ${state.calendarMultiSelecting ? 'multi-selecting' : ''}">
        <div class="calendar-day-header">
          <button type="button" class="calendar-day-select" data-calendar-detail-date="${key}" aria-label="${state.calendarMultiSelecting ? 'Seleccionar' : 'Ver detalles del'} ${key}" aria-pressed="${isSelected}">${day.getDate()}</button>${dayAction}
        </div>
        <div class="calendar-day-items">${eventMarkup}${attendanceMarkup}${more}</div>
      </div>
    `);
  }
  grid.innerHTML = `${dayHeaders}${dayCells.join('')}`;
  const monthEvents = state.calendarEvents.filter(event => {
    const start = calendarDateFromKey(event.fecha_inicio);
    const end = calendarDateFromKey(event.fecha_fin || event.fecha_inicio);
    return start.getMonth() === state.calendarMonth.getMonth()
      || end.getMonth() === state.calendarMonth.getMonth()
      || (start < range.start && end > range.start);
  });
  summary.innerHTML = `
    <span><strong>${monthEvents.length}</strong> evento${monthEvents.length === 1 ? '' : 's'} de planificación</span>
    <span><strong>${state.calendarAttendances.length}</strong> asistencia${state.calendarAttendances.length === 1 ? '' : 's'} registrada${state.calendarAttendances.length === 1 ? '' : 's'} en la vista</span>
  `;
  const selectionToolbar = document.getElementById('calendar-selection-toolbar');
  const selectionCount = document.getElementById('calendar-selection-count');
  const createSelectionButton = document.getElementById('calendar-selection-create');
  if (selectionToolbar && selectionCount && createSelectionButton) {
    const count = state.calendarSelectedDays.size;
    selectionToolbar.hidden = !state.calendarMultiSelecting;
    selectionCount.textContent = `${count} día${count === 1 ? '' : 's'} seleccionado${count === 1 ? '' : 's'}`;
    createSelectionButton.disabled = count < 2;
  }
  grid.querySelectorAll('[data-calendar-event]').forEach(button => {
    button.addEventListener('click', () => openCalendarEventModal(Number(button.dataset.calendarEvent)));
  });
  grid.querySelectorAll('[data-calendar-date]').forEach(button => {
    button.addEventListener('click', () => openCalendarEventModal(null, button.dataset.calendarDate));
  });
  grid.querySelectorAll('[data-calendar-detail-date]').forEach(button => {
    const dateKey = button.dataset.calendarDetailDate;
    button.addEventListener('pointerdown', () => {
      state.calendarSuppressClickDate = null;
      if (!manager || state.calendarMultiSelecting) return;
      clearTimeout(state.calendarPressTimer);
      state.calendarPressTimer = setTimeout(() => {
        state.calendarMultiSelecting = true;
        state.calendarSelectedDays.add(dateKey);
        state.calendarSelectedDay = dateKey;
        state.calendarSuppressClickDate = dateKey;
        renderCalendario();
      }, 450);
    });
    ['pointerup', 'pointerleave', 'pointercancel'].forEach(type => {
      button.addEventListener(type, () => clearTimeout(state.calendarPressTimer));
    });
    button.addEventListener('click', event => {
      if (state.calendarSuppressClickDate === dateKey) {
        state.calendarSuppressClickDate = null;
        return;
      }
      if (state.calendarMultiSelecting || (manager && event.shiftKey)) {
        state.calendarMultiSelecting = true;
        toggleCalendarSelectedDate(dateKey);
        renderCalendario();
        return;
      }
      state.calendarSelectedDay = button.dataset.calendarDetailDate;
      renderCalendario();
    });
  });
  renderCalendarDayDetails(state.calendarSelectedDay);
}

function renderCalendarDayDetails(dateKey) {
  const details = document.getElementById('calendar-day-details');
  const title = document.getElementById('calendar-day-title');
  const content = document.getElementById('calendar-day-content');
  if (!details || !title || !content) return;
  details.hidden = false;
  if (state.calendarMultiSelecting) {
    details.hidden = true;
    return;
  }
  title.textContent = calendarDateFromKey(dateKey).toLocaleDateString('es-NI', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const events = state.calendarEvents.filter(event =>
    event.fecha_inicio <= dateKey && (event.fecha_fin || event.fecha_inicio) >= dateKey
  );
  const attendances = state.calendarAttendances.filter(item => item.fecha === dateKey);
  const eventRows = events.map(event => {
    const arrival = event.tipo === 'LLEGADA_INSUMO';
    const color = calendarEventColor(event);
    const related = arrival ? event.insumo_nombre : event.menu_item_nombre;
    const time = event.hora_inicio
      ? `${calendarTimeLabel(event.hora_inicio)}–${calendarTimeLabel(event.hora_fin)}`
      : 'Todo el día';
    const dateRange = event.fecha_fin && event.fecha_fin !== event.fecha_inicio
      ? `${calendarDateFromKey(event.fecha_inicio).toLocaleDateString('es-NI')} – ${calendarDateFromKey(event.fecha_fin).toLocaleDateString('es-NI')}`
      : '';
    const quantity = event.cantidad_esperada
      ? `${event.cantidad_esperada} ${event.insumo_unidad_medida || ''}`.trim()
      : '';
    const status = event.estado === 'REALIZADO' ? 'Realizado' : event.estado === 'CANCELADO' ? 'Cancelado' : 'Planificado';
    const item = `
      <span class="calendar-detail-icon ${arrival ? 'delivery' : 'dish'} color-${color} material-symbols-outlined">${arrival ? 'local_shipping' : 'restaurant'}</span>
      <span class="calendar-detail-copy">
        <strong>${escHtml(event.titulo)}</strong>
        <span>${escHtml(related || '')}${quantity ? ` · ${escHtml(quantity)}` : ''}${event.proveedor_nombre ? ` · ${escHtml(event.proveedor_nombre)}` : ''}</span>
        <span>${escHtml(time)}${dateRange ? ` · ${escHtml(dateRange)}` : ''} · ${status}</span>
        ${event.descripcion ? `<span class="calendar-detail-note">${escHtml(event.descripcion)}</span>` : ''}
      </span>`;
    return calendarManager()
      ? `<button type="button" class="calendar-detail-row calendar-event-detail" data-calendar-event="${event.id}">${item}</button>`
      : `<div class="calendar-detail-row">${item}</div>`;
  }).join('');
  const attendanceRows = attendances.map(attendance => `
    <div class="calendar-detail-row attendance">
      <span class="calendar-detail-icon attendance material-symbols-outlined">badge</span>
      <span class="calendar-detail-copy">
        <strong>${escHtml(attendance.empleado_nombre)}</strong>
        <span>Turno ${escHtml(attendance.turno_nombre)}</span>
        <span>Entrada ${escHtml(formatLocalTime(attendance.hora_entrada_real))} · Salida ${attendance.hora_salida_real ? escHtml(formatLocalTime(attendance.hora_salida_real)) : 'En curso'}</span>
      </span>
    </div>
  `).join('');
  content.innerHTML = eventRows + attendanceRows
    || '<p class="calendar-day-empty">No hay eventos ni asistencias registrados para este día.</p>';
  content.querySelectorAll('[data-calendar-event]').forEach(button => {
    button.addEventListener('click', () => openCalendarEventModal(Number(button.dataset.calendarEvent)));
  });
}

async function loadCalendarCatalogs() {
  if (state.calendarCatalogsLoaded) return;
  const [menuItems, insumos, proveedores] = await Promise.all([
    api('/menu/items?incluir_inactivos=true'),
    api('/inventario/insumos'),
    api('/inventario/proveedores'),
  ]);
  state.calendarMenuItems = menuItems;
  state.calendarInsumos = insumos;
  state.calendarProveedores = proveedores;
  state.calendarCatalogsLoaded = true;
}

function fillCalendarSelect(id, rows, placeholder) {
  const select = document.getElementById(id);
  if (!select) return;
  select.innerHTML = `<option value="">${escHtml(placeholder)}</option>`
    + rows.map(row => `<option value="${row.id}">${escHtml(row.nombre)}</option>`).join('');
}

function setCalendarEventTypeFields() {
  const arrival = document.getElementById('calendar-event-type')?.value === 'LLEGADA_INSUMO';
  document.querySelectorAll('.calendar-arrival-fields').forEach(el => { el.hidden = !arrival; });
  document.querySelectorAll('.calendar-dish-field').forEach(el => { el.hidden = arrival; });
}

function updateCalendarQuantityUnit() {
  const select = document.getElementById('calendar-event-insumo');
  const hint = document.getElementById('calendar-quantity-unit');
  if (!select || !hint) return;
  const insumo = state.calendarInsumos.find(item => item.id === Number(select.value));
  hint.textContent = insumo?.unidad_medida
    ? `La cantidad se registra en ${insumo.unidad_medida}.`
    : 'La cantidad se registra en la unidad base del insumo.';
}

async function openCalendarEventModal(eventId = null, dateKey = null, bulkDates = []) {
  if (!calendarManager()) return;
  try {
    await loadCalendarCatalogs();
  } catch {
    return;
  }
  if (!eventId && bulkDates.length < 2 && state.calendarMultiSelecting) {
    state.calendarMultiSelecting = false;
    state.calendarSelectedDays.clear();
    renderCalendario();
  }
  fillCalendarSelect('calendar-event-dish', state.calendarMenuItems, 'Selecciona un platillo');
  fillCalendarSelect('calendar-event-insumo', state.calendarInsumos, 'Selecciona un insumo');
  fillCalendarSelect('calendar-event-provider', state.calendarProveedores, 'Sin proveedor asignado');

  const form = document.getElementById('calendar-event-form');
  form.reset();
  const existing = eventId
    ? state.calendarEvents.find(event => event.id === eventId)
    : null;
  document.getElementById('calendar-event-id').value = existing?.id || '';
  document.getElementById('calendar-event-title').textContent = existing ? 'Editar evento' : 'Nuevo evento';
  state.calendarBulkDates = existing ? [] : [...bulkDates].sort();
  const bulkHint = document.getElementById('calendar-bulk-hint');
  const dateRange = document.getElementById('calendar-event-date-range');
  bulkHint.hidden = state.calendarBulkDates.length < 2;
  bulkHint.textContent = state.calendarBulkDates.length >= 2
    ? `Se creará una copia del evento únicamente en estos ${state.calendarBulkDates.length} días seleccionados.`
    : '';
  dateRange.hidden = state.calendarBulkDates.length >= 2;
  document.querySelector(`input[name="calendar-event-color"][value="${calendarEventColor(existing || {})}"]`).checked = true;
  document.getElementById('calendar-event-type').value = existing?.tipo || 'DISPONIBILIDAD_PLATILLO';
  document.getElementById('calendar-event-dish').value = existing?.menu_item_id || '';
  document.getElementById('calendar-event-insumo').value = existing?.insumo_id || '';
  updateCalendarQuantityUnit();
  document.getElementById('calendar-event-provider').value = existing?.proveedor_id || '';
  document.getElementById('calendar-event-quantity').value = existing?.cantidad_esperada || '';
  document.getElementById('calendar-event-name').value = existing?.titulo || '';
  document.getElementById('calendar-event-start').value = existing?.fecha_inicio || state.calendarBulkDates[0] || dateKey || calendarDateKey(new Date());
  document.getElementById('calendar-event-end').value = existing?.fecha_fin || '';
  document.getElementById('calendar-event-time-start').value = existing?.hora_inicio?.slice(0, 5) || '';
  document.getElementById('calendar-event-time-end').value = existing?.hora_fin?.slice(0, 5) || '';
  document.getElementById('calendar-event-status').value = existing?.estado || 'PLANIFICADO';
  document.getElementById('calendar-event-description').value = existing?.descripcion || '';
  document.getElementById('delete-calendar-event').style.display = existing ? 'inline-flex' : 'none';
  setCalendarEventTypeFields();
  document.getElementById('modal-calendar-event').classList.add('show');
}

function closeCalendarEventModal() {
  document.getElementById('modal-calendar-event')?.classList.remove('show');
  state.calendarBulkDates = [];
  const bulkHint = document.getElementById('calendar-bulk-hint');
  const dateRange = document.getElementById('calendar-event-date-range');
  if (bulkHint) bulkHint.hidden = true;
  if (dateRange) dateRange.hidden = false;
}

async function saveCalendarEvent(event) {
  event.preventDefault();
  const id = document.getElementById('calendar-event-id').value;
  const tipo = document.getElementById('calendar-event-type').value;
  const fechaInicio = document.getElementById('calendar-event-start').value;
  const fechaFin = document.getElementById('calendar-event-end').value;
  const horaInicio = document.getElementById('calendar-event-time-start').value;
  const horaFin = document.getElementById('calendar-event-time-end').value;
  const titulo = document.getElementById('calendar-event-name').value.trim();
  if (!titulo || !fechaInicio) return showToast('Completa el título y la fecha inicial', 'warning');
  if (Boolean(horaInicio) !== Boolean(horaFin)) return showToast('Indica ambas horas o deja el evento sin horario', 'warning');
  if (fechaFin && fechaFin < fechaInicio) return showToast('La fecha final no puede ser anterior a la inicial', 'warning');
  if (horaInicio && (!fechaFin || fechaFin === fechaInicio) && horaFin <= horaInicio) {
    return showToast('La hora final debe ser posterior a la inicial', 'warning');
  }
  const menuItemId = document.getElementById('calendar-event-dish').value;
  const insumoId = document.getElementById('calendar-event-insumo').value;
  const proveedorId = document.getElementById('calendar-event-provider').value;
  if (tipo === 'DISPONIBILIDAD_PLATILLO' && !menuItemId) return showToast('Selecciona el platillo', 'warning');
  if (tipo === 'LLEGADA_INSUMO' && !insumoId) return showToast('Selecciona el insumo', 'warning');

  const quantity = document.getElementById('calendar-event-quantity').value;
  const body = {
    tipo,
    titulo,
    color_etiqueta: document.querySelector('input[name="calendar-event-color"]:checked')?.value || 'azul',
    descripcion: document.getElementById('calendar-event-description').value.trim() || null,
    fecha_inicio: fechaInicio,
    fecha_fin: fechaFin || null,
    hora_inicio: horaInicio || null,
    hora_fin: horaFin || null,
    estado: document.getElementById('calendar-event-status').value,
    menu_item_id: tipo === 'DISPONIBILIDAD_PLATILLO' ? Number(menuItemId) : null,
    insumo_id: tipo === 'LLEGADA_INSUMO' ? Number(insumoId) : null,
    proveedor_id: tipo === 'LLEGADA_INSUMO' && proveedorId ? Number(proveedorId) : null,
    cantidad_esperada: tipo === 'LLEGADA_INSUMO' && quantity ? Number(quantity) : null,
  };
  const button = document.getElementById('save-calendar-event');
  button.disabled = true;
  try {
    const bulk = !id && state.calendarBulkDates.length >= 2;
    if (bulk) {
      body.fecha_inicio = state.calendarBulkDates[0];
      body.fecha_fin = null;
      body.fechas = state.calendarBulkDates;
    }
    await api(id ? `/calendario/eventos/${id}` : bulk ? '/calendario/eventos/masivo' : '/calendario/eventos', {
      method: id ? 'PUT' : 'POST',
      body: JSON.stringify(body),
    });
    closeCalendarEventModal();
    if (bulk) exitCalendarMultiSelect();
    showToast(id ? 'Evento actualizado' : bulk ? `Evento creado en ${body.fechas.length} días` : 'Evento creado', 'success');
    await loadCalendario();
  } catch {
    // api() reports the request error.
  } finally {
    button.disabled = false;
  }
}

async function deleteCalendarEvent() {
  const id = document.getElementById('calendar-event-id').value;
  if (!id || !window.confirm('¿Eliminar este evento del calendario?')) return;
  const button = document.getElementById('delete-calendar-event');
  button.disabled = true;
  try {
    await api(`/calendario/eventos/${id}`, { method: 'DELETE' });
    closeCalendarEventModal();
    showToast('Evento eliminado', 'success');
    await loadCalendario();
  } catch {
    // api() reports the request error.
  } finally {
    button.disabled = false;
  }
}

async function guardarGasto() {
  const fecha = document.getElementById('gasto-fecha')?.value;
  const categoria = document.getElementById('gasto-categoria')?.value;
  const monto = parseFloat(document.getElementById('gasto-monto')?.value);
  const concepto = document.getElementById('gasto-descripcion')?.value.trim();

  if (!fecha) return showToast('Selecciona una fecha', 'warning');
  if (!categoria) return showToast('Selecciona una categoría', 'warning');
  if (!monto || monto <= 0) return showToast('Ingresa un monto válido', 'warning');
  if (!concepto) return showToast('Ingresa una descripción', 'warning');

  const btn = document.getElementById('save-gasto-btn');
  btn.disabled = true;
  btn.textContent = 'Guardando…';
  try {
    await api('/gastos/', {
      method: 'POST',
      body: JSON.stringify({ categoria, monto, concepto, fecha }),
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

/*    =========================================================================
   Tables (Salón)
   ========================================================================= */
let activeEstadoFilter = 'all';
let activeZonaFilter = 'all';
let activeMgmtCatFilter = 'all';
let activeMgmtStatusFilter = 'activos';
let activeCartaCatFilter = 'all';
let cartaSearch = '';

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
    actualizarOcupacion();
    enriquecerMesasOcupadas();
  } catch { state.tables = []; renderTables([]); actualizarOcupacion(); }
}

function renderZonasFilters(zonas) {
  const container = document.getElementById('zona-filters');
  if (!container) return;
  container.innerHTML = `
    <button type="button" class="shrink-0 flex items-center gap-1.5 h-8 px-3.5 rounded-full text-xs font-semibold border-2 border-slate-200 bg-white text-slate-600 aria-selected:bg-brand-coral aria-selected:text-white aria-selected:border-brand-coral" data-zona="all" role="tab" aria-selected="true">🗺️ Todas las Zonas</button>
    ${zonas.map(z => `<button type="button" class="shrink-0 flex items-center gap-1.5 h-8 px-3.5 rounded-full text-xs font-semibold border-2 border-slate-200 bg-white text-slate-600 aria-selected:bg-brand-coral aria-selected:text-white aria-selected:border-brand-coral" data-zona="${z.id}" role="tab" aria-selected="false">📍 ${z.nombre}</button>`).join('')}
  `;
  container.querySelectorAll('[data-zona]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('[data-zona]').forEach(c => {
        c.classList.remove('active');
        c.setAttribute('aria-selected', 'false');
      });
      chip.classList.add('active');
      chip.setAttribute('aria-selected', 'true');
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

const ESTADO_MESA = {
  LIBRE: {
    label: 'Libre', border: 'border-emerald-200', iconBox: 'bg-emerald-50 text-emerald-600', icon: 'table_restaurant',
    badge: 'border-emerald-100 text-emerald-700', dot: 'bg-emerald-500',
    statusClass: 'text-emerald-600', statusIcon: 'check_circle', statusText: 'Lista p/ asignar',
    rows: [
      { icon: 'chair', text: m => `Capacidad ${m.capacidad} personas` },
      { icon: 'cleaning_services', text: () => 'Limpia y montada' },
    ],
    footer: 'border-2 border-slate-200 text-brand-navy bg-white', footerIcon: 'add', footerText: 'Abrir comanda', extra: 'add_circle',
  },
  OCUPADA: {
    label: 'Ocupada', border: 'border-brand-coral/25', iconBox: 'bg-brand-coral/10 text-brand-coral', icon: 'restaurant',
    badge: 'border-brand-coral/15 text-brand-coral', dot: 'bg-brand-coral',
    statusClass: 'text-brand-coral', statusIcon: 'timer', statusText: 'En atención',
    rows: [
      { icon: 'person', text: () => '<span class="oc-mesero">Asignando…</span>' },
      { icon: 'groups', text: m => `Hasta ${m.capacidad} comensales` },
    ],
    footer: 'bg-brand-turquoise text-white', footerIcon: 'receipt_long', footerText: m => `Cuenta: <span class="oc-total">C$ —</span>`, extra: '',
  },
  RESERVADA: {
    label: 'Reservada', border: 'border-brand-sun/40', iconBox: 'bg-brand-sun/15 text-amber-500', icon: 'event_available',
    badge: 'border-brand-sun/40 text-amber-600', dot: 'bg-amber-400',
    statusClass: 'text-amber-500', statusIcon: 'schedule', statusText: 'Apartada',
    rows: [
      { icon: 'event', text: () => 'Reserva activa' },
    ],
    footer: 'border-2 border-brand-sun/40 text-amber-600 bg-white', footerIcon: 'lock', footerText: 'Reservada', extra: '',
  },
  MANTENIMIENTO: {
    label: 'Mantenimiento', border: 'border-slate-200', iconBox: 'bg-slate-100 text-slate-500', icon: 'build',
    badge: 'border-slate-200 text-slate-500', dot: 'bg-slate-400',
    statusClass: 'text-slate-500', statusIcon: 'warning', statusText: 'Fuera de servicio',
    rows: [
      { icon: 'construction', text: () => 'En reparación' },
    ],
    footer: 'border-2 border-slate-200 text-slate-400 bg-white opacity-80', footerIcon: 'settings', footerText: 'Mantenimiento', extra: '',
  },
};

function tableCardHTML(m) {
  const estado = m.estado || 'LIBRE';
  const s = ESTADO_MESA[estado] || ESTADO_MESA.LIBRE;
  const zona = m.zona_nombre || 'Zona ' + m.zona_id;
  const rows = s.rows.map(r => `
        <div class="flex items-center gap-1.5 text-xs text-slate-600">
          <span class="material-symbols-outlined text-[14px] text-slate-400">${r.icon}</span><span>${r.text(m)}</span>
        </div>`).join('');
  const footerText = typeof s.footerText === 'function' ? s.footerText(m) : s.footerText;
  return `
      <article class="relative flex flex-col justify-between gap-2 bg-white rounded-2xl p-2.5 sm:p-3.5 ${s.border} border-2 cursor-pointer shadow-[0_1px_2px_rgba(15,23,42,0.05)] transition active:scale-[0.98]"
               data-mesa-id="${m.id}" data-estado="${estado}" data-zona-id="${m.zona_id}" role="button" tabindex="0"
               aria-label="Mesa ${m.numero}${m.apodo ? ', ' + m.apodo : ''}, ${estado.toLowerCase()}">
        <div class="flex items-start gap-2.5 flex-wrap">
          <div class="grid place-items-center w-8 h-8 rounded-lg shrink-0 ${s.iconBox}">
            <span class="material-symbols-outlined text-[18px]">${s.icon}</span>
          </div>
          <div class="min-w-0 flex-1 leading-tight">
            <h3 class="font-display font-bold text-sm sm:text-base text-slate-900 whitespace-nowrap">Mesa ${m.numero}</h3>
            <span class="block text-[11px] font-medium text-slate-400">${zona}</span>
            ${m.apodo ? `<span class="oc-apodo mt-0.5 inline-flex items-center gap-0.5 text-[11px] font-bold text-brand-coral"><span class="material-symbols-outlined text-[12px]">tag</span>${escHtml(m.apodo)}</span>` : ''}
          </div>
          <span class="ml-auto shrink-0 inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${s.badge}">
            <span class="w-1.5 h-1.5 rounded-full ${s.dot}${estado === 'OCUPADA' ? ' animate-ping' : ''}"></span>${s.label}
          </span>
        </div>
        <div class="flex items-center gap-1.5 text-xs font-semibold ${s.statusClass}">
          <span class="material-symbols-outlined text-[15px] mb-0.5">${s.statusIcon}</span><span class="oc-status">${s.statusText}</span>
        </div>
        <div class="space-y-1">${rows}</div>
        <div class="mt-0.5 flex items-center justify-between py-1.5 px-2 rounded-lg text-xs font-semibold ${s.footer}">
          <span class="flex items-center gap-1.5"><span class="material-symbols-outlined text-[16px]">${s.footerIcon}</span>${footerText}</span>
          ${s.extra ? `<span class="material-symbols-outlined text-[16px]">${s.extra}</span>` : ''}
        </div>
      </article>`;
}

function renderTables(mesas) {
  const grid = document.getElementById('table-grid');
  if (!grid) return;
  if (!mesas || mesas.length === 0) {
    grid.innerHTML = '<p class="text-center text-slate-400" style="grid-column:1/-1;padding:32px;font-size:13px;">No hay mesas configuradas</p>';
    return;
  }
  grid.innerHTML = mesas.map(tableCardHTML).join('');

  grid.querySelectorAll('[data-mesa-id]').forEach(card => {
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

function actualizarOcupacion() {
  const ts = state.tables || [];
  const total = ts.length;
  const ocupadas = ts.filter(t => t.estado === 'OCUPADA').length;
  const pct = total ? Math.round((ocupadas / total) * 100) : 0;
  const set2 = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set2('cnt-all', total);
  set2('cnt-libre', ts.filter(t => t.estado === 'LIBRE').length);
  set2('cnt-ocupada', ocupadas);
  set2('cnt-reservada', ts.filter(t => t.estado === 'RESERVADA').length);
  set2('occupancy-pct', pct + '%');
  set2('occupancy-count', ocupadas + '/' + total);
  const bar = document.getElementById('occupancy-bar');
  if (bar) bar.style.width = pct + '%';
}

function enriquecerMesasOcupadas() {
  state.tables.filter(t => t.estado === 'OCUPADA' && t.id).forEach(m => {
    api('/ordenes/?mesa_id=' + m.id)
      .then(ords => {
        const activa = (ords || []).find(o => !['PAGADA', 'CANCELADA'].includes(o.estado));
        m._orden = activa || null;
        if (activa) actualizarCardOcupada(m, activa);
      })
      .catch(() => {});
  });
}

function actualizarCardOcupada(m, o) {
  const card = document.querySelector(`#table-grid [data-mesa-id="${m.id}"]`);
  if (!card) return;
  const time = card.querySelector('.oc-status');
  const mesero = card.querySelector('.oc-mesero');
  const total = card.querySelector('.oc-total');
  if (time) time.textContent = 'Hace ' + getTiempoTranscurrido(o.fecha_creacion);
  const nombreMesero = o.mesero?.nombre || o.mesero?.username || '';
  if (mesero) mesero.textContent = nombreMesero || 'Sin asignar';
  if (total) total.textContent = 'C$' + parseFloat(o.total || 0).toFixed(2);
}

/* =========================================================================
   Table Filtering (Estado)
   ========================================================================= */
document.querySelectorAll('[data-filter]').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('[data-filter]').forEach(c => {
      c.classList.remove('active');
      c.setAttribute('aria-selected', 'false');
    });
    chip.classList.add('active');
    chip.setAttribute('aria-selected', 'true');
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

const ESTADO_PILL_KDS = {
  PENDIENTE:   { label: 'Nueva',          cls: 'bg-brand-coral/10 text-brand-coral' },
  PREPARANDO:  { label: 'En Preparación', cls: 'bg-brand-turquoise/10 text-brand-turquoise' },
  ENTREGADA:   { label: 'Lista',          cls: 'bg-emerald-50 text-emerald-600' },
  PAGADA:      { label: 'Pagada',         cls: 'bg-slate-100 text-slate-500' },
  CANCELADA:   { label: 'Cancelada',      cls: 'bg-slate-100 text-slate-400' },
};

function renderCocinaTabCounts() {
  const set2 = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  const enCocina = cocinaOrdenes.filter(o => o.estado === 'PENDIENTE' || o.estado === 'PREPARANDO').length;
  const listas = cocinaOrdenes.filter(o => o.estado === 'ENTREGADA').length;
  set2('kc-count-cocina', enCocina);
  set2('kc-count-lista', listas);
}

async function loadCocinaOrdenes() {
  const grid = document.getElementById('cocina-grid');
  if (!grid) return;
  try {
    const ordenes = await api('/ordenes/');
    cocinaOrdenes = ordenes;
    renderCocinaCards();
    renderCocinaTabCounts();
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
    grid.innerHTML = `<div class="text-center text-slate-400 py-12 text-[13px]" style="grid-column:1/-1;">${emptyMsg}</div>`;
    return;
  }

  grid.innerHTML = filtered.map(o => {
    const esParaLlevar = !o.mesa_id;
    const zona = esParaLlevar ? 'Salón' : (o.mesa?.zona?.nombre || '—');
    const mesaLabel = esParaLlevar ? 'Para Llevar' : `Mesa ${o.mesa?.numero || o.mesa_id}`;
    const mesero = o.mesero?.username || `Usuario #${o.mesero_id}`;
    const tiempo = getTiempoTranscurrido(o.fecha_creacion);
    const minutos = getMinutosTranscurrido(o.fecha_creacion);
    const tiempoClass = minutos > 20 ? 'kc-tiempo-urgente' : minutos > 8 ? 'kc-tiempo-ok' : 'kc-tiempo-calmado';
    const pill = ESTADO_PILL_KDS[o.estado] || ESTADO_PILL_KDS.PENDIENTE;
    const showActions = o.estado !== 'PAGADA' && o.estado !== 'CANCELADA';

    const itemsHtml = (o.detalles || []).map(d => {
      const nombre = d.producto_nombre || `Producto #${d.producto_id}`;
      const notas = d.notas ? `
            <span class="kc-notas"><span class="material-symbols-outlined text-[12px]">info</span>${d.notas}</span>` : '';
      return `
          <li class="flex items-start justify-between gap-2 px-3.5 py-2 border-b border-slate-100 last:border-none">
            <span class="kc-qty">${d.cantidad}×</span>
            <span class="min-w-0 flex-1">
              <span class="block text-[13px] font-semibold text-slate-700 leading-snug">${nombre}</span>
              ${notas}
            </span>
          </li>`;
    }).join('');

    const actionsHtml = showActions ? (() => {
      const cobrarBtn = `<button type="button" class="kc-btn-cobrar" onclick="cobrarOrden(${o.id})"><span class="material-symbols-outlined text-[18px]">payments</span>Cobrar</button>`;
      const cancelBtn = `<button type="button" class="kc-btn-cancelar" onclick="cambiarEstadoKDS(${o.id}, 'CANCELADA')" title="Cancelar orden"><span class="material-symbols-outlined text-[16px]">close</span>Cancelar</button>`;
      if (o.estado === 'PENDIENTE') {
        return `<div class="kc-actions">
            <button type="button" class="kc-btn-entregar kc-btn-coral" onclick="cambiarEstadoKDS(${o.id}, 'PREPARANDO')"><span class="material-symbols-outlined text-[19px]">soup_kitchen</span>En Preparación</button>
            ${cobrarBtn}
            ${cancelBtn}
          </div>`;
      }
      if (o.estado === 'PREPARANDO') {
        return `<div class="kc-actions">
            <button type="button" class="kc-btn-entregar kc-btn-turquoise" onclick="cambiarEstadoKDS(${o.id}, 'ENTREGADA')"><span class="material-symbols-outlined text-[19px]">check_circle</span>Lista p/ Servir</button>
            ${cobrarBtn}
            ${cancelBtn}
          </div>`;
      }
      return `<div class="kc-actions">
          ${cobrarBtn}
          ${cancelBtn}
        </div>`;
    })() : '';

    return `
      <article class="kc-card animate-in">
        <header class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[16px] text-slate-400 shrink-0">${esParaLlevar ? 'shopping_bag' : 'table_restaurant'}</span>
              <h3 class="font-display font-extrabold text-sm text-brand-navy truncate">${mesaLabel}</h3>
            </div>
            <p class="text-[11px] font-medium text-slate-500 mt-0.5 truncate">📍 ${zona} · 🧑‍🍳 ${mesero} · Orden #${o.id}</p>
          </div>
          <div class="shrink-0 flex flex-col items-end gap-1">
            <span class="kc-tiempo ${tiempoClass}"><span class="material-symbols-outlined text-[14px]">timer</span>${tiempo}</span>
            <span class="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${pill.cls}">${pill.label}</span>
          </div>
        </header>
        <ul class="kc-items mt-2.5">${itemsHtml}</ul>
        <div class="flex items-center justify-between mt-3 px-3.5">
          <span class="text-[13px] font-extrabold text-brand-navy">C$${parseFloat(o.total || 0).toFixed(2)}</span>
          <span class="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">${(o.detalles || []).length} ítem${(o.detalles || []).length === 1 ? '' : 's'}</span>
        </div>
        ${actionsHtml}
      </article>`;
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

async function cobrarOrden(ordenId) {
  const orden = cocinaOrdenes.find(item => item.id === ordenId);
  openMetodoPago(orden || { id: ordenId, total: 0 }, 'kds');
}

function openMetodoPago(orden, origen) {
  if (!orden?.id) return showToast('No se encontró la orden que deseas cobrar', 'error');
  state.paymentOrder = { id: orden.id, total: Number(orden.total || 0), origen };
  state.paymentBusy = false;
  document.getElementById('payment-order-total').textContent =
    `C$${state.paymentOrder.total.toFixed(2)}`;
  const onlineButton = document.getElementById('btn-pago-online');
  onlineButton.disabled = true;
  document.getElementById('payment-online-status').textContent =
    'Verificando disponibilidad…';
  document.getElementById('btn-pago-local').disabled = false;
  document.getElementById('modal-metodo-pago').classList.add('show');
  verificarDisponibilidadPagoOnline();
}

async function verificarDisponibilidadPagoOnline() {
  const button = document.getElementById('btn-pago-online');
  const statusText = document.getElementById('payment-online-status');
  try {
    const disponibilidad = await api('/pagos/disponibilidad', { silent: true });
    button.disabled = !disponibilidad.habilitado;
    statusText.textContent = disponibilidad.habilitado
      ? `Disponible${disponibilidad.proveedor_configurado ? ` · ${disponibilidad.proveedor_configurado}` : ''}`
      : 'Aún no está configurado el proveedor de pagos.';
  } catch {
    button.disabled = true;
    statusText.textContent = 'No se pudo verificar. Intenta de nuevo.';
  }
}

function cerrarMetodoPago() {
  document.getElementById('modal-metodo-pago').classList.remove('show');
  state.paymentOrder = null;
  state.paymentBusy = false;
  document.getElementById('btn-pago-local').disabled = false;
  document.getElementById('btn-pago-online').disabled = true;
}

async function confirmarPagoLocal() {
  const orden = state.paymentOrder;
  if (!orden || state.paymentBusy) return;
  if (!confirm(`¿Confirmas que recibiste el pago de la Orden #${orden.id} en el local?`)) return;
  state.paymentBusy = true;
  document.getElementById('btn-pago-local').disabled = true;
  try {
    await api(`/ordenes/${orden.id}/pagar`, { method: 'PUT' });
    showToast(`Orden #${orden.id} pagada con éxito`, 'success');
    cerrarMetodoPago();
    if (orden.origen === 'mesa' && state.currentOcupada?.orden?.id === orden.id) {
      closeDetalleMesaOcupada();
      await loadTables();
    } else {
      await loadCocinaOrdenes();
    }
  } catch {
    state.paymentBusy = false;
    document.getElementById('btn-pago-local').disabled = false;
  }
}

function crearClaveIdempotencia(ordenId) {
  const random = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `pos-${ordenId}-${random}`;
}

async function iniciarPagoOnline() {
  const orden = state.paymentOrder;
  if (!orden || state.paymentBusy) return;
  const checkoutWindow = window.open('about:blank', '_blank');
  if (!checkoutWindow) {
    showToast('Permite las ventanas emergentes para abrir el pago en línea.', 'warning', 5000);
    return;
  }

  state.paymentBusy = true;
  document.getElementById('btn-pago-online').disabled = true;
  document.getElementById('btn-pago-local').disabled = true;
  document.getElementById('payment-online-status').textContent =
    'Preparando el checkout seguro…';
  try {
    const result = await api(`/pagos/ordenes/${orden.id}/checkout`, {
      method: 'POST',
      headers: { 'Idempotency-Key': crearClaveIdempotencia(orden.id) },
    });
    const checkoutUrl = result?.pago?.checkout_url;
    let checkoutAddress;
    try {
      checkoutAddress = new URL(checkoutUrl);
    } catch {
      showToast('El proveedor no devolvió una dirección de pago válida.', 'error', 5000);
      throw new Error('URL de checkout inválida');
    }
    if (checkoutAddress.protocol !== 'https:') {
      showToast('El proveedor no devolvió una dirección de pago segura.', 'error', 5000);
      throw new Error('El proveedor no devolvió una dirección de pago segura.');
    }
    checkoutWindow.location.replace(checkoutAddress.href);
    cerrarMetodoPago();
    showToast(
      'Checkout abierto. La orden se marcará pagada solo al confirmar el proveedor.',
      'success',
      6000,
    );
  } catch {
    checkoutWindow.close();
    state.paymentBusy = false;
    document.getElementById('btn-pago-online').disabled = false;
    document.getElementById('btn-pago-local').disabled = false;
  }
}
window.cobrarOrden = cobrarOrden;

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
  if (!grid) return;
  if (!items || items.length === 0) {
    grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:32px;">
      <span class="material-symbols-outlined text-[34px] text-slate-300">restaurant_menu</span>
      <p class="text-[13px] font-medium text-slate-400 mt-2">No hay productos disponibles</p>
    </div>`;
    return;
  }
  grid.innerHTML = items.map(item => {
    const media = getMenuMedia(item.categoria?.nombre);
    const cat = item.categoria?.nombre || 'Sin categoría';
    const catTagBg = /bebida/i.test(cat) ? 'bg-brand-turquoise/10 text-brand-turquoise'
      : /marisco|ceviche|pescado/i.test(cat) ? 'bg-brand-coral/10 text-brand-coral'
      : /postre/i.test(cat) ? 'bg-amber-100 text-amber-600'
      : 'bg-slate-100 text-slate-500';
    return `
      <article class="menu-card animate-in h-full" data-item-id="${item.id}">
        <div class="menu-card-media grid place-items-center ${media.bg}" aria-hidden="true">
          <span class="material-symbols-outlined text-[40px] ${media.color}">${media.icon}</span>
        </div>
        <div class="p-3 flex flex-col gap-1.5 flex-1">
          <span class="inline-flex self-start items-center text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${catTagBg}">${cat}</span>
          <h3 class="text-[13px] font-bold leading-snug text-brand-navy line-clamp-2">${item.nombre}</h3>
          <div class="mt-auto pt-1 flex items-center justify-between">
            <span class="font-display font-extrabold text-[15px] text-brand-navy">C$${parseFloat(item.precio).toFixed(2)}</span>
            <button type="button" class="grid place-items-center w-8 h-8 rounded-full bg-brand-coral text-white shadow-sm shadow-brand-coral/30 active:scale-90 transition"
                    aria-label="Agregar ${item.nombre}" onclick="openOrderModal(null, null)">+</button>
          </div>
        </div>
      </article>`;
  }).join('');
}

function getMenuMedia(cat) {
  const n = (cat || '').toLowerCase();
  if (n.includes('bebida')) return { bg: 'bg-brand-turquoise/15', color: 'text-brand-turquoise', icon: 'local_cafe' };
  if (n.includes('marisco') || n.includes('ceviche') || n.includes('pescado')) return { bg: 'bg-brand-coral/10', color: 'text-brand-coral', icon: 'set_meal' };
  if (n.includes('postre')) return { bg: 'bg-amber-50', color: 'text-amber-500', icon: 'icecream' };
  if (n.includes('entrada')) return { bg: 'bg-emerald-50', color: 'text-emerald-600', icon: 'eco' };
  return { bg: 'bg-brand-sun/15', color: 'text-amber-500', icon: 'restaurant_menu' };
}

/* =========================================================================
   Order Modal (Tomar Comanda)
   ========================================================================= */
let orderModalCategory = 'all';
let orderModalSearch = '';

async function renderOrderModalCategories() {
  const container = document.getElementById('order-modal-categories');
  if (!container) return;

  if (!state.categories || !state.categories.length) {
    try { state.categories = await api('/menu/categorias'); } catch { state.categories = []; }
  }

  let html = `<button class="category-tab active" data-om-cat="all">Todo</button>`;
  state.categories.forEach(cat => {
    html += `<button class="category-tab" data-om-cat="${cat.id}">${cat.nombre}</button>`;
  });
  container.innerHTML = html;

  container.querySelectorAll('.category-tab').forEach(tab => {
    tab.addEventListener('click', () => filterOrderModalByCategory(tab.dataset.omCat));
  });
}

function openOrderModal(mesaId, mesaNumero) {
  state.currentOrder = { mesaId, items: [] };
  state.selectedMesa = mesaId;
  orderModalCategory = 'all';
  orderModalSearch = '';

  const titleEl = document.getElementById('order-modal-mesa');
  const clienteRow = document.getElementById('order-modal-cliente-row');
  const cobrarRow = document.getElementById('order-modal-cobrar-row');
  if (mesaId) {
    titleEl.textContent = `Mesa ${mesaNumero}`;
    if (clienteRow) clienteRow.style.display = 'none';
    if (cobrarRow) cobrarRow.style.display = 'none';
  } else {
    titleEl.textContent = '🛍️ Para Llevar';
    if (clienteRow) clienteRow.style.display = '';
    if (cobrarRow) cobrarRow.style.display = 'flex';
  }

  document.getElementById('order-modal-count').textContent = '0';
  document.getElementById('order-modal-subtotal').textContent = 'C$0.00';
  document.getElementById('order-modal-descuento-row').style.display = 'none';
  document.getElementById('order-modal-total').textContent = 'C$0.00';

  const searchInput = document.getElementById('order-modal-search');
  if (searchInput) searchInput.value = '';
  const clienteInput = document.getElementById('order-modal-cliente');
  if (clienteInput) {
    clienteInput.value = '';
    if (!mesaId) setTimeout(() => clienteInput.focus(), 300);
  }

  document.getElementById('order-modal-cart').innerHTML =
    '<p style="text-align:center;color:#9ca3af;padding:16px;font-size:13px;">Vacío — toca + para agregar</p>';
  document.getElementById('order-modal-menu').innerHTML =
    '<p class="text-center text-muted" style="grid-column:1/-1;padding:24px;">Cargando menú…</p>';

  document.getElementById('modal-order').classList.add('show');
  renderOrderModalCategories();
  loadOrderModalMenu();
}

function abrirOrdenParaLlevar() {
  openOrderModal(null, null);
}
window.abrirOrdenParaLlevar = abrirOrdenParaLlevar;
function openParaLlevarModal() {
  abrirOrdenParaLlevar();
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
    const catId = parseInt(orderModalCategory, 10);
    filtered = filtered.filter(i => i.categoria_id === catId);
  }

  if (orderModalSearch) {
    const q = orderModalSearch.toLowerCase();
    filtered = filtered.filter(i => i.nombre.toLowerCase().includes(q));
  }

  if (filtered.length === 0) {
    grid.innerHTML = '<p class="text-center text-muted" style="grid-column:1/-1;padding:24px;">No hay productos disponibles</p>';
    return;
  }

  grid.innerHTML = filtered.map(item => {
    const cat = (item.categoria?.nombre || '').toLowerCase();
    let emoji = '🍽️';
    if (cat.includes('bebida')) emoji = '🥤';
    else if (cat.includes('ceviche')) emoji = '🐟';
    else if (cat.includes('fuerte') || cat.includes('plato')) emoji = '🍛';
    else if (cat.includes('postre')) emoji = '🍰';

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
    } else if (existing._descuentoMonto) {
      const linea = existing.precio_unitario * existing.cantidad;
      if (existing._descuentoMonto > linea) existing._descuentoMonto = linea;
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

  cart.innerHTML = items.map((item, idx) => {
    const desc = item._descuentoMonto || 0;
    return `
    <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #f3f4f6;">
      <div style="flex:1;min-width:0;">
        <div style="font-weight:500;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.nombre}</div>
        <div style="font-size:12px;color:#6b7280;">C$${item.precio_unitario.toFixed(2)}${item._precioAjustado ? ' <span style="color:var(--amarillo-solar);font-size:10px;">✏️</span>' : ''}${desc > 0 ? ` <span style="color:var(--rojo-cangrejo);font-weight:600;">· -C$${desc.toFixed(2)}</span>` : ''}</div>
      </div>
      <div style="display:flex;align-items:center;gap:4px;flex-shrink:0;">
        <button class="qty-btn" onclick="changeOrderModalQty(${item.producto_id}, -1)" style="width:26px;height:26px;font-size:14px;">−</button>
        <span style="min-width:20px;text-align:center;font-weight:600;font-size:13px;">${item.cantidad}</span>
        <button class="qty-btn" onclick="changeOrderModalQty(${item.producto_id}, 1)" style="width:26px;height:26px;font-size:14px;">+</button>
        <button onclick="aplicarDescuentoItemModal(${idx})" style="background:none;border:none;color:${desc > 0 ? 'var(--rojo-cangrejo)' : 'var(--amarillo-solar)'};font-size:14px;cursor:pointer;padding:2px 4px;" title="Descuento en C$">✏️</button>
        <button onclick="deleteOrderItem(${idx})" style="background:none;border:none;color:#E63946;font-size:14px;cursor:pointer;padding:2px 4px;" title="Eliminar">🗑</button>
      </div>
    </div>`;
  }).join('');
}

function deleteOrderItem(idx) {
  state.currentOrder.items.splice(idx, 1);
  renderOrderModalMenu(state.menuItems);
  renderOrderModalCart();
  updateOrderModalTotals();
}

function aplicarDescuentoItemModal(idx) {
  const items = state.currentOrder.items;
  const item = items[idx];
  if (!item) return;
  const linea = item.precio_unitario * item.cantidad;
  const actual = item._descuentoMonto || 0;
  const input = prompt(
    `Descuento en Córdobas (C$) para "${item.nombre}"\n\n` +
    `Subtotal del ítem: C$${linea.toFixed(2)}\n` +
    `Descuento actual: C$${actual.toFixed(2)}\n\n` +
    `Ingresa 0 o deja vacío para quitar el descuento.`,
    actual > 0 ? actual.toFixed(2) : ''
  );
  if (input === null) return;
  const texto = input.trim();
  if (texto === '') {
    delete item._descuentoMonto;
    renderOrderModalCart();
    updateOrderModalTotals();
    showToast(`Descuento de "${item.nombre}" eliminado`, 'success');
    return;
  }
  const monto = parseFloat(texto);
  if (isNaN(monto) || monto < 0) return showToast('Ingresa un monto de descuento válido', 'warning');
  if (monto > linea) return showToast(`El descuento no puede exceder C$${linea.toFixed(2)} (total del ítem)`, 'warning');
  if (monto === 0) {
    delete item._descuentoMonto;
    renderOrderModalCart();
    updateOrderModalTotals();
    showToast(`Descuento de "${item.nombre}" eliminado`, 'success');
    return;
  }
  item._descuentoMonto = monto;
  renderOrderModalCart();
  updateOrderModalTotals();
  showToast(`Descuento de C$${monto.toFixed(2)} aplicado a "${item.nombre}"`, 'success');
}
window.aplicarDescuentoItemModal = aplicarDescuentoItemModal;

function updateOrderModalTotals() {
  const items = state.currentOrder.items;
  const count = items.reduce((s, i) => s + i.cantidad, 0);
  const subtotal = items.reduce((s, i) => s + i.precio_unitario * i.cantidad, 0);
  const descuento = items.reduce((s, i) => s + (i._descuentoMonto || 0), 0);
  const total = Math.max(subtotal - descuento, 0);
  document.getElementById('order-modal-count').textContent = count;
  document.getElementById('order-modal-subtotal').textContent = `C$${subtotal.toFixed(2)}`;
  const descRow = document.getElementById('order-modal-descuento-row');
  if (descuento > 0) {
    descRow.style.display = '';
    document.getElementById('order-modal-descuento').textContent = `-C$${descuento.toFixed(2)}`;
  } else {
    descRow.style.display = 'none';
  }
  document.getElementById('order-modal-total').textContent = `C$${total.toFixed(2)}`;
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

  const btn = document.getElementById('confirm-order-modal');
  btn.disabled = true;
  btn.textContent = '⏳ Enviando…';

  let ordenParaCobrar = null;
  try {
    if (state.currentOrder._addToExisting && state.currentOrder._ordenId) {
      await api(`/ordenes/${state.currentOrder._ordenId}/items`, {
        method: 'POST',
        body: JSON.stringify({
          items: items.map(i => {
            const obj = { producto_id: i.producto_id, cantidad: i.cantidad, notas: i.notas };
            if (i._precioAjustado) obj.precio_unitario = i.precio_unitario;
            if (i._descuentoMonto) obj.descuento_monto = i._descuentoMonto;
            return obj;
          }),
        }),
      });
      showToast('Ítems agregados a la orden existente', 'success');
    } else {
      const mesaId = state.currentOrder.mesaId;
      const clienteInput = document.getElementById('order-modal-cliente');
      const nombreCliente = clienteInput ? clienteInput.value.trim() || null : null;

      const orden = await api('/ordenes/', {
        method: 'POST',
        body: JSON.stringify({
          mesa_id: mesaId,
          nombre_cliente: nombreCliente,
          detalles: items.map(i => {
            const obj = { producto_id: i.producto_id, cantidad: i.cantidad, notas: i.notas };
            if (i._precioAjustado) obj.precio_unitario = i.precio_unitario;
            if (i._descuentoMonto) obj.descuento_monto = i._descuentoMonto;
            return obj;
          }),
        }),
      });

      if (!mesaId && orden && orden.id) {
        const cobrarNow = document.getElementById('order-modal-cobrar-now')?.checked;
        if (cobrarNow) {
          ordenParaCobrar = orden;
        } else {
          showToast('¡Comanda para llevar guardada!', 'success');
        }
      } else {
        showToast('¡Comanda enviada a cocina con éxito!', 'success');
      }
    }

    if (ordenParaCobrar) {
      showToast('Orden creada. Selecciona cómo se recibió el pago.', 'success');
    }

    const mesaId = state.currentOrder.mesaId;
    closeOrderModal();
    if (ordenParaCobrar) openMetodoPago(ordenParaCobrar, 'kds');

    if (mesaId) {
      const mesa = state.tables.find(t => t.id === mesaId);
      if (mesa) {
        mesa.estado = 'OCUPADA';
        const card = document.querySelector(`#table-grid [data-mesa-id="${mesaId}"]`);
        if (card) {
          applyTableFilters();
          actualizarOcupacion();
          enriquecerMesasOcupadas();
        }
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
  bindMenuMgmtStatusFilters();
  try {
    state.menuItems = await api('/menu/items?incluir_inactivos=true');
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
    const media = getMenuMedia(cat);
    const catTagBg = /bebida/i.test(cat) ? 'bg-brand-turquoise/10 text-brand-turquoise'
      : /marisco|ceviche|pescado/i.test(cat) ? 'bg-brand-coral/10 text-brand-coral'
      : /postre/i.test(cat) ? 'bg-amber-100 text-amber-600'
      : 'bg-slate-100 text-slate-500';
    const available = item.disponible !== false;
    const thumb = item.imagen_url
      ? `<img src="${item.imagen_url}" alt="${item.nombre}">`
      : `<span class="material-symbols-outlined ${media.color}" aria-hidden="true">${media.icon}</span>`;
    const prepTime = item.tiempo_preparacion
      ? `<div class="card-subtitle" style="margin-top:2px;">⏱️ ~${item.tiempo_preparacion} min</div>`
      : '';
    return `
      <div class="data-card menu-mgmt-card animate-in" data-dish-id="${item.id}">
        <div class="mgmt-thumb grid place-items-center ${media.bg}" aria-hidden="true">${thumb}</div>
        <span class="mgmt-cat-badge ${catTagBg}">${cat}</span>
        <div class="card-title">${item.nombre}</div>
        ${prepTime}
        ${item.descripcion ? `<div class="card-subtitle" style="margin-top:2px;">${item.descripcion}</div>` : ''}
        <div class="mgmt-price-row">
          <span class="card-price">C$${parseFloat(item.precio).toFixed(2)}</span>
          <div class="flex items-center gap-1.5">
            <button type="button" class="mgmt-icon-btn edit" aria-label="Editar ${item.nombre}" onclick="openEditDish(${item.id})">
              <span class="material-symbols-outlined">edit</span>
            </button>
            <button type="button" class="mgmt-icon-btn del" aria-label="Eliminar ${item.nombre}" onclick="deleteDish(${item.id}, '${item.nombre.replace(/'/g, "\\'")}')">
              <span class="material-symbols-outlined">delete</span>
            </button>
          </div>
        </div>
        <span class="card-badge ${available ? 'badge-active' : 'badge-inactive'}" style="position:absolute;top:12px;right:12px;">${available ? 'Activo' : 'Inactivo'}</span>
      </div>`;
  }).join('');
}

function renderMenuMgmtCatFilters(categorias) {
  const container = document.getElementById('menu-mgmt-cat-filters');
  if (!container) return;
  container.innerHTML = `
    <button class="chip active px-4 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap" data-cat="all" role="tab" aria-selected="true">Todas <span class="chip-count" data-count-for="all">(0)</span></button>
    ${categorias.map(c => `<button class="chip px-4 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap" data-cat="${c.id}" role="tab" aria-selected="false">${getCategoryEmoji(c.nombre)} ${c.nombre} <span class="chip-count" data-count-for="${c.id}">(0)</span></button>`).join('')}
  `;
  container.querySelectorAll('.chip[data-cat]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip[data-cat]').forEach(c => {
        c.classList.remove('active');
        c.setAttribute('aria-selected', 'false');
      });
      chip.classList.add('active');
      chip.setAttribute('aria-selected', 'true');
      activeMgmtCatFilter = chip.dataset.cat;
      applyMenuMgmtFilter();
    });
  });
  aplicarContadoresMenuMgmt();
}

function aplicarContadoresMenuMgmt() {
  const items = state.menuItems || [];
  const setCount = (key, n) => {
    document.querySelectorAll(`#menu-mgmt-cat-filters [data-count-for="${key}"], #menu-mgmt-status-filters [data-count-for="${key}"]`).forEach(el => { el.textContent = `(${n})`; });
  };
  setCount('all', items.length);
  const byCat = {};
  items.forEach(i => { byCat[i.categoria_id] = (byCat[i.categoria_id] || 0) + 1; });
  Object.entries(byCat).forEach(([cid, n]) => setCount(cid, n));
  const activos = items.filter(i => i.disponible !== false).length;
  setCount('activos', activos);
  setCount('inactivos', items.length - activos);
}

function applyMenuMgmtFilter() {
  aplicarContadoresMenuMgmt();
  let filtered = state.menuItems;
  if (activeMgmtCatFilter !== 'all') {
    filtered = filtered.filter(i => String(i.categoria_id) === activeMgmtCatFilter);
  }
  if (activeMgmtStatusFilter === 'activos') {
    filtered = filtered.filter(i => i.disponible !== false);
  } else if (activeMgmtStatusFilter === 'inactivos') {
    filtered = filtered.filter(i => i.disponible === false);
  }
  renderMenuMgmt(filtered);
}

function bindMenuMgmtStatusFilters() {
  const container = document.getElementById('menu-mgmt-status-filters');
  if (!container) return;
  container.querySelectorAll('.chip[data-status]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.chip[data-status]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeMgmtStatusFilter = chip.dataset.status;
      applyMenuMgmtFilter();
    });
  });
}

async function deleteDish(itemId, nombre) {
  if (!confirm(`¿Eliminar el platillo "${nombre}"?\n• Sin ventas: se borra permanentemente (con su receta).\n• Con ventas: se archiva conservando el historial y el nombre queda disponible.`)) return;
  try {
    const res = await api(`/menu/items/${itemId}`, { method: 'DELETE' });
    showToast(res?.mensaje || (res?.resultado === 'eliminado' ? `"${nombre}" eliminado` : `"${nombre}" archivado`));
    if (res?.resultado === 'eliminado') {
      state.menuItems = state.menuItems.filter(i => i.id !== itemId);
    } else {
      const item = state.menuItems.find(i => i.id === itemId);
      if (item) item.disponible = false;
    }
    applyMenuMgmtFilter();
  } catch { /* handled by api() */ }
}

/* --- Carta (Menu Browse) Filters --- */
function renderCartaCatFilters(categorias) {
  const container = document.getElementById('carta-cat-filters');
  if (!container) return;
  container.innerHTML = `
    <button class="category-tab active" data-cat="all" role="tab" aria-selected="true">🍽️ Todos <span class="cat-count">0</span></button>
    ${categorias.map(c => `<button class="category-tab" data-cat="${c.id}" role="tab" aria-selected="false">${getCategoryEmoji(c.nombre)} ${c.nombre} <span class="cat-count">0</span></button>`).join('')}
  `;
  container.querySelectorAll('.category-tab[data-cat]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('.category-tab[data-cat]').forEach(c => {
        c.classList.remove('active');
        c.setAttribute('aria-selected', 'false');
      });
      chip.classList.add('active');
      chip.setAttribute('aria-selected', 'true');
      activeCartaCatFilter = chip.dataset.cat;
      applyCartaFilter();
    });
  });
  aplicarContadoresCarta();
}

function aplicarContadoresCarta() {
  const container = document.getElementById('carta-cat-filters');
  if (!container) return;
  const items = state.menuItems || [];
  const allCount = container.querySelector('[data-cat="all"] .cat-count');
  if (allCount) allCount.textContent = items.length;
  const byCat = {};
  items.forEach(i => {
    if (i.disponible !== false) byCat[i.categoria_id] = (byCat[i.categoria_id] || 0) + 1;
  });
  container.querySelectorAll('.category-tab[data-cat]:not([data-cat="all"]) .cat-count').forEach(el => {
    const btn = el.closest('.category-tab');
    el.textContent = byCat[parseInt(btn.dataset.cat, 10)] || 0;
  });
}

function applyCartaFilter() {
  aplicarContadoresCarta();
  let filtered = (state.menuItems || []).filter(i => i.disponible !== false);
  if (activeCartaCatFilter !== 'all') {
    filtered = filtered.filter(i => String(i.categoria_id) === activeCartaCatFilter);
  }
  if (cartaSearch) {
    const q = cartaSearch.toLowerCase();
    filtered = filtered.filter(i =>
      (i.nombre || '').toLowerCase().includes(q) ||
      (i.categoria?.nombre || '').toLowerCase().includes(q)
    );
  }
  renderMenuItems(filtered, 'menu-grid');
}

/* --- Dish Modal --- */
async function openNewDishModal() {
  document.getElementById('dish-modal-title').textContent = 'Nuevo Platillo';
  document.getElementById('dish-form').reset();
  document.getElementById('dish-id').value = '';
  setDishToggle(true);
  clearRecipeRows();
  resetDishImage();
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
  document.getElementById('dish-prep-time').value = item.tiempo_preparacion || '';
  setDishToggle(item.disponible !== false);

  resetDishImage();

  const preview = document.getElementById('dish-image-preview');
  const hint = document.getElementById('dish-image-hint');
  if (preview) {
    if (item.imagen_url) {
      preview.src = item.imagen_url;
      preview.style.display = 'block';
    } else {
      preview.style.display = 'none';
      preview.removeAttribute('src');
    }
  }
  if (hint) hint.textContent = item.imagen_url ? 'Imagen actual. Puedes reemplazarla seleccionando un archivo nuevo.' : 'Sin imagen. Puedes subir una ahora.';

  clearRecipeRows();
  if (item.ingredientes_receta && item.ingredientes_receta.length > 0) {
    item.ingredientes_receta.forEach(r => addRecipeRow(r.insumo_id, r.cantidad_necesaria, r.descuento_por_lote));
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

function _buildInsumoOptions(categoriaId, selectedId) {
  const filtered = categoriaId
    ? state.insumos.filter(i => i.categoria_id === parseInt(categoriaId, 10))
    : state.insumos;
  return filtered.map(i =>
    `<option value="${i.id}" ${i.id === selectedId ? 'selected' : ''}>${i.nombre} (${i.unidad_medida})</option>`
  ).join('');
}

function _buildCatInsumoOptions(selectedCatId) {
  let html = '<option value="">Todas</option>';
  (state.categoriasInsumo || []).forEach(c => {
    html += `<option value="${c.id}" ${c.id === selectedCatId ? 'selected' : ''}>${c.nombre}</option>`;
  });
  return html;
}

function addRecipeRow(ingredienteId, cantidad, descuentoLote) {
  const container = document.getElementById('dish-recipe-rows');
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:6px;flex-wrap:wrap;';
  row.className = 'recipe-row';

  let catId = '';
  if (ingredienteId) {
    const insumo = state.insumos.find(i => i.id === ingredienteId);
    if (insumo) catId = insumo.categoria_id || '';
  }

  row.innerHTML = `
    <select class="form-input recipe-cat-filter" style="flex:1;height:36px;font-size:12px;">${_buildCatInsumoOptions(catId)}</select>
    <select class="form-input recipe-ingrediente" style="flex:2;height:36px;font-size:13px;">${_buildInsumoOptions(catId, ingredienteId)}</select>
    <input type="number" class="form-input recipe-cantidad" style="flex:1;height:36px;font-size:13px;" step="0.001" min="0.001" placeholder="Cant." value="${cantidad || ''}">
    <label title="Si está activo, este ingrediente NO se descuenta por plato sino solo por Producción de Cocina" style="display:flex;align-items:center;gap:3px;font-size:11px;color:#6b7280;white-space:nowrap;cursor:pointer;">
      <input type="checkbox" class="recipe-lote" style="width:14px;height:14px;">
      <span>Lote</span>
    </label>
    <button type="button" class="btn-remove-recipe" style="background:none;border:none;color:#E63946;font-size:18px;cursor:pointer;padding:4px;" title="Quitar">🗑️</button>
  `;

  const catSelect = row.querySelector('.recipe-cat-filter');
  const ingSelect = row.querySelector('.recipe-ingrediente');
  catSelect.addEventListener('change', () => {
    const prev = ingSelect.value;
    ingSelect.innerHTML = _buildInsumoOptions(catSelect.value, null);
    if (ingSelect.querySelector(`option[value="${prev}"]`)) ingSelect.value = prev;
  });

  row.querySelector('.btn-remove-recipe').addEventListener('click', () => row.remove());
  container.appendChild(row);
  if (descuentoLote) {
    const loteCb = row.querySelector('.recipe-lote');
    if (loteCb) loteCb.checked = true;
  }
}

function buildRecetaPayload() {
  const rows = document.querySelectorAll('#dish-recipe-rows .recipe-row');
  const receta = [];
  rows.forEach(row => {
    const sel = row.querySelector('.recipe-ingrediente');
    const rawId = sel ? sel.value : '';
    const insumo_id = parseInt(rawId, 10);
    const cantidad_necesaria = parseFloat(row.querySelector('.recipe-cantidad').value);
    const descuento_por_lote = row.querySelector('.recipe-lote')?.checked || false;
    if (Number.isInteger(insumo_id) && insumo_id > 0 && Number.isFinite(cantidad_necesaria) && cantidad_necesaria > 0) {
      receta.push({ insumo_id, cantidad_necesaria, descuento_por_lote });
    }
  });
  return receta;
}

async function loadInsumosForRecipe() {
  const tasks = [];
  if (state.insumos.length === 0) {
    tasks.push(
      api('/inventario/insumos').then(d => { state.insumos = d; }).catch(() => { state.insumos = []; })
    );
  }
  if (!state.categoriasInsumo || state.categoriasInsumo.length === 0) {
    tasks.push(
      api('/inventario/categorias-insumo').then(d => { state.categoriasInsumo = d; }).catch(() => { state.categoriasInsumo = []; })
    );
  }
  if (tasks.length) await Promise.all(tasks);
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

  const prepRaw = Number(document.getElementById('dish-prep-time').value);
  payload.tiempo_preparacion = (Number.isFinite(prepRaw) && prepRaw > 0) ? Math.round(prepRaw) : null;

  if (!payload.nombre || !payload.precio || !payload.categoria_id) {
    return showToast('Completa nombre, precio y categoría', 'warning');
  }

  const receta = buildRecetaPayload();
  if (id) {
    payload.ingredientes_receta = receta;
  } else if (receta.length > 0) {
    payload.receta = receta;
  }

  try {
    let savedId = id ? parseInt(id, 10) : null;
    if (id) {
      await api(`/menu/items/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Platillo actualizado');
    } else {
      const created = await api('/menu/items', { method: 'POST', body: JSON.stringify(payload) });
      savedId = created.id;
      showToast('Platillo creado');
    }
    const fileInput = document.getElementById('dish-image');
    if (savedId && fileInput && fileInput.files && fileInput.files.length > 0) {
      try {
        const comprimida = await compressImageFile(fileInput.files[0]);
        await uploadDishImage(savedId, comprimida);
        showToast('Platillo guardado — imagen actualizada');
      } catch (errImg) {
        const motivo = (errImg && errImg.message) ? errImg.message : 'Error inesperado';
        showToast(`Platillo guardado, pero la imagen falló: ${motivo}. Reintenta subirla.`, 'error', 6000);
        return;
      }
    }
    closeDishModal();
    loadMenuManagement();
  } catch { /* handled */ }
}

async function uploadDishImage(itemId, file) {
  const formData = new FormData();
  formData.append('archivo', file);
  const updated = await api(`/menu/items/${itemId}/imagen`, {
    method: 'POST',
    body: formData,
  });
  const idx = state.menuItems.findIndex(i => i.id === itemId);
  if (idx !== -1) state.menuItems[idx] = { ...state.menuItems[idx], ...updated };
  return updated;
}

/* Comprime la foto en el navegador (canvas → máx. 1600px, WebP ~85%) antes de
   subirla: evita el rechazo por tamaño en el servidor y acelera la subida.
   En iPhone Safari también convierte HEIC → JPEG/WebP automáticamente. */
function compressImageFile(file) {
  const maxDim = 1600;
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('No se pudo leer la imagen seleccionada'));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error('No se pudo procesar esta foto. Usa otra imagen o conviértela a JPG.'));
      img.onload = () => {
        try {
          const ancho = img.naturalWidth;
          const alto = img.naturalHeight;
          const escala = Math.min(1, maxDim / Math.max(ancho, alto));
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(ancho * escala));
          canvas.height = Math.max(1, Math.round(alto * escala));
          canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
          const soportaWebp = canvas.toDataURL('image/webp').startsWith('data:image/webp');
          const tipo = soportaWebp ? 'image/webp' : 'image/jpeg';
          canvas.toBlob(blob => {
            if (!blob) return reject(new Error('No se pudo comprimir la imagen'));
            const base = (file.name || 'imagen').replace(/\.[^.]+$/, '');
            const nombre = `${base}.${tipo === 'image/webp' ? 'webp' : 'jpg'}`;
            resolve(new File([blob], nombre, { type: tipo }));
          }, tipo, 0.85);
        } catch {
          reject(new Error('No se pudo procesar esta foto. Usa otra imagen o conviértela a JPG.'));
        }
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function previewDishImage() {
  const input = document.getElementById('dish-image');
  const preview = document.getElementById('dish-image-preview');
  const hint = document.getElementById('dish-image-hint');
  if (!input || !preview) return;
  const file = input.files && input.files[0];
  if (!file) {
    preview.style.display = 'none';
    preview.removeAttribute('src');
    if (hint) hint.textContent = 'Se comprime en el navegador (WebP). Si no eliges imagen se usará el placeholder.';
    return;
  }
  const reader = new FileReader();
  reader.onload = (ev) => {
    preview.src = ev.target.result;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);
  if (hint) hint.textContent = file.name;
}

function resetDishImage() {
  const input = document.getElementById('dish-image');
  const preview = document.getElementById('dish-image-preview');
  const hint = document.getElementById('dish-image-hint');
  if (input) input.value = '';
  if (preview) { preview.style.display = 'none'; preview.removeAttribute('src'); }
  if (hint) hint.textContent = 'Se comprime en el navegador (WebP). Si no eliges imagen se usará el placeholder.';
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
  let html = `<button class="chip ${state.activeInsumoCatFilter === null ? 'active' : ''} px-4 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap" data-cat="all" role="tab" aria-selected="${state.activeInsumoCatFilter === null}" onclick="applyInsumoFilter(null)">Todas <span class="chip-count" data-count-for="all">(0)</span></button>`;
  html += cats.map(c =>
    `<button class="chip ${state.activeInsumoCatFilter === c.id ? 'active' : ''} px-4 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap" data-cat="${c.id}" role="tab" aria-selected="${state.activeInsumoCatFilter === c.id}" onclick="applyInsumoFilter(${c.id})">${getCategoryEmoji(c.nombre)} ${c.nombre} <span class="chip-count" data-count-for="${c.id}">(0)</span></button>`
  ).join('');
  container.innerHTML = html;
  aplicarContadoresInsumo();
}

function aplicarContadoresInsumo() {
  const cats = state.categoriasInsumo || [];
  const items = state.insumos || [];
  const setContador = (key, n) => {
    document.querySelectorAll(`#insumo-cat-filters [data-count-for="${key}"]`).forEach(el => { el.textContent = `(${n})`; });
  };
  setContador('all', items.length);
  cats.forEach(c => setContador(c.id, items.filter(i => i.categoria_id === c.id).length));
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
  const strip = document.getElementById('stock-alerts');
  if (!strip) return;
  if (!alerts || alerts.length === 0) {
    strip.innerHTML = '<div class="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs sm:text-sm font-semibold w-full min-w-0"><span class="material-symbols-outlined shrink-0 text-[16px] text-emerald-600">verified</span><span class="min-w-0">Todo en orden — no hay alertas de stock</span></div>';
    return;
  }
  strip.innerHTML = alerts.map((a, idx) => `
    <div class="flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer bg-${idx % 2 ? 'sky' : 'amber'}-50 border border-${idx % 2 ? 'sky' : 'amber'}-200 text-${idx % 2 ? 'sky' : 'amber'}-900 text-xs sm:text-sm font-semibold transition active:scale-[0.98] w-full min-w-0" onclick="openStockModal(${a.id})" title="Ajustar stock de ${a.nombre}">
      <span class="material-symbols-outlined shrink-0 text-[16px] text-${idx % 2 ? 'sky' : 'amber'}-600">${idx % 2 ? 'schedule' : 'warning'}</span>
      <span class="min-w-0 truncate">${a.nombre} — ${a.cantidad_actual} ${a.unidad_medida} (mín: ${a.stock_minimo})</span>
    </div>`).join('');
}

function insumoTint(catNombre = '') {
  const n = (catNombre || '').toLowerCase();
  if (/carne|pollo|res|cerdo|pescado|marisco/.test(n)) return { bg: '#FFE8E3', color: '#E64A2E', icon: 'set_meal' };
  if (/abarrote|grano|arroz|aceite|enlatado/.test(n)) return { bg: '#FFF4D6', color: '#B45309', icon: 'package_2' };
  if (/l[áa]cteo|leche|queso|crema/.test(n)) return { bg: '#D6F5F8', color: '#0F766E', icon: 'liquid' };
  if (/veget|fruta|verdura|lechuga|cebolla|tomate/.test(n)) return { bg: '#DCFCE7', color: '#15803D', icon: 'eco' };
  if (/condiment|especia|sal|salsa/.test(n)) return { bg: '#F1F5F9', color: '#475569', icon: 'spa' };
  if (/bebida|jugo|gaseosa/.test(n)) return { bg: '#E0F2FE', color: '#0369A1', icon: 'local_cafe' };
  return { bg: '#E0F2FE', color: '#0369A1', icon: 'inventory_2' };
}

function renderInsumos(insumos) {
  const grid = document.getElementById('insumo-grid');
  if (!grid) return;
  if (!insumos || insumos.length === 0) {
    grid.innerHTML = '<p class="text-center text-slate-400 text-sm p-8 col-span-full">No hay insumos registrados</p>';
    return;
  }
  grid.innerHTML = insumos.map(i => {
    const pct = parseFloat(i.stock_minimo) > 0
      ? Math.min((parseFloat(i.cantidad_actual) / parseFloat(i.stock_minimo)) * 100, 100)
      : 100;
    const level = pct > 60 ? 'ok' : pct > 30 ? 'bajo' : 'crit';
    const barClass = level === 'ok' ? 'bar-ok' : level === 'bajo' ? 'bar-warn' : 'bar-crit';
    const badgeText = level === 'ok' ? 'OK' : level === 'bajo' ? 'BAJO' : 'CRÍTICO';
    const badgeCls = level === 'ok'
      ? 'bg-[#D6F5F8] text-[#0F766E]'
      : level === 'bajo'
        ? 'bg-amber-100 text-amber-700 border border-amber-300'
        : 'bg-[#FFE8E3] text-[#E64A2E] border border-[#E64A2E]/30';
    const tint = insumoTint(i.categoria_nombre);
    const catBadge = i.categoria_nombre
      ? `<span class="insumo-cat-badge" style="background:${tint.bg};color:${tint.color}">${getCategoryEmoji(i.categoria_nombre)} ${i.categoria_nombre}</span>`
      : '';
    return `
      <div class="data-card flex flex-col insumo-card animate-in">
        <div class="insumo-head" style="background:${tint.bg};color:${tint.color}">
          <span class="material-symbols-outlined">${tint.icon}</span>
          <span class="insumo-level ${badgeCls}">${badgeText}</span>
        </div>
        <div class="insumo-body">
          <span class="insumo-name truncate">${i.nombre}</span>
          ${catBadge}
          <div class="insumo-stock-labels">
            <span>Stock actual</span><span>Mín: ${i.stock_minimo} ${i.unidad_medida}</span>
          </div>
          <div class="stock-bar-track"><div class="stock-bar-fill ${barClass}" style="width:${pct}%"></div></div>
          <div class="insumo-footer">
            <span class="insumo-qty-${level}">${i.cantidad_actual} ${i.unidad_medida}</span>
            <button class="mgmt-icon-btn tune" onclick="openStockModal(${i.id})" title="Ajustar stock de ${i.nombre}">
              <span class="material-symbols-outlined">tune</span>
            </button>
          </div>
        </div>
      </div>`;
  }).join('');
}

/* --- Stock Modal --- */
function openStockModal(insumoId) {
  const insumo = state.insumos.find(i => i.id === insumoId);
  if (!insumo) return;

  document.getElementById('stock-insumo-id').value = insumo.id;
  document.getElementById('stock-detalles-insumo-id').value = insumo.id;
  document.getElementById('stock-insumo-unidad-base-id').value = insumo.unidad_medida_id;
  document.getElementById('stock-insumo-empaque-id').value = insumo.unidad_empaque_id || '';
  document.getElementById('stock-insumo-factor-empaque').value = insumo.factor_empaque || '';
  state._stockOriginalUnidadId = insumo.unidad_medida_id;
  document.getElementById('stock-info').innerHTML = `
    <div class="stock-info-name">${insumo.nombre}</div>
    <div class="stock-info-qty">${insumo.cantidad_actual} ${insumo.unidad_medida}</div>
    <div class="stock-info-unit">Mínimo: ${insumo.stock_minimo} ${insumo.unidad_medida}</div>`;
  document.getElementById('stock-qty').value = '';
  document.getElementById('stock-motivo').value = 'Ajuste de inventario';
  setStockType('ENTRADA');
  switchStockTab('movimiento');

  const movUnidadSel = document.getElementById('stock-mov-unidad');
  const baseUnit = state.unidadesMedida.find(u => u.id === insumo.unidad_medida_id);
  const sameType = state.unidadesMedida.filter(u => u.tipo_magnitud === (baseUnit?.tipo_magnitud || 'UNIDAD'));
  const empaqueId = insumo.unidad_empaque_id;
  const empaqueUnit = empaqueId ? state.unidadesMedida.find(u => u.id === empaqueId) : null;
  const opts = [];
  if (empaqueUnit && !sameType.some(u => u.id === empaqueUnit.id)) {
    opts.push(`<option value="${empaqueUnit.id}">${empaqueUnit.nombre} (${empaqueUnit.abreviatura}) [Empaque]</option>`);
  }
  movUnidadSel.innerHTML = opts.concat(sameType.map(u =>
    `<option value="${u.id}" ${u.id === insumo.unidad_medida_id ? 'selected' : ''}>${u.nombre} (${u.abreviatura})</option>`
  )).join('');
  document.getElementById('stock-conversion-preview').style.display = 'none';
  updateStockConversionPreview();

  const catSel = document.getElementById('stock-cat-select');
  catSel.innerHTML = '<option value="">Sin categoría</option>' +
    state.categoriasInsumo.map(c => `<option value="${c.id}" ${c.id === insumo.categoria_id ? 'selected' : ''}>${c.nombre}</option>`).join('');
  const unidadSel = document.getElementById('stock-unidad-select');
  unidadSel.innerHTML = state.unidadesMedida.map(u =>
    `<option value="${u.id}" ${u.id === insumo.unidad_medida_id ? 'selected' : ''}>${u.nombre} (${u.abreviatura})</option>`
  ).join('');
  document.getElementById('stock-minimo').value = insumo.stock_minimo ?? '';

  const empaqueSel = document.getElementById('stock-empaque-select');
  const candidates = baseUnit
    ? state.unidadesMedida.filter(u => u.id !== insumo.unidad_medida_id && (u.tipo_magnitud === baseUnit.tipo_magnitud || baseUnit.tipo_magnitud === 'PERSONALIZADO'))
    : state.unidadesMedida;
  empaqueSel.innerHTML = '<option value="">Sin empaque</option>' +
    candidates.map(u => `<option value="${u.id}" ${u.id === insumo.unidad_empaque_id ? 'selected' : ''}>${u.nombre} (${u.abreviatura})</option>`).join('');
  document.getElementById('stock-empaque-factor').value = insumo.factor_empaque ?? '';
  updateStockDetailsEmpaquePreview();

  document.getElementById('stock-cat-panel').style.display = 'none';
  document.getElementById('stock-unidad-panel').style.display = 'none';

  document.getElementById('modal-stock').classList.add('show');
}

function switchStockTab(tab) {
  document.querySelectorAll('#stock-tabs .period-tab').forEach(b => b.classList.toggle('active', b.dataset.stockTab === tab));
  document.getElementById('stock-tab-movimiento').style.display = tab === 'movimiento' ? '' : 'none';
  document.getElementById('stock-tab-detalles').style.display = tab === 'detalles' ? '' : 'none';
}

function setStockType(tipo) {
  document.getElementById('stock-entrada-btn').classList.toggle('active', tipo === 'ENTRADA');
  document.getElementById('stock-salida-btn').classList.toggle('active', tipo === 'SALIDA');
  updateStockConversionPreview();
}

function updateStockConversionPreview() {
  const preview = document.getElementById('stock-conversion-preview');
  const baseId = parseInt(document.getElementById('stock-insumo-unidad-base-id').value) || null;
  const selectedId = parseInt(document.getElementById('stock-mov-unidad').value) || null;
  const qty = parseFloat(document.getElementById('stock-qty').value) || 0;
  const tipo = document.getElementById('stock-entrada-btn').classList.contains('active') ? 'ENTRADA' : 'SALIDA';
  const insumo = state.insumos.find(i => i.id === parseInt(document.getElementById('stock-insumo-id').value));
  if (!baseId || !selectedId || selectedId === baseId || qty <= 0 || !insumo) {
    preview.style.display = 'none';
    return;
  }
  const movUnit = state.unidadesMedida.find(u => u.id === selectedId);
  const baseUnit = state.unidadesMedida.find(u => u.id === baseId);
  if (!movUnit || !baseUnit) { preview.style.display = 'none'; return; }
  const arrow = tipo === 'ENTRADA' ? '+' : '-';
  let convertedQty;
  if (insumo.unidad_empaque_id && selectedId === insumo.unidad_empaque_id && insumo.factor_empaque) {
    convertedQty = qty * insumo.factor_empaque;
    preview.textContent = `${arrow} ${qty} ${movUnit.nombre} = ${arrow}${convertedQty.toFixed(2)} ${baseUnit.abreviatura} en stock (factor empaque: ${insumo.factor_empaque})`;
  } else {
    const fromChain = movUnit.factor_conversion || 1;
    const toChain = baseUnit.factor_conversion || 1;
    convertedQty = qty * fromChain / toChain;
    preview.textContent = `${arrow} ${qty} ${movUnit.nombre} = ${arrow}${convertedQty.toFixed(2)} ${baseUnit.nombre} (${baseUnit.abreviatura}) en stock`;
  }
  preview.style.display = '';
}

function closeStockModal() {
  document.getElementById('modal-stock').classList.remove('show');
}

async function saveStock(e) {
  e.preventDefault();
  const insumoId = document.getElementById('stock-insumo-id').value;
  const tipoFinal = document.getElementById('stock-entrada-btn').classList.contains('active') ? 'ENTRADA' : 'SALIDA';
  const movUnidadId = parseInt(document.getElementById('stock-mov-unidad').value) || null;
  const baseId = parseInt(document.getElementById('stock-insumo-unidad-base-id').value) || null;
  const payload = {
    cantidad: parseFloat(document.getElementById('stock-qty').value),
    tipo: tipoFinal,
    motivo: document.getElementById('stock-motivo').value.trim() || 'Ajuste de inventario',
  };
  if (movUnidadId && movUnidadId !== baseId) {
    payload.unidad_medida_id = movUnidadId;
  }

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

async function saveStockDetails(e) {
  e.preventDefault();
  const insumoId = document.getElementById('stock-detalles-insumo-id').value;
  const catVal = document.getElementById('stock-cat-select').value;
  const unidadVal = document.getElementById('stock-unidad-select').value;
  const minimoVal = document.getElementById('stock-minimo').value;
  const empaqueVal = document.getElementById('stock-empaque-select').value;
  const empaqueFactorVal = document.getElementById('stock-empaque-factor').value;
  const payload = {};
  if (catVal) payload.categoria_id = parseInt(catVal);
  if (unidadVal) payload.unidad_medida_id = parseInt(unidadVal);
  if (minimoVal !== '' && minimoVal !== null) payload.stock_minimo = parseFloat(minimoVal);
  if (empaqueVal) {
    payload.unidad_empaque_id = parseInt(empaqueVal);
    if (empaqueFactorVal) payload.factor_empaque = parseFloat(empaqueFactorVal);
  } else {
    payload.unidad_empaque_id = null;
    payload.factor_empaque = null;
  }

  if (Object.keys(payload).length === 0) {
    return showToast('No hay cambios para guardar', 'warning');
  }

  const origId = state._stockOriginalUnidadId;
  if (payload.unidad_medida_id && origId && payload.unidad_medida_id !== origId) {
    state._pendingStockPayload = payload;
    openUnitEquivModal(origId, payload.unidad_medida_id);
    return;
  }

  await _submitStockDetails(payload);
}

async function _submitStockDetails(payload) {
  const insumoId = document.getElementById('stock-detalles-insumo-id').value;
  try {
    await api(`/inventario/insumos/${insumoId}`, {
      method: 'PATCH', body: JSON.stringify(payload),
    });
    showToast('Detalles actualizados');
    closeStockModal();
    loadInventory();
  } catch { /* handled */ }
}

function openUnitEquivModal(oldUnitId, newUnitId) {
  const oldUnit = state.unidadesMedida.find(u => u.id === oldUnitId);
  const newUnit = state.unidadesMedida.find(u => u.id === newUnitId);
  if (!oldUnit || !newUnit) {
    _submitStockDetails(state._pendingStockPayload);
    return;
  }
  document.getElementById('unit-equiv-question').textContent =
    `¿Cuántas ${newUnit.nombre} hay en 1 ${oldUnit.nombre}?`;
  document.getElementById('unit-equiv-hint').textContent =
    `Ejemplo: si 1 ${oldUnit.nombre} = 5 ${newUnit.nombre}, escriba 5`;
  document.getElementById('unit-equiv-factor').value = '';
  document.getElementById('modal-unit-equiv').classList.add('show');
  document.getElementById('unit-equiv-factor').focus();
}

function closeUnitEquivModal() {
  document.getElementById('modal-unit-equiv').classList.remove('show');
  state._pendingStockPayload = null;
}

function cancelUnitEquiv() {
  const payload = state._pendingStockPayload;
  closeUnitEquivModal();
  if (payload && payload.unidad_medida_id) {
    const origId = state._stockOriginalUnidadId;
    const sel = document.getElementById('stock-unidad-select');
    if (sel && origId) sel.value = origId;
  }
}

async function confirmUnitEquiv() {
  const factor = parseFloat(document.getElementById('unit-equiv-factor').value);
  if (!factor || factor <= 0) {
    return showToast('Ingrese un factor de conversión válido', 'warning');
  }
  const payload = state._pendingStockPayload;
  closeUnitEquivModal();
  if (!payload) return;
  payload.factor_conversion_unidad = factor;
  await _submitStockDetails(payload);
}

function updateStockDetailsEmpaquePreview() {
  const preview = document.getElementById('stock-details-empaque-preview');
  const helper = document.getElementById('stock-details-empaque-helper');
  const factorGroup = document.getElementById('stock-empaque-factor-group');
  const section = document.getElementById('stock-empaque-section');
  const empaqueId = parseInt(document.getElementById('stock-empaque-select')?.value) || null;
  const factor = parseFloat(document.getElementById('stock-empaque-factor')?.value) || 0;
  const insumoId = parseInt(document.getElementById('stock-detalles-insumo-id')?.value) || null;
  const insumo = insumoId ? state.insumos.find(i => i.id === insumoId) : null;
  const baseId = parseInt(document.getElementById('stock-unidad-select')?.value) || null;
  const baseUnit = baseId ? state.unidadesMedida.find(u => u.id === baseId) : null;

  if (!empaqueId) {
    if (factorGroup) factorGroup.style.display = 'none';
    if (preview) preview.style.display = 'none';
    if (helper) helper.style.display = 'none';
    return;
  }
  if (factorGroup) factorGroup.style.display = '';
  if (!factor || !insumo || !baseUnit) {
    if (preview) preview.style.display = 'none';
    if (helper) helper.style.display = 'none';
    return;
  }
  const empaqueUnit = state.unidadesMedida.find(u => u.id === empaqueId);
  if (!empaqueUnit) { preview.style.display = 'none'; if (helper) helper.style.display = 'none'; return; }
  preview.textContent = `1 ${empaqueUnit.nombre} de ${insumo.nombre} equivale a ${factor} ${baseUnit.abreviatura}`;
  preview.style.display = '';
  helper.textContent = `💡 Configuración: 1 ${empaqueUnit.nombre} equivale a ${factor} ${baseUnit.nombre} en inventario.`;
  helper.style.display = '';
}

/* --- Stock Detalles — Gear Subpanels --- */
function toggleStockCatPanel() {
  const p = document.getElementById('stock-cat-panel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
}

async function guardarStockCategoriaInsumo() {
  const nombre = document.getElementById('stock-cat-nombre').value.trim();
  if (!nombre) return showToast('Ingresa el nombre', 'warning');
  try {
    await api('/inventario/categorias-insumo', { method: 'POST', body: JSON.stringify({ nombre }) });
    document.getElementById('stock-cat-nombre').value = '';
    await loadCategoriasInsumo();
    const sel = document.getElementById('stock-cat-select');
    const insumoId = parseInt(document.getElementById('stock-detalles-insumo-id').value);
    const insumo = state.insumos.find(i => i.id === insumoId);
    sel.innerHTML = '<option value="">Sin categoría</option>' +
      state.categoriasInsumo.map(c => `<option value="${c.id}" ${insumo && c.id === insumo.categoria_id ? 'selected' : ''}>${c.nombre}</option>`).join('');
    document.getElementById('stock-cat-panel').style.display = 'none';
    showToast('Categoría creada');
  } catch { /* handled */ }
}

function toggleStockUnidadPanel() {
  const p = document.getElementById('stock-unidad-panel');
  p.style.display = p.style.display === 'none' ? 'block' : 'none';
}

async function guardarStockUnidadMedida() {
  const nombre = document.getElementById('stock-unidad-nombre').value.trim();
  const abreviatura = document.getElementById('stock-unidad-abrev').value.trim();
  if (!nombre) return showToast('Ingresa el nombre', 'warning');
  if (!abreviatura) return showToast('Ingresa la abreviatura', 'warning');
  try {
    await api('/inventario/unidades-medida', { method: 'POST', body: JSON.stringify({ nombre, abreviatura }) });
    document.getElementById('stock-unidad-nombre').value = '';
    document.getElementById('stock-unidad-abrev').value = '';
    await loadUnidadesMedida();
    const sel = document.getElementById('stock-unidad-select');
    const insumoId = parseInt(document.getElementById('stock-detalles-insumo-id').value);
    const insumo = state.insumos.find(i => i.id === insumoId);
    sel.innerHTML = state.unidadesMedida.map(u =>
      `<option value="${u.id}" ${insumo && u.id === insumo.unidad_medida_id ? 'selected' : ''}>${u.nombre} (${u.abreviatura})</option>`
    ).join('');
    document.getElementById('stock-unidad-panel').style.display = 'none';
    showToast('Unidad creada');
  } catch { /* handled */ }
}

/* --- Insumo Modal --- */
function openNewInsumoModal() {
  document.getElementById('insumo-form').reset();
  document.getElementById('insumo-qty').value = '0';
  document.getElementById('insumo-min').value = '5';
  populateUnidadSelect();
  populateInsumoEmpaqueSelect();
  populateCatInsumoSelect();
  document.getElementById('insumo-empaque-factor').disabled = true;
  document.getElementById('insumo-empaque-preview').style.display = 'none';
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

function populateInsumoEmpaqueSelect() {
  const sel = document.getElementById('insumo-empaque-unit');
  const baseId = parseInt(document.getElementById('insumo-unit')?.value) || null;
  const baseUnit = baseId ? state.unidadesMedida.find(u => u.id === baseId) : null;
  const candidates = baseUnit
    ? state.unidadesMedida.filter(u => u.id !== baseId && (u.tipo_magnitud === baseUnit.tipo_magnitud || baseUnit.tipo_magnitud === 'PERSONALIZADO'))
    : state.unidadesMedida;
  sel.innerHTML = '<option value="">Sin empaque</option>' +
    candidates.map(u => `<option value="${u.id}">${u.nombre} (${u.abreviatura})</option>`).join('');
}

function updateInsumoEmpaquePreview() {
  const preview = document.getElementById('insumo-empaque-preview');
  const helper = document.getElementById('insumo-empaque-helper');
  const factorInput = document.getElementById('insumo-empaque-factor');
  const factorGroup = document.getElementById('insumo-empaque-factor-group');
  const empaqueId = parseInt(document.getElementById('insumo-empaque-unit').value) || null;
  const factor = parseFloat(document.getElementById('insumo-empaque-factor').value) || 0;
  const insumoNombre = document.getElementById('insumo-name').value.trim() || 'este insumo';
  const baseId = parseInt(document.getElementById('insumo-unit')?.value) || null;
  const baseUnit = baseId ? state.unidadesMedida.find(u => u.id === baseId) : null;
  factorInput.disabled = !empaqueId;
  if (factorGroup) factorGroup.style.display = empaqueId ? '' : 'none';
  if (!empaqueId || factor <= 0 || !baseUnit) {
    preview.style.display = 'none';
    if (helper) helper.style.display = 'none';
    return;
  }
  const empaqueUnit = state.unidadesMedida.find(u => u.id === empaqueId);
  if (!empaqueUnit) { preview.style.display = 'none'; if (helper) helper.style.display = 'none'; return; }
  preview.textContent = `1 ${empaqueUnit.nombre} de ${insumoNombre} equivale a ${factor} ${baseUnit.abreviatura}`;
  preview.style.display = '';
  helper.textContent = `💡 Configuración: 1 ${empaqueUnit.nombre} equivale a ${factor} ${baseUnit.nombre} en inventario.`;
  helper.style.display = '';
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
  const empaqueId = parseInt(document.getElementById('insumo-empaque-unit').value) || null;
  const empaqueFactor = parseFloat(document.getElementById('insumo-empaque-factor').value) || null;
  if (empaqueId && empaqueFactor && empaqueFactor > 0) {
    payload.unidad_empaque_id = empaqueId;
    payload.factor_empaque = empaqueFactor;
  }
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
   Unidades de Medida — Gestión Completa (Modal)
   ========================================================================= */
function openUnidadesModal() {
  document.getElementById('unidades-list-panel').style.display = '';
  document.getElementById('unidades-form-panel').style.display = 'none';
  document.getElementById('unidades-modal-title').textContent = 'Unidades de Medida';
  renderUnidadesTable();
  document.getElementById('modal-unidades').classList.add('show');
}

function closeUnidadesModal() {
  document.getElementById('modal-unidades').classList.remove('show');
}

function renderUnidadesTable() {
  const tbody = document.getElementById('unidades-table-body');
  const units = state.unidadesMedida;
  if (!units || units.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted" style="padding:24px;">No hay unidades registradas</td></tr>';
    return;
  }
  const magnitudIcons = { PESO: '⚖️', VOLUMEN: '🧪', UNIDAD: '📦', PERSONALIZADO: '✏️' };
  const unitsById = {};
  units.forEach(u => { unitsById[u.id] = u; });
  tbody.innerHTML = units.map(u => {
    const icon = magnitudIcons[u.tipo_magnitud] || '📦';
    const base = u.unidad_base_id ? (unitsById[u.unidad_base_id]?.nombre || '?') : '—';
    const factor = u.factor_conversion != null ? u.factor_conversion : '—';
    return `<tr>
      <td class="unidades-td-name">${u.nombre}</td>
      <td><span class="unidades-abrev-badge">${u.abreviatura}</span></td>
      <td><span class="unidades-mag-badge">${icon} ${u.tipo_magnitud}</span></td>
      <td>${base}</td>
      <td>${factor}</td>
      <td>
        <button class="icon-btn-sm" onclick="openEditUnidadForm(${u.id})" title="Editar">✏️</button>
        <button class="icon-btn-sm" onclick="eliminarUnidadCompleta(${u.id})" title="Eliminar">🗑️</button>
      </td>
    </tr>`;
  }).join('');
}

function openCreateUnidadForm() {
  document.getElementById('unidad-edit-id').value = '';
  document.getElementById('unidad-form-nombre').value = '';
  document.getElementById('unidad-form-abrev').value = '';
  document.getElementById('unidad-form-magnitud').value = 'UNIDAD';
  document.getElementById('unidad-form-derivada').checked = false;
  document.getElementById('unidad-conversion-fields').style.display = 'none';
  document.getElementById('unidad-form-base').innerHTML = '<option value="">Seleccionar base...</option>';
  document.getElementById('unidad-form-factor').value = '';
  document.getElementById('unidad-conversion-preview').textContent = '';
  document.getElementById('unidades-modal-title').textContent = 'Nueva Unidad';
  document.getElementById('unidades-list-panel').style.display = 'none';
  document.getElementById('unidades-form-panel').style.display = '';
}

function openEditUnidadForm(id) {
  const unit = state.unidadesMedida.find(u => u.id === id);
  if (!unit) return;
  document.getElementById('unidad-edit-id').value = id;
  document.getElementById('unidad-form-nombre').value = unit.nombre;
  document.getElementById('unidad-form-abrev').value = unit.abreviatura;
  document.getElementById('unidad-form-magnitud').value = unit.tipo_magnitud;
  const hasBase = !!unit.unidad_base_id;
  document.getElementById('unidad-form-derivada').checked = hasBase;
  document.getElementById('unidad-conversion-fields').style.display = hasBase ? '' : 'none';
  populateUnidadBaseSelect(unit.tipo_magnitud, unit.unidad_base_id);
  document.getElementById('unidad-form-factor').value = unit.factor_conversion != null ? unit.factor_conversion : '';
  document.getElementById('unidades-modal-title').textContent = 'Editar Unidad';
  document.getElementById('unidades-list-panel').style.display = 'none';
  document.getElementById('unidades-form-panel').style.display = '';
  updateConversionPreview();
}

function populateUnidadBaseSelect(magnitud, selectedId) {
  const sel = document.getElementById('unidad-form-base');
  const excludeId = parseInt(document.getElementById('unidad-edit-id').value) || null;
  const sameType = state.unidadesMedida.filter(u => u.tipo_magnitud === magnitud && u.id !== excludeId);
  const candidates = (magnitud === 'PERSONALIZADO' || sameType.length === 0)
    ? state.unidadesMedida.filter(u => u.id !== excludeId)
    : sameType;
  const hint = magnitud === 'PERSONALIZADO'
    ? 'Todas las unidades disponibles'
    : sameType.length === 0
      ? 'No hay otras unidades de esta magnitud'
      : '';
  sel.innerHTML = `<option value="">${hint || 'Seleccionar base...'}</option>` +
    candidates
      .map(u => `<option value="${u.id}" ${u.id === selectedId ? 'selected' : ''}>${u.nombre} (${u.abreviatura}) [${u.tipo_magnitud}]</option>`)
      .join('');
}

function toggleUnidadDerivada() {
  const checked = document.getElementById('unidad-form-derivada').checked;
  document.getElementById('unidad-conversion-fields').style.display = checked ? '' : 'none';
  if (checked) {
    const magnitud = document.getElementById('unidad-form-magnitud').value;
    populateUnidadBaseSelect(magnitud, null);
  }
  updateConversionPreview();
}

function updateConversionPreview() {
  const preview = document.getElementById('unidad-conversion-preview');
  const derivada = document.getElementById('unidad-form-derivada').checked;
  if (!derivada) { preview.textContent = ''; return; }
  const nombre = document.getElementById('unidad-form-nombre').value.trim();
  const abrev = document.getElementById('unidad-form-abrev').value.trim();
  const factor = document.getElementById('unidad-form-factor').value;
  const baseId = parseInt(document.getElementById('unidad-form-base').value) || null;
  const baseUnit = baseId ? state.unidadesMedida.find(u => u.id === baseId) : null;
  if (!nombre || !factor || !baseUnit) {
    preview.textContent = 'Completa nombre, factor y unidad base para ver la vista previa.';
    return;
  }
  preview.textContent = `1 ${nombre} (${abrev || '?'}) = ${factor} ${baseUnit.nombre} (${baseUnit.abreviatura})`;
}

async function saveUnidadFormCompleta() {
  const id = document.getElementById('unidad-edit-id').value || null;
  const nombre = document.getElementById('unidad-form-nombre').value.trim();
  const abreviatura = document.getElementById('unidad-form-abrev').value.trim();
  const tipo_magnitud = document.getElementById('unidad-form-magnitud').value;
  const derivada = document.getElementById('unidad-form-derivada').checked;
  const factor = parseFloat(document.getElementById('unidad-form-factor').value) || null;
  const baseId = parseInt(document.getElementById('unidad-form-base').value) || null;

  if (!nombre) return showToast('Ingresa el nombre', 'warning');
  if (!abreviatura) return showToast('Ingresa la abreviatura', 'warning');
  if (derivada && !baseId) return showToast('Selecciona una unidad base', 'warning');
  if (derivada && !factor) return showToast('Ingresa el factor de conversión', 'warning');

  const body = { nombre, abreviatura, tipo_magnitud };
  if (derivada) {
    body.unidad_base_id = baseId;
    body.factor_conversion = factor;
  } else {
    body.unidad_base_id = null;
    body.factor_conversion = null;
  }

  try {
    if (id) {
      await api(`/inventario/unidades-medida/${id}`, { method: 'PUT', body: JSON.stringify(body) });
      showToast('Unidad actualizada');
    } else {
      await api('/inventario/unidades-medida', { method: 'POST', body: JSON.stringify(body) });
      showToast('Unidad creada');
    }
    await loadUnidadesMedida();
    populateUnidadSelect();
    openUnidadesModal();
  } catch { /* handled by api() */ }
}

async function eliminarUnidadCompleta(id) {
  const unit = state.unidadesMedida.find(u => u.id === id);
  if (!confirm(`¿Eliminar la unidad "${unit?.nombre || id}"?`)) return;
  try {
    await api(`/inventario/unidades-medida/${id}`, { method: 'DELETE' });
    await loadUnidadesMedida();
    populateUnidadSelect();
    renderUnidadesTable();
    showToast('Unidad eliminada');
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
  syncMassTurnoButton();
}

const EMP_AVATAR_TINTS = [
  ['#0F3B66', '#E3EAF3'], ['#006B6B', '#E0F2EF'], ['#B4462A', '#FDEBE6'],
  ['#7A5AF8', '#ECE8FE'], ['#D97706', '#FEF3E2'], ['#0E7490', '#E0F2FE'],
];

function empIniciales(nombre, apellido) {
  return (((nombre || '')?.[0] || '') + ((apellido || '')?.[0] || '')).toUpperCase() || '?';
}

function empRolMeta(puesto) {
  const n = (puesto || '').toLowerCase();
  if (n.includes('admin')) return { emoji: '🛡️', cls: 'badge-rol-admin' };
  if (n.includes('coci')) return { emoji: '🍳', cls: 'badge-rol-cocina' };
  if (n.includes('caj') || n.includes('cont')) return { emoji: '🧾', cls: 'badge-rol-caja' };
  if (n.includes('mes')) return { emoji: '🤵', cls: 'badge-rol-mesero' };
  if (n.includes('ger')) return { emoji: '📊', cls: 'badge-rol-ger' };
  return { emoji: '👤', cls: 'badge-rol-default' };
}

function renderPersonalTable(empleados, usuarios) {
  const container = document.getElementById('personal-table-container');
  const userMap = {};
  (usuarios || []).forEach(u => { userMap[u.empleado_id] = u; });

  if (!empleados || empleados.length === 0) {
    container.innerHTML = `
      <div class="p-10 text-center">
        <span class="material-symbols-outlined text-[40px] text-slate-300">groups</span>
        <p class="mt-3 text-sm font-semibold text-slate-500">No hay empleados registrados</p>
        <p class="text-xs text-slate-400 mt-1">Usa "Agregar Empleado" para comenzar</p>
      </div>`;
    return;
  }

  const totalActivos = empleados.filter(e => e.activo).length;
  const planilla = empleados.reduce((s, e) => s + parseFloat(e.salario_base || e.puesto?.salario_base || 0), 0);

  container.innerHTML = `
    <div class="flex items-center justify-between px-4 py-3 border-b border-slate-100">
      <div>
        <h3 class="font-display text-base font-extrabold text-brand-navy leading-none">Directorio de Empleados</h3>
        <p class="text-xs text-slate-500 mt-1">${empleados.length} empleados · ${totalActivos} activos</p>
      </div>
      <span class="inline-flex items-center gap-1 h-8 px-3 rounded-full bg-[#E8F1F1] text-[12px] font-bold text-[#006B6B]">
        <span class="material-symbols-outlined text-[15px]">payments</span> Planilla C$${planilla.toFixed(2)}
      </span>
    </div>
    <div class="overflow-x-auto">
      <table id="personal-table" class="employee-table w-full text-sm min-w-[720px]">
        <thead>
          <tr>
            <th>Empleado</th>
            <th>Puesto</th>
            <th>Salario</th>
            <th>Teléfono</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          ${empleados.map((e, i) => {
            const user = userMap[e.id];
            const nombreCompleto = `${e.nombre} ${e.apellido}`;
            const nq = nombreCompleto.replace(/'/g, "\\'");
            const username = user?.username || '';
            const [aviB, aviF] = EMP_AVATAR_TINTS[i % EMP_AVATAR_TINTS.length];
            const rol = empRolMeta(e.puesto?.nombre);
            const subtitulo = [e.cedula_identidad, username].filter(Boolean).join(' · ');
            const salario = parseFloat(e.salario_base || e.puesto?.salario_base || 0).toFixed(2);
            return `
            <tr>
              <td>
                <div class="flex items-center gap-3">
                  <span class="emp-avatar shrink-0" style="background:${aviB};color:${aviF};">${empIniciales(e.nombre, e.apellido)}</span>
                  <div class="min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-bold text-slate-800 truncate">${nombreCompleto}</span>
                      <span class="emp-status ${e.activo ? 'emp-status-activo' : 'emp-status-inactivo'}">${e.activo ? 'Activo' : 'Inactivo'}</span>
                    </div>
                    ${subtitulo ? `<p class="text-xs text-slate-400 truncate">${subtitulo}</p>` : ''}
                  </div>
                </div>
              </td>
              <td><span class="emp-rol-badge ${rol.cls}">${rol.emoji} ${e.puesto?.nombre || '—'}</span></td>
              <td class="salary-cell text-[#0F3B66] font-bold whitespace-nowrap">C$${salario}</td>
              <td class="whitespace-nowrap">${e.telefono || '—'}</td>
              <td>
                <div class="flex items-center gap-1.5">
                  <button class="emp-action emp-turq" title="Ver nómina de ${nombreCompleto}" onclick="openNominaModal(${e.id}, '${nq}')"><span class="material-symbols-outlined">payments</span></button>
                  <button class="emp-action emp-sky" title="Ver asistencias de ${nombreCompleto}" onclick="openAsistenciasModal(${e.id}, '${nq}')"><span class="material-symbols-outlined">history</span></button>
                  ${user ? `<button class="emp-action emp-slate" title="Restablecer contraseña de ${username}" onclick="openResetPasswordModal(${user.id}, '${user.username}')"><span class="material-symbols-outlined">key</span></button>` : ''}
                  ${user ? `<button class="emp-action emp-danger admin-only" title="Eliminar usuario de ${nombreCompleto}" onclick="openEliminarUsuarioModal(${user.id}, '${user.username}', '${nq}')"><span class="material-symbols-outlined">delete</span></button>` : ''}
                  ${user && user.rol === 'Vendedor' ? `
                  <button class="btn-toggle-turno ${user.turno_habilitado ? 'active text-emerald-600 bg-emerald-50' : 'inactive text-slate-400 bg-slate-100'} admin-only p-1.5 rounded-lg transition-colors" data-id="${user.id}" data-enabled="${user.turno_habilitado ? 'true' : 'false'}" title="${user.turno_habilitado ? 'Deshabilitar Turno' : 'Habilitar Turno'} de ${nombreCompleto}">
                    <span class="material-symbols-outlined text-lg leading-none block">${user.turno_habilitado ? 'toggle_on' : 'toggle_off'}</span>
                  </button>` : ''}
                  <button class="emp-action emp-danger admin-only ${e.activo ? '' : 'is-disabled'}" title="Dar de baja" onclick="openEliminarEmpleadoModal(${e.id})"><span class="material-symbols-outlined">person_off</span></button>
                </div>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;
}

/* -------------------------------------------------------------------------
   Habilitación Dinámica de Turno (vendedores)
   ------------------------------------------------------------------------- */

function syncMassTurnoButton() {
  const btn = document.getElementById('btn-toggle-all-turnos');
  if (!btn) return;
  const vendedores = (state.usuarios || []).filter(u => u.rol === 'Vendedor');
  const allEnabled = vendedores.length > 0 && vendedores.every(u => u.turno_habilitado);
  btn.dataset.enabled = String(allEnabled);
  btn.querySelector('.material-symbols-outlined').textContent = allEnabled ? 'toggle_on' : 'toggle_off';
  const label = btn.querySelector('span:last-child');
  if (label) label.textContent = allEnabled ? 'Turnos Habilitados' : 'Habilitar Todos los Turnos';
}

async function toggleTurnoMasivo() {
  const btn = document.getElementById('btn-toggle-all-turnos');
  if (!btn) return;
  const next = btn.dataset.enabled !== 'true';
  btn.disabled = true;
  try {
    const res = await api('/personal/usuarios/turno-masivo', {
      method: 'PATCH',
      body: JSON.stringify({ turno_habilitado: next }),
    });
    (state.usuarios || []).forEach(u => {
      if (u.rol === 'Vendedor') u.turno_habilitado = next;
    });
    renderPersonalTable(state.empleados, state.usuarios);
    syncMassTurnoButton();
    showToast(next
      ? `Meseros habilitados para iniciar turno (${res.actualizados || 0})`
      : 'Turno de todos los meseros deshabilitado');
  } catch { /* handled by api() */ } finally { btn.disabled = false; }
}

async function toggleTurnoUsuario(usuarioId, habilitar) {
  try {
    const res = await api(`/personal/usuarios/${usuarioId}/turno`, {
      method: 'PATCH',
      body: JSON.stringify({ turno_habilitado: habilitar }),
    });
    const usu = (state.usuarios || []).find(u => u.id === usuarioId);
    if (usu) usu.turno_habilitado = res.turno_habilitado;
    renderPersonalTable(state.empleados, state.usuarios);
    syncMassTurnoButton();
    showToast(habilitar
      ? 'Mesero habilitado para iniciar turno'
      : 'Mesero deshabilitado — no podrá iniciar turno');
  } catch { /* handled by api() */ }
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

/* =========================================================================
   Dar de Baja Empleado (borrado lógico con autorización por contraseña)
   ========================================================================= */
let eliminarEmpleadoId = null;

function openEliminarEmpleadoModal(empleadoId) {
  eliminarEmpleadoId = empleadoId;
  const emp = (state.empleados || []).find(x => x.id === empleadoId);
  const nombre = emp ? `${emp.nombre} ${emp.apellido}` : `#${empleadoId}`;
  document.getElementById('baja-empleado-nombre').textContent = nombre;
  const pw = document.getElementById('baja-empleado-password');
  pw.value = '';
  document.getElementById('confirm-eliminar-empleado').disabled = false;
  document.getElementById('modal-eliminar-empleado').classList.add('show');
  setTimeout(() => pw.focus(), 80);
}

function closeEliminarEmpleadoModal() {
  document.getElementById('modal-eliminar-empleado').classList.remove('show');
  eliminarEmpleadoId = null;
}

async function confirmEliminarEmpleado() {
  if (!eliminarEmpleadoId) return;
  const pw = document.getElementById('baja-empleado-password');
  if (!pw.value) return showToast('Ingresa tu contraseña para autorizar', 'warning');
  const btn = document.getElementById('confirm-eliminar-empleado');
  btn.disabled = true;
  try {
    await api(`/personal/empleados/${eliminarEmpleadoId}`, {
      method: 'DELETE',
      body: JSON.stringify({ password: pw.value }),
    });
    showToast('Empleado dado de baja correctamente');
    closeEliminarEmpleadoModal();
    loadPersonal();
  } catch (e) {
    pw.focus();
    pw.select();
  } finally {
    btn.disabled = false;
  }
}

/* =========================================================================
   Eliminar Usuario (físico o archivo con liberación de username)
   ========================================================================= */
let eliminarUsuarioId = null;

function openEliminarUsuarioModal(usuarioId, username, nombreEmpleado) {
  eliminarUsuarioId = usuarioId;
  document.getElementById('eliminar-usuario-nombre').textContent = nombreEmpleado || `#${usuarioId}`;
  document.getElementById('eliminar-usuario-username').textContent = username || '';
  const pw = document.getElementById('eliminar-usuario-password');
  pw.value = '';
  document.getElementById('confirm-eliminar-usuario').disabled = false;
  document.getElementById('modal-eliminar-usuario').classList.add('show');
  setTimeout(() => pw.focus(), 80);
}

function closeEliminarUsuarioModal() {
  document.getElementById('modal-eliminar-usuario').classList.remove('show');
  eliminarUsuarioId = null;
}

async function confirmEliminarUsuario() {
  if (!eliminarUsuarioId) return;
  const pw = document.getElementById('eliminar-usuario-password');
  if (!pw.value) return showToast('Ingresa tu contraseña para autorizar', 'warning');
  const btn = document.getElementById('confirm-eliminar-usuario');
  btn.disabled = true;
  try {
    const res = await api(`/personal/usuarios/${eliminarUsuarioId}`, {
      method: 'DELETE',
      body: JSON.stringify({ password: pw.value }),
    });
    showToast(res?.mensaje || 'Usuario procesado correctamente');
    closeEliminarUsuarioModal();
    loadPersonal();
  } catch (e) {
    pw.focus();
    pw.select();
  } finally {
    btn.disabled = false;
  }
}

async function calcularNomina() {
  const fechaInicio = document.getElementById('nomina-fecha-inicio').value;
  const fechaFin = document.getElementById('nomina-fecha-fin').value;

  if (!fechaInicio || !fechaFin) return showToast('Selecciona ambas fechas', 'warning');
  if (!nominaModalEmpleadoId) return showToast('Error: no se identificó el empleado', 'error');

  const btn = document.getElementById('btn-calcular-nomina');
  btn.disabled = true;
  btn.textContent = '⏳ Calculando…';

  const buildBody = (recalcular) => JSON.stringify({
    empleado_id: nominaModalEmpleadoId,
    fecha_inicio: fechaInicio,
    fecha_fin: fechaFin,
    recalcular,
  });

  const finalizarCalculo = (result, mensaje) => {
    state.nominaActual = result;
    renderNominaResult(result);
    showToast(mensaje, 'success');
    loadNominaHistorial(nominaModalEmpleadoId);
  };

  try {
    const result = await api('/nomina/calcular', {
      method: 'POST',
      silent: true,
      body: buildBody(false),
    });
    finalizarCalculo(result, 'Nómina calculada con éxito');
  } catch (e) {
    const msg = (e && e.message) || '';
    if (!/Ya existe nómina registrada/.test(msg)) {
      showToast(msg || 'Error al calcular nómina', 'error');
      return;
    }
    if (!confirm('Ya existe un registro para este periodo. ¿Deseas recalcular los montos con el esquema actual?')) {
      return;
    }
    btn.textContent = '⏳ Recalculando…';
    try {
      const result = await api('/nomina/calcular', {
        method: 'POST',
        body: buildBody(true),
      });
      finalizarCalculo(result, `Nómina recalculada: C$${parseFloat(result.pago_neto).toFixed(2)}`);
    } catch { /* handled by api() */ }
  } finally {
    btn.disabled = false;
    btn.textContent = '🧮 Calcular Nómina';
  }
}

async function recalcularNominaRegistro(nominaId) {
  try {
    const result = await api(`/nomina/${nominaId}/recalcular`, { method: 'PUT' });
    if (state.nominaActual && state.nominaActual.id === result.id) {
      state.nominaActual = result;
      renderNominaResult(result);
    }
    showToast(`Nómina recalculada: C$${parseFloat(result.pago_neto).toFixed(2)}`, 'success');
    loadNominaHistorial(nominaModalEmpleadoId);
  } catch { /* handled by api() */ }
}

function renderNominaResult(data) {
  const resultDiv = document.getElementById('nomina-result');
  resultDiv.style.display = 'block';

  document.getElementById('nomina-periodo-text').textContent =
    `${data.fecha_inicio} al ${data.fecha_fin}`;

  const base = parseFloat(data.salario_quincenal_teorico);
  const tarifa = parseFloat(data.tarifa_hora_extra || (parseFloat(data.salario_base_mensual) / 240));
  const horasExtras = parseFloat(data.total_horas_extras);
  const montoExtras = parseFloat(data.pago_horas_extras);

  document.getElementById('nomina-salario-base').textContent = `C$${base.toFixed(2)}`;

  if (horasExtras > 0) {
    document.getElementById('nomina-horas-extras').textContent =
      `${horasExtras.toFixed(2)} h × C$${tarifa.toFixed(2)}/h`;
    document.getElementById('nomina-pago-extras').textContent = `C$${montoExtras.toFixed(2)}`;
  } else {
    document.getElementById('nomina-horas-extras').textContent = '0.00 h';
    document.getElementById('nomina-pago-extras').textContent = 'C$0.00';
  }

  const diasTrabajados = horasExtras > 0 ? 'Con horas' : '0 h';
  document.getElementById('nomina-asistencia-dias').textContent = `${horasExtras.toFixed(2)} h extra`;

  const adelantosRow = document.getElementById('nomina-adelantos-row');
  const adelantosDisplay = document.getElementById('nomina-adelantos-display');
  const totalAdelantos = parseFloat(data.total_adelantos || 0);
  if (totalAdelantos > 0) {
    adelantosRow.style.display = 'flex';
    adelantosDisplay.textContent = `-C$${totalAdelantos.toFixed(2)}`;
  } else {
    adelantosRow.style.display = 'none';
  }

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

let adelantoEmpleadoId = null;

function openRegistrarAdelantoModal(empleadoId) {
  adelantoEmpleadoId = empleadoId;
  document.getElementById('adelanto-monto').value = '';
  document.getElementById('adelanto-observacion').value = '';
  document.getElementById('modal-registrar-adelanto').classList.add('show');
}

function closeRegistrarAdelantoModal() {
  document.getElementById('modal-registrar-adelanto').classList.remove('show');
  adelantoEmpleadoId = null;
}

async function guardarAdelanto(e) {
  e.preventDefault();
  const monto = parseFloat(document.getElementById('adelanto-monto').value);
  if (!monto || monto <= 0) {
    return showToast('Ingrese un monto válido mayor a cero.', 'error');
  }
  const observacion = document.getElementById('adelanto-observacion').value.trim();

  const btn = document.getElementById('btn-guardar-adelanto');
  btn.disabled = true;
  btn.textContent = '⏳ Guardando…';

  try {
    await api(`/nomina/adelantos`, {
      method: 'POST',
      body: JSON.stringify({
        empleado_id: adelantoEmpleadoId,
        monto,
        observacion: observacion || undefined,
      }),
    });
    showToast('Adelanto registrado con éxito', 'success');
    closeRegistrarAdelantoModal();
  } catch {
    /* handled by api() */
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Guardar Adelanto';
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
      ? `Pagado: ${new Date(n.fecha_pago).toLocaleDateString('es-NI')}`
      : '';

    const adel = parseFloat(n.total_adelantos || 0);
    const adelLine = adel > 0
      ? `<div class="nh-adelantos" style="font-size:11px;color:var(--rojo-cangrejo);">Adelantos: -C$${adel.toFixed(2)}</div>`
      : '';
    const recalcBtn = !esPagado
      ? `<button class="emp-action emp-sky admin-only nh-recalc" title="Recalcular con el esquema actual" onclick="recalcularNominaRegistro(${n.id})"><span class="material-symbols-outlined">sync</span></button>`
      : '';
    return `
      <div class="nomina-history-item">
        <div class="nh-period">
          <div class="nh-dates">📅 ${n.fecha_inicio} — ${n.fecha_fin}</div>
          ${paidDate ? `<div class="nh-paid">${paidDate}</div>` : ''}
          ${adelLine}
        </div>
        <div class="nh-amount">C$${parseFloat(n.pago_neto).toFixed(2)}</div>
        <span class="nh-status ${statusClass}">${statusText}</span>
        ${recalcBtn}
      </div>`;
  }).join('');
}

/* =========================================================================
   Nuevo Empleado (Modal)
   ========================================================================= */
let puestosCache = [];

async function loadPuestos(force) {
  if (!force && puestosCache.length > 0) return;
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

function togglePuestoPanel() {
  const panel = document.getElementById('puesto-panel');
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

async function guardarPuesto() {
  const nombre = document.getElementById('new-puesto-nombre').value.trim();
  if (!nombre) return showToast('Ingresa el nombre del puesto', 'warning');
  try {
    const nuevo = await api('/personal/puestos', { method: 'POST', body: JSON.stringify({ nombre, salario_base: 0 }) });
    document.getElementById('new-puesto-nombre').value = '';
    document.getElementById('puesto-panel').style.display = 'none';
    await loadPuestos(true);
    populatePuestoSelect();
    const sel = document.getElementById('ne-puesto');
    sel.value = nuevo.id;
    showToast('Puesto creado');
  } catch { /* handled */ }
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
          const entrada = formatLocalTime(a.hora_entrada_real);
          const salida = a.hora_salida_real
            ? formatLocalTime(a.hora_salida_real)
            : '<span style="color:#E63946;font-weight:600;">Activo</span>';
          const ot = parseFloat(a.horas_extras);
          const otBadge = ot > 0
            ? `<span style="background:#fef9c3;color:#854d0e;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;">${ot.toFixed(2)}h</span>`
            : '<span style="color:#9ca3af;">0.00h</span>';
          const auditInfo = a.anulada
            ? `<span title="Anulado por Usuario #${a.modificado_por ?? '—'} · Motivo: ${a.motivo_modificacion || '—'}" style="cursor:help;background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:999px;font-size:11px;font-weight:600;">🚫 Anulado</span>`
            : (a.horas_extras_originales != null
              ? `<span title="Original: ${parseFloat(a.horas_extras_originales).toFixed(2)}h\nMotivo: ${a.motivo_modificacion || '—'}\nModificado por: Usuario #${a.modificado_por}" style="cursor:help;background:#fee2e2;color:#991b1b;padding:2px 6px;border-radius:999px;font-size:11px;font-weight:600;">✏️ Auditado</span>`
              : '<span style="color:#9ca3af;font-size:11px;">—</span>');
          const empleadoNombre = document.getElementById('asis-employee-name')?.textContent || '';
          const acciones = a.anulada
            ? '<span style="color:#9ca3af;font-size:11px;">—</span>'
            : `
              <button class="btn-action-action" onclick="openEditarHorariosModal(${a.id}, '${a.fecha}', '${empleadoNombre.replace(/'/g, "\\'")}', '${a.hora_entrada_real}', '${a.hora_salida_real || ''}')" title="Editar Entrada/Salida">✏️</button>
              <button class="btn-action-action" onclick="openEditOTModal(${a.id}, '${a.fecha}', ${a.horas_extras})" title="Editar Horas Extras">⏱️</button>
              <button class="btn-action-action btn-action-danger admin-only" onclick="openAnularAsistenciaModal(${a.id}, '${a.fecha}')" title="Eliminar/Anular registro">🗑️</button>`;
          return `
            <tr>
              <td>${a.id}</td>
              <td>${a.fecha}</td>
              <td>${entrada}</td>
              <td>${salida}</td>
              <td>${otBadge}</td>
              <td>${auditInfo}</td>
              <td style="font-size:12px;color:#6b7280;">Turno #${a.turno_id}</td>
              <td>${acciones}</td>
            </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

/* =========================================================================
   Anular Asistencia
   ========================================================================= */
let anularAsistenciaId = null;

function openAnularAsistenciaModal(asistenciaId, fecha) {
  anularAsistenciaId = asistenciaId;
  document.getElementById('anular-asis-id').textContent = asistenciaId;
  document.getElementById('anular-asis-fecha').textContent = fecha || '—';
  document.getElementById('anular-asis-motivo').value = '';
  document.getElementById('modal-anular-asistencia').classList.add('show');
}

function closeAnularAsistenciaModal() {
  document.getElementById('modal-anular-asistencia').classList.remove('show');
  anularAsistenciaId = null;
}

async function confirmAnularAsistencia() {
  const motivo = document.getElementById('anular-asis-motivo').value;
  if (!motivo || !motivo.trim()) {
    return showToast('El motivo de la anulación es obligatorio', 'warning');
  }
  if (!anularAsistenciaId) return showToast('Error: no se identificó el registro', 'error');

  try {
    const anulada = await api(`/asistencia/${anularAsistenciaId}`, {
      method: 'DELETE',
      body: JSON.stringify({ motivo: motivo.trim() }),
    });
    showToast(`Registro de asistencia #${anulada.id} anulado correctamente`, 'success');
    closeAnularAsistenciaModal();
    if (asisEmpleadoId) loadAsistenciasEmpleado(asisEmpleadoId);
  } catch { /* handled by api() */ }
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

let editHorariosAsistenciaId = null;

function openEditarHorariosModal(asistenciaId, fecha, empleadoNombre, horaEntradaLocal, horaSalidaLocal) {
  editHorariosAsistenciaId = asistenciaId;
  document.getElementById('editar-horarios-fecha').textContent = fecha;
  document.getElementById('editar-horarios-empleado').textContent = empleadoNombre;

  const toInputValue = (localStr) => (localStr ? String(localStr).slice(0, 16) : '');

  document.getElementById('editar-hora-entrada').value = toInputValue(horaEntradaLocal);
  document.getElementById('editar-hora-salida').value = toInputValue(horaSalidaLocal);
  updateHorariosPreviews();
  document.getElementById('editar-horarios-motivo').value = '';
  document.getElementById('confirm-editar-horarios').disabled = true;
  document.getElementById('modal-editar-horarios').classList.add('show');

  const motivoInput = document.getElementById('editar-horarios-motivo');
  const handler = () => {
    document.getElementById('confirm-editar-horarios').disabled = !motivoInput.value.trim();
  };
  motivoInput.removeEventListener('input', motivoInput._horariosHandler);
  motivoInput._horariosHandler = handler;
  motivoInput.addEventListener('input', handler);

  ['editar-hora-entrada', 'editar-hora-salida'].forEach((id) => {
    const el = document.getElementById(id);
    el.removeEventListener('input', el._horariosPreviewHandler);
    el._horariosPreviewHandler = updateHorariosPreviews;
    el.addEventListener('input', el._horariosPreviewHandler);
  });
}

function format12hPreview(value) {
  if (!value) return '—';
  const [datePart, timePart] = value.split('T');
  let [h, m] = timePart.split(':').map(Number);
  const ap = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  const [y, mo, d] = datePart.split('-');
  return `${d}/${mo}/${y} · ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')} ${ap}`;
}

function updateHorariosPreviews() {
  const entrada = document.getElementById('editar-hora-entrada').value;
  const salida = document.getElementById('editar-hora-salida').value;
  document.getElementById('editar-hora-entrada-preview').textContent = format12hPreview(entrada);
  document.getElementById('editar-hora-salida-preview').textContent = salida ? format12hPreview(salida) : 'Sin salida registrada';
}

function closeEditarHorariosModal() {
  document.getElementById('modal-editar-horarios').classList.remove('show');
  editHorariosAsistenciaId = null;
}

async function confirmEditarHorarios() {
  const fechaHoraEntrada = document.getElementById('editar-hora-entrada').value;
  const fechaHoraSalida = document.getElementById('editar-hora-salida').value || null;
  const motivo = document.getElementById('editar-horarios-motivo').value.trim();

  if (!fechaHoraEntrada) return showToast('La fecha y hora de entrada es obligatoria', 'warning');
  if (fechaHoraSalida && fechaHoraSalida <= fechaHoraEntrada) {
    return showToast('La salida debe ser posterior a la entrada (usa la fecha del día siguiente en turnos nocturnos)', 'warning');
  }
  if (!motivo) return showToast('El motivo es obligatorio para auditoría', 'warning');
  if (!editHorariosAsistenciaId) return showToast('Error: no se identificó la asistencia', 'error');

  try {
    await api(`/asistencia/${editHorariosAsistenciaId}/editar-horarios`, {
      method: 'PUT',
      body: JSON.stringify({ fecha_hora_entrada: fechaHoraEntrada, fecha_hora_salida: fechaHoraSalida, motivo }),
    });
    showToast('Horarios actualizados con auditoría registrada', 'success');
    closeEditarHorariosModal();
    if (asisEmpleadoId) loadAsistenciasEmpleado(asisEmpleadoId);
  } catch { /* handled by api() */ }
}

/* =========================================================================
   Preparación de Cocina (Producción por Lote)
   ========================================================================= */
let prepRowCount = 0;
let loteInsumoIds = [];

async function openPreparacionModal() {
  prepRowCount = 0;
  document.getElementById('preparacion-rows').innerHTML = '';
  document.getElementById('prep-notas').value = '';
  document.getElementById('prep-lote-toggle').checked = false;
  try {
    loteInsumoIds = await api('/inventario/insumos/lote-ids');
  } catch {
    loteInsumoIds = [];
  }
  updatePrepSummary();
  addPreparacionRow();
  document.getElementById('modal-preparacion').classList.add('show');
}

function closePreparacionModal() {
  document.getElementById('modal-preparacion').classList.remove('show');
}

function addPreparacionRow() {
  prepRowCount++;
  const id = prepRowCount;
  const container = document.getElementById('preparacion-rows');
  const insumos = state.insumos || [];
  const loteOnly = document.getElementById('prep-lote-toggle')?.checked;

  let filtered = insumos;
  if (loteOnly) {
    filtered = insumos.filter(i => loteInsumoIds.includes(i.id));
  }

  const sorted = [...filtered].sort((a, b) => {
    const aLote = loteInsumoIds.includes(a.id);
    const bLote = loteInsumoIds.includes(b.id);
    if (aLote && !bLote) return -1;
    if (!aLote && bLote) return 1;
    return a.nombre.localeCompare(b.nombre);
  });

  const options = sorted.map(i => {
    const isLote = loteInsumoIds.includes(i.id);
    const badge = isLote ? ' <span class="toggle-lote-badge">LOTE</span>' : '';
    return `<option value="${i.id}" data-stock="${i.cantidad_actual}" data-unit="${i.unidad_medida}">${i.nombre} (Stock: ${i.cantidad_actual} ${i.unidad_medida})${badge}</option>`;
  }).join('');

  const row = document.createElement('div');
  row.className = 'prep-row';
  row.style.cssText = 'display:flex;gap:8px;align-items:end;margin-bottom:8px;';
  row.innerHTML = `
    <div style="flex:3;">
      <label class="form-label" style="font-size:12px;">Insumo</label>
      <select class="form-input prep-insumo" data-row="${id}" style="height:36px;font-size:13px;" onchange="updatePrepSummary()">
        <option value="">Seleccionar…</option>
        ${options}
      </select>
    </div>
    <div style="flex:1.5;">
      <label class="form-label" style="font-size:12px;">Cantidad</label>
      <input type="number" class="form-input prep-cantidad" data-row="${id}" step="0.01" min="0.01" placeholder="0" style="height:36px;font-size:13px;" oninput="updatePrepSummary()">
    </div>
    <button type="button" class="btn btn-secondary" onclick="this.closest('.prep-row').remove();updatePrepSummary();" style="height:36px;padding:0 8px;font-size:14px;color:#E63946;" title="Eliminar">✕</button>
  `;
  container.appendChild(row);
}

function updatePrepSummary() {
  const rows = document.querySelectorAll('.prep-row');
  let total = 0;
  rows.forEach(row => {
    const cant = parseFloat(row.querySelector('.prep-cantidad')?.value || 0);
    if (cant > 0) total++;
  });
  document.getElementById('prep-summary').textContent = `Total insumos: ${total}`;
}

async function submitPreparacion() {
  const rows = document.querySelectorAll('.prep-row');
  const detalles = [];

  for (const row of rows) {
    const insumoId = row.querySelector('.prep-insumo')?.value;
    const cantidad = parseFloat(row.querySelector('.prep-cantidad')?.value || 0);
    if (!insumoId || cantidad <= 0) continue;
    detalles.push({ insumo_id: parseInt(insumoId), cantidad });
  }

  if (detalles.length === 0) return showToast('Agrega al menos un insumo con cantidad', 'warning');

  const notas = document.getElementById('prep-notas').value.trim() || null;

  try {
    await api('/inventario/preparaciones', {
      method: 'POST',
      body: JSON.stringify({ detalles, notas }),
    });
    showToast(`Producción registrada: ${detalles.length} insumo(s) descontado(s)`, 'success');
    closePreparacionModal();
    await loadInsumos();
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
  const grid = document.getElementById('cierre-summary');
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
    ['cc-ingresos', 'cc-nomina', 'cc-insumos', 'cc-gastos-op', 'cc-utilidad', 'cc-descuentos'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = 'C$0.00';
    });
    document.getElementById('cierre-periodo-label').textContent = '';
    document.getElementById('cierre-ordenes-info').textContent = '';
    document.getElementById('cierre-top-list').innerHTML = '';
    destroyCharts();
    return;
  }

  const fmt = v => 'C$' + parseFloat(v).toLocaleString('es-NI', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const utilPositiva = data.utilidad_neta >= 0;

  document.getElementById('cc-ingresos').textContent = fmt(data.ingresos_totales);
  document.getElementById('cc-nomina').textContent = fmt(data.gastos_nomina);
  document.getElementById('cc-insumos').textContent = fmt(data.costo_insumos);
  document.getElementById('cc-gastos-op').textContent = fmt(data.gastos_operativos);

  const descEl = document.getElementById('cc-descuentos');
  if (descEl) {
    descEl.textContent = `-${fmt(Math.abs(data.total_descuentos || 0))}`.replace('C$-', '-C$');
  }

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
            label: ctx => `${ctx.label}: C$${parseFloat(ctx.parsed).toLocaleString('es-NI', { minimumFractionDigits: 2 })}`,
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
              if (ctx.datasetIndex === 1) return `Ingresos: C$${parseFloat(ctx.parsed.y).toLocaleString('es-NI')}`;
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
          <span class="cierre-top-rev">C$${parseFloat(p.ingresos_generados).toLocaleString('es-NI')}</span>
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

  document.getElementById('oc-mesa-numero').textContent = mesa.apodo ? `${mesa.numero} · «${mesa.apodo}»` : mesa.numero;
  const apodoInput = document.getElementById('oc-apodo-input');
  if (apodoInput) apodoInput.value = mesa.apodo || '';
  document.getElementById('oc-items-list').innerHTML =
    '<p style="text-align:center;color:#9ca3af;padding:16px;">Cargando orden…</p>';
  ['oc-subtotal', 'oc-total'].forEach(id => {
    document.getElementById(id).textContent = 'C$0.00';
  });

  document.getElementById('btn-agregar-pedido').style.display = '';
  document.getElementById('btn-pre-cuenta').style.display = '';
  document.getElementById('btn-cerrar-cuenta').style.display = '';
  document.getElementById('btn-forzar-librar').style.display = 'none';

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
      document.getElementById('oc-subtotal').textContent = 'C$0.00';
      document.getElementById('oc-total').textContent = 'C$0.00';
      document.getElementById('btn-agregar-pedido').style.display = 'none';
      document.getElementById('btn-pre-cuenta').style.display = 'none';
      document.getElementById('btn-cerrar-cuenta').style.display = 'none';
      document.getElementById('btn-forzar-librar').style.display = 'block';
      return;
    }

    document.getElementById('btn-agregar-pedido').style.display = '';
    document.getElementById('btn-pre-cuenta').style.display = '';
    document.getElementById('btn-cerrar-cuenta').style.display = '';
    document.getElementById('btn-forzar-librar').style.display = 'none';

    state.currentOcupada.orden = orden;
    document.getElementById('oc-orden-id').textContent = orden.id;
    renderOcItems(orden);
  } catch {
    document.getElementById('oc-items-list').innerHTML =
      '<p style="text-align:center;color:#E63946;padding:16px;">Error al cargar la orden.</p>';
  }
}

async function forzarLibrarMesa() {
  const oc = state.currentOcupada;
  if (!oc) return;
  if (!confirm('¿Liberar esta mesa? No se encontró orden activa asociada.')) return;

  try {
    await api(`/salon/mesas/${oc.mesaId}`, {
      method: 'PUT',
      body: JSON.stringify({ estado: 'LIBRE' }),
    });
    const mesa = state.tables.find(t => t.id === oc.mesaId);
    if (mesa) {
      mesa.estado = 'LIBRE';
      mesa.apodo = null;
    }
    showToast('Mesa liberada correctamente', 'success');
    closeDetalleMesaOcupada();
    renderTables(state.tables);
  } catch {
    showToast('Error al liberar la mesa', 'error');
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
      const precioBase = parseFloat(d.precio_unitario);
      const subtotalBase = precioBase * d.cantidad;
      const descMonto = parseFloat(d.descuento_monto || 0);
      const subtotalFinal = subtotalBase - descMonto;
      const hasDesc = d.descuento_porcentaje || d.descuento_monto;

      const descLabel = hasDesc
        ? `<span style="font-size:11px;color:#E63946;">${d.descuento_porcentaje ? d.descuento_porcentaje + '%' : ''}${d.motivo_descuento ? ' · ' + d.motivo_descuento : ''}</span>`
        : '';

      return `
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f3f4f6;">
          <div style="flex:1;min-width:0;">
            <div style="font-weight:600;font-size:13px;">${nombre} ${descLabel}</div>
            <div style="font-size:12px;color:#6b7280;">${d.cantidad} × C$${precioBase.toFixed(2)}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;">
            ${hasDesc ? `<span style="font-size:11px;color:#9ca3af;text-decoration:line-through;">C$${subtotalBase.toFixed(2)}</span>` : ''}
            <span style="font-weight:600;font-size:14px;color:${hasDesc ? 'var(--rojo-cangrejo)' : 'var(--azul-marino)'};">C$${subtotalFinal.toFixed(2)}</span>
          </div>
        </div>`;
    }).join('');
  }

  const subtotal = parseFloat(orden.subtotal || orden.total || 0);
  const descuento = parseFloat(orden.descuento_total || 0);
  const total = parseFloat(orden.total || 0);

  document.getElementById('oc-subtotal').textContent = `C$${subtotal.toFixed(2)}`;

  const descRow = document.getElementById('oc-descuento-row');
  if (descuento > 0) {
    descRow.style.display = '';
    document.getElementById('oc-descuento').textContent = `-C$${descuento.toFixed(2)}`;
  } else {
    descRow.style.display = 'none';
  }

  document.getElementById('oc-total').textContent = `C$${total.toFixed(2)}`;

  // Populate discount target select with items
  const targetSelect = document.getElementById('oc-discount-target');
  if (targetSelect) {
    let opts = '<option value="global">🌐 Toda la orden</option>';
    if (detalles.length) {
      detalles.forEach(d => {
        const producto = state.menuItems.find(mi => mi.id === d.producto_id);
        const nombre = producto ? producto.nombre : `#${d.producto_id}`;
        opts += `<option value="item-${d.id}">📦 ${nombre}</option>`;
      });
    }
    targetSelect.innerHTML = opts;
  }
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
  const fecha = now.toLocaleDateString('es-NI');
  const hora = now.toLocaleTimeString('es-NI', { hour: '2-digit', minute: '2-digit' });
  const total = parseFloat(orden.total || 0);

  let lines = [];
  lines.push('════════════════════════════════');
  lines.push('    🍽️  SAZÓN CARIBEÑO');
  lines.push('════════════════════════════════');
  lines.push(`Fecha: ${fecha}  Hora: ${hora}`);
  const mesaTexto = mesa ? `Mesa: ${mesa.numero}` : (orden.nombre_cliente ? `Cliente: ${orden.nombre_cliente}` : 'Para Llevar');
  lines.push(`${mesaTexto}   Orden: #${orden.id}`);
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
  openMetodoPago(oc.orden, 'mesa');
}

/* =========================================================================
   Apodo de Mesa — asignar/limpiar apodo temporal de una mesa ocupada
   ========================================================================= */
async function guardarApodo() {
  const oc = state.currentOcupada;
  if (!oc) return;

  const input = document.getElementById('oc-apodo-input');
  const valor = (input?.value || '').trim();

  try {
    const mesa = await api(`/salon/mesas/${oc.mesaId}/apodo`, {
      method: 'PATCH',
      body: JSON.stringify({ apodo: valor }),
    });

    const local = state.tables.find(t => t.id === oc.mesaId);
    if (local) local.apodo = mesa.apodo || null;

    document.getElementById('oc-mesa-numero').textContent = mesa.apodo ? `${mesa.numero} · «${mesa.apodo}»` : mesa.numero;
    renderTables(state.tables);
    enriquecerMesasOcupadas();
    showToast(mesa.apodo ? `Apodo guardado: ${mesa.apodo}` : 'Apodo eliminado', 'success');
  } catch (err) {
    showToast(err.message || 'Error al guardar el apodo', 'error');
  }
}

/* =========================================================================
   Discount Application — Occupied Table
   ========================================================================= */
async function aplicarDescuentoOrder() {
  const oc = state.currentOcupada;
  if (!oc || !oc.orden) return showToast('No hay orden activa', 'error');

  const tipo = document.getElementById('oc-discount-type')?.value;
  const valor = parseFloat(document.getElementById('oc-discount-value')?.value);
  const target = document.getElementById('oc-discount-target')?.value;
  const motivo = document.getElementById('oc-discount-motivo')?.value.trim() || null;

  if (!valor || valor <= 0) return showToast('Ingresa un valor de descuento válido', 'warning');

  const ordenId = oc.orden.id;

  try {
    let orden;
    if (target === 'global') {
      orden = await api(`/ordenes/${ordenId}/descuento-global`, {
        method: 'POST',
        body: JSON.stringify({ tipo, valor, motivo }),
      });
    } else if (target && target.startsWith('item-')) {
      const detalleId = parseInt(target.replace('item-', ''));
      orden = await api(`/ordenes/${ordenId}/descuento-item`, {
        method: 'POST',
        body: JSON.stringify({ detalle_id: detalleId, tipo, valor, motivo }),
      });
    } else {
      return showToast('Selecciona un objetivo para el descuento', 'warning');
    }

    oc.orden = orden;
    renderOcItems(orden);
    document.getElementById('oc-discount-value').value = '';
    document.getElementById('oc-discount-motivo').value = '';
    showToast('Descuento aplicado correctamente', 'success');
  } catch { /* api() handles error */ }
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
    container.innerHTML = '<p class="ch-empty">Sin órdenes pagadas en la caja actual todavía.</p>';
    return;
  }

  const sorted = [...ordenes].sort((a, b) => b.id - a.id);
  container.innerHTML = `
    <table class="cierre-hist-table">
      <thead>
        <tr>
          <th>N° Orden</th>
          <th>Mesa / Modalidad</th>
          <th>Fecha</th>
          <th class="right">Total</th>
          <th>Estado</th>
        </tr>
      </thead>
      <tbody>
        ${sorted.map(o => {
          const mesa = o.mesa_id ? state.tables.find(t => t.id === o.mesa_id) : null;
          const mesaLabel = mesa ? `Mesa ${mesa.numero}` : (o.nombre_cliente || 'Para Llevar');
          const modalidad = mesa ? 'Salón' : 'Para Llevar';
          const desc = parseFloat(o.descuento_total || 0);
          const fec = String(o.fecha_creacion || '').replace('T', ' ').slice(0, 16);
          return `
            <tr>
              <td class="order-id">#${o.id}</td>
              <td>
                <span class="td-main">${mesaLabel}</span>
                <span class="td-sub">${modalidad}</span>
              </td>
              <td>
                <span class="td-main">${fec.slice(11, 16)}</span>
                <span class="td-sub">${fec.slice(0, 10)}</span>
              </td>
              <td class="right">
                <span class="td-total">C$${parseFloat(o.total).toFixed(2)}</span>
                ${desc > 0 ? `<span class="td-desc">−C$${desc.toFixed(2)} desc</span>` : ''}
              </td>
              <td>
                <span class="cierre-estado-badge ${o.estado === 'PAGADA' ? 'is-pagada' : 'is-otro'}">${o.estado}</span>
              </td>
            </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

function clearHistorialOrdenesDia() {
  const container = document.getElementById('historial-ordenes-list');
  if (container) container.innerHTML = '<p class="ch-empty">Historial limpiado tras el cierre de caja.</p>';
}

/* =========================================================================
   Venta Retroactiva — Modal + CRUD
   ========================================================================= */
let vrItems = [];

function openVentaRetroactivaModal() {
  const fechaInput = document.getElementById('vr-fecha');
  if (fechaInput) {
    const today = new Date();
    fechaInput.value = today.toISOString().slice(0, 10);
  }
  vrItems = [{ producto_id: '', cantidad: 1 }];
  renderVRItems();
  loadVRMesaSelect();
  document.getElementById('modal-venta-retroactiva')?.classList.add('show');
}

function closeVentaRetroactivaModal() {
  document.getElementById('modal-venta-retroactiva')?.classList.remove('show');
}

async function loadVRMesaSelect() {
  const select = document.getElementById('vr-mesa');
  if (!select) return;
  try {
    const zonas = await api('/salon/zonas');
    let html = '<option value="">Venta directa / Para llevar</option>';
    for (const z of zonas) {
      const mesas = z.mesas || [];
      if (!mesas.length) continue;
      html += `<optgroup label="${z.nombre}">`;
      for (const m of mesas) {
        html += `<option value="${m.id}">Mesa ${m.numero}</option>`;
      }
      html += '</optgroup>';
    }
    select.innerHTML = html;
  } catch { /* keep default option */ }
}

async function loadVRMenuItems() {
  if (!state.menuItems?.length) {
    try {
      state.menuItems = await api('/menu/items');
    } catch { return []; }
  }
  return state.menuItems.filter(m => m.disponible !== false);
}

async function renderVRItems() {
  const container = document.getElementById('vr-items-list');
  if (!container) return;
  const items = await loadVRMenuItems();
  const optionsHtml = items.map(m =>
    `<option value="${m.id}">${m.nombre} — C$${parseFloat(m.precio).toFixed(2)}</option>`
  ).join('');

  container.innerHTML = vrItems.map((item, i) => `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;">
      <select class="form-input vr-item-producto" data-idx="${i}" style="flex:2;">
        <option value="">Seleccionar plato…</option>
        ${optionsHtml}
      </select>
      <input type="number" class="form-input vr-item-cantidad" data-idx="${i}" value="${item.cantidad}" min="1" style="width:60px;flex:0;">
      <button type="button" class="btn" onclick="removeVRItem(${i})" style="color:var(--rojo-cangrejo);background:none;border:none;font-size:18px;padding:0 6px;" title="Eliminar">✕</button>
    </div>
  `).join('');

  container.querySelectorAll('.vr-item-producto').forEach(sel => {
    sel.value = vrItems[sel.dataset.idx]?.producto_id || '';
    sel.addEventListener('change', () => {
      vrItems[sel.dataset.idx].producto_id = sel.value;
      updateVRTotal();
    });
  });
  container.querySelectorAll('.vr-item-cantidad').forEach(inp => {
    inp.addEventListener('input', () => {
      vrItems[inp.dataset.idx].cantidad = parseInt(inp.value) || 1;
      updateVRTotal();
    });
  });
  updateVRTotal();
}

function addVRItem() {
  vrItems.push({ producto_id: '', cantidad: 1 });
  renderVRItems();
}

function removeVRItem(idx) {
  vrItems.splice(idx, 1);
  if (!vrItems.length) vrItems.push({ producto_id: '', cantidad: 1 });
  renderVRItems();
}

function updateVRTotal() {
  let total = 0;
  const items = state.menuItems || [];
  for (const item of vrItems) {
    const prod = items.find(p => String(p.id) === String(item.producto_id));
    if (prod) total += parseFloat(prod.precio) * item.cantidad;
  }
  const el = document.getElementById('vr-total-preview');
  if (el) el.textContent = `Total: C$${total.toFixed(2)}`;
}

async function guardarVentaRetroactiva() {
  const fecha = document.getElementById('vr-fecha')?.value;
  const mesaId = document.getElementById('vr-mesa')?.value;

  if (!fecha) return showToast('Selecciona una fecha', 'warning');

  const detalles = vrItems
    .filter(item => item.producto_id)
    .map(item => ({
      producto_id: parseInt(item.producto_id),
      cantidad: item.cantidad,
    }));

  if (!detalles.length) return showToast('Agrega al menos un plato', 'warning');

  const body = { fecha, detalles };
  if (mesaId) body.mesa_id = parseInt(mesaId);

  const btn = document.getElementById('save-venta-retroactiva');
  btn.disabled = true;
  btn.textContent = 'Registrando…';
  try {
    await api('/ordenes/retroactiva', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    closeVentaRetroactivaModal();
    showToast('Venta pasada registrada con éxito', 'success');
    loadCierreReportes('diario');
    loadHistorialOrdenesDia();
  } catch { /* handled by api() */ }
  finally {
    btn.disabled = false;
    btn.textContent = 'Registrar Venta';
  }
}

/* =========================================================================
   Ejecutar Cierre de Caja
   ========================================================================= */
async function ejecutarCierreCaja() {
  if (!confirm('¿Estás seguro de cerrar la caja? Se archivarán todas las órdenes pagadas y gastos de la caja actual.')) return;

  const btn = document.getElementById('btn-cerrar-caja');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">progress_activity</span> Cerrando…'; }

  try {
    const data = await api('/caja/cierre', { method: 'POST' });
    showToast(`Caja cerrada: ${data.total_ordenes} órdenes archivadas, C$${parseFloat(data.total_ventas).toFixed(2)} en ventas`, 'success');
    clearHistorialOrdenesDia();
    loadCierreReportes('diario');
  } catch (err) {
    console.error('Error al cerrar la caja:', err);
    showToast(`Error al cerrar la caja: ${err.message}`, 'error', 5000);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">lock</span> Cerrar Caja'; }
  }
}

/* =========================================================================
   Clock
   ========================================================================= */
function updateClock() {
  const now = new Date();
  const time = now.toLocaleTimeString('es-NI', { hour: '2-digit', minute: '2-digit' });
  const dateStr = now.toLocaleDateString('es-NI', { weekday: 'long', day: 'numeric', month: 'long' });
  const el1 = document.getElementById('comandero-clock');
  const el2 = document.getElementById('salon-clock');
  const el3 = document.getElementById('salon-clock-m');
  const el4 = document.getElementById('salon-date');
  const el5 = document.getElementById('attendance-clock');
  const el6 = document.getElementById('kds-clock-m');
  const el7 = document.getElementById('comandero-date');
  const el8 = document.getElementById('carta-clock-m');
  const el9 = document.getElementById('menu-mgmt-clock-m');
  const el10 = document.getElementById('inventory-clock-m');
  const el11 = document.getElementById('personal-clock-m');
  const el12 = document.getElementById('cuenta-clock-m');
  const el13 = document.getElementById('gastos-clock-m');
  const el14 = document.getElementById('desktop-clock');
  const el15 = document.getElementById('desktop-date');
  if (el1) el1.textContent = time;
  if (el2) el2.textContent = time;
  if (el3) el3.textContent = time;
  if (el4) el4.textContent = dateStr;
  if (el5) el5.textContent = time;
  if (el6) el6.textContent = time;
  if (el7) el7.textContent = dateStr;
  if (el8) el8.textContent = time;
  if (el9) el9.textContent = time;
  if (el10) el10.textContent = time;
  if (el11) el11.textContent = time;
  if (el12) el12.textContent = time;
  if (el13) el13.textContent = time;
  if (el14) el14.textContent = time;
  if (el15) el15.textContent = dateStr;
}

/* =========================================================================
   Event Listeners
   ========================================================================= */
document.addEventListener('DOMContentLoaded', () => {
  document.addEventListener('click', event => {
    const target = event.target instanceof Element
      ? event.target.closest('button[aria-label="Notificaciones"]')
      : null;
    if (target) alternarNotificaciones();
  });
  document.addEventListener('click', event => {
    const target = event.target instanceof Element
      ? event.target.closest('button[aria-label="Buscar"], button[aria-label="Buscar platillo"]')
      : null;
    if (!target) return;
    if (state.currentScreen !== 'menu-view') navigateTo('menu-view');
    setTimeout(() => document.getElementById('menu-search')?.focus(), 0);
  });
  document.getElementById('notifications-close')?.addEventListener('click', () => cerrarNotificaciones({ devolverFoco: true }));
  document.getElementById('notifications-refresh')?.addEventListener('click', () => {
    void cargarNotificaciones();
  });
  document.getElementById('notifications-panel')?.addEventListener('click', event => {
    const target = event.target instanceof Element ? event.target.closest('[data-notification-screen]') : null;
    if (!target) return;
    cerrarNotificaciones();
    navigateTo(target.dataset.notificationScreen);
  });
  document.addEventListener('click', event => {
    const panel = document.getElementById('notifications-panel');
    const target = event.target;
    if (panel && !panel.hidden && target instanceof Element
        && !panel.contains(target) && !target.closest('button[aria-label="Notificaciones"]')) {
      cerrarNotificaciones();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') cerrarNotificaciones({ devolverFoco: true });
  });

  document.getElementById('app-error-back')?.addEventListener('click', volverDePantallaError);

  window.addEventListener('error', event => {
    if (event instanceof ErrorEvent) mostrarPantallaError();
  });
  window.addEventListener('unhandledrejection', () => mostrarPantallaError());

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
      document.querySelectorAll('[data-cocina-tab]').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      cocinaTab = btn.dataset.cocinaTab;
      renderCocinaCards();
    });
  });

  document.getElementById('calendar-prev')?.addEventListener('click', () => {
    clearTimeout(state.calendarPressTimer);
    state.calendarMultiSelecting = false;
    state.calendarSelectedDays.clear();
    state.calendarMonth = new Date(state.calendarMonth.getFullYear(), state.calendarMonth.getMonth() - 1, 1);
    state.calendarSelectedDay = calendarDateKey(state.calendarMonth);
    loadCalendario();
  });
  document.getElementById('calendar-next')?.addEventListener('click', () => {
    clearTimeout(state.calendarPressTimer);
    state.calendarMultiSelecting = false;
    state.calendarSelectedDays.clear();
    state.calendarMonth = new Date(state.calendarMonth.getFullYear(), state.calendarMonth.getMonth() + 1, 1);
    state.calendarSelectedDay = calendarDateKey(state.calendarMonth);
    loadCalendario();
  });
  document.getElementById('calendar-today')?.addEventListener('click', () => {
    clearTimeout(state.calendarPressTimer);
    state.calendarMultiSelecting = false;
    state.calendarSelectedDays.clear();
    const today = new Date();
    state.calendarMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    state.calendarSelectedDay = calendarDateKey(today);
    loadCalendario();
  });
  document.getElementById('calendar-selection-clear')?.addEventListener('click', () => {
    state.calendarSelectedDays.clear();
    renderCalendario();
  });
  document.getElementById('calendar-selection-cancel')?.addEventListener('click', exitCalendarMultiSelect);
  document.getElementById('calendar-selection-create')?.addEventListener('click', () => {
    if (state.calendarSelectedDays.size < 2) return;
    openCalendarEventModal(null, null, [...state.calendarSelectedDays]);
  });
  document.getElementById('btn-calendar-add')?.addEventListener('click', () => openCalendarEventModal());
  document.getElementById('calendar-event-type')?.addEventListener('change', setCalendarEventTypeFields);
  document.getElementById('calendar-event-insumo')?.addEventListener('change', updateCalendarQuantityUnit);
  document.getElementById('calendar-event-form')?.addEventListener('submit', saveCalendarEvent);
  document.getElementById('close-calendar-event')?.addEventListener('click', closeCalendarEventModal);
  document.getElementById('cancel-calendar-event')?.addEventListener('click', closeCalendarEventModal);
  document.getElementById('delete-calendar-event')?.addEventListener('click', deleteCalendarEvent);
  document.getElementById('modal-calendar-event')?.addEventListener('click', event => {
    if (event.target.id === 'modal-calendar-event') closeCalendarEventModal();
  });
  document.getElementById('camera-form')?.addEventListener('submit', guardarCamara);
  document.getElementById('camera-cancel-edit')?.addEventListener('click', resetCameraForm);
  document.getElementById('camera-clip-modal')?.addEventListener('click', event => {
    if (event.target.id === 'camera-clip-modal') cerrarClipModal();
  });

  // KDS refresh
  document.getElementById('btn-refresh-cocina')?.addEventListener('click', loadCocinaOrdenes);

  // Logout
  document.getElementById('btn-logout')?.addEventListener('click', logout);

  // Attendance toggle (iniciar / finalizar)
  document.getElementById('btn-enable-attendance-notifications')?.addEventListener('click', activarAvisosTurno);
  document.getElementById('turno-select')?.addEventListener('change', (event) => {
    const turnoId = event.currentTarget.value;
    const key = `pos_turno_seleccionado_${state.user?.id}`;
    if (turnoId) localStorage.setItem(key, turnoId);
    else localStorage.removeItem(key);
    verificarAvisosTurno();
  });
  document.getElementById('btn-attendance-toggle')?.addEventListener('click', async () => {
    const toggle = document.getElementById('btn-attendance-toggle');
    if (state.currentAsistencia) {
      if (toggle) { toggle.disabled = true; toggle.innerHTML = '<span class="material-symbols-outlined text-sm">stop</span> ⏳ Finalizando…'; }
      try {
        await finalizarTurno();
      } catch { /* handled by finalizarTurno */ }
      finally {
        if (toggle) { toggle.disabled = false; renderAttendanceStatus(); }
      }
    } else {
      const select = document.getElementById('turno-select');
      const turnoId = parseInt(select?.value);
      if (!turnoId) return showToast('Selecciona un turno primero', 'warning');
      if (toggle) { toggle.disabled = true; toggle.innerHTML = '<span class="material-symbols-outlined text-sm">schedule</span> ⏳ Iniciando…'; }
      try {
        await iniciarTurno(turnoId);
      } catch { /* handled by iniciarTurno */ }
      finally {
        if (toggle) { toggle.disabled = false; renderAttendanceStatus(); }
      }
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

  // Venta retroactiva
  document.getElementById('btn-venta-retroactiva')?.addEventListener('click', openVentaRetroactivaModal);
  document.getElementById('close-venta-retroactiva')?.addEventListener('click', closeVentaRetroactivaModal);
  document.getElementById('cancel-venta-retroactiva')?.addEventListener('click', closeVentaRetroactivaModal);
  document.getElementById('vr-add-item')?.addEventListener('click', addVRItem);
  document.getElementById('venta-retroactiva-form')?.addEventListener('submit', (e) => { e.preventDefault(); guardarVentaRetroactiva(); });

  // Menu Management
  document.getElementById('btn-preparacion')?.addEventListener('click', async () => {
    await loadInsumos();
    openPreparacionModal();
  });
  document.getElementById('close-preparacion')?.addEventListener('click', closePreparacionModal);
  document.getElementById('cancel-preparacion')?.addEventListener('click', closePreparacionModal);
  document.getElementById('confirm-preparacion')?.addEventListener('click', submitPreparacion);
  document.getElementById('btn-add-prep-row')?.addEventListener('click', addPreparacionRow);
  document.getElementById('prep-lote-toggle')?.addEventListener('change', () => {
    const rows = document.querySelectorAll('#preparacion-rows .prep-row');
    rows.forEach(row => {
      const sel = row.querySelector('.prep-insumo');
      const prev = sel.value;
      const loteOnly = document.getElementById('prep-lote-toggle')?.checked;
      const insumos = state.insumos || [];
      let filtered = loteOnly ? insumos.filter(i => loteInsumoIds.includes(i.id)) : insumos;
      const sorted = [...filtered].sort((a, b) => {
        const aL = loteInsumoIds.includes(a.id), bL = loteInsumoIds.includes(b.id);
        if (aL && !bL) return -1; if (!aL && bL) return 1;
        return a.nombre.localeCompare(b.nombre);
      });
      const opts = sorted.map(i => {
        const badge = loteInsumoIds.includes(i.id) ? ' <span class="toggle-lote-badge">LOTE</span>' : '';
        return `<option value="${i.id}">${i.nombre} (Stock: ${i.cantidad_actual} ${i.unidad_medida})${badge}</option>`;
      }).join('');
      sel.innerHTML = `<option value="">Seleccionar…</option>${opts}`;
      if (sel.querySelector(`option[value="${prev}"]`)) sel.value = prev;
    });
  });

  document.getElementById('btn-nuevo-platillo')?.addEventListener('click', async () => {
    await loadCategories();
    populateCategorySelect();
    openNewDishModal();
  });
  document.getElementById('close-dish-modal')?.addEventListener('click', closeDishModal);
  document.getElementById('cancel-dish-modal')?.addEventListener('click', closeDishModal);
  document.getElementById('dish-form')?.addEventListener('submit', saveDish);
  document.getElementById('dish-image')?.addEventListener('change', previewDishImage);

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
  document.getElementById('btn-nuevo-insumo')?.addEventListener('click', openNewInsumoModal);
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

  // Unidades modal
  document.getElementById('btn-unidades')?.addEventListener('click', openUnidadesModal);
  document.getElementById('close-unidades-modal')?.addEventListener('click', closeUnidadesModal);
  document.getElementById('btn-create-unidad')?.addEventListener('click', openCreateUnidadForm);
  document.getElementById('cancel-unidad-form')?.addEventListener('click', openUnidadesModal);
  document.getElementById('save-unidad-form')?.addEventListener('click', saveUnidadFormCompleta);
  document.getElementById('unidad-form-derivada')?.addEventListener('change', toggleUnidadDerivada);
  document.getElementById('unidad-form-magnitud')?.addEventListener('change', () => {
    if (document.getElementById('unidad-form-derivada').checked) {
      populateUnidadBaseSelect(document.getElementById('unidad-form-magnitud').value, null);
    }
    updateConversionPreview();
  });
  document.getElementById('unidad-form-base')?.addEventListener('change', updateConversionPreview);
  ['unidad-form-nombre', 'unidad-form-abrev', 'unidad-form-factor'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', updateConversionPreview);
  });

  // Stock modal
  document.getElementById('close-stock-modal')?.addEventListener('click', closeStockModal);
  document.getElementById('cancel-stock-modal')?.addEventListener('click', closeStockModal);
  document.getElementById('stock-form')?.addEventListener('submit', saveStock);
  document.getElementById('stock-entrada-btn')?.addEventListener('click', () => setStockType('ENTRADA'));
  document.getElementById('stock-salida-btn')?.addEventListener('click', () => setStockType('SALIDA'));
  document.querySelectorAll('#stock-tabs .period-tab').forEach(b => {
    b.addEventListener('click', () => switchStockTab(b.dataset.stockTab));
  });
  document.getElementById('stock-details-form')?.addEventListener('submit', saveStockDetails);
  document.querySelectorAll('#modal-stock .stock-cancel-details').forEach(b => {
    b.addEventListener('click', closeStockModal);
  });
  document.getElementById('stock-cat-toggle')?.addEventListener('click', toggleStockCatPanel);
  document.getElementById('stock-cat-save')?.addEventListener('click', guardarStockCategoriaInsumo);
  document.getElementById('stock-cat-cancel')?.addEventListener('click', toggleStockCatPanel);
  document.getElementById('stock-unidad-toggle')?.addEventListener('click', toggleStockUnidadPanel);
  document.getElementById('stock-unidad-save')?.addEventListener('click', guardarStockUnidadMedida);
  document.getElementById('stock-unidad-cancel')?.addEventListener('click', toggleStockUnidadPanel);
  document.getElementById('stock-mov-unidad')?.addEventListener('change', updateStockConversionPreview);
  document.getElementById('stock-qty')?.addEventListener('input', updateStockConversionPreview);
  document.getElementById('stock-empaque-select')?.addEventListener('change', updateStockDetailsEmpaquePreview);
  document.getElementById('stock-empaque-factor')?.addEventListener('input', updateStockDetailsEmpaquePreview);
  document.getElementById('stock-unidad-select')?.addEventListener('change', updateStockDetailsEmpaquePreview);

  // Insumo modal — packaging
  document.getElementById('insumo-unit')?.addEventListener('change', populateInsumoEmpaqueSelect);
  document.getElementById('insumo-empaque-unit')?.addEventListener('change', updateInsumoEmpaquePreview);
  document.getElementById('insumo-empaque-factor')?.addEventListener('input', updateInsumoEmpaquePreview);

  // Order modal
  document.getElementById('close-order-modal')?.addEventListener('click', closeOrderModal);
  document.getElementById('cancel-order-modal')?.addEventListener('click', closeOrderModal);
  document.getElementById('confirm-order-modal')?.addEventListener('click', submitOrder);

  // Order modal search
  document.getElementById('order-modal-search')?.addEventListener('input', (e) => {
    filterOrderModalBySearch(e.target.value);
  });

  // Carta (browse) search
  const cartaSearchInput = document.getElementById('menu-search');
  const cartaClearBtn = document.getElementById('menu-search-clear');
  const syncCartaSearch = () => {
    if (cartaClearBtn) cartaClearBtn.classList.toggle('hidden', !cartaSearch);
  };
  cartaSearchInput?.addEventListener('input', (e) => {
    cartaSearch = e.target.value.trim();
    syncCartaSearch();
    applyCartaFilter();
  });
  cartaClearBtn?.addEventListener('click', () => {
    if (cartaSearchInput) cartaSearchInput.value = '';
    cartaSearch = '';
    syncCartaSearch();
    applyCartaFilter();
    cartaSearchInput?.focus();
  });

  // Gestionar Mesas modal
  document.getElementById('btn-gestion-mesas')?.addEventListener('click', openGestionMesas);
  document.getElementById('close-gestion-mesas')?.addEventListener('click', closeGestionMesas);
  document.getElementById('gestion-guardar-mesa')?.addEventListener('click', guardarMesa);

  // Gestión de Turnos modal
  document.getElementById('btn-turnos')?.addEventListener('click', openTurnosModal);
  document.getElementById('close-turnos-modal')?.addEventListener('click', () => document.getElementById('modal-turnos').classList.remove('show'));
  document.getElementById('turno-save-btn')?.addEventListener('click', saveTurno);
  document.getElementById('turno-entrada')?.addEventListener('input', calcularHoraSalida);
  document.getElementById('turno-horas')?.addEventListener('input', calcularHoraSalida);
  document.getElementById('turno-cancel-edit')?.addEventListener('click', () => {
    document.getElementById('turno-edit-id').value = '';
    document.getElementById('turno-form-title').textContent = 'Nuevo Turno';
    document.getElementById('turno-save-btn').textContent = 'Crear Turno';
    document.getElementById('turno-cancel-edit').style.display = 'none';
    document.getElementById('turno-nombre').value = '';
    document.getElementById('turno-entrada').value = '08:00';
    document.getElementById('turno-horas').value = '8';
    calcularHoraSalida();
  });

  // Habilitación Dinámica de Turno (vendedores)
  document.getElementById('btn-toggle-all-turnos')?.addEventListener('click', toggleTurnoMasivo);
  document.getElementById('personal-table-container')?.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn-toggle-turno');
    if (!btn) return;
    toggleTurnoUsuario(Number(btn.dataset.id), btn.dataset.enabled !== 'true');
  });

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
  document.getElementById('btn-registrar-adelanto')?.addEventListener('click', () => {
    if (nominaModalEmpleadoId) openRegistrarAdelantoModal(nominaModalEmpleadoId);
  });
  document.getElementById('close-adelanto-modal')?.addEventListener('click', closeRegistrarAdelantoModal);
  document.getElementById('cancel-adelanto-btn')?.addEventListener('click', closeRegistrarAdelantoModal);
  document.getElementById('adelanto-form')?.addEventListener('submit', guardarAdelanto);

  // Nuevo Empleado modal
  document.getElementById('btn-nuevo-empleado')?.addEventListener('click', async () => {
    await loadPuestos();
    populatePuestoSelect();
    openNuevoEmpleadoModal();
  });
  document.getElementById('close-nuevo-empleado')?.addEventListener('click', closeNuevoEmpleadoModal);
  document.getElementById('cancel-nuevo-empleado')?.addEventListener('click', closeNuevoEmpleadoModal);
  document.getElementById('nuevo-empleado-form')?.addEventListener('submit', saveNuevoEmpleado);
  document.getElementById('btn-toggle-puesto-panel')?.addEventListener('click', togglePuestoPanel);
  document.getElementById('btn-save-puesto')?.addEventListener('click', guardarPuesto);

  // Reset Password modal
  document.getElementById('close-reset-password')?.addEventListener('click', closeResetPasswordModal);
  document.getElementById('cancel-reset-password')?.addEventListener('click', closeResetPasswordModal);
  document.getElementById('confirm-reset-password')?.addEventListener('click', confirmResetPassword);

  // Dar de Baja Empleado modal
  document.getElementById('close-eliminar-empleado')?.addEventListener('click', closeEliminarEmpleadoModal);
  document.getElementById('cancel-eliminar-empleado')?.addEventListener('click', closeEliminarEmpleadoModal);
  document.getElementById('confirm-eliminar-empleado')?.addEventListener('click', confirmEliminarEmpleado);
  document.getElementById('baja-empleado-password')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); confirmEliminarEmpleado(); }
  });

  // Eliminar Usuario modal
  document.getElementById('close-eliminar-usuario')?.addEventListener('click', closeEliminarUsuarioModal);
  document.getElementById('cancel-eliminar-usuario')?.addEventListener('click', closeEliminarUsuarioModal);
  document.getElementById('confirm-eliminar-usuario')?.addEventListener('click', confirmEliminarUsuario);
  document.getElementById('eliminar-usuario-password')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); confirmEliminarUsuario(); }
  });

  // Asistencias modal
  document.getElementById('close-asistencias')?.addEventListener('click', closeAsistenciasModal);

  // Anular Asistencia modal
  document.getElementById('close-anular-asistencia')?.addEventListener('click', closeAnularAsistenciaModal);
  document.getElementById('cancel-anular-asistencia')?.addEventListener('click', closeAnularAsistenciaModal);
  document.getElementById('confirm-anular-asistencia')?.addEventListener('click', confirmAnularAsistencia);

  // Editar Horas Extras modal
  document.getElementById('close-edit-ot')?.addEventListener('click', closeEditOTModal);
  document.getElementById('cancel-edit-ot')?.addEventListener('click', closeEditOTModal);
  document.getElementById('confirm-edit-ot')?.addEventListener('click', confirmEditOT);

  document.getElementById('close-editar-horarios')?.addEventListener('click', closeEditarHorariosModal);
  document.getElementById('cancel-editar-horarios')?.addEventListener('click', closeEditarHorariosModal);
  document.getElementById('confirm-editar-horarios')?.addEventListener('click', confirmEditarHorarios);

  // Gastos modal
  document.getElementById('btn-nuevo-gasto')?.addEventListener('click', openGastosModal);
  document.getElementById('close-gasto-modal')?.addEventListener('click', closeGastosModal);
  document.getElementById('cancel-gasto-modal')?.addEventListener('click', closeGastosModal);
  document.getElementById('gasto-form')?.addEventListener('submit', (e) => { e.preventDefault(); guardarGasto(); });

  // Para Llevar
  document.getElementById('btn-para-llevar')?.addEventListener('click', openParaLlevarModal);

  // FAB Nueva comanda rápida (Salón)
  document.getElementById('btn-nueva-comanda')?.addEventListener('click', openParaLlevarModal);

  // Descuentos
  document.getElementById('btn-aplicar-descuento')?.addEventListener('click', aplicarDescuentoOrder);
  document.getElementById('oc-discount-value')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); aplicarDescuentoOrder(); }
  });

  // Detalle Mesa Ocupada modal
  document.getElementById('close-detalle-mesa-ocupada')?.addEventListener('click', closeDetalleMesaOcupada);
  document.getElementById('btn-agregar-pedido')?.addEventListener('click', agregarAlPedido);
  document.getElementById('btn-pre-cuenta')?.addEventListener('click', openPreCuenta);
  document.getElementById('btn-cerrar-cuenta')?.addEventListener('click', cerrarCuenta);
  document.getElementById('btn-forzar-librar')?.addEventListener('click', forzarLibrarMesa);

  // Método de pago
  document.getElementById('close-metodo-pago')?.addEventListener('click', cerrarMetodoPago);
  document.getElementById('cancel-metodo-pago')?.addEventListener('click', cerrarMetodoPago);
  document.getElementById('btn-pago-local')?.addEventListener('click', confirmarPagoLocal);
  document.getElementById('btn-pago-online')?.addEventListener('click', iniciarPagoOnline);
  document.getElementById('modal-metodo-pago')?.addEventListener('click', (event) => {
    if (event.target === event.currentTarget) cerrarMetodoPago();
  });

  // Apodo de mesa ocupada
  document.getElementById('btn-save-apodo')?.addEventListener('click', guardarApodo);
  document.getElementById('oc-apodo-input')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); guardarApodo(); }
  });

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

  // Sincronización al volver a la pestaña/foco (recupera pausas de móvil/desktop)
  const alVolverPestana = () => {
    if (!state.token || !state.user) return;
    verificarSesionTurno();
    enviarHeartbeat();
    syncAsistenciaActiva();
    verificarAvisosTurno();
  };
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) alVolverPestana();
  });
  window.addEventListener('focus', alVolverPestana);
  window.addEventListener('online', alVolverPestana);

  // Restore session
  if (state.token && state.user) {
    updateUserBadges();
    applyRoleRestrictions();
    showApp();
    showAttendancePanel();
    loadTurnos();
    navigateTo('salon');
    iniciarIntervalosSesion();
  } else {
    showLogin();
  }
});
