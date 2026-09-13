# 🍽️ Documentación Completa de Funciones Frontend — Sazón Caribeño POS

> **Propósito:** Documento de referencia para trabajar las vistas por separado.
> Define: estructura del shell, pantallas (screens), modales y las **funciones JS** con el **HTML que cada una renderiza y consume** (IDs, clases, `data-*`, endpoints).
> *Documento vivo — marcado para trabajo independiente.*

---

## Índice
1. [Arquitectura del Frontend](#1-arquitectura-del-frontend)
2. [Shell de la Aplicación (layout base)](#2-shell-de-la-aplicación-layout-base)
3. [Pantallas (Screens) — Requisitos HTML](#3-pantallas-screens--requisitos-html)
   - [3.1 Login](#31-login--screen-login)
   - [3.2 Salón / Mapa de Mesas](#32-salón--mapa-de-mesas--screen-salon)
   - [3.3 Comandas / Panel de Cocina (KDS)](#33-comandas--panel-de-cocina-kds--screen-comandero)
   - [3.4 Carta (POS)](#34-carta-pos--screen-menu-view)
   - [3.5 Gestión de Menú](#35-gestión-de-menú--screen-menu-mgmt)
   - [3.6 Almacén Digital / Inventario](#36-almacén-digital--inventario--screen-inventory)
   - [3.7 Personal y Nóminas](#37-personal-y-nóminas--screen-personal)
   - [3.8 Cierre de Caja](#38-cierre-de-caja--screen-cuenta)
   - [3.9 Gestión de Gastos](#39-gestión-de-gastos--screen-gastos)
4. [Modales (Modal) — Requisitos HTML](#4-modales-modal--requisitos-html)
5. [Referencia de Funciones JS](#5-referencia-de-funciones-js)
6. [Tokens de Diseño (CSS)](#6-tokens-de-diseño-css)
7. [Convenciones y Notas Críticas](#7-convenciones-y-notas-críticas)

---

## 1. Arquitectura del Frontend

- **Vanilla JS SPA**, sin frameworks ni build step. Un solo archivo `js/app.js`.
- Sirve FastAPI desde `app/Templates/` (INDEX: `index.html`, CSS: `css/style.css`, JS: `js/app.js`).
- **`API_BASE`** auto-detecta: local (`localhost`/`127.0.0.1`) → `http://127.0.0.1:8000/api/v1`, remoto → `${location.origin}/api/v1`.
- **Token/sesión** en `localStorage`: `pos_token` (JWT) y `pos_user` (JSON con rol).
- **Cache-bust**: los `<link>`/`<script>` usan query string `?v=X`; se incrementa en cada cambio de CSS/JS.
- **Navegación**: `.screen` se muestra/oculta con clase `.active` (ver `navigateTo`).
- **Tailwind** (CDN) + **Material Symbols** (fuente de iconos) ya cargados en `<head>`; `tailwind.config` define tokens Material (`primary`, `surface-container`, etc.).

### Estructura de carpetas del frontend
```
app/Templates/
├── index.html            # Shell + las 9 pantallas + todos los modales + bottom-nav
├── css/style.css         # CSS custom (tokens, componentes, responsive)
├── js/app.js             # Toda la lógica JS (SPA)
└── carta/                # (Carta Digital pública — separada del POS)
```

---

## 2. Shell de la Aplicación (layout base)

Aplica a **todas las pantallas** (excepto Login). Contiene sidebar, main content y bottom-nav móvil.

### 2.1 Sidebar (desktop ≥1024px)
- `<aside id="sidebar">` flotante fijo izquierda, 260px, fondo navy `#003366`.
- **Logo de marca** al tope.
- `<nav class="sidebar-nav">` con `<a class="nav-item" data-screen="...">` (uno por pantalla), ícono + label, activo con borde izquierdo turquesa.
- **Panel de asistencia** (`#attendance-panel`): botón check-in, título turno, página de inicio (entrada/salida), reloj.
- **Tarjeta de usuario** abajo (`#user-card`): avatar iniciales, nombre, rol, botón salir.

### 2.2 Main content
- `<main class="main-content">` con `margin-left: 260px` (desktop).
- Cada pantalla es `<section class="screen" id="screen-...">` (ver sección 3).

### 2.3 Bottom Nav (móvil <768px)
- `<nav class="bottom-nav" id="bottom-nav">` fijo abajo, 5 ítems:
```
Salón (data-screen="salon") | Comandas (comandero) | Carta (menu-view) | Caja (cuenta) | Más (id="bottom-nav-more")
```
- Ícono activo en píldora navy `#0D233A` con ícono blanco (Material Symbols).

### 2.4 Botones reutilizables (clases)
| Clase | Uso |
|---|---|
| `.btn-primary` | Acción primaria, navy sólido |
| `.btn-turquoise` | Acción secundaria (Para Llevar, confirmar) |
| `.btn-secondary` | Outline |
| `.btn-danger` / `.btn-rojo` | Destructiva (Cerrar Caja, Eliminar) |
| `.btn-sm` | Pequeño en tarjetas/tablas |
| `.admin-only` | Visible solo Admin/Gerente (RBAC vía `body:not(...)`) |
| `.nav-locked` | Ítem de nav restringido |

---

## 3. Pantallas (Screens) — Requisitos HTML

Cada pantalla es una `<section class="screen" id="screen-...">`. Al renderizar dinámicamente, los contenedores usan los IDs indicados.

### 3.1 Login — `#screen-login`
**Estructura:**
```html
<section id="screen-login" class="screen active">
  <div class="login-card">
    <!-- logo -->
    <h1>Sazón Caribeño</h1>
    <p> Sistema de Gestión Restaurante </p>
    <input id="login-username" placeholder="Usuario">
    <input id="login-password" type="password" placeholder="Contraseña">
    <button id="login-btn">Iniciar Sesión</button>
    <small>v1.0.0 — Caribe</small>
  </div>
</section>
```
**Funciones:** `showLogin()`, `showApp()`, `login(username, password)`.
**Nota:** Es la única pantalla que no necesita sidebar/main-content.

### 3.2 Salón / Mapa de Mesas — `#screen-salon`
**Header** (`.screen-header`):
- Título `Mapa de Mesas` (+ subtítulo).
- Reloj: `#salon-clock` (hora) y `#salon-date` (fecha).
- Botones: `#btn-para-llevar` (turquesa, `onclick="abrirOrdenParaLlevar()"`), `#btn-gestion-mesas` (secondary, `.admin-only`, abre gestión de mesas).
- **Topbar móvil** `.mobile-topbar` (logo + "EN LÍNEA" + campana/lupa) y título con reloj `#salon-clock-m`.

**Cuerpo:**
```html
<div class="screen-body">
  <div class="chips-row"> <!-- filtros de estado -->
    <button class="chip active" data-filter="all">Todas</button>
    <button class="chip" data-filter="LIBRE">🟢 Libres</button>
    <button class="chip" data-filter="OCUPADA">🔴 Ocupadas</button>
    <button class="chip" data-filter="RESERVADA">🟡 Reservadas</button>
  </div>
  <div class="chips-row" id="zona-filters"> <!-- filtros de zona dinámicos -->
    <button class="chip active" data-zona="all">🗺️ Todas las Zonas</button>
  </div>
  <main id="table-grid" class="table-grid"></main>
</div>
```

**Render dinámico:** `renderTables(mesas)` inyecta en `#table-grid`. Tarjetas `div.table-card[data-mesa-id][data-estado][data-zona-id][role="button"][tabindex]`. Usa utilidades Tailwind (config tokens Material). Botones: `openTable(id)`, `addItemToTable(id)`, `showTableDetails(id)`.

**Eventos / filtros:** `loadTables()` → `applyTableFilters()` filtra estado + zona; `renderZonasFilters(zonas)` puebla `#zona-filters`.

**Endpoints:** `GET /salon/mapa` (zonas con mesas + `mesero_nombre`, `minutos_transcurridos`, `total_acumulado`), `GET /salon/zonas`.

### 3.3 Comandas / Panel de Cocina (KDS) — `#screen-comandero`
**Header:** Título `Panel de Cocina`, reloj `#comandero-clock`/`#comandero-date`, botón refrescar `#btn-refresh-cocina`.

**Cuerpo:**
```html
<div class="screen-body">
  <div class="kds-tabs">
    <button class="kds-tab active" data-cocina-tab="cocina">En Cocina</button>
    <button class="kds-tab" data-cocina-tab="lista">Listas para Servir</button>
    <button class="kds-tab" data-cocina-tab="historial">Historial</button>
  </div>
  <div id="cocina-grid" class="cocina-grid"></div>
</div>
```

**Render dinámico:** `loadCocinaOrdenes()` → `renderCocinaCards()` inyecta en `#cocina-grid` tarjetas `.kc-card` (zona, mesa, mesero, tiempo con urgencia por color, lista de items, botones de estado). Filtros por tab vía `data-cocina-tab`.

**Eventos:** `cambiarEstadoKDS(ordenId, nuevoEstado)` (`PATCH /ordenes/{id}/estado`), `cobrarOrden(ordenId)` (pago rápido → `PUT /ordenes/{id}/pagar`).

**Endpoints:** `GET /ordenes/`, `PATCH /ordenes/{id}/estado`, `PUT /ordenes/{id}/pagar`.

### 3.4 Carta (POS) — `#screen-menu-view`
**Header:** Título `Carta`.

**Cuerpo:**
```html
<div class="screen-body">
  <div class="category-tabs" id="carta-cat-filters"> <!-- chips categ Cheyenne -->
    <button class="category-tab active" data-cat="all">Todos</button>
  </div>
  <div id="menu-grid" class="menu-grid"></div>
</div>
```

**Render dinámico:** `loadMenuBrowse()` → `renderMenuItems(items, 'menu-grid')`, `renderCartaCatFilters(categorias)`, `applyCartaFilter()`.
**Nota:** Las tarjetas al hacer clic abren el modal de orden (agregar al cart).

**Endpoints:** `GET /menu/items`, `GET /menu/categorias`.

### 3.5 Gestión de Menú — `#screen-menu-mgmt`
**Header:** Título `Gestión de Menú`; botones `#btn-preparacion` ("🍳 Producción del Día", `.admin-only`) y `#btn-nuevo-platillo` ("+ Nuevo Platillo").

**Cuerpo:**
```html
<div class="screen-body">
  <div class="chips-row" id="menu-mgmt-cat-filters"> <!-- chips de categoría -->
    <button class="chip active" data-cat="all">Todas</button>
  </div>
  <div class="chips-row" id="menu-mgmt-status-filters">
    <button class="chip active" data-status="activos">Activos</button>
    <button class="chip" data-status="inactivos">Inactivos</button>
  </div>
  <div id="menu-mgmt-grid" class="data-card-grid"></div>
</div>
```

**Render dinámico:** `loadMenuManagement()` → `renderMenuMgmt(items)` inyecta tarjetas `.data-card` con thumbnail, título, precio, tiempo de preparación, badge categoría y acciones editar/eliminar (ver `renderMenuMgmtCatFilters`, `applyMenuMgmtFilter`, `bindMenuMgmtStatusFilters`).

**Endpoints:** `GET /menu/items?incluir_inactivos=true` (Admin/Gerente), `DELETE /menu/items/{id}`.

### 3.6 Almacén Digital / Inventario — `#screen-inventory`
**Header:** Título `Almacén Digital`; botones `#btn-unidades` ("⚖️ Unidades"), `#btn-nuevo-insumo` ("+ Nuevo Insumo").

**Cuerpo:**
```html
<div class="screen-body">
  <div class="chips-row" id="insumo-cat-filters"> <!-- chips de categoría insumo -->
    <button class="chip active" data-cat="all">Todas</button>
  </div>
  <div id="stock-alerts"> <!-- franja de alertas stock bajo -->
  </div>
  <div id="insumo-grid" class="data-card-grid"></div>
</div>
```

**Render dinámico:** `loadInventory()` → `renderInsumos(insumos)`, `renderAlerts(alerts)`, `renderInsumoCatFilters()`. Tarjeta de insumo: `onclick="openStockModal(<id>)"`, muestra stock, unidad, badge categoría, stock mínimo.

**Modales ligados:** `#modal-stock`, `#modal-insumo`, `#modal-unidades`.

**Endpoints:** `GET /inventario/insumos`, `GET /inventario/insumos/alertas`, `GET /inventario/categorias-insumo`, `GET /inventario/unidades-medida`.

### 3.7 Personal y Nóminas — `#screen-personal`
**Header:** Título `Personal y Nóminas`; botones `#btn-turnos` ("⏱️ Gestión de Turnos", `.admin-only`), `#btn-nuevo-empleado` ("➕ Agregar Empleado").

**Cuerpo:**
```html
<div class="screen-body">
  <div class="tabs"> <!-- Asistencia | Órdenes | ... --> </div>
  <div id="personal-table-container" class="table-container">
    <table class="employee-table" id="personal-table"> ... </table>
  </div>
</div>
```

**Render dinámico:** `loadPersonal()` → `renderPersonalTable(empleados, usuarios)`. Columnas: empleado (avatar+nombre), puesto, salario, teléfono, acciones (añadir nómina, asistencias, historial, reset password, baja).

**Endpoints:** `GET /personal/empleados`, `GET /personal/usuarios`, `GET /personal/puestos`.

### 3.8 Cierre de Caja — `#screen-cuenta`
**Header:** Título `Cierre de Caja`; tabs de periodo `.period-tab` (Hoy/Semana/Quincenal/Mes), botones `#btn-venta-retroactiva` (turquesa, `.admin-only`) y `#btn-cerrar-caja` (rojo).

**Cuerpo:**
```html
<div class="screen-body">
  <div class="period-tabs">
    <button class="period-tab active" data-periodo="diario">Hoy</button>
    <button class="period-tab" data-periodo="semanal">Semana</button>
    <button class="period-tab" data-periodo="quincenal">Quincenal</button>
    <button class="period-tab" data-periodo="mensual">Mes</button>
  </div>
  <div id="cierre-summary" class="cierre-summary-grid">
    <!-- 6 tarjetas .cierre-card --> (Ingresos, Gastos Nómina, Costo Insumos, Gastos Op., Descuentos, Utilidad)
  </div>
  <div id="cierre-charts" class="cierre-charts-row">
    <!-- Chart.js: pie costos + bar top 5 -->
  </div>
  <div id="historial-ordenes" class="table-container"> ... tabla ... </div>
</div>
```

**Render dinámico:** `loadCierreReportes(periodo)` → `renderCierreReportes(data)`.

**Endpoints:** `GET /reportes/cierre?periodo=`, `GET /caja/historial-diario`, `POST /caja/cierre`.

### 3.9 Gestión de Gastos — `#screen-gastos`
**Header:** Título `Gestión de Gastos Operativos`; botón `#btn-nuevo-gasto` ("+ Registrar Gasto").

**Cuerpo:**
```html
<div class="screen-body">
  <div class="chips-row" id="gasto-cat-filters"> <!-- chips de categoría gasto -->
    <button class="chip active" data-cat="all">Todos</button>
  </div>
  <table id="gastos-table">
    <thead><tr><th>ID</th><th>Fecha</th><th>Categoría</th><th>Descripción</th><th>Monto</th><th>Registrado Por</th></tr></thead>
    <tbody id="gastos-tbody"></tbody>
  </table>
</div>
```

**Render dinámico:** `loadGastos()` → `renderGastosTable()`, `renderGastoFilters()`, `applyGastoFilter(cat)`.

**Endpoints:** `GET /gastos/`, `POST /gastos/`.

---

## 4. Modales (Modal) — Requisitos HTML

Todos siguen el patrón `.modal-overlay` + `.modal-sheet` con `.modal-header` (título + botón cerrar `×`) y form/body. Se muestran agregando clase `.show` al `.modal-overlay`.

| Modal (ID) | Función principal | Contenido / Notas |
|---|---|---|
| `#modal-gestion-mesas` | `openGestionMesas/close` | Form mesa (número, capacidad, zona), lista de mesas, panel zonas `#zonas-panel` (CRUD), tabla `#gestion-mesas-tbody`, `#gestion-zonas-tbody` |
| `#modal-order` | `openOrderModal/menu/cart` | Categorías dinámicas `#order-cat-tabs`, menú `#order-menu-grid`, carrito `#order-cart`, totales `#order-subtotal/#order-total` o similar, botón confirmar `#order-confirm` |
| `#modal-detalle-mesa-ocupada` | `openDetalleMesaOcupada` | Detalle de orden `#oc-items`, fila total `#oc-total`, botones: `#btn-agregar-item`, `#btn-pre-cuenta`, `#btn-cobrar`, `#btn-forzar-librar`; sección descuentos `#oc-discount-section` |
| `#modal-pre-cuenta` | `openPreCuenta` | Resumen de cuenta + botón imprimir |
| `#modal-dish` | `openNewDishModal/openEditDish` | Form platillo: nombre, precio, categoría, tiempo preparación, descripción, imagen (`#dish-image`), receta dinámica (`.recipe-row`), botones lote; panel categorías `#cat-panel` |
| `#modal-preparacion` | `openPreparacionModal` | Producción por lote: filas insumo (`.prep-row`) + resumen |
| `#modal-insumo` | `openNewInsumoModal` | Form insumo: nombre, categoría, unidad, stock, costo, stock mínimo, empaque; paneles `#cat-insumo-panel`, `#unidad-panel` |
| `#modal-stock` | `openStockModal` | 2 tabs (Movimiento/Detalles): ajuste stock `#save-stock`, detalles `#save-stock-details`, subpaneles categoría/unidad |
| `#modal-unidades` | `openUnidadesModal` | Unidades de medida: tabla + form create/edit, `#unidad-derived` toggle, base select `#unidad-base`, factor `#unidad-factor` |
| `#modal-nomina` | `openNominaModal` | Cálculo/pago de nómina por empleado |
| `#modal-nuevo-empleado` | `openNuevoEmpleadoModal` | Form empleado: nombre, puesto, salario C$, teléfono, usuario/contraseña |
| `#modal-eliminar-empleado` | `openEliminarEmpleadoModal` | Confirmación + input contraseña (borrado lógico) |
| `#modal-asistencias` | `openAsistenciasModal` | Historial de asistencias del empleado + ifras + anular |
| `#modal-edit-ot` | `openEditOTModal` | Editar horas extras |
| `#modal-editar-horarios` | `openEditarHorariosModal` | Editar entrada/salida + motivo |
| `#modal-anular-asistencia` | `openAnularAsistenciaModal` | Confirmación anular asistencia + motivo |
| `#modal-turnos` | `openTurnosModal` | CRUD turnos (nombre, entrada, horas teóricas, salida calculada) |
| `#modal-registrar-adelanto` | `openRegistrarAdelantoModal` | Adelanto de salario |
| `#modal-registrar-gasto` | `openGastosModal` | Form gasto (fecha, categoría, monto, descripción) |
| `#modal-reset-password` | `openResetPasswordModal` | Reset contraseña usuario |
| `#modal-venta-retroactiva` | `openVentaRetroactivaModal` | Venta pasada: mesa + items dinámicos + total |
| `#modal-unit-equiv` | `openUnitEquivModal` | Confirmación de conversión al cambiar unidad base |

---

## 5. Referencia de Funciones JS

> Lista de todas las funciones del frontend agrupadas por módulo, con su rol y los elementos HTML que tocan. Usa esto como **contrato** al rediseñar: **no renombrar** funciones ni IDs, **no romper** los `data-*` ni endpoints.

### Autenticación y sesión
| Función | Rol |
|---|---|
| `login(username, password)` | POST `/auth/login`, guarda token, `showApp()`, `applyRoleRestrictions()` |
| `logout()` | Limpia token/usuario, `showLogin()` |
| `updateUserBadges()` | Actualiza nombre/rol en UI |
| `applyRoleRestrictions()` | Muestra/oculta `.admin-only` y `.nav-locked` por rol |
| `showLogin()` / `showApp()` | Alterna `#screen-login` vs app shell |

### Navegación y layout
| Función | Rol |
|---|---|
| `navigateTo(screenId)` | Activa la `.screen` e inicializa su contenido (usa `data-screen`) |
| `updateClock()` | Rellena relojes `#salon-clock/date`, `#comandero-clock/date`, `#salon-clock-m` |
| `showToast(message, type)` | Notificaciones globales |

### Asistencia / Turnos
| Función | Rol |
|---|---|
| `iniciarTurno(turnoId)` / `finalizarTurno()` | Check-in/out asistencia |
| `renderAttendanceStatus()` | Estado del panel de asistencia (alterna por `style.opacity/pointerEvents`) |
| `loadTurnos()`, `calcularHoraSalida()`, `openTurnosModal()`, `renderTurnosTable()`, `editTurno()`, `deleteTurno()`, `saveTurno()` | CRUD `#modal-turnos` |
| `enviarHeartbeat()` | Heartbeat periódico (solo Vendedor con turno activo) |

### Gastos
| Función | Rol |
|---|---|
| `loadGastos()`, `renderGastoFilters()`, `applyGastoFilter(cat)`, `renderGastosTable()` | Vista `#screen-gastos` |
| `openGastosModal()`, `closeGastosModal()`, `guardarGasto()` | Form `#modal-registrar-gasto` |

### Salón / Mesas / Zonas
| Función | Rol |
|---|---|
| `loadTables()`, `renderZonasFilters(zonas)`, `applyTableFilters()`, `renderTables(mesas)` | Mapa `#table-grid` |
| `openGestionMesas()`, `closeGestionMesas()`, `loadGestionMesas()`, `renderZonasList()`, `renderGestionMesasList()`, `editarMesa()`, `eliminarMesa()`, `guardarMesa()`, `toggleZonasPanel()`, `guardarZona()`, `eliminarZona()` | Gestión `#modal-gestion-mesas` |

### Comandas / KDS
| Función | Rol |
|---|---|
| `loadCocinaOrdenes()`, `renderCocinaCards()`, `getTiempoTranscurrido()`, `getMinutosTranscurrido()`, `cambiarEstadoKDS()`, `cobrarOrden()` | `#screen-comandero`, `#cocina-grid` |

### Orden / Comanda (modal)
| Función | Rol |
|---|---|
| `getCategoryEmoji()`, `renderMenuItems(items)`, `renderOrderModalCategories()`, `openOrderModal()`, `abrirOrdenParaLlevar()`, `openParaLlevarModal()`, `closeOrderModal()`, `loadOrderModalMenu()`, `renderOrderModalMenu()`, `changeOrderModalQty()`, `renderOrderModalCart()`, `deleteOrderItem()`, `aplicarDescuentoItemModal()`, `updateOrderModalTotals()`, `filterOrderModalByCategory()`, `filterOrderModalBySearch()`, `submitOrder()` | Modal `#modal-order` |

### Carta / Gestión Menú
| Función | Rol |
|---|---|
| `loadMenuBrowse()`, `loadCategories()` | Vista `#screen-menu-view` |
| `loadMenuManagement()`, `renderMenuMgmt()` | Vista `#screen-menu-mgmt` |
| `populateCategorySelect()`, `renderMenuMgmtCatFilters()`, `applyMenuMgmtFilter()`, `bindMenuMgmtStatusFilters()`, `deleteDish()` | Filtros/acciones menú |
| `renderCartaCatFilters()`, `applyCartaFilter()` | Filtros carta |
| `openNewDishModal()`, `openEditDish()`, `setDishToggle()`, `clearRecipeRows()`, `addRecipeRow()`, `buildRecetaPayload()`, `loadInsumosForRecipe()`, `closeDishModal()`, `saveDish()`, `uploadDishImage()`, `previewDishImage()`, `resetDishImage()` | Modal `#modal-dish` (recetas + imagen) |
| `toggleCatPanel()`, `renderCatList()`, `guardarCategoriaMenu()`, `eliminarCategoriaMenu()` | Panel categorías |

### Inventario
| Función | Rol |
|---|---|
| `loadInventory()`, `loadCategoriasInsumo()`, `loadUnidadesMedida()`, `renderInsumoCatFilters()`, `applyInsumoFilter()`, `loadInsumos()`, `loadInsumoAlerts()`, `renderAlerts()`, `renderInsumos()` | Vista `#screen-inventory` |
| `openStockModal()`, `switchStockTab()`, `setStockType()`, `updateStockConversionPreview()`, `closeStockModal()`, `saveStock()`, `saveStockDetails()`, `_submitStockDetails()`, `openUnitEquivModal()`, `closeUnitEquivModal()`, `cancelUnitEquiv()`, `confirmUnitEquiv()`, `updateStockDetailsEmpaquePreview()` | Modal `#modal-stock` |
| `openNewInsumoModal()`, `populateUnidadSelect()`, `populateCatInsumoSelect()`, `populateInsumoEmpaqueSelect()`, `updateInsumoEmpaquePreview()`, `closeInsumoModal()`, `saveInsumo()`, `toggleCatInsumoPanel()`, `renderCatInsumoList()`, `guardarCategoriaInsumo()`, `eliminarCategoriaInsumo()`, `toggleUnidadPanel()`, `renderUnidadList()`, `guardarUnidadMedida()`, `eliminarUnidadMedida()` | Modal `#modal-insumo` |
| `openUnidadesModal()`, `closeUnidadesModal()`, `renderUnidadesTable()`, `openCreateUnidadForm()`, `openEditUnidadForm()`, `populateUnidadBaseSelect()`, `toggleUnidadDerivada()`, `updateConversionPreview()`, `saveUnidadFormCompleta()`, `eliminarUnidadCompleta()` | Modal `#modal-unidades` |
| `openPreparacionModal()`, `closePreparacionModal()`, `addPreparacionRow()`, `updatePrepSummary()`, `submitPreparacion()` | Modal `#modal-preparacion` |

### Personal y Nóminas
| Función | Rol |
|---|---|
| `loadPersonal()`, `renderPersonalTable()`, `openNominaModal()`, `closeNominaModal()`, `openEliminarEmpleadoModal()`, `closeEliminarEmpleadoModal()`, `confirmEliminarEmpleado()`, `calcularNomina()`, `renderNominaResult()`, `toggleNominaDetalle()`, `pagarNomina()`, `openRegistrarAdelantoModal()`, `closeRegistrarAdelantoModal()`, `guardarAdelanto()`, `loadNominaHistorial()`, `renderNominaHistorial()` | Vista `#screen-personal` + modales nómina |
| `loadPuestos()`, `populatePuestoSelect()`, `togglePuestoPanel()`, `guardarPuesto()`, `openNuevoEmpleadoModal()`, `closeNuevoEmpleadoModal()`, `saveNuevoEmpleado()`, `openResetPasswordModal()`, `closeResetPasswordModal()`, `confirmResetPassword()` | Modal `#modal-nuevo-empleado`, puestos |
| `openAsistenciasModal()`, `closeAsistenciasModal()`, `loadAsistenciasEmpleado()`, `renderAsistenciasTable()`, `openAnularAsistenciaModal()`, `closeAnularAsistenciaModal()`, `confirmAnularAsistencia()`, `openEditOTModal()`, `closeEditOTModal()`, `confirmEditOT()`, `openEditarHorariosModal()`, `format12hPreview()`, `updateHorariosPreviews()`, `closeEditarHorariosModal()`, `confirmEditarHorarios()` | Modales asistencias |

### Cierre de Caja / Reportes
| Función | Rol |
|---|---|
| `loadCierreReportes(periodo)`, `renderCierreReportes()`, `destroyCharts()`, `renderPieChart()`, `renderBarChart()`, `renderTopList()` | Vista `#screen-cuenta` (Chart.js) |
| `openVentaRetroactivaModal()`, `closeVentaRetroactivaModal()`, `loadVRMesaSelect()`, `loadVRMenuItems()`, `renderVRItems()`, `addVRItem()`, `removeVRItem()`, `updateVRTotal()` | Modal `#modal-venta-retroactiva` |
| `ejecutarCierreCaja()` | `POST /caja/cierre` |
| `loadHistorialOrdenesDia()`, `renderHistorialOrdenesDia()`, `clearHistorialOrdenesDia()` | Historial diario |

### Salón (detalle mesa ocupada + pre-cuenta)
| Función | Rol |
|---|---|
| `openDetalleMesaOcupada()`, `closeDetalleMesaOcupada()`, `loadOcupadaOrden()`, `forzarLibrarMesa()`, `renderOcItems()`, `agregarAlPedido()`, `openPreCuenta()`, `closePreCuenta()`, `cerrarCuenta()`, `aplicarDescuentoOrder()` | Modales `#modal-detalle-mesa-ocupada`, `#modal-pre-cuenta` |

### Helpers
| Función | Rol |
|---|---|
| `api(endpoint, options)` | Wrapper fetch con token, errores, 401 |
| `formatLocalTime(isoStr)` | Formatea hora literal (12h AM/PM) sin conversión de zona |

---

## 6. Tokens de Diseño (CSS)

`:root` en `css/style.css`:

| Token | Valor | Uso |
|---|---|---|
| `--azul-marino` | `#003366` | Primario |
| `--rojo-cangrejo` | `#E63946` | Destructivo |
| `--amarillo-solar` | `#FFB703` | Advertencia |
| `--turquesa-ola` | `#2A9D8F` | Éxito / secundario |
| `--text-muted` / `--text-secondary` | `#94A3B8` / gris | Texto secundario |
| `--border-light` | `#E2E8F0` | Bordes |
| `--radius-md/lg/xl/full` | 8/12/16/999px | Redondeo |
| `--font-headline` (Manrope) / `--font-body` (Inter) | — | Tipografía |

Tailwind config (en `index.html`): `primary #0D233A`, `primary-container #003366`, `secondary #007166`, `secondary-container #8CF5E4`, `error #BA1A1A`, `error-container #F9DEDC`, `outline-variant #C3C6D1`, `surface-container #EEF2F7`, `surface-container-low #F1F5F9`, `surface-dim #DDE3EA`, `on-surface #0F172A`, `on-surface-variant #5B6B7C`, `scale 98`.

---

## 7. Convenciones y Notas Críticas

1. **NO renombrar** funciones, IDs, `data-*` o queries en la refactorización: los `render*()` y event listeners dependen de ellos. Usa esta doc como contrato.
2. **Moneda**: siempre `C$` (códorneta nicaragüense). Formato `.toLocaleString('es-NI')`.
3. **Idioma**: strings de UI en español.
4. **RBAC**: `.admin-only` solo Admin/Gerente (vía `body:not(.role-administrador):not(.role-gerente)`); `.nav-locked` deja ver pero bloquea. Role in `#screen-personal` etc.
5. **Responsive**: breakpoints móvil <768px; tablet 768–1024px; desktop ≥1024px.
6. **Modales**: siempre `.modal-overlay` + `.modal-sheet` + `.modal-header`(título + `×`). Se activan con `.show`.
7. **Cache-bust**: tras editar CSS/JS, subir `?v=` en `index.html`.
8. **Reloj**: hora local fija Nicaragua (`formatLocalTime` literal, sin `Date`).
9. **Iconos**: se usan **Material Symbols** (`<span class="material-symbols-outlined">nombre</span>`).
10. **Tailwind + CSS custom coexisten**: usa utilidades Tailwind donde el HTML de Stitch las use (especialmente tarjetas de Salón) y CSS custom para el shell/componentes base.
