/* =========================================================================
 *  Sazón Caribeño — Carta Digital (frontend público)
 *  Consume la API pública /api/public (sin autenticación).
 *  Replica los 5 screens de Stitch: menú desktop, menú móvil,
 *  detalle desktop, detalle móvil y bienvenida.
 * ========================================================================= */

const API_BASE = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000/api/public'
  : `${location.origin}/api/public`;

/* Assets locales del proyecto (sin dependencias remotas ni Stitch) -------- */
const PLACEHOLDER_IMG = 'img/placeholder-dish.svg';
const IMG_HERO_DESKTOP = 'img/hero-desktop.jpg';
const IMG_HERO_MOBILE = 'img/hero-mobile.jpg';
const IMG_LOGO = 'img/logo.png';
const IMG_LOGO_SMALL = 'img/logo-small.png';

/* =========================================================================
   Estado
   ========================================================================= */
const state = {
  categories: [],
  items: [],
  activeCatId: null,
};

/* =========================================================================
   Utilidades
   ========================================================================= */
function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatPrice(value) {
  const num = Number.parseFloat(value);
  if (Number.isNaN(num)) return 'C$ 0';
  const decimals = (num % 1 === 0) ? 0 : 2;
  const text = new Intl.NumberFormat('es-NI', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: 2,
  }).format(num);
  return `C$ ${text}`;
}

function imgFor(item) {
  return (item && item.imagen_url) || PLACEHOLDER_IMG;
}

function itemById(id) {
  return state.items.find((i) => i.id === Number(id)) || null;
}

function categoryById(id) {
  return state.categories.find((c) => c.id === Number(id)) || null;
}

function itemsOfCategory(catId) {
  return state.items.filter((i) => i.categoria && i.categoria.id === catId);
}

async function api(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* =========================================================================
   Render: chips, nav, bento, secciones
   ========================================================================= */
function renderChips() {
  const all = `<button class="chip${state.activeCatId === null ? ' active' : ''}" data-cat="all">Todos</button>`;
  const cats = state.categories.map((c) => (
    `<button class="chip${state.activeCatId === c.id ? ' active' : ''}" data-cat="${c.id}">${esc(c.nombre)}</button>`
  )).join('');
  document.getElementById('chips').innerHTML = all + cats;
}

function renderNav() {
  const links = state.categories.slice(0, 5).map((c) => (
    `<li><a href="#cat-${c.id}" class="nav-link${state.activeCatId === c.id ? ' active' : ''}" data-cat="${c.id}">${esc(c.nombre)}</a></li>`
  )).join('');
  document.getElementById('nav-links').innerHTML = links;
}

function renderBento() {
  const wrap = document.getElementById('bento');
  if (!state.categories.length) {
    wrap.innerHTML = '';
    return;
  }

  const [first, ...rest] = state.categories;
  let html = '';

  html += `
    <a href="#chips-wrap" class="bento-tile bento-img" data-cat="${first.id}">
      <img src="${IMG_HERO_MOBILE}" alt="${esc(first.nombre)}" loading="lazy">
      <div class="bento-shade"></div>
      <h3 class="t-headline-md">${esc(first.nombre)}</h3>
    </a>`;

  const icons = rest.slice(0, 2);
  icons.forEach((c, i) => {
    const icon = i % 2 === 0 ? 'local_dining' : 'icecream';
    const cls = i % 2 === 0 ? 'bento-tile bento-icon bento-low' : 'bento-tile bento-icon bento-yellow';
    html += `
      <a href="#chips-wrap" class="${cls}" data-cat="${c.id}">
        <span class="material-symbols-outlined ms-48">${icon}</span>
        <span class="t-label">${esc(c.nombre)}</span>
      </a>`;
  });

  const wide = rest[2];
  if (wide) {
    html += `
      <a href="#chips-wrap" class="bento-tile bento-wide" data-cat="${wide.id}">
        <div>
          <h3 class="t-headline-md">${esc(wide.nombre)}</h3>
          <p class="t-body-md">${esc(wide.descripcion || 'Explora nuestra selección')}</p>
        </div>
        <span class="material-symbols-outlined">local_bar</span>
      </a>`;
  }

  wrap.innerHTML = html;
}

function cardHTML(item) {
  const disp = !!item.disponible;
  const title = esc(item.nombre);
  const desc = esc(item.descripcion || '');
  return `
    <article class="card${disp ? '' : ' card-off'}" data-id="${item.id}" role="button" tabindex="0" aria-label="${title}">
      <div class="card-media">
        <img src="${imgFor(item)}" alt="${title}" loading="lazy">
        <span class="badge badge-fresco"><span class="material-symbols-outlined ms-16 fill">eco</span>100% Fresco</span>
        <span class="badge badge-avail${disp ? '' : ' off'}">${disp ? 'Disponible' : 'Agotado'}</span>
        <div class="agotado-overlay"><span>Agotado hoy</span></div>
      </div>
      <div class="card-body">
        <div class="card-head">
          <h3 class="t-headline-md card-title">${title}</h3>
          <span class="t-price card-price${disp ? '' : ' muted'}">${formatPrice(item.precio)}</span>
        </div>
        <p class="t-body-md card-desc">${desc}</p>
        <div class="card-avail${disp ? '' : ' off'}"><span class="dot"></span>${disp ? 'Disponible' : 'Agotado'}</div>
      </div>
    </article>`;
}

function sectionHTML(category) {
  const its = itemsOfCategory(category.id);
  if (!its.length) return '';
  const subtitle = category.descripcion
    ? `<p class="t-body-lg section-subtitle">${esc(category.descripcion)}</p>`
    : '';
  return `
    <section class="menu-section" id="cat-${category.id}">
      <div class="section-head">
        <h2 class="t-headline-lg">${esc(category.nombre)}</h2>
        ${subtitle}
      </div>
      <div class="cards-grid">
        ${its.map(cardHTML).join('')}
      </div>
    </section>`;
}

function renderSections() {
  const wrap = document.getElementById('menu-sections');
  let html;
  if (!state.items.length && !state.categories.length) {
    html = `<div class="state-msg t-body-lg">Aún no hay platillos en la carta. Próximamente.</div>`;
  } else {
    const visible = state.activeCatId === null
      ? state.categories
      : state.categories.filter((c) => c.id === state.activeCatId);
    const sections = visible.map(sectionHTML).filter(Boolean).join('');
    html = sections || `<div class="state-msg t-body-lg">No hay platillos disponibles en esta categoría.</div>`;
  }
  wrap.innerHTML = html;
}

function renderAll() {
  renderChips();
  renderNav();
  renderBento();
  renderSections();
}

/* =========================================================================
   Modal de detalle
   ========================================================================= */
function openModal(item) {
  const disp = !!item.disponible;
  const catName = (item.categoria && item.categoria.nombre) || 'Categoría';
  const timerLabel = item.tiempo_preparacion
    ? `Preparación: ~${item.tiempo_preparacion} min`
    : `Categoría: ${catName}`;

  document.getElementById('modal-media').innerHTML = `
    <img src="${imgFor(item)}" alt="${esc(item.nombre)}">
    <div class="modal-img-badges">
      <span class="badge-img"><span class="material-symbols-outlined ms-18">local_fire_department</span>Popular</span>
      <span class="badge-img"><span class="material-symbols-outlined ms-18">set_meal</span>${esc(catName)}</span>
    </div>`;

  document.getElementById('modal-body').innerHTML = `
    <div class="modal-title-row">
      <h2 class="t-headline-lg">${esc(item.nombre)}</h2>
      <span class="price-badge">${formatPrice(item.precio)}</span>
    </div>
    <div class="modal-meta">
      <div class="meta-pill${disp ? '' : ' meta-off'}">
        <span class="material-symbols-outlined ms-18 fill">check_circle</span>
        <span class="txt">${disp ? 'Disponible' : 'Agotado'}</span>
      </div>
      <div class="meta-pill">
        <span class="material-symbols-outlined ms-18">timer</span>
        <span>${esc(timerLabel)}</span>
      </div>
    </div>
    <div class="modal-desc">
      <h4 class="t-label desc-label">Descripción</h4>
      <p>${esc(item.descripcion || 'Sin descripción disponible.')}</p>
    </div>
    <div class="modal-flags">
      <div class="flag">
        <div class="flag-icon tertiary"><span class="material-symbols-outlined">set_meal</span></div>
        <span class="flag-txt-tertiary">${esc(catName)}</span>
      </div>
      <div class="flag">
        <div class="flag-icon primary"><span class="material-symbols-outlined">eco</span></div>
        <span class="flag-txt-primary">100% Fresco</span>
      </div>
    </div>`;

  document.getElementById('modal-overlay').classList.add('open');
  document.body.classList.add('modal-open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.classList.remove('modal-open');
}

/* =========================================================================
   Selección de categoría
   ========================================================================= */
function selectCategory(catId) {
  state.activeCatId = catId;
  renderAll();
  const wrap = document.getElementById('menu-sections');
  if (wrap.firstElementChild && wrap.firstElementChild.id) {
    wrap.firstElementChild.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* =========================================================================
   Bottom nav
   ========================================================================= */
function onBottomNav(e) {
  const btn = e.target.closest('.bn-btn');
  if (!btn) return;
  document.querySelectorAll('.bn-btn').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  const nav = btn.dataset.nav;
  if (nav === 'menu') {
    state.activeCatId = null;
    renderAll();
    scrollToTop();
  } else if (nav === 'favoritos') {
    if (state.categories.length) {
      selectCategory(state.categories[0].id);
    }
  } else if (nav === 'postres') {
    const postre = state.categories.find((c) => /postre|dulce/i.test(c.nombre));
    if (postre) selectCategory(postre.id);
    else scrollToTop();
  } else if (nav === 'info') {
    document.querySelector('.footer').scrollIntoView({ behavior: 'smooth' });
  }
}

/* =========================================================================
   Eventos
   ========================================================================= */
function bindEvents() {
  document.getElementById('chips').addEventListener('click', (e) => {
    const chip = e.target.closest('.chip');
    if (!chip) return;
    const value = chip.dataset.cat;
    selectCategory(value === 'all' ? null : Number(value));
  });

  document.getElementById('nav-links').addEventListener('click', (e) => {
    const link = e.target.closest('.nav-link');
    if (!link) return;
    e.preventDefault();
    selectCategory(Number(link.dataset.cat));
  });

  document.getElementById('bento').addEventListener('click', (e) => {
    const tile = e.target.closest('[data-cat]');
    if (!tile) return;
    e.preventDefault();
    selectCategory(Number(tile.dataset.cat));
  });

  document.getElementById('menu-sections').addEventListener('click', (e) => {
    const card = e.target.closest('.card');
    if (!card) return;
    const item = itemById(card.dataset.id);
    if (item) openModal(item);
  });

  document.getElementById('menu-sections').addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const card = e.target.closest('.card');
    if (!card) return;
    e.preventDefault();
    const item = itemById(card.dataset.id);
    if (item) openModal(item);
  });

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('btn-close-detail').addEventListener('click', closeModal);

  document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'modal-overlay') closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  document.querySelector('.bottomnav').addEventListener('click', onBottomNav);

  document.getElementById('btn-menu').addEventListener('click', scrollToTop);
  document.getElementById('btn-search').addEventListener('click', () => {
    document.getElementById('chips-wrap').scrollIntoView({ behavior: 'smooth' });
  });
  document.getElementById('brand-top').addEventListener('click', (e) => {
    e.preventDefault();
    scrollToTop();
  });
}

/* =========================================================================
   Carga de datos
   ========================================================================= */
async function loadCarta() {
  const wrap = document.getElementById('menu-sections');
  try {
    const [categories, items] = await Promise.all([api('/categories'), api('/menu')]);
    state.categories = categories;
    state.items = items;
    renderAll();
    bindEvents();
  } catch (err) {
    console.error('Error cargando la carta:', err);
    wrap.innerHTML = `
      <div class="state-msg t-body-lg">
        No pudimos cargar la carta en este momento.
        <br>
        <button id="btn-retry">Reintentar</button>
      </div>`;
    document.getElementById('btn-retry').addEventListener('click', loadCarta);
  }
}

/* =========================================================================
   Init
   ========================================================================= */
function init() {
  document.getElementById('hero-desktop-bg').style.backgroundImage = `url('${IMG_HERO_DESKTOP}')`;
  document.getElementById('welcome-hero-bg').style.backgroundImage = `url('${IMG_HERO_MOBILE}')`;
  document.getElementById('hero-logo').src = IMG_LOGO;
  document.getElementById('footer-logo').src = IMG_LOGO_SMALL;
  bindEvents();
  loadCarta();
}

document.addEventListener('DOMContentLoaded', init);
