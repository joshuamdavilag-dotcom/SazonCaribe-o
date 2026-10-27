# AGENTS.md — Sazón Caribeño POS

## Project Overview

Restaurant management POS system (ERP) built with FastAPI + SQLAlchemy 2.x + Pydantic v2 + MySQL.
The ERP frontend is a Vanilla JS SPA served by FastAPI from `app/Templates/`.
A public **Carta Digital** (menú para clientes vía QR, sin autenticación) is served from `app/Templates/carta/` and consumes the public API `/api/public`.

## UI Design System (Stitch)

The UI designs for the POS are hosted in a Stitch project (Google design tool). Any UI/UX work should keep these designs in sync with the real app.

- **Stitch project**: `Sazón Caribeño POS` — id `projects/5811892442693590109`, visibility PRIVATE, type PROJECT_DESIGN
- **Design system asset**: `assets/7885020225276488721` — displayName `Sazón Caribeño`, colorMode LIGHT, fonts Manrope (headline) + Inter (body/label), roundness ROUND_EIGHT, custom color `#003366`
- Design tokens mirror the CSS variables below (Azul Marino `#003366`, Turquesa Ola `#2A9D8F`, Amarillo Solar `#FFB703`, Rojo Cangrejo `#E63946`, fondo `#F8FAFC`)
- The `designMd` of the design system documents the full brand spec (palette, layout, typography, components, screen-by-screen guide)

Screens generated (all DESKTOP, Spanish UI, C$ currency):

| # | Screen | Screen id |
|---|--------|-----------|
| 1 | Login | `e68d80da195d498083037d771545a824` |
| 2 | Salón — Mapa de Mesas | `8adeb99b2d064cbe98e443b646c5bb0e` |
| 3 | Comandas KDS — Panel de Cocina | `7051083a0a0d4aa7b9cca82469477676` |
| 4 | Carta | `6b59b551d2054705ab3b6421f76e8c5b` |
| 5 | Gestión de Menú | `d3e3d6af2b9a4429b24dd7bea8e0f788` |
| 6 | Almacén Digital / Inventario | `f5c9e40bdb814dd699375394d354ff29` |
| 7 | Personal y Nóminas | `d556ca736bc444d89a6ef08e04558c4e` |
| 8 | Cierre de Caja | `d52769260e9d48ca92c18b0f4c427771` |
| 9 | Gestión de Gastos | `475c06441add40deb17769e60d7a4f26` |
| 10 | Modal Nueva Comanda | `85a0cc9a1c6a47e9b47c71049dc18e50` |
| 11 | Modal Detalle Mesa Ocupada | `4ff34507ef3346af8d7da85ea7c73379` |
| 12 | Modal Pre-Cuenta | `e9a8d16f8dca40159b84761bcb62d3a9` |

Notes: `stitch_list_screens` may return an empty `{}` (unreliable for verification — use `stitch_get_project`); new screens inherit the design system automatically when generated with `designSystem: assets/7885020225276488721`.

## Tech Stack

| Layer        | Technology                                  |
|--------------|---------------------------------------------|
| Framework    | FastAPI 0.138.0 + Uvicorn                   |
| ORM          | SQLAlchemy 2.x (mapped_column, Mapped)      |
| Schemas      | Pydantic v2 (ConfigDict from_attributes)    |
| Database     | MySQL via PyMySQL                            |
| Auth         | python-jose (JWT HS256) + bcrypt (direct)   |
| Migrations   | Alembic                                     |
| Image Storage| ImgBB API (via httpx) — permanent URLs       |
| HTTP Client  | httpx 0.28.1                                |
| Frontend     | Vanilla JS SPA + Custom CSS (style.css)      |
| Testing      | requests (standalone E2E scripts)            |

## Architecture

Multi-layer pattern: **API → Service → Repository → Model**

```
app/
├── main.py                  # FastAPI app, CORS, router registration, static mounts (/Templates + /carta), startup migrations, heartbeat watcher BG task, orphaned mesa fix, joshi password fix, constraint fix
├── core/
│   ├── config.py            # Pydantic Settings (.env) — includes HEARTBEAT_TIMEOUT_SECONDS, IMGBB_API_KEY, VAPID_*, PUSH_*, GEMINI_*
│   ├── database.py          # Engine, SessionLocal, Base, get_db() (SQLite archivo → pool normal; :memory: → StaticPool)
│   ├── security.py          # bcrypt (direct) + JWT — SECRET_KEY/ALGORITHM/ACCESS_TOKEN_EXPIRE_MINUTES read from .env via Settings
│   └── vapid.py             # Claves VAPID derivadas de SECRET_KEY (determinista) — Web Push
├── api/
│   ├── deps.py              # get_current_user, requerir_rol(roles)
│   └── endpoints/           # API controllers (one file per domain)
│       ├── auth.py          # POST /auth/login, /auth/verify
│       ├── personal.py      # Puestos, empleados, usuarios CRUD
│       ├── asistencia.py    # Turnos, check-in/out, iniciar turno, heartbeat, anular asistencia
│       ├── nomina.py        # Nómina y pagos
│       ├── inventario.py    # Proveedores, insumos, movimientos, catálogos de insumo
│       ├── menu.py          # Categorías, items, recetas
│       ├── menu_publico.py  # API pública Carta Digital (solo lectura, sin auth)
│       ├── salon.py         # Zonas, mesas, mapa
│       ├── orden.py         # Órdenes, agregar items, facturación, pagar, descuentos
│       ├── caja.py          # Historial diario, cierre de caja (archivado)
│       ├── gasto.py         # Gastos operativos CRUD + editar/eliminar auditado
│       ├── auditoria.py     # Bitácora de auditoría (GET paginado, Admin/Gerente)
│       ├── calendario.py    # Planificación autenticada + consulta de asistencias reales
│       ├── reportes.py      # Reportes financieros por periodo
│       ├── push.py          # Suscripciones push del dispositivo (config/subscribe/unsubscribe)
│       ├── estudio_mercado.py # Estudio de Mercado con Gemini (generar, listar, detalle, eliminar, documentos, chat)
│       └── analitica.py     # Cierre de caja legacy (métricas simples)
├── schemas/
│   ├── personal.py          # RolEnum, Puesto/Empleado/Usuario schemas
│   ├── asistencia.py        # TurnoCreate, TurnoUpdate, TurnoResponse, Asistencia, horas extras schemas
│   ├── nomina.py            # Nomina schemas
│   ├── inventario.py        # Proveedor, Ingrediente, Insumo (with packaging), UnidadMedida schemas
│   ├── menu.py              # MenuItem (imagen_url, tiempo_preparacion), Receta, Categoria schemas
│   ├── menu_publico.py      # Schemas públicos Carta Digital (sin costos/recetas/inventario)
│   ├── salon.py             # Mesa, Zona schemas
│   ├── orden.py             # Orden, DetalleOrden, AgregarItems, AplicarDescuentoItemRequest, AplicarDescuentoGlobalRequest schemas
│   ├── caja.py              # CierreCajaResponse, HistorialDiarioResponse
│   ├── gasto.py             # GastoCreate, GastoResponse
│   ├── calendario.py        # EventoCalendario request/response y respuesta de calendario
│   ├── reportes.py          # PeriodoEnum, CierreCajaPeriodoResponse (includes gastos_operativos)
│   ├── analitica.py         # CierreCajaResponse (legacy)
│   ├── push.py              # PushClaves, PushSuscripcionCreate/Response, PushConfigResponse
│   ├── estudio_mercado.py   # EstudioMercadoResponse, GenerarEstudioRequest, ChatEstudioRequest/Response, DocumentoResponse
│   └── auth.py              # LoginRequest, TokenResponse
├── models/
│   ├── personal.py          # Puesto, Empleado, Usuario
│   ├── asistencia.py        # Turno (Matutino/Nocturno), Asistencia (audit columns + ultimo_heartbeat)
│   ├── nomina.py            # Nomina
│   ├── inventario.py        # Proveedor, Ingrediente, Insumo, MovimientoInventario
│   ├── menu.py              # CategoriaMenu, MenuItem (imagen_url, tiempo_preparacion), Receta
│   ├── salon.py             # Zona, Mesa, EstadoMesa
│   ├── orden.py             # Orden, DetalleOrden, EstadoOrden (mesa_id nullable; metodo_pago; subtotal, descuento_total, nombre_cliente; descuento_porcentaje/monto/motivo on DetalleOrden; anulada/motivo_anulacion/anulada_por/anulada_en on Orden; cantidad_devuelta/motivo_devolucion/devuelta_en on DetalleOrden)
│   ├── caja.py              # CierreCaja
│   ├── gasto.py             # Gasto, CategoriaGasto enum (+ eliminado/motivo_eliminacion/eliminado_por/eliminado_en)
│   ├── calendario.py        # EventoCalendario, TipoEventoCalendario, EstadoEventoCalendario
│   ├── push.py              # PushSuscripcion (usuario_id, endpoint unique, p256dh, auth)
│   ├── estudio_mercado.py   # EstudioMercado, DocumentoEstudioMercado, MensajeEstudioMercado
│   └── __init__.py          # Registers all models including Gasto
├── repositories/
│   ├── base_repository.py   # Generic base repository
│   ├── usuario_repository.py
│   ├── empleado_repository.py
│   ├── turno_repository.py
│   ├── asistencia_repository.py  # + actualizar_heartbeat(), get_activas_sin_heartbeat()
│   ├── nomina_repository.py
│   ├── inventario_repository.py
│   ├── menu_repository.py       # _query_items_base() compartida; obtener_items_publicos(), obtener_item_publico_por_id() (Carta Digital); actualizar_imagen_url()
│   ├── salon_repository.py
│   ├── orden_repository.py
│   ├── caja_repository.py
│   ├── gasto_repository.py       # obtener_por_rango(), sumar_por_rango()
│   ├── calendario_repository.py  # eventos por rango + asistencias no anuladas con nombres
│   ├── reportes_repository.py    # + obtener_gastos_clasificados(), obtener_descuentos_totales()
│   ├── estudio_mercado_repository.py # Métricas del periodo, CRUD de estudios, documentos y mensajes
│   └── analitica_repository.py
├── services/
│   ├── personal_service.py
│   ├── asistencia_service.py     # + actualizar_heartbeat(), cerrar_turnos_stale(), crear_turno(), actualizar_turno(), eliminar_turno(), anular_asistencia()
│   ├── nomina_service.py
│   ├── inventario_service.py     # SALIDA movements auto-generate Gasto records; _convertir_cantidad_si_necesaria() per-insumo packaging
│   ├── menu_service.py          # + consultas públicas reutilizables: obtener_menu_publico(), obtener_categorias_publicas(), obtener_item_publico_por_id(); subir_imagen() (upload multipart)
│   ├── preparacion_service.py   # Producción por lote: registrar_preparacion() valida stock, descuenta insumos (SALIDA + Gasto SUMINISTROS), crea DetallePreparacionCocina
│   ├── salon_service.py
│   ├── orden_service.py          # validar_stock_suficiente() + descontar_stock() + revertir_stock() + TRANSICIONES_VALIDAS; _convertir_si_necesario() per-insumo packaging; aplicar_descuento_item(), aplicar_descuento_global(), quitar_descuento_item(); _recalcular_totales()
│   ├── caja_service.py
│   ├── gasto_service.py          # registrar_gasto(), registrar_gasto_automatico()
│   ├── calendario_service.py     # CRUD de eventos, validación de referencias, respuesta combinada
│   ├── reportes_service.py       # Utilidad = ingresos - nómina - insumos - gastos_operativos; incluye descuentos en response
│   ├── conversion_service.py     # convertir_cantidad() — transitive chain resolution via _get_chain()
│   ├── turno_service.py          # Standalone functions
│   ├── push_service.py           # Suscripciones push, preferencias por usuario (avisos_cocina/mesero/todas/fuera_de_turno), usuarios_avisos_cocina(), usuarios_con_avisos_mesero(), usuarios_avisos_mesero_todas(), enviar(), notificar_nueva_comanda()/notificar_comanda_lista(); usuarios_administracion(), notificar_estudio_mercado()
│   ├── gemini_service.py         # Cliente Gemini: rotación de modelos, reintentos, thinkingConfig adaptativo, clasificador de alcance
│   ├── estudio_mercado_service.py # Generación del estudio (métricas + temporada), guardrail de temas, chat con documentos, _contexto_negocio()
│   ├── extraccion_texto.py       # Extrae texto de PDF/DOC/DOCX/XLS/XLSX/CSV para el análisis
│   └── analitica_service.py
├── db/
│   └── init_db.py
├── Templates/
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js                 # POS SPA, calendario mensual y detalle diario; órdenes con POST /ordenes/{id}/items; push (suscripción + deep links)
│   ├── sw.js                     # Service Worker de Web Push (scope /Templates/) — push + notificationclick
│   └── carta/                    # Carta Digital pública (sin auth): index.html, css/style.css, js/app.js, img/ (hero, logos, placeholder) + img/platos/ (imágenes subidas por el ERP)
├── docs/
│   └── CALENDARIO.md             # Guía funcional y técnica completa del calendario
└── tests/
```

## Running the Project

```bash
pip install -r requirements.txt
python -m app.db.init_db
python -m app.main
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# Docs: http://localhost:8000/docs
```

## Seed Users

| Username | Password    | Role           | Notes |
|----------|-------------|----------------|-------|
| joshi_0211 | @0420311001000V | Administrador | Auto-seeded on startup if DB empty |
| admin    | password123 | Administrador  | init_db.py seed |
| gerente  | password123 | Gerente        | init_db.py seed |
| mesero   | password123 | Vendedor       | init_db.py seed |

`_seed_datos_prueba()` also creates 4 more employees with full July 2026 test data.

## Code Conventions

### Python / Backend

- Models: modern SQLAlchemy 2.x — `Mapped`, `mapped_column`, `relationship` with string refs
- Schemas: `ConfigDict(from_attributes=True)` for ORM mode
- Services raise `HTTPException` (404, 400, 403) for business rule violations
- Repositories use `joinedload` for eager loading
- JWT `sub` claim must be `str` (not int) — python-jose requirement
- All API endpoints prefixed with `/api/v1/`
- Write endpoints protected with `Depends(requerir_rol([RolEnum.ADMINISTRADOR, RolEnum.GERENTE]))`
- All orden endpoints protected with `Depends(get_current_user)`
- No comments in code unless explicitly requested
- Spanish user-facing strings, English internal identifiers
- `RolEnum` defined in `app/schemas/personal.py`
- SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES read from `.env` via `get_settings()`
- Case-insensitive login: usernames normalized to lowercase (`strip().lower()`) at auth endpoint and user creation service; `UsuarioRepository.get_by_username()` hace doble pasada tolerante (exacta primero → fallback `LOWER(TRIM(username))`) para sanear filas legacy
- Login con mensajes diferenciados (decisión de UX para diagnóstico interno): 401 `"No existe el usuario 'X'"` vs 401 `"Contraseña incorrecta"`; `verificar_password()` captura hashes corruptos/legacy (devuelve `False` + log en vez de 500); startup `_auditar_hashes()` lista usuarios con hash no-bcrypt (`[AUTH AUDIT]`)

### Frontend / JS

- Vanilla JS SPA — no frameworks, no build step
- **Assets con URL estable (SIN parámetro de versión)**: `app/Templates/index.html` carga `css/style.css` y `js/app.js` **sin `?v=`**: la URL de los archivos nunca cambia (igual que la Carta Digital). El cache se resuelve con `Cache-Control: no-cache` + `ETag`/`304` (middleware `_revalidar_estaticos` en `app/main.py`): el navegador revalida en cada carga y recibe 304, por lo que **nunca queda con una copia vieja sin tocar ninguna URL**. **No volver a agregar `?v=`** (eso sí cambia el link).
- `API_BASE` auto-detects: local (`localhost`/`127.0.0.1`) → `http://127.0.0.1:8000/api/v1`, otherwise → `${location.origin}/api/v1` (works on Render)
- Token stored in `localStorage` as `pos_token`; user as `pos_user`
- Adding items to existing order uses `POST /ordenes/{id}/items` (legacy PATCH endpoint removed)
- Sidebar layout: 260px fixed sidebar + flex main content
- Card grids: `repeat(auto-fill, minmax(280px, 1fr))`
- All modals use `.modal-overlay.show` pattern
- `showToast(message, type)` for notifications
- Role-based nav: `.nav-locked` class for restricted items
- Gastos screen: `#screen-gastos` with table (ID, Fecha, Categoría, Descripción, Monto, Registrado Por, Acciones); modal `#modal-registrar-gasto` with fecha picker + categoría select + monto + descripción; `loadGastos()` fetches `GET /gastos/`, `guardarGasto()` posts `POST /gastos/`. Columna Acciones (`admin-only`) con ✏️/🗑️ → `#modal-editar-gasto` (`confirmarEditarGasto()` → `PUT /gastos/{id}`) y `#modal-eliminar-gasto` (`confirmarEliminarGasto()` → `DELETE /gastos/{id}`); ambos con motivo obligatorio y refresco de la tabla
- Caja — Auditoría y anulación: el historial de órdenes de la caja (`renderHistorialOrdenesDia`, target `gestor`) muestra columnas ↩ (devolver) y 🗑️ (anular) `admin-only` → `#modal-devolver-item`/`#modal-anular-orden`. El panel `#caja-auditoria-panel` (dentro de `#cierre-gestor-panel`, oculto para no-gestores) muestra la bitácora: filtros `#auditoria-desde`/`#auditoria-hasta` + `#btn-filtrar-auditoria`, tabla `#auditoria-tbody`, paginación `#btn-auditoria-anterior`/`#btn-auditoria-siguiente` con `state.auditOffset`/`auditLimit`, total `#auditoria-total` y `#auditoria-pagina`. `loadAuditoria()`/`renderAuditoria()` consumen `GET /auditoria/`; se recarga al entrar a Caja (gestor) y con `#btn-refresh-auditoria`. El render muestra antes/después en un `<details>` por registro
- Calendario: `#screen-calendario` mensual y responsive; `loadCalendario()` pide eventos + asistencias reales a `GET /calendario/?desde=&hasta=` una vez por navegación/mes; `renderCalendario()` dibuja semanas y permite elegir fecha para mostrar detalle diario completo. Asistencias son solo consulta (sin anuladas); Admin/Gerente crean/editar/eliminan eventos por modal `#modal-calendar-event`. Catálogos se cargan una vez desde Menú, Insumos y Proveedores. Reglas completas y contrato: `docs/CALENDARIO.md`.
- Salón: `#zona-filters` chip row dynamically populated from `GET /salon/zonas`; filters combine with estado chips via `applyTableFilters()`; zone CRUD in `#zonas-panel` (collapsible) within Gestionar Mesas modal; startup `_fix_orphaned_mesas()` auto-frees OCUPADA tables with no active orders; table detail modal shows "Forzar Libramiento" button when OCUPADA but no active order found; `forzarLibrarMesa()` usa `PATCH /salon/mesas/{id}/estado` con `{nuevo_estado:'LIBRE'}` (cualquier rol autenticado, limpia `apodo`), NO `PUT /salon/mesas/{id}` (Admin/Gerente) para que el Vendedor también pueda liberar mesas huérfanas
- Inventario: `#insumo-cat-filters` chip row dynamically populated from `GET /inventario/categorias-insumo`; filters items by `categoria_id`; `#stock-alerts` es un panel colapsable (`toggleStockAlerts()` + `state.stockAlertsOpen`, cerrado por defecto): la cabecera muestra el conteo de insumos con stock crítico y "Ver detalle" despliega la lista (`#stock-alerts-list`, `max-h-72` con scroll; cada fila abre `openStockModal()`; icono rojo si el stock es 0, ámbar si está bajo el mínimo); `#modal-insumo` has ⚙️ toggle buttons for inline category and unit subpanels (`#cat-insumo-panel`, `#unidad-panel`); dynamic `<select>` populated from `GET /inventario/unidades-medida`; `loadInventory()` fetches both catalog endpoints + insumos + alerts; category cards show `categoria_nombre` badge; `#modal-stock` has two tabs (Movimiento/Detalles) — Movimiento tab adjusts stock via `PATCH /insumos/{id}/stock`, Detalles tab edits category/unit/stock_minimo via `PATCH /insumos/{id}`; gear subpanels for inline category/unit creation from stock modal
- KDS (Panel de Cocina): `#screen-comandero` with 3 filter tabs (`data-cocina-tab`: cocina/lista/historial), `#cocina-grid` card grid; `loadCocinaOrdenes()` → `renderCocinaCards()`; `cambiarEstadoKDS(id, estado)` → `PATCH /ordenes/{id}/estado`; cards show zone, mesa, mesero, elapsed time with urgency colors, and item list with `producto_nombre`
- Nueva Comanda (`.order-card`): tarjetas **tipo marketplace en 1 columna** (foto a la izquierda + nombre/precio a la derecha, todo visible en la misma tarjeta ancha). `.order-card` es `flex-direction: row` con `min-height: 124px`; `.oc-media` es una miniatura fija de 148px (`width: 148px`, `align-self: stretch`, `border-radius` solo del lado izquierdo) con la foto `position: absolute; inset: 0` (la imagen NUNCA define la altura). `.oc-body`: `.oc-name` (**sin `line-clamp` — el nombre se ve completo**, 16px) → `.oc-price` en negrita azul debajo del nombre → `.oc-foot` (`flex-wrap: wrap` + `flex-shrink: 0` en los hijos, `padding-top: 10px`) alineado a la derecha con `.oc-add` (píldora "＋ Agregar"), `.oc-stepper` (píldora turquesa `− qty +`) y **`.oc-disc-btn` (🏷️ descuento por producto: se enciende en amarillo `.on` cuando el ítem tiene descuento)**. Badge `.oc-badge` de tiempo/cantidad arriba a la derecha de la miniatura; `.oc-tag` de categoría solo cuando no hay agrupación. Grid `minmax(0, 1fr)` con `.order-card > * { min-width: 0 }` (evita desbordes); sheet `max-width: 780px`; móvil miniatura 104px con tarjeta `min-height: 104px`
- Descuento por producto (`.oc-disc-btn` / `openMenuItemDiscount(productoId)`): botón 🏷️ en cada tarjeta del catálogo que agrega el platillo si no está en la comanda y abre `#order-item-disc-sheet` (`openItemDiscountSheet(idx)`); `applyItemDiscount()`/`clearItemDiscount()` refrescan también el catálogo (`renderOrderModalMenu`) para que el botón refleje el estado `.on`
- Responsive design: Custom CSS (NOT Tailwind); mobile `<768px`, tablet `768-1024px`
- Dynamic Carta categories: Fetches from `GET /menu/categorias`; order modal category tabs rendered dynamically from same source
- Carta — acceso a Descuentos: `#btn-carta-descuentos` (`.admin-only`, header de `#screen-menu-view`) abre `#screen-descuentos` vía `navigateTo('descuentos')`; esa pantalla tiene `#btn-descuentos-volver` → `navigateTo('menu-view')`. No hay entrada de Descuentos en el sidebar (v6.19)
- C$ currency: All monetary values use `C$` (Córdobas nicaragüenses)
- Personal module: New employee modal has `telefono` field + `C$` salary label; `saveNuevoEmpleado()` sends `salario_base` + `telefono` in employee body; ⚙️ button next to Puesto select opens `#puesto-panel` (inline subpanel) to create new Puesto inline — `guardarPuesto()` posts `POST /personal/puestos`, reloads select, auto-selects new puesto
- Unidades de Medida: `#modal-unidades` management modal with table view + create/edit form; `#unidad-derived` toggle shows/hides base unit select + conversion factor; magnitud-filtered base unit select via `populateUnidadBaseSelect()` (falls back to all units for PERSONALIZADO magnitud); live conversion preview text
- Stock modal: Two-tab layout — Movimiento tab (adjust stock via `PATCH /insumos/{id}/stock` with unit selector + conversion preview) and Detalles tab (edit category/unit/stock_minimo via `PATCH /insumos/{id}` with packaging fields section); gear subpanels for inline category/unit creation
- Insumo modal: Packaging section with `Unidad de Empaque` select (`#insumo-unidad-empaque`) + `Factor` input; dynamic preview text ("1 Bolsa de Arroz equivale a 5 lb")
- Gestión de Turnos: `#modal-turnos` CRUD modal for shift templates (nombre, hora_entrada, horas_teoricas); auto-calculated `hora_salida` field (readonly, displays "(calculada)") derived from `entrada + horas_teoricas` via `calcularHoraSalida()` with midnight crossover; table with editar/eliminar actions; button in Personal header (Admin/Gerente only via `.admin-only` CSS class)
- Avisos de turno: `#btn-enable-attendance-notifications` requests browser notification permission; while the POS is open it reminds once when the selected shift is underway without a check-in and once when an active attendance reaches its scheduled end. The selected shift is remembered per user; times use `America/Managua`. Notifications can appear while the browser is minimized, but not after it is closed.
- Habilitación Dinámica de Turno: `#btn-toggle-all-turnos` en el header de Personal + botón `.btn-toggle-turno` por fila (solo usuarios rol `Vendedor`); `syncMassTurnoButton()` refleja el estado agregado con etiquetas **explícitas** — "Habilitar Turnos (n/total)" cuando quedan habilitados por habilitar y "Deshabilitar Turnos de Todos" cuando todos están habilitados (nunca una etiqueta de estado ambigua como "Turnos Habilitados"); `toggleTurnoMasivo()` → `PATCH /personal/usuarios/turno-masivo`, `toggleTurnoUsuario(id, bool)` → `PATCH /personal/usuarios/{id}/turno` (delegación `click` sobre `#personal-table-container`); ambos `admin-only`; **toda deshabilitación pide confirmación** (`confirm()` con el nombre del usuario en el caso individual y con el total en el masivo) porque cerrar el turno de alguien es una acción forzosa y visible para el empleado
- Cierre de turno del empleado (409 honesto): `finalizarTurno()` trata el `409` de `POST /asistencia/check-out` como **advertencia larga** (no "éxito"): avisa que el turno ya fue cerrado automáticamente, muestra la hora de salida registrada y la causa, e indica que gerencia puede corregirlo con Editar Horarios. `state.avisoCierreAutomatico` + `syncAsistenciaActiva()` detectan que el turno abierto desapareció de la BD y muestran el aviso **una sola vez por turno** (`showToast` + aviso persistente en el panel de asistencia)
- Badge "⏱️ Auto" en el historial de asistencias: marca los registros cerrados automáticamente (`Asistencia.observaciones` con causa de cierre) con el motivo en el `title`; convive con el badge "✏️ Auditado" (corrección manual de horarios) cuando ambos aplican; el resto de la UI de asistencia usa etiquetas explícitas (Entrada / Salida / Horas extras) en lugar de rótulos genéricos. `editar_horarios()` preserva `horas_extras_originales` (solo si estaba en NULL) para que la corrección manual de un cierre automático quede trazable.
- Editar Horarios: `#modal-editar-horarios` modal with `<input type="time">` for entrada + salida; opens from 🕐 button in asistencias table; `openEditarHorariosModal()` prefill con `slice(0,16)` del string crudo (sin conversión); `confirmEditarHorarios()` posts `PUT /asistencia/{id}/editar-horarios` with `fecha_hora_entrada`, `fecha_hora_salida`, `motivo`; backend guarda la hora local tal cual SIN conversión a UTC; recalculates horas extras if exit time provided; audit trail via `motivo_modificacion` + `modificado_por`
- Role-based CSS: `body:not(.role-administrador):not(.role-gerente) .admin-only { display: none !important; }` — Gerente can see admin-only elements (Gestionar Mesas, Gestión de Turnos buttons)
- **Push (Web Push)**: los botones de aviso llevan el atributo `data-push-toggle` (hay dos: `#notifications-push` dentro del panel de notificaciones y `#desktop-push-toggle` en el topbar de escritorio). `pintarEstadoPush()` los sincroniza (`.push-activo` + texto "Avisos activados"/"Activar avisos") y el estado se explica en `#notifications-push-estado` ("Recibirás avisos de comandas **mientras tu turno esté abierto**"). El service worker se registra con `navigator.serviceWorker.register('/Templates/sw.js', { scope: '/Templates/' })` — **URL estable, sin `?v=`**; la actualización del SW llega sola por `ETag`/`Cache-Control: no-cache` y se fuerza con `registro.update()`. Deep links: `?pantalla=` (destino) y `?mesa=` (mesa a abrir); se leen una sola vez (`DESTINO_URL`) y se borran de la barra de direcciones con `history.replaceState` (`limpiarUrlDestino()`), así que **la URL visible del ERP siempre es la canónica** (`/Templates/index.html`).
- `formatLocalTime(isoStr)` helper formatea de forma literal el string crudo (extrae HH:MM y muestra 12h AM/PM) — sin conversión de zona; los datetimes de asistencia son hora local fija de Managua
- Reloj en vivo: `updateClock()` muestra hora actual en KDS (`#comandero-clock`) y Salón (`#salon-clock`), actualiza cada 30s via `setInterval`
- `cobrarOrden(ordenId)` — pago rápido desde KDS: PATCH estado a PAGADA + PUT mesa a LIBRE (si tiene mesa_id); alternativa al flujo de detalle de mesa ocupada
- Asistencias — Anular: botón 🗑️ en columna ACCIONES del modal `#modal-asistencias` (`.admin-only` + `.btn-action-danger`), solo para registros no anulados; `openAnularAsistenciaModal(id, fecha)` abre `#modal-anular-asistencia` (texto de advertencia "¿Estás seguro de que deseas eliminar este registro de asistencia (#ID)? Esta acción recalculará o descartará las horas para la nómina." + motivo obligatorio); `confirmAnularAsistencia()` hace `DELETE /asistencia/{id}` con body `{motivo}` y recarga el historial; las filas anuladas muestran badge "🚫 Anulado" (con motivo en tooltip) y ocultan acciones

### Design Tokens (CSS)

| Token            | Value     | Usage                    |
|------------------|-----------|--------------------------|
| `--azul-marino`  | `#003366` | Primary, headers         |
| `--rojo-cangrejo`| `#E63946` | Alerts, destructive      |
| `--amarillo-solar`| `#FFB703`| Warnings, highlights     |
| `--turquesa-ola` | `#2A9D8F` | Success, secondary       |

### Modo oscuro

- **Mecanismo**: `document.documentElement` lleva el atributo `data-theme="dark"` (sin atributo = claro). El tema elegido se guarda en `localStorage` bajo `pos_tema` (`'dark'`/`'light'`).
- **Sin FOUC**: script inline en el `<head>` de `index.html` lee `pos_tema` (o `prefers-color-scheme`) **antes** de cargar el CSS y aplica `data-theme`.
- **API JS** (`app/Templates/js/app.js`, bloque "Tema claro / oscuro"): `temaActual()`, `temaPreferido()`, `aplicarTema(tema, guardar)`, `alternarTema()`, `pintarEstadoTema()`, `actualizarMetaTema()`, `actualizarGraficosTema()`, `iniciarTema()`. Botones con `data-tema-toggle` (+ `data-tema-icono` / `data-tema-texto`): `#btn-tema` en el topbar de escritorio y el ítem "Modo oscuro" del menú móvil.
- **Regla de CSS (obligatoria)**: nunca escribir un color literal nuevo en una regla que deba adaptarse. Usar `color-mix(in srgb, <color-claro> var(--mix-*-pct), var(--mix-*-base))`:
  | Variable | Claro | Oscuro |
  |---|---|---|
  | `--mix-ink-pct` / `--mix-ink-base` | `100%` / `transparent` | `45%` / `#e8f0f8` |
  | `--mix-surface-pct` / `--mix-surface-base` | `100%` / `transparent` | `10%` / `#0b1220` |
  | `--mix-border-pct` / `--mix-border-base` | `100%` / `transparent` | `20%` / `#2a3849` |
  Con `--mix-*-pct: 100%` + base `transparent`, `color-mix()` devuelve **exactamente** el color original → **el modo claro queda pixel-idéntico**. Los tintes translúcidos (`rgba(...)` de fondo) se dejan tal cual: funcionan en ambos temas.
- **Dónde va el bloque oscuro**: al **final** de `style.css` (después de todas las reglas claras) para que gane por orden de aparición sin `!important`.
- **Gráficos**: `actualizarGraficosTema()` ajusta `Chart.defaults.color`/`borderColor` y el `borderColor` del doughnut al color de tarjeta del tema activo.
- **Assets**: las URLs siguen siendo estables (sin `?v=`); el tema no toca `<link>`/`<script>`.

## RBAC Rules

| Action                        | Administrador | Gerente | Vendedor |
|-------------------------------|:-------------:|:-------:|:--------:|
| Read all endpoints            | Y             | Y       | Y        |
| Menu/Inventario write         | Y             | Y       | N        |
| Ordenes (create, add items)   | Y             | Y       | Y        |
| Pagar orden (auto-libera mesa)| Y             | Y       | Y        |
| Iniciar turno                 | Y             | Y       | Y        |
| Gestionar turnos (CRUD)       | Y             | Y       | N        |
| Habilitar turno (vendedores)  | Y             | Y       | N        |
| Dar de baja empleado (lógica) | Y             | Y       | N        |
| Gastos operativos             | Y             | Y       | N        |
| Consultar calendario          | Y             | Y       | Y        |
| Gestionar eventos calendario | Y             | Y       | N        |
| Cierre de caja (reportes)     | Y             | Y       | N        |
| Ver ventas del día (resumen)  | Y             | Y       | Y        |
| Cerrar caja (archivar)        | Y             | Y       | N        |
| Anular pedido / devolver ítem | Y             | Y       | N        |
| Editar/Eliminar gasto         | Y             | Y       | N        |
| Consultar auditoría           | Y             | Y       | N        |
| Nomina                        | Y             | Y       | N        |

## Business Rules

- **Calendario de planificación**: `EventoCalendario` persiste disponibilidad planificada de platillos y llegadas de insumos; consulta autenticada para cualquier rol, escritura Admin/Gerente. Asistencias reales consultadas desde `Asistencia` por fecha calendario y `anulada=False`; incluye empleado, turno, hora de entrada/salida, no se editan desde esta pantalla. Rango API inclusivo máximo 63 días; no programa turnos ni altera disponibilidad de platillos/stock. Los eventos pueden cubrir varias fechas; las horas son opcionales (ambas o ninguna); estados `PLANIFICADO`/`REALIZADO`/`CANCELADO`. La cantidad esperada de entrega se registra en unidad base del insumo y no genera movimiento de inventario. Ver `docs/CALENDARIO.md`.
- **Payroll**: El salario base del período se prorratea según su duración: **semanal (hasta 8 días) = salario_mensual / 4**, **quincenal (hasta 20 días) = salario_mensual / 2**, **mensual (más de 20 días) = salario_mensual**. Salary is per-employee (`Empleado.salario_base`), not per-puesto. Pago de nómina = base del período + horas extras — NO se recalcula por horas ordinarias trabajadas, eliminando discrepancias por suma de asistencias
- **Overtime**: (salary / 240) per hour (1.0x, sin recargo); `monto_horas_extras = total_horas_extras × (salario_base / 240)`
- **IVA**: Removed — menu prices are tax-inclusive; `IVA_RATE=0.0`
- **Turno**: Template (Matutino/Nocturno); Asistencia = actual check-in record
- **MenuItem**: Must have `categoria_id`, `nombre`, `precio`; `disponible` toggles visibility
- **Anulación de pedidos y devolución de líneas (auditado)**: `POST /ordenes/{id}/anular` (Admin/Gerente) marca `Orden.anulada=True` + `motivo_anulacion`/`anulada_por`/`anulada_en` (borrado lógico, nunca `db.delete`); la orden sale de TODOS los totales de ventas (caja abierta e históricos). `POST /ordenes/{id}/devolver-item` (Admin/Gerente) con `{detalle_id, cantidad, motivo}` acumula `DetalleOrden.cantidad_devuelta`/`motivo_devolucion`/`devuelta_en` y recalcula `subtotal`/`descuento_total`/`total` prorrateando las unidades devueltas. Bloqueos: 404 si la orden/detalle no existe, 400 si el motivo está vacío, la orden ya está anulada, la orden pertenece a una caja ya cerrada (`cierre_caja_id` no nulo), o si `cantidad` excede las unidades vigentes de la línea. NO revierte inventario. Cada operación se registra en `RegistroAuditoria` (`ORDEN_ANULADA`/`ITEM_DEVUELTO`) con antes/después y el autor. Frontend: botones ↩/🗑️ (`admin-only`) en el historial de órdenes de la Caja (target `gestor`) → `#modal-devolver-item` / `#modal-anular-orden`.
- **Edición y eliminación de gastos (auditado)**: `PUT /gastos/{id}` edita `concepto`/`monto`/`categoria`/`fecha` con `motivo` obligatorio; `DELETE /gastos/{id}` marca `Gasto.eliminado=True` + `motivo_eliminacion`/`eliminado_por`/`eliminado_en` (borrado lógico, nunca `db.delete`). Ambos Admin/Gerente. Reglas: 404 si no existe, 400 si ya está eliminado, si el motivo está vacío, o si la edición no cambia ningún campo. A diferencia de las órdenes, los gastos PUEDEN editarse/eliminarse aunque pertenezcan a una caja ya cerrada (decisión explícita del negocio). Eliminar un gasto SUMINISTROS auto-generado NO devuelve stock. Los gastos eliminados se excluyen de `CajaRepository`, `GastoRepository`, `ReportesRepository` (rangos y `sin_archivar`) y `AnaliticaRepository`. Cada operación se registra en `RegistroAuditoria` (`GASTO_EDITADO`/`GASTO_ELIMINADO`) con antes/después y el autor. Frontend: columnas ✏️/🗑️ (`admin-only`) en la tabla de Gastos → `#modal-editar-gasto` / `#modal-eliminar-gasto`.
- **Bitácora de auditoría**: `RegistroAuditoria` (modelo existente) + `AuditoriaService.registrar(db, actor, accion, entidad_tipo, entidad_id, descripcion, antes=, despues=)` (añade a la sesión; el caller hace commit) y `AuditoriaService.registrar_sistema(db, accion, entidad_tipo, entidad_id, descripcion, antes=, despues=)` para eventos **sin actor humano** (actor `sistema` / rol `Sistema`). Consulta vía `GET /api/v1/auditoria/?desde=&hasta=&limit=&offset=` (solo Admin/Gerente, paginado, máx. `limit=100`, 400 si `desde > hasta`). En el ERP se muestra en el panel "Movimientos y Cambios" (`#caja-auditoria-panel`) dentro de la pantalla Caja (Cierre de Caja), visible solo para gestores (`#cierre-gestor-panel`), con filtros de fecha, paginación y detalle antes/después por registro. Acciones registradas actualmente: `PRECIO_ASIGNADO`/`PRECIO_ACTUALIZADO`/`DESCUENTO_*`, `ORDEN_ANULADA`, `ITEM_DEVUELTO`, `GASTO_EDITADO`, `GASTO_ELIMINADO`, `TURNO_CERRADO_AUTOMATICAMENTE`.
- **Cierre automático de turnos siempre auditado**: `TURNO_CERRADO_AUTOMATICAMENTE` se registra con antes/después (entrada, salida, horas extras, estado) y `descripcion` = la causa (`observaciones`). Actor = el gerente/admin que deshabilitó el turno (`PersonalService.cambiar_turno_habilitado()` / `habilitar_turno_masivo()` pasan `actor=current_user`) o `sistema` cuando el cierre lo hizo el `_heartbeat_watcher()`. Regla de oro: **ningún cambio forzado es invisible** — todo cierre automático queda en la bitácora y es corregible con Editar Horarios.
- **Migraciones de startup de auditoría**: `_migrate_ordenes_anulacion()` (columnas `anulada/motivo_anulacion/anulada_por/anulada_en` en `ordenes`; `cantidad_devuelta/motivo_devolucion/devuelta_en` en `detalles_orden`) y `_migrate_gastos_eliminacion()` (`eliminado/motivo_eliminacion/eliminado_por/eliminado_en` en `gastos`) en `app/main.py`, idempotentes vía `information_schema`. `Orden.mesero` usa `foreign_keys=[mesero_id]` (la FK `anulada_por` creó un segundo camino a `usuarios`); relación `anulado_por_usuario` con `foreign_keys=[anulada_por]`.
- **Anulación de registro de asistencia**: `DELETE /asistencia/{id}` (Admin/Gerente) marca `Asistencia.anulada=True` (borrado lógico, nunca `db.delete`) con `motivo` obligatorio que se guarda en `motivo_modificacion` + `modificado_por` (auditoría). Bloquea: registro inexistente (404), motivo vacío (400), turno aún activo sin salida (400), registro ya anulado (400). Los registros anulados NO cuentan para nómina: `get_finalizadas_por_rango`, `get_asistencias_por_rango_fechas` y `get_asistencia_del_dia` filtran `Asistencia.anulada == False`, por lo que horas normales y extras se descartan del cálculo y el empleado puede volver a marcar entrada el mismo día. El historial (`get_asistencias_por_empleado`) conserva el registro con badge "🚫 Anulado" (y motivo en tooltip) para trazabilidad.
- **Borrado lógico de platillos**: `DELETE /menu/items/{id}` does a SOFT DELETE — sets `disponible=False` (never `db.delete`). Receta e historial de ventas (`detalle_orden`) se conservan; el plato puede reactivarse editándolo. `IntegrityError` se captura y devuelve 400 con mensaje claro. `GET /menu/items` devuelve solo activos por defecto; `?incluir_inactivos=true` (solo Admin/Gerente) los incluye para Gestión de Menú. La unicidad de nombre verifica también inactivos.
- **Eliminación con liberación de nombres (platos y usuarios)**: `DELETE /menu/items/{id}` y `DELETE /personal/usuarios/{id}` usan una regla borrar/archivar para liberar el nombre (título del plato / username + cédula) y poder reutilizarlo tras una "baja". Sin registros asociados → borrado físico (`db.delete`; la receta se purga vía `cascade="all, delete-orphan"`); con referencias contables → archivo: renombra a `{valor}_deleted_{id}` (idempotente; truncado al `max_len` de la columna; colisión → sufijo `uuid4` corto) y marca `disponible=False`/`activo=False`. Helpers: `_nombre_archivado()` en `MenuService` (max 100) y `PersonalService` (username 50, cédula 20); `PersonalService._usuario_tiene_referencias()` (6 FKs: ordenes.mesero_id, gastos.registrado_por, asistencias.modificado_por, adelantos_salario.registrado_por_id, preparaciones_cocina.registrado_por, cierres_caja.cerrado_por) y `_empleado_tiene_referencias()` (3 FKs: asistencias/nominas/adelantos_salario.empleado_id). Se borra primero el usuario y luego su empleado (ambos solo si las dos consultas dan 0). El endpoint de usuario pide `{password}` (autorización, patrón de `dar_de_baja_empleado`), 400 si es auto-borrado o ya archivado, 401 si la contraseña es incorrecta. **Login**: `POST /auth/login` rechaza con 403 "Tu usuario está desactivado..." si `usuario.activo == False` (nuevo check tras validar password).
- **Migración de startup `_migrate_nombres_archivados()`** (en `app/main.py`, corre en cada inicio): platos `disponible=False` → si no tienen ventas se `db.delete` (aceptado: desactivar un plato limpio lo purga en el siguiente reinicio); con ventas → renombra. Usuarios `activo=False` → SOLO renombra username y cédula del empleado vinculado (nunca borra en la migración; el borrado físico es exclusivo del endpoint). Idempotente vía sufijo `_deleted_{id}`.
- **CategoriaMenu**: Dynamic categories; delete guarded if category has associated platillos
- **Orden**: `mesa_id` nullable (para llevar / retroactive / direct sales) + array of `detalles` (each with `producto_id`, `cantidad`, optional `notas` for special instructions like "Sin cebolla", "poco cocido")
- **One-active-order-per-mesa**: Only ONE active order (PENDIENTE/PREPARANDO/ENTREGADA) per mesa. New items via `POST /ordenes/{id}/items`. Does NOT apply to para llevar (mesa_id null).
- **Edición de comanda abierta**: `PUT /ordenes/{id}/items` (cualquier rol autenticado, bloqueado en PAGADA/CANCELADA) reemplaza el contenido de la orden. El body `{items: [{detalle_id?, producto_id, cantidad, notas?, descuento_monto?, motivo_descuento?}]}` es el estado FINAL deseado: los ítems con `detalle_id` se actualizan (cantidad/precio actual/notas/descuento), los que van sin `detalle_id` se agregan, y todo `DetalleOrden` existente que no aparezca se elimina. `detalle_id` que no pertenezca a la orden → 404. Ajusta inventario por diferencia (`_calcular_diferencia_cantidades` para aumentos, `_revertir_detalle` para reducciones o retiros) generando `MovimientoInventario` (SALIDA/ENTRADA) y `Gasto` (SUMINISTROS) en aumentos. `_sincronizar_detalle_edicion()` actualiza la línea usando siempre el precio actual del catálogo y recalcula `descuento_porcentaje` desde `descuento_monto` (400 si el descuento excede la línea). Totales recalculados en memoria sobre los detalles vigentes. Si la orden queda con ítems y estaba en PREPARANDO/ENTREGADA vuelve a PENDIENTE (reentra a cocina); una lista vacía deja los totales en 0.00 sin forzar estado. El estado terminal (PAGADA/CANCELADA) nunca se toca. Frontend: modo edición de `#modal-order` precarga los ítems existentes (con `_detalleId`), muestra "Tu comanda" y al confirmar hace `PUT` con la lista completa.
- **Pagar orden**: `PUT /ordenes/{id}/pagar` sets PAGADA + LIBRE in a single transaction. If mesa_id is null (para llevar), only sets PAGADA.
- **Orden state machine**: `PENDIENTE → PREPARANDO → ENTREGADA → PAGADA` (any state can also → CANCELADA). Invalid transitions return 400.
- **Adelantos de Salario**: `AdelantoSalario` model linked to Empleado + Nomina (via `total_adelantos`); auto-creates a `Gasto` (OPERATIVO) on registration; deducted from `pago_neto` in nomina calculations; API at `POST /nomina/adelantos`, `GET /nomina/empleados/{id}/adelantos`
- **Descuentos**: Per-item (`descuento_porcentaje` / `descuento_monto` + `motivo_descuento` on `DetalleOrden`) or global (distributed proportionally). `Orden.subtotal` is sum of line totals before discount; `descuento_total` is total discount; `Orden.total = subtotal - descuento_total`. Discounts applied via `POST /ordenes/{id}/descuento-item` and `POST /ordenes/{id}/descuento-global`. Removed via `DELETE /ordenes/{id}/descuento-item/{detalle_id}`. **Al crear/editar comanda**: el botón ✏️ de cada ítem del modal solicita un Descuento en C$ (`aplicarDescuentoItemModal()`), se envía como `descuento_monto` en `DetalleOrdenCreate` (create + `POST /ordenes/{id}/items`), y el backend lo aplica en `_procesar_detalles()` (valida que no exceda el total de la línea, 400 en caso contrario).
- **Cierre de caja**: `POST /caja/cierre` creates `CierreCaja` + links PAGADA orders AND all unarchived gastos via `cierre_caja_id` FK.
- **Mesa states**: LIBRE, OCUPADA, RESERVADA, MANTENIMIENTO
- **Apodo temporal de mesa**: `Mesa.apodo` (VARCHAR 100, nullable) guarda un apodo temporal para rastrear al cliente si se movió de mesa (ej: "Mesa 1" → "Juan"). Solo se puede asignar a mesas OCUPADA vía `PATCH /salon/mesas/{id}/apodo` (cualquier rol autenticado; apodo vacío lo limpia). Se **borra automáticamente** siempre que la mesa vuelve a LIBRE por cualquier vía: `pagar_orden` (`orden_service.py`), `PATCH /mesas/{id}/estado`, `PUT /mesas/{id}` con estado LIBRE, y `_fix_orphaned_mesas()` (startup). Se muestra únicamente en el mapa de Salón (tarjeta de mesa + modal de mesa ocupada); KDS y pre-cuenta NO lo muestran. Frontend: input `#oc-apodo-input` + `#btn-save-apodo` en el modal de mesa ocupada (`guardarApodo()` → PATCH); `escHtml()` sanitiza el apodo en las tarjetas.
- **Insumo**: `cantidad_actual` adjusted via `tipo: ENTRADA|SALIDA` movements; optional `unidad_empaque_id` FK + `factor_empaque` (1 empaque = X base); conversion in stock/recipes uses per-insumo packaging factor before falling back to global chain
- **Unidad base change migration**: When editing insumo's `unidad_medida_id`, backend requires `factor_conversion_unidad` (how many new units in 1 old unit); auto-converts `cantidad_actual`, `costo_unitario`, and all linked `Receta.cantidad_necesaria` rows using the old unit; frontend shows equivalence modal with old/new unit names
- **CategoríaInsumo**: Dynamic categories; delete guarded if category has associated insumos
- **UnidadMedida**: Dynamic units (nombre, abreviatura, tipo_magnitud: PESO/VOLUMEN/UNIDAD/PERSONALIZADO, unidad_base_id FK, factor_conversion); delete guarded if unit has associated insumos; startup migration `_fix_unidades_medida()` corrects magnitudes and conversion chains for all 15 standard units
- **Gastos operativos**: `Gasto` table tracks operational expenses (categoría: OPERATIVO, MANTENIMIENTO, SUMINISTROS, SERVICIOS, IMPUESTOS, OTROS)
- **Gastos auto-generados**: Every SALIDA de inventario (manual or recipe-based) auto-creates a `Gasto` with `categoria=SUMINISTROS` and `monto=cantidad×costo_unitario`. No setea `registrado_por` (queda `None`).
- **Reportes financieros**: `utilidad_neta = ingresos_totales - gastos_nomina - costo_insumos - gastos_operativos` — flujo de caja real: `costo_insumos` = gastos SUMINISTROS únicamente (NO costo teórico de recetas, para evitar doble contabilidad)
- **Archivado**: `Orden.cierre_caja_id` FK links orders to cierre session; `Gasto.cierre_caja_id` FK links gastos to cierre session; `historial-diario` filters `cierre_caja_id IS NULL` for both orders and gastos.
- **Dynamic zones**: `Zona` model with FK from Mesa; delete guarded if zone has mesas
- **Dynamic menu categories**: `CategoriaMenu` model, backend CRUD, delete guarded
- **Dynamic inventory categories & units**: `CategoriaInsumo` + `UnidadMedida` models; `Insumo` uses `unidad_medida_id` FK + `categoria_id` FK
- **Nómina calculations**: `pago_base` = salario del período (semanal = mensual/4, quincenal = mensual/2, mensual = mensual completo según días del rango); `tarifa_hora = salario_base / 240` (1.0x); `pago_neto = pago_base + (total_horas_extras × tarifa_hora) - total_adelantos` (mínimo 0). No se recalculan horas ordinarias trabajadas. Nuevas columnas `salario_semanal_teorico` y `salario_periodo_teorico` (migración `_migrate_nomina_periodos()`).
- **Recalculación de nómina**: `NominaCalcularRequest` acepta `recalcular: bool = False`. Si `recalcular=True` y ya existe una nómina `PENDIENTE` para el empleado/período, `POST /nomina/calcular` recalcula los montos con la fórmula actual y **actualiza** el registro existente (no crea duplicado); si la existente está `PAGADO` responde 400. `PUT /nomina/{id}/recalcular` (Admin/Gerente) hace lo mismo sobre una nómina por ID: 404 si no existe, 400 si no está `PENDIENTE`. La actualización solo toca los campos numéricos (preserva `estado` y `fecha_pago`). Se usa para corregir nóminas pendientes creadas con el esquema de cálculo anterior.
- **Frontend recalculación**: botón 🔄 (icono `sync`) en cada ítem del Historial de Nóminas (`#nomina-history-list`) solo cuando la nómina está `PENDIENTE` y marcado `.admin-only` (`recalcularNominaRegistro(id)` → `PUT /nomina/{id}/recalcular`). Al presionar "Calcular Nómina", si la API responde "Ya existe nómina registrada", `calcularNomina()` pide confirmación ("¿Deseas recalcular los montos con el esquema actual?") y reenvía con `recalcular: true`; usa `api(..., { silent: true })` para que la primera llamada no muestre el toast de error antes de la confirmación.

## API Endpoints Summary

| Method | Path                                        | Auth     | RBAC              |
|--------|---------------------------------------------|----------|--------------------|
| POST   | /api/v1/auth/login                          | No       | —                  |
| GET    | /api/v1/auth/me                             | Yes      | Any (sesión propia) |
| GET    | /api/v1/personal/puestos                    | Yes      | Any                |
| POST   | /api/v1/personal/puestos                    | Yes      | Admin, Gerente     |
| POST   | /api/v1/personal/empleados                  | Yes      | Admin, Gerente     |
| GET    | /api/v1/personal/empleados                  | Yes      | Any                |
| PUT    | /api/v1/personal/empleados/{id}             | Yes      | Admin, Gerente     |
| DELETE | /api/v1/personal/empleados/{id}             | Yes      | Admin, Gerente     |
| POST   | /api/v1/personal/usuarios                   | Yes      | Admin, Gerente     |
| GET    | /api/v1/personal/usuarios                   | Yes      | Any                |
| DELETE | /api/v1/personal/usuarios/{id}              | Yes      | Admin, Gerente     |
| PUT    | /api/v1/personal/usuarios/{id}/reset-password | Yes    | Admin, Gerente     |
| PATCH  | /api/v1/personal/usuarios/turno-masivo      | Yes      | Admin, Gerente     |
| PATCH  | /api/v1/personal/usuarios/{id}/turno        | Yes      | Admin, Gerente     |
| POST   | /api/v1/asistencia/turnos                   | Yes      | Admin, Gerente     |
| GET    | /api/v1/asistencia/turnos                   | Yes      | Any                |
| POST   | /api/v1/asistencia/turnos/iniciar/{id} | Yes      | Any |
| PUT    | /api/v1/asistencia/turnos/{id}         | Yes      | Admin, Gerente     |
| DELETE | /api/v1/asistencia/turnos/{id}         | Yes      | Admin, Gerente     |
| POST   | /api/v1/asistencia/turnos/heartbeat/{id} | Yes      | Any                |
| POST   | /api/v1/asistencia/check-in                 | Yes      | Any                |
| POST   | /api/v1/asistencia/check-out                | Yes      | Any                |
| GET    | /api/v1/asistencia/activa                   | Yes      | Any                |
| GET    | /api/v1/asistencia/empleados/{id}/historial | Yes      | Any                |
| PUT    | /api/v1/asistencia/{id}/horas-extras        | Yes      | Admin, Gerente     |
| PUT    | /api/v1/asistencia/{id}/editar-horarios     | Yes      | Admin, Gerente     |
| DELETE | /api/v1/asistencia/{id}                     | Yes      | Admin, Gerente     |
| POST   | /api/v1/menu/items                          | Yes      | Admin, Gerente     |
| GET    | /api/v1/menu/items                          | Yes      | Any                |
| GET    | /api/v1/menu/items/{id}                     | Yes      | Any                |
| PUT    | /api/v1/menu/items/{id}                     | Yes      | Admin, Gerente     |
| DELETE | /api/v1/menu/items/{id}                     | Yes      | Admin, Gerente     |
| POST   | /api/v1/menu/items/{id}/imagen              | Yes      | Admin, Gerente     |
| GET    | /api/v1/menu/categorias                     | Yes      | Any                |
| POST   | /api/v1/menu/categorias                     | Yes      | Admin, Gerente     |
| DELETE | /api/v1/menu/categorias/{id}                | Yes      | Admin, Gerente     |
| POST   | /api/v1/inventario/insumos                  | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/insumos                  | Yes      | Any                |
| GET    | /api/v1/inventario/insumos/{id}             | Yes      | Any                |
| PATCH  | /api/v1/inventario/insumos/{id}/stock       | Yes      | Admin, Gerente     |
| PATCH  | /api/v1/inventario/insumos/{id}             | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/insumos/alertas          | Yes      | Any                |
| GET    | /api/v1/inventario/insumos/lote-ids         | Yes      | Any                |
| POST   | /api/v1/inventario/movimientos              | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/ingredientes             | Yes      | Any                |
| POST   | /api/v1/inventario/ingredientes             | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/ingredientes/alertas     | Yes      | Any                |
| GET    | /api/v1/inventario/ingredientes/{id}/historial | Yes    | Any                |
| GET    | /api/v1/inventario/proveedores              | Yes      | Any                |
| POST   | /api/v1/inventario/proveedores              | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/categorias-insumo         | Yes      | Any                |
| POST   | /api/v1/inventario/categorias-insumo         | Yes      | Admin, Gerente     |
| DELETE | /api/v1/inventario/categorias-insumo/{id}    | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/unidades-medida           | Yes      | Any                |
| POST   | /api/v1/inventario/unidades-medida           | Yes      | Admin, Gerente     |
| DELETE | /api/v1/inventario/unidades-medida/{id}      | Yes      | Admin, Gerente     |
| PUT    | /api/v1/inventario/unidades-medida/{id}      | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/unidades-medida/convertir | Yes      | Any                |
| POST   | /api/v1/inventario/preparaciones             | Yes      | Admin, Gerente     |
| GET    | /api/v1/inventario/preparaciones             | Yes      | Any                |
| GET    | /api/v1/salon/mapa                          | Yes      | Any                |
| GET    | /api/v1/salon/mesas                         | Yes      | Any                |
| POST   | /api/v1/salon/mesas                         | Yes      | Admin, Gerente     |
| PUT    | /api/v1/salon/mesas/{id}                    | Yes      | Admin, Gerente     |
| DELETE | /api/v1/salon/mesas/{id}                    | Yes      | Admin, Gerente     |
| PATCH  | /api/v1/salon/mesas/{id}/estado             | Yes      | Any                |
| PATCH  | /api/v1/salon/mesas/{id}/apodo               | Yes      | Any                |
| POST   | /api/v1/salon/zonas                         | Yes      | Admin, Gerente     |
| GET    | /api/v1/salon/zonas                         | Yes      | Any                |
| DELETE | /api/v1/salon/zonas/{id}                    | Yes      | Admin, Gerente     |
| POST   | /api/v1/ordenes/                            | Yes      | Any                |
| POST   | /api/v1/ordenes/retroactiva                  | Yes      | Admin, Gerente     |
| GET    | /api/v1/ordenes/                            | Yes      | Any                |
| GET    | /api/v1/ordenes/{id}                        | Yes      | Any                |
| PATCH  | /api/v1/ordenes/{id}/estado                 | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/items                  | Yes      | Any                |
| PUT    | /api/v1/ordenes/{id}/items                  | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/descuento-item         | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/descuento-global       | Yes      | Any                |
| DELETE | /api/v1/ordenes/{id}/descuento-item/{detalle_id} | Yes  | Any                |
| POST   | /api/v1/ordenes/{id}/anular                 | Yes      | Admin, Gerente     |
| POST   | /api/v1/ordenes/{id}/devolver-item          | Yes      | Admin, Gerente     |
| PUT    | /api/v1/ordenes/{id}/pagar                  | Yes      | Any                |
| GET    | /api/v1/caja/historial-diario               | Yes      | Any                |
| GET    | /api/v1/caja/ventas-dia                     | Yes      | Any                |
| POST   | /api/v1/caja/cierre                         | Yes      | Admin, Gerente     |
| POST   | /api/v1/gastos/                             | Yes      | Admin, Gerente     |
| GET    | /api/v1/gastos/                             | Yes      | Admin, Gerente     |
| PUT    | /api/v1/gastos/{id}                         | Yes      | Admin, Gerente     |
| DELETE | /api/v1/gastos/{id}                         | Yes      | Admin, Gerente     |
| GET    | /api/v1/auditoria/                          | Yes      | Admin, Gerente     |
| GET    | /api/v1/estudio-mercado/                    | Yes      | Admin, Gerente     |
| POST   | /api/v1/estudio-mercado/generar             | Yes      | Admin, Gerente     |
| GET    | /api/v1/estudio-mercado/{id}                | Yes      | Admin, Gerente     |
| GET    | /api/v1/estudio-mercado/{id}/exportar       | Yes      | Admin, Gerente     |
| DELETE | /api/v1/estudio-mercado/{id}                | Yes      | Admin, Gerente     |
| GET    | /api/v1/estudio-mercado/documentos          | Yes      | Admin, Gerente     |
| POST   | /api/v1/estudio-mercado/documentos          | Yes      | Admin, Gerente     |
| DELETE | /api/v1/estudio-mercado/documentos/{id}     | Yes      | Admin, Gerente     |
| GET    | /api/v1/estudio-mercado/chat/historial      | Yes      | Admin, Gerente     |
| POST   | /api/v1/estudio-mercado/chat               | Yes      | Admin, Gerente     |
| DELETE | /api/v1/estudio-mercado/chat/historial      | Yes      | Admin, Gerente     |
| GET    | /api/v1/push/config                         | Yes      | Any                |
| GET    | /api/v1/push/preferencias                   | Yes      | Any (propia)       |
| PATCH  | /api/v1/push/preferencias                   | Yes      | Any (propia)       |
| PATCH  | /api/v1/personal/usuarios/{id}/avisos       | Yes      | Admin, Gerente     |
| POST   | /api/v1/push/subscribe                      | Yes      | Any                |
| POST   | /api/v1/push/unsubscribe                    | Yes      | Any                |
| GET    | /api/v1/push/subscriptions                  | Yes      | Any                |
| DELETE | /api/v1/push/subscriptions/{id}             | Yes      | Any (propia)       |
| GET    | /api/v1/descuentos/                         | Yes      | Any                |
| POST   | /api/v1/descuentos/                         | Yes      | Admin, Gerente     |
| PUT    | /api/v1/descuentos/{id}                     | Yes      | Admin, Gerente     |
| DELETE | /api/v1/descuentos/{id}                     | Yes      | Admin, Gerente     |
| GET    | /api/v1/calendario/?desde=&hasta=            | Yes      | Any                |
| POST   | /api/v1/calendario/eventos                   | Yes      | Admin, Gerente     |
| PUT    | /api/v1/calendario/eventos/{id}              | Yes      | Admin, Gerente     |
| DELETE | /api/v1/calendario/eventos/{id}              | Yes      | Admin, Gerente     |
| GET    | /api/v1/reportes/cierre?periodo=            | Yes      | Admin, Gerente     |
| GET    | /api/v1/nomina/pendientes                   | Yes      | Any                |
| POST   | /api/v1/nomina/calcular                     | Yes      | Any                |
| POST   | /api/v1/nomina/generar                      | Yes      | Admin, Gerente     |
| PUT    | /api/v1/nomina/{id}/pagar                   | Yes      | Admin, Gerente     |
| PUT    | /api/v1/nomina/{id}/recalcular              | Yes      | Admin, Gerente     |
| GET    | /api/v1/nomina/empleado/{id}                | Yes      | Any                |
| GET    | /api/v1/nomina/empleados/{id}/historial     | Yes      | Any                |
| POST   | /api/v1/nomina/adelantos                    | Yes      | Admin, Gerente     |
| GET    | /api/v1/nomina/empleados/{id}/adelantos     | Yes      | Any                |
| GET    | /api/v1/analitica/cierre-caja               | Yes      | Admin, Gerente     |
| GET    | /api/public/menu                            | No       | Pública (solo lectura) |
| GET    | /api/public/categories                      | No       | Pública (solo lectura) |
| GET    | /api/public/menu/{categoria_id}             | No       | Pública (solo lectura) |
| GET    | /api/public/item/{item_id}                  | No       | Pública (solo lectura) |
| GET    | /healthcheck                                | No       | —                  |

### Query Parameters

| Endpoint | Params | Descripción |
|----------|--------|-------------|
| `GET /ordenes/` | `?estado=&mesa_id=` | Filtrar por estado de orden y/o mesa específica |
| `GET /gastos/` | `?fecha_inicio=&fecha_fin=` | Filtrar gastos por rango de fechas |
| `GET /nomina/empleados/{id}/adelantos` | `?fecha_inicio=&fecha_fin=` | Filtrar adelantos por rango de fechas |
| `GET /menu/items` | `?incluir_inactivos=true` | Incluir platillos deshabilitados (solo Admin/Gerente) |

## API Pública (Carta Digital)

Endpoints de solo lectura **consumidos por la Carta Digital** (menú público para clientes vía QR). **No requieren autenticación** y reutilizan exactamente los modelos actuales (`CategoriaMenu`, `MenuItem`) sin duplicar información.

- `GET /api/public/menu` → todos los platos con `disponible=True`
- `GET /api/public/categories` → todas las categorías
- `GET /api/public/menu/{categoria_id}` → platos disponibles filtrados por categoría (id, `gt=0`)
- `GET /api/public/item/{item_id}` → plato disponible por id (404 si no existe o no está disponible)

**Seguridad**: los endpoints públicos NUNCA exponen costos, recetas/insumos, inventario interno, usuarios ni roles. `MenuItemPublicoResponse` y `CategoriaMenuPublicaResponse` (en `app/schemas/menu_publico.py`) solo serializan `id`, `nombre`, `descripcion`, `precio`, `disponible`, `imagen_url`, `tiempo_preparacion`, `categoria`. La lógica reutilizable vive en `MenuService`/`MenuRepository`:

- `MenuRepository._query_items_base(incluir_insumos)` — consulta base compartida; `incluir_insumos=False` NO carga recetas/insumos (uso público)
- `MenuRepository.obtener_items_publicos(categoria_id=None)` / `obtener_item_publico_por_id(item_id)` — solo platos `disponible=True`
- `MenuService.obtener_menu_publico()` / `obtener_categorias_publicas()` / `obtener_item_publico_por_id()` — reutilizan los repos públicos
- Router `app/api/endpoints/menu_publico.py` registrado en `main.py` bajo prefijo `/api/public`

### Carta Digital — Frontend público y separación ERP/Pública

La Carta Digital es un frontend **completamente separado del POS** (sin autenticación, sin acceso al ERP) servido por FastAPI como archivos estáticos:

- `app/Templates/carta/index.html` — página pública (mobile-first, UI en español, C$)
- `app/Templates/carta/css/style.css` — estilos propios de la carta (design tokens idénticos al POS)
- `app/Templates/carta/js/app.js` — consumidor de la API pública; `API_BASE` detecta local (`http://127.0.0.1:8000/api/public`) vs remoto (`${location.origin}/api/public`); `PLACEHOLDER_IMG = 'img/placeholder-dish.svg'`
- **Curaduría pública de categorías** (solo carta, ERP intacto): `curarCategorias()` en `app.js` filtra y ordena lo que ve el cliente — oculta `CATEGORIAS_OCULTAS` ("Especialidades de la Casa", "Algo para Picar"), excluye categorías sin platillos disponibles y aplica `ORDEN_CATEGORIAS` estricto (Platos Ejecutivos, Platos Fuertes, Mariscos, Zona Caribeña, Para Compartir, Bebidas, Extras); categorías no listadas se agregan al final. Matching por nombre normalizado (lowercase + sin acentos). No hay chip "Todo": la vista principal es un grid de tarjetas de categoría (`renderCategoryCards()`); al seleccionar una categoría se muestran sus platillos y el chip "Categorías" vuelve al overview
- `app/Templates/carta/img/` — assets locales únicos de la carta: `hero-desktop.jpg`, `hero-mobile.jpg`, `logo.png`, `logo-small.png`, `placeholder-dish.svg`. **No hay imágenes remotas ni dependencias de Stitch.**
- `app/Templates/carta/img/platos/` — directorio gestionado por el ERP vía subida de imágenes (creado con `os.makedirs(exist_ok=True)` al subir)

Montado en `app/main.py` con `app.mount("/carta", StaticFiles(directory="app/Templates/carta", html=True), name="carta")` — la URL pública es `/carta/` (index.html por defecto). El mount `/carta` es el que sirve también las imágenes de platos (`/carta/img/platos/<file>`).

**Flujo completo (de punta a punta):**

```
ERP (POS)                     API Pública                    Carta Digital              Cliente
─────────                     ───────────                    ─────────────              ───────
Gestión de Menú        →      GET /api/public/menu     →      js/app.js fetch()   →     escanea QR
│  · Admin/Gerente            GET /api/public/categories      renderChips()/renderBento()   abre /carta/
│  · CRUD platillos           GET /api/public/menu/{cat}      renderSections()          explora
│  · disponible toggle        GET /api/public/item/{id}       openModal() detalle        · foto · precio
│  · tiempo_preparacion                                       · descripción · disponib.  · descripción
│  · imagen (multipart)                                       · "Preparación: ~N min"    · disponibilidad
└──→ POST /menu/items/{id}/imagen                                (placeholder si imagen null)
        escribe app/Templates/carta/img/platos/ ──servido por /carta──►
```

La Carta Digital **solo lee** a través de `/api/public`; nunca toca el ERP ni sus endpoints `/api/v1`. La única vía de escritura es la del Administrador/Gerente en Gestión de Menú (datos + imágenes), que alimenta la misma base de datos. `disponible=False` (incluido el borrado lógico) oculta el plato de la carta inmediatamente.

## Key Backend Patterns

### OrdenService state machine: `TRANSICIONES_VALIDAS`
```python
TRANSICIONES_VALIDAS = {
    PENDIENTE:  {PREPARANDO, CANCELADA},
    PREPARANDO: {ENTREGADA, CANCELADA},
    ENTREGADA:  {PAGADA, CANCELADA},
    PAGADA:     set(),  # terminal
    CANCELADA:  set(),  # terminal
}
```
Invalid transitions return `400: No se puede cambiar de '{actual}' a '{nuevo}'`.

### OrdenService stock management
- `validar_stock_suficiente()` — validates all recipe ingredients have enough stock before any order operations
- `descontar_stock()` — deducts stock, creates `MovimientoInventario` (SALIDA), auto-generates `Gasto` (SUMINISTROS)
- `revertir_stock()` — reverses all ingredient stock on cancellation, creates ENTRADA audit trail
- `_procesar_detalles()` — delegates to the three named functions; applies per-item C$ discount (`DetalleOrdenCreate.descuento_monto`/`motivo_descuento`), validates discount ≤ line total (400 otherwise), computes `descuento_porcentaje`, and returns `(detalles, subtotal, descuento_total)`; used by both `crear_orden()` and `agregar_items_canonico()`
- `cambiar_estado()` — calls `revertir_stock()` inside `begin_nested()` when transitioning to CANCELADA

### Gastos module
- `Gasto` model with `CategoriaGasto` enum (OPERATIVO, MANTENIMIENTO, SUMINISTROS, SERVICIOS, IMPUESTOS, OTROS)
- `GastoService.registrar_gasto_automatico()` — creates SUMINISTROS gastos from SALIDA inventory movements
- `InventarioService.registrar_movimiento()` — calls `gasto_service.registrar_gasto_automatico()` when `tipo=SALIDA`
- `ReportesRepository.obtener_gastos_clasificados()` — classifies gastos-table records in a date range into 3 buckets: `costo_insumos` (categoría SUMINISTROS), `gastos_nomina` (gastos ligados a `adelantos_salario`), `gastos_operativos` (OPERATIVO/MANTENIMIENTO/SERVICIOS/IMPUESTOS/OTROS)
- `ReportesRepository.obtener_gastos_clasificados_sin_archivar()` — same classification for unarchived gastos (`cierre_caja_id IS NULL`); used by the DIARIO caja dashboard
- `ReportesService.obtener_cierre()` — utilidad_neta subtracts gastos_nomina + costo_insumos + gastos_operativos; `gastos_nomina` suma los adelantos de la tabla gastos sobre el `pago_neto` de la tabla Nominas, y `costo_insumos` es SOLO el bucket SUMINISTROS de la tabla gastos (el costo teórico de recetas NO se usa para evitar doble contabilidad)
- **Frontend**: `#screen-gastos` with sortable table, `#modal-registrar-gasto` form (with date picker); `loadGastos()` fetches `GET /gastos/`, `guardarGasto()` posts `POST /gastos/` with optional `fecha`; Admin/Gerente only via `.nav-item-admin`

### Descuentos predeterminados (catálogo de promociones)
- `DescuentoFrecuente` model (`descuentos_frecuentes`): `nombre` (unique), `tipo` (`TipoDescuento`: PORCENTAJE/MONTO), `valor`, `activo`. Es un **catálogo global reutilizable**, no está ligado a un platillo.
- Endpoints: `GET /descuentos/?solo_activos=` (todos los roles), `POST/PUT/DELETE /descuentos/{id}` (Admin/Gerente)
- **Ubicación en la UI (v6.19)**: la pantalla `#screen-descuentos` **ya no tiene entrada propia en el sidebar** (se eliminó para ahorrar espacio). Se accede desde el **botón `#btn-carta-descuentos`** (clase `.admin-only`) en el header de la pantalla **Carta** (`#screen-menu-view`) → `navigateTo('descuentos')`. El header de la pantalla tiene el botón **`#btn-descuentos-volver`** ("← Volver a Carta") → `navigateTo('menu-view')`.
- **Guard de rol**: `navigateTo()` fuerza `menu-view` con toast de advertencia si un no-gestor intenta `descuentos` (defensa en profundidad; el botón ya está oculto por CSS para Vendedor)
- **Frontend**: `#descuentos-list` (grid de tarjetas con nombre, tipo, valor y acciones ✏️ Editar / 🗑️ Eliminar), `#modal-descuento` (`#descuento-form`, toggle `#desc-toggle` para tipo, `#desc-valor-label` dinámico); `loadDescuentos()`, `openNuevoDescuento()`, `openEditarDescuento(id)`, `guardarDescuento()`, `eliminarDescuento(id)`. Los descuentos activos también se ofrecen como "descuentos rápidos" dentro de la comanda (`GET /descuentos/?solo_activos=true`, `silent: true`)

### Kitchen production (batch preparation)
- `PreparacionCocina` + `DetallePreparacionCocina` models in `app/models/inventario.py`
- `Receta.descuento_por_lote` boolean — when True, ingredient is NOT deducted per-plato but only via batch production
- `PreparacionService.registrar_preparacion()` — validates stock, deducts ingredients, creates `MovimientoInventario` (SALIDA) + auto-generated `Gasto` (SUMINISTROS) + `DetallePreparacionCocina` records
- `POST /inventario/preparaciones` — Admin/Gerente only; auto-links to active asistencia if any
- `GET /inventario/preparaciones` — lists today's preparations with detalles
- `OrdenService.descontar_stock()` / `revertir_stock()` / `validar_stock_suficiente()` all skip ingredients where `descuento_por_lote=True`
- **Frontend**: "🍳 Producción del Día" button in `#screen-menu-mgmt` header; `#modal-preparacion` with dynamic insumo rows (select + quantity); `openPreparacionModal()` loads insumos; `submitPreparacion()` posts to endpoint; recipe rows have "Lote" checkbox to toggle `descuento_por_lote`

### Venta retroactiva (ventas de días pasados)
- `POST /ordenes/retroactiva` — creates and pays an order directly with a custom `fecha_creacion`; Admin/Gerente only
- `VentaRetroactivaCreate` schema: `fecha` (required), `mesa_id` (optional — null for direct sales), `detalles` (list of `producto_id` + `cantidad`)
- No inventory deduction (historical record); no table state mutation; order created as `PAGADA` immediately
- `Orden.mesa_id` is nullable (startup migration `_migrate_orden_mesa_nullable()`); NULL = venta directa / para llevar
- **Frontend**: `#modal-venta-retroactiva` in Cierre de Caja screen; "Venta Pasada" button (admin-only via `.admin-only`); dynamic item rows with product select + quantity; auto-calculated total; mesa select grouped by zone

### Personal module — salary per employee
- `Empleado` model has its own `salario_base` column (NOT inherited from `Puesto`)
- `Puesto.salario_base` is the default value used when creating new employees; employees can have individual overrides
- `NominaService` uses `empleado.salario_base` (not `empleado.puesto.salario_base`) for all payroll calculations
- `Empleado` also has optional `telefono` column (VARCHAR(20))
- **Frontend**: Employee table shows `C$` prefix; new employee modal has `telefono` field + `C$` salary label; `saveNuevoEmpleado()` sends `salario_base` + `telefono` directly in employee body
- **Baja de empleado (borrado lógico con autorización)**: `DELETE /personal/empleados/{id}` (Admin/Gerente) recibe `{password}` en el body; `PersonalService.dar_de_baja_empleado()` valida la contraseña del usuario en sesión vía `verificar_password()` (401 si es incorrecta), bloquea auto-baja (400) y baja ya inactiva (400), desactiva `Empleado.activo` y `Usuario.activo` vinculado (sin tocar asistencias/nóminas históricas). Frontend: botón 🗑️ en columna Acciones (`.admin-only`), `#modal-eliminar-empleado` con advertencia "¿Estás seguro...?" + input de contraseña; `confirmEliminarEmpleado()` hace DELETE y recarga la tabla.
- **Avisos push por usuario (gerencia)**: botón 🔔 (`.emp-action .emp-amber .admin-only`) en la columna Acciones de Personal → `#modal-avisos-usuario` (`openAvisosUsuarioModal(id, nombre)` carga los flags frescos de `GET /personal/usuarios`, `confirmAvisosUsuario()` hace `PATCH /personal/usuarios/{id}/avisos`). "Todas las comandas" se deshabilita si "Avisos de mesero" está apagado (`sincronizarFilasAvisosUsuario()`). Si gerencia edita su propio usuario, el panel de Notificaciones se resincroniza (`sincronizarEstadoPush()`).

### Menu categories (dynamic)
- `CategoriaMenu` model (id, nombre, descripcion) with `MenuItem.categoria_id` FK
- `GET /menu/categorias` → all categories; `POST /menu/categorias` → create; `DELETE /menu/categorias/{id}` → delete (guarded: 400 if category has platillos)
- **Frontend**: `#screen-menu-mgmt` has `#menu-mgmt-cat-filters` chip row dynamically populated from `GET /menu/categorias`; `#modal-dish` has ⚙️ toggle button → `#cat-panel` (collapsible) with input + save + list with delete buttons; `loadCategorias()` fetches categories, `guardarCategoriaMenu()` posts, `eliminarCategoriaMenu()` deletes; filter logic via `activeMgmtCatFilter` + `applyMenuMgmtFilter()`

### Subida de imágenes y tiempo de preparación (Carta Digital)
- `MenuItem` model has `imagen_url` (String 500, nullable) and `tiempo_preparacion` (Integer nullable, minutos) — documented in the model comments
- **`imagen_url` is server-managed ONLY**: it is NOT accepted in `MenuItemCreate`/`MenuItemUpdate`; clients can never write paths/URLs manually
- `POST /menu/items/{id}/imagen` (Admin/Gerente) receives multipart field `archivo`; `MenuService.subir_imagen()` validates the image **by content with Pillow** (`Image.open` + `verify()` — independent of MIME/extension, which varies by device), size ≤ 15 MB (`IMAGEN_MAX_BYTES`), optimizes via `MenuService._procesar_imagen_webp()` (EXIF transpose, verify, resize to max width 1080px, WebP quality 80%), encodes to Base64, uploads to ImgBB with **up to `IMGBB_INTENTOS` (3) attempts + backoff** (`IMGBB_BACKOFF_SEGUNDOS`) for transient network errors/5xx, extracts `data.url`, and persists it in `imagen_url`; every failure path (corrupt/non-image/file >15MB/ImgBB) raises HTTPException 400/502 (never a silent no-op)
- **ImgBB integration**: Uses `httpx` to POST to ImgBB with `key` + Base64 `image` param; no `expiration` param = permanent storage; timeout 30s; 4xx raises immediately (502 with status), network/5xx retried then 502; missing `IMGBB_API_KEY` raises 500
- **Frontend compression (nuevo)**: `compressImageFile()` re-encodea la foto en el navegador (canvas → máx. 1600px, WebP ~85%, fallback JPEG) antes de subirla — evita el rechazo por tamaño, acelera la subida, y en iPhone Safari convierte HEIC→WebP/JPEG automáticamente; si el navegador no decodifica la imagen → mensaje "No se pudo procesar esta foto…"
- **Optimización de imágenes (Carta Digital)**: todas las imágenes subidas se almacenan ya comprimidas (WebP q80, ≤1080px de ancho) para carga rápida; el frontend usa `loading="lazy"` + `decoding="async"` en platillos/tarjetas y un skeleton shimmer CSS (`.card-media`/`.cat-card`/`.modal-media` sin `.img-loaded`) que se detiene vía listener capture de eventos `load`/`error` en `app.js`
- **Backward compatibility**: Existing images stored locally at `/carta/img/platos/` still work — `imagen_url` accepts any URL format; Carta Digital's `imgFor(item)` handles both local and external URLs
- `MenuItemResponse` and `MenuItemPublicoResponse` expose `imagen_url` + `tiempo_preparacion`; `MenuItemCreate`/`MenuItemUpdate` accept `tiempo_preparacion` only
- Startup migration `_migrate_menu_item_imagen_tiempo()` (idempotent via `information_schema`) adds both columns
- **Frontend POS**: `#modal-dish` has file input `#dish-image` (accept png/jpeg/webp/gif) + `#dish-prep-time` (minutes) + live preview (`previewDishImage()`); `saveDish()` sends `tiempo_preparacion` en el JSON y, si se eligió archivo, lo comprime con `compressImageFile()` y lo sube tras guardar vía `uploadDishImage()` (`FormData` + `Content-Type: undefined` so fetch sets the multipart boundary); feedback explícito: éxito → "Platillo guardado — imagen actualizada", fallo → "Platillo guardado, pero la imagen falló: <motivo>" y el modal permanece abierto con el archivo intacto (nunca skip silencioso); `openEditDish()`/`resetDishImage()` limpian el input para evitar archivos fantasma; `renderMenuMgmt()` shows thumbnail + "⏱️ ~N min"
- **Carta Digital**: `imgFor(item)` returns `item.imagen_url` or the local placeholder `img/placeholder-dish.svg`; `openModal()` shows "Preparación: ~N min" in the timer pill (falls back to category); hero/logos are local assets in `app/Templates/carta/img/` — no remote images, no Stitch dependencies

### Hora local fija Nicaragua (America/Managua) en asistencia
- Todo timestamp de asistencia se almacena como **hora local fija de Managua sin offset y SIN conversión** (naive `DATETIME`): lo que envía el formulario es exactamente lo que queda en la BD
- Helper central: `app/core/tiempo.py` — `ahora_local()` / `hoy_local()` / `ventana_dia_negocio()` via `ZoneInfo("America/Managua")` (requiere `tzdata` en requirements.txt); usado por `asistencia_service.py`, `turno_service.py`, `asistencia_repository.py`
- **Día de negocio**: `ventana_dia_negocio(t)` devuelve `(inicio, fin)` del "hoy" laboral — ventana de 24h que corte a la `HORA_INICIO_DIA` (config `.env`, default 7 AM). Ej: 2026-09-28 01:00 → `[2026-09-27 07:00, 2026-09-28 07:00)`; 07:00 marca el salto al día nuevo. Solo aplica a los guards de "hoy" (iniciar turno / check-in / check-out); la columna `fecha` sigue siendo día calendario
- `editar_horarios` NO suma/resta horas: parsea `YYYY-MM-DDTHH:MM` y guarda tal cual (antes restaba 6h para UTC)
- Frontend helper `formatLocalTime(isoStr)` in `app.js` formatea el string de forma literal (extrae HH:MM y muestra 12h AM/PM) — NO usa `Date`, no agrega `'Z'`, no convierte zonas
- Modal Editar Horarios: prefill con `slice(0,16)` del string crudo; el valor del input se envía tal cual al backend
- All locale references use `es-NI` (Nicaragua, UTC-6) instead of `es-CO` (Colombia, UTC-5)
- MySQL `DATETIME` type strips timezone info on read; stored values remain correct local time
- `security.py` uses `datetime.now(timezone.utc)` for JWT token expiration (timezone-aware)
- Registros históricos previos al cambio están en UTC naive (+6h respecto a la hora real local); los nuevos writes ya son hora local

### Heartbeat auto-close background task
- `POST /asistencia/turnos/heartbeat/{id}` — updates `Asistencia.ultimo_heartbeat` timestamp
- Background `_heartbeat_watcher()` task runs every `HEARTBEAT_INTERVAL_SECONDS` (default: 300s / 5 min), queries `get_activas_sin_heartbeat()` for turnos **sin salida y ya deshabilitados** en `HEARTBEAT_TIMEOUT_SECONDS`
- **Regla del watcher**: un vendedor manteniene el turno abierto mientras (a) su usuario está `activo=True` Y (b) su `turno_habilitado=True` (o rol ≠ Vendedor). El watcher es un *fallback* de seguridad: solo cierra turnos cuyo dueño ya NO puede continuar — `Usuario.activo=False`, `Vendedor` con turno deshabilitado o sin usuario vinculado. La línea base es `COALESCE(ultimo_heartbeat, hora_entrada_real)` (incluye turnos cuyo primer heartbeat nunca llegó), y los registros anulados se excluyen.
- Stale turnos are auto-closed with `hora_salida_real = COALESCE(ultimo_heartbeat, hora_entrada_real)` and hours calculated normally
- Configurable via `.env`: `HEARTBEAT_INTERVAL_SECONDS` (BG check interval, default 300s) and `HEARTBEAT_TIMEOUT_SECONDS` (stale threshold, default 900s / 15 min)
- **Frontend**: `enviarHeartbeat()` (Vendedor con turno activo) usa el interceptor `api()` con `{method:'POST', keepalive:true, silent:true}`; si el back responde que el turno ya se cerró (400 con "salida" / "No se encontró la asistencia") limpia `state.currentAsistencia` + toast "Tu turno se cerró automáticamente…". `syncAsistenciaActiva()` realinea el turno activo contra `GET /asistencia/activa` (BD, no localStorage) y se dispara desde `iniciarIntervalosSesion()` (login/restore) y en `visibilitychange`/`focus`. `iniciarIntervalosSesion()` arranca en `login()` y en el restore de sesión el heartbeat (120 s) + el polling `verificarSesionTurno()` (60 s → `GET /auth/me`); ambos se limpian en `logout()`. Interceptor global `api()`: ante `403` con detail `TURNO_DESHABILITADO` / `USUARIO_DESACTIVADO` muestra toast + `logout()` automático (los sentinels se suprimen del toast genérico vía `ERRORES_SESION`); el toast de cierre se muestra incluso con `silent: true`. **Robustez offline (caída de internet)**: un `401` SOLO hace logout si es realmente de nuestra API (body JSON con `detail`) o si el token ya expiró localmente (`_jwtExpirado()` lee `exp` del payload sin verificar firma); portales cautivos/proxies del WiFi que responden 401 con HTML se tratan como pérdida de conexión → toast `"Sin conexión a internet — reintentando…"` SIN logout. Los errores de red (`TypeError`/"Failed to fetch") también muestran ese toast en español. `fetch` usa `cache: 'no-store'` (evita refrescos viejos tras subir imágenes) y `window 'online'` dispara `alVolverPestana()` (heartbeat + sync + poll) al reconectar.

### Gestión de Turnos CRUD
- `POST /asistencia/turnos` → create shift template (nombre, hora_entrada, horas_teoricas)
- `PUT /asistencia/turnos/{id}` → update (Admin/Gerente only)
- `DELETE /asistencia/turnos/{id}` → delete (Admin/Gerente only)
- `TurnoUpdate` schema for PUT body; `TurnoResponse` for list
- **Frontend**: `#modal-turnos` with inline CRUD; `calcularHoraSalida()` auto-computes `hora_salida` from `hora_entrada + horas_teoricas` using modulo 1440 for midnight crossover; `hora_salida` field is readonly/calculated

### Habilitación Dinámica de Turno (vendedores)
- `Usuario.turno_habilitado` (Boolean, default `False`, nullable `False`) controla si un usuario con rol `Vendedor` puede iniciar sesión.
- **Gate de login**: `POST /auth/login` devuelve `403` "Tu turno de trabajo no está habilitado actualmente por gerencia." si `rol == "Vendedor"` y `turno_habilitado == False`. Admin/Gerente omiten la verificación (no existen roles Mesero/Cocinero en `RolEnum`).
- `PATCH /personal/usuarios/{id}/turno` → body `{"turno_habilitado": bool}`; `PATCH /personal/usuarios/turno-masivo` → mismo body, actualiza a todos los `Vendedor`. Ambos Admin/Gerente. Respuestas: `TurnoUsuarioResponse {usuario, turnos_cerrados}` (individual) y `TurnoMasivoResponse {actualizados, turnos_cerrados}` (masivo) — `turnos_cerrados` = cuántos turnos abiertos se cerraron **como efecto de la deshabilitación** (0 si no había turnos abiertos), para que la gerencia vea el impacto real de la acción.
- **Cierre de asistencia al deshabilitar (regla ≤15 min)**: deshabilitar a un Vendedor con turno activo cierra su asistencia **en ese momento** (NO espera al watcher). `PersonalService.cambiar_turno_habilitado()` / `habilitar_turno_masivo()` llaman `AsistenciaService.cerrar_asistencias_por_deshabilitacion(empleado_ids, actor=current_user)` solo cuando el nuevo estado es `False` y el rol es Vendedor. La salida forzada: con heartbeat → `max(ultimo_heartbeat, ahora − HEARTBEAT_TIMEOUT)` (descuento garantizado ≤15 min; con app abierta ≤2 min); sin heartbeat → `hora_entrada_real` (no se inventa tiempo; gerencia corrige con Editar Horarios). Las horas extras se calculan desde la hora de salida programada del turno, nunca son negativas y se limitan a 99.99 horas. La misma regla se usa en check-out, edición de horarios y cierre automático. Idempotente: el UPDATE condicional solo cierra registros aún sin salida. `observaciones = "Cierre automático por deshabilitación de turno"`. El cierre queda **auditado** (`TURNO_CERRADO_AUTOMATICAMENTE`) y la API reporta cuántos turnos se cerraron (`turnos_cerrados`).
- **`POST /asistencia/check-out` sobre un turno ya cerrado → 409**: si la asistencia abierta ya fue cerrada automáticamente (deshabilitación o watcher), el check-out NO devuelve 200 con el registro cerrado (eso hacía creer al empleado que su salida quedó registrada); responde `409` con un `detail` que incluye la **hora de salida registrada**, la **causa** (`observaciones`) y la indicación de corregirla con Editar Horarios. Helper `_detalle_turno_ya_cerrado()` en `app/api/endpoints/asistencia.py`.
- **`iniciar_turno` idempotente**: `turno_service.iniciar_turno()` reusa la asistencia abierta existente (`get_abierta_por_empleado()`, la más antigua) — CERO duplicados ante doble clic/reenvío; si ya finalizó el turno del día de negocio vigente → `400 "Ya registraste y finalizaste tu turno hoy"` (el día no se reabre); las anuladas no bloquean (permiten re-marcar el mismo día). **El "hoy" NO es el día calendario** (los turnos de bar/restaurante cruzan medianoche): es la ventana 7:00 AM → 7:00 AM del `HORA_INICIO_DIA` (`ventana_dia_negocio()` en `app/core/tiempo.py`, configurable vía `.env`, default 7). Un turno iniciado a la 1:00 AM pertenece al servicio del día anterior. Los guards de `iniciar_turno`, check-in (`tiene_registro_hoy`) y el fallback de check-out usan `get_asistencia_del_dia_negocio()`, que consulta la ventana sobre `hora_entrada_real` (NOT NULL) — nunca sobre la columna `fecha` (fecha calendario, usada solo para historial/recortes/reporte y NO cambió). Entrada 6:59 AM = servicio anterior; a partir de las 7:00 AM abre el nuevo.
- **`GET /asistencia/activa`** (cualquier rol autenticado): devuelve `AsistenciaResponse | null` con la asistencia abierta del empleado logueado; `AsistenciaService.obtener_asistencia_activa()` realinea el panel contra la BD (no localStorage).
- Migración de startup `_migrate_usuarios_turno_habilitado()`: agrega la columna si falta y, **solo en la primera ejecución**, habilita (`= 1`) a los Vendedores ya existentes para no bloquearlos en el despliegue. En reinicios posteriores no toca el estado.
- Los Vendedores nuevos nacen con `turno_habilitado = False` y requieren habilitación de gerencia.
- **Invalidación de sesiones activas**: `get_current_user` (en `app/api/deps.py`) valida en **cada petición** el usuario fresco de BD — si `activo == False` → `403 USUARIO_DESACTIVADO`; si rol `Vendedor` y `turno_habilitado == False` → `403 TURNO_DESHABILITADO`. Esto corta de raíz las sesiones abiertas (todas las rutas autenticadas pasan por `get_current_user`, incluso vía `requerir_rol`). Usuario eliminado físicamente → `401` (token inválido, logout automático). `GET /auth/me` (nuevo, `AuthMeResponse`: id, username, rol, turno_habilitado, activo) expone la sesión y sirve de fuente para el polling. Al deshabilitar: la sesión muere ≤60 s (polling) o al instante al volver a la pestaña (`syncAsistenciaActiva()` en `visibilitychange`/`focus`), y la asistencia activa queda cerrada con la regla ≤15 min del toggle (el watcher es solo el fallback para turnos huérfanos). Bloqueo total inmediato: sin deshabilitación, un vendedor NO pierde turno ni sesión por inactividad (hay tope de 8h solo en el cálculo de extras); deshabilitado, no puede ni cerrar turno ni enviar heartbeat (403).

### KDS (Kitchen Display System)
- `OrdenRepository.obtener_ordenes_filtradas()` eager-loads `Orden.mesa.zona` and `Orden.mesero` for KDS card display
- `DetalleOrdenResponse` includes `producto_nombre` — populated via `@model_validator` from eager-loaded `DetalleOrden.producto` relationship
- Frontend `renderCocinaCards()` filters by tab: cocina (PENDIENTE/PREPARANDO), lista (ENTREGADA), historial (PAGADA/CANCELADA)
- `cambiarEstadoKDS(id, estado)` calls `PATCH /ordenes/{id}/estado` — validates against `TRANSICIONES_VALIDAS` state machine
- `editarOrdenKDS(id)` — botón "✏️ Editar" en tarjetas KDS (PENDIENTE/PREPARANDO/ENTREGADA); con mesa reusa `agregarAlPedido()`, sin mesa (para llevar) abre `openOrderModal(null, null, orden)`; ambas entran al modo edición que hace `PUT /ordenes/{id}/items` con el estado final de la comanda
- **Auto-refresh**: `iniciarIntervalosSesion()` arranca `state.kdsRefreshInterval` (15 s) que recarga el KDS solo cuando `state.currentScreen === 'comandero'` y la pestaña está visible; se limpia en `logout()`
- **Botón principal de cocina**: `.kc-btn-principal` (ancho completo, 52px, `order: -1`) domina la tarjeta — `PENDIENTE` → "🔥 Empezar Preparación" (rojo, `local_fire_department`), `PREPARANDO` → "🛎️ ¡Listo! Avisar al Mesero" (turquesa, `room_service`). "Cobrar", "Editar" y "Cancelar" siguen disponibles para el cocinero

### Notificaciones push (Web Push / VAPID)
- **Arquitectura**: Web Push con VAPID (`pywebpush==2.0.1`). El aviso llega al teléfono aunque la app esté cerrada o el navegador en segundo plano (a diferencia de WebSocket/SSE, que exigen la pestaña abierta).
- **Claves VAPID derivadas de `SECRET_KEY`** (`app/core/vapid.py`): si `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` no están definidas, se derivan de forma determinista (P-256) del `SECRET_KEY`. Así producción funciona sin configurar nada en el dashboard de Render y **las suscripciones de los dispositivos sobreviven a los reinicios** (mientras el `SECRET_KEY` no cambie). Las variables de entorno mandan sobre la derivación.
  - `claves_vapid()` → `(public_key, private_key)` base64url **str**
  - `clave_privada_vapid()` → clave privada base64url **str** (py-webpush 2.0.1 usa `Vapid.from_string`, que exige `str`; pasar `bytes` revienta con `'bytes' object has no attribute 'encode'`)
- `app/models/push.py` → tabla `push_suscripciones` (`usuario_id` FK CASCADE, `endpoint` **String(500) unique** — no `Text` para no chocar con el límite de índice de MySQL/Aiven, `p256dh`, `auth`, `user_agent`, `creada_en`, `ultimo_envio_en`). Se crea sola con `Base.metadata.create_all` en el arranque.
- **Disparadores** (en la capa de endpoints, `app/api/endpoints/orden.py`):
  - `POST /ordenes/`, `POST /ordenes/{id}/items`, `PUT /ordenes/{id}/items` → `nueva_comanda` → notifica al **stream de cocina**
  - `PATCH /ordenes/{id}/estado` con `ENTREGADA` → `comanda_lista` → notifica al **stream de meseros**
- **Cada usuario elige qué recibe (opt-in)**: cualquier cuenta puede recibir avisos; nadie los recibe si no los activó en su dispositivo y eligió al menos un tipo. Cuatro preferencias booleanas por usuario (`app/models/personal.py`):
  - `avisos_cocina` (default **False**) → comandas nuevas o editadas.
  - `avisos_mesero` (default **True**) → sus propias comandas cuando la cocina las marca listas.
  - `avisos_mesero_todas` (default **False**) → además las comandas listas de otros meseros. Si `avisos_mesero=False`, `aplicar_preferencias_avisos()` fuerza `avisos_mesero_todas=False`.
  - `avisos_fuera_de_turno` (default **True**) → recibir aunque no tenga turno abierto / app cerrada / sin sesión.
- **Streams de entrega** (`PushService`): `usuarios_avisos_cocina()` → `avisos_cocina=True`; `usuarios_avisos_mesero_todas()` → `avisos_mesero=True AND avisos_mesero_todas=True`; `usuarios_con_avisos_mesero(ids)` → meseros de la orden con `avisos_mesero=True`. El stream de cocina excluye al mesero que creó la orden (nada de autosnotificaciones). Todos pasan por `usuarios_reciben_avisos()`.
- **Entrega "fuera del sistema"** (`PushService.usuarios_reciben_avisos()`): el aviso llega aunque el turno esté cerrado, la app cerrada o el navegador sin sesión. Reglas → `Usuario.activo=True` y `Empleado.activo=True` (obligatorias); si el rol es `Vendedor`, además `Usuario.turno_habilitado=True` (gerencia lo deshabilitó explícitamente = no recibe); `Usuario.avisos_fuera_de_turno` decide el resto → `True` recibe siempre, `False` solo mientras `Asistencia.hora_salida_real IS NULL` + `Asistencia.anulada=False`.
- **Migración de startup `_migrate_usuarios_avisos_comandas()`**: agrega las columnas nuevas y, **solo la primera vez** (cuando `avisos_cocina` no existía), hace backfill respetando el comportamiento previo: puestos de cocina → `avisos_cocina=True`; todos → `avisos_mesero=True`; el resto queda en False. Los usuarios nuevos nacen con `avisos_cocina` según su puesto (`crear_usuario_sistema()` usa `es_puesto_cocina()`).
- **Quién los edita**: el propio usuario desde el panel de Notificaciones (`#push-avisos-cocina`, `#push-avisos-mesero`, `#push-avisos-mesero-todas`, `#push-avisos-fuera-turno`; las casillas se deshabilitan sin suscripción y "Todas las comandas" solo con "Avisos de mesero" activo) y gerencia desde Personal con el botón 🔔 (`.emp-amber.admin-only`) → `#modal-avisos-usuario`.
- **Endpoints de preferencias**: autoservicio `GET`/`PATCH /api/v1/push/preferencias` (parcial: solo se aplican los campos enviados). Gerencia `PATCH /api/v1/personal/usuarios/{id}/avisos` (Admin/Gerente, 404 si no existe). `PushConfigResponse` y `UsuarioResponse` exponen los cuatro flags.
- **Cocina = por Puesto, no por rol**: `es_puesto_cocina()` acepta nombres que contengan `cocin`, `cosin` o `chef` (en producción el puesto es `Cosinero/Chef`, con typo, y NO contiene "cocin").
- **Los envíos son tarea en segundo plano** (`BackgroundTasks` + `ejecutar_notificacion_push()` que abre su propia `SessionLocal()`): un fallo de push **jamás** rompe el flujo de la orden; el error queda en el log (`[PUSH] ...`) y la suscripción que responde `404`/`410` se elimina (podada automática).
- **Service worker**: `app/Templates/sw.js`, registrado con `navigator.serviceWorker.register('/Templates/sw.js', { scope: '/Templates/' })` (**URL estable, sin `?v=`**). El scope cubre `/Templates/index.html` (el mount de `StaticFiles` no usa `html=True`, así que `sw.js` se sirve directo). Maneja `push` (muestra notificación con icono `Imagenes/notificacion.png`) y `notificationclick` (si el ERP ya está abierto le manda `postMessage({tipo:'destino', pantalla, mesa})` para navegar sin recargar ni tocar la URL; si está cerrado abre `/Templates/index.html?pantalla=…` y la app limpia los parámetros al cargar).
- **Enlaces profundos**: `?pantalla=comandero` (cocina) y `?pantalla=salon&mesa=<mesa_id>` (mesero). `aplicarDestinoSolicitado()` los aplica en `login()` y en la restauración de sesión; `sincronizarPuestoUsuario()` NO pisa el deep link (solo navega a cocina si no hay `?pantalla=`). Los parámetros se leen una sola vez al cargar (`DESTINO_URL`) y `limpiarUrlDestino()` los borra de la barra de direcciones (`history.replaceState`): **la URL que ve el usuario nunca cambia**.
- **Frontend**: `activarNotificacionesPush()` / `desactivarNotificacionesPush()` / `sincronizarEstadoPush()` / `pintarEstadoPush()` / `alternarNotificacionesPush()` en `app/Templates/js/app.js`. Botones con atributo `data-push-toggle` (panel de notificaciones `#notifications-push` + topbar de escritorio `#desktop-push-toggle`). Las casillas de tipo de aviso llaman `alternarPreferenciaPush(campo, valor)` (actualización optimista con rollback si falla el PATCH) y `pintarEstadoPush()` resume en `#notifications-push-estado` qué recibirá el usuario.
- **Endpoints** (`app/api/endpoints/push.py`, todos autenticados): `GET /push/config` (clave pública VAPID + `habilitado`), `POST /push/subscribe` (upsert por `endpoint`), `POST /push/unsubscribe`, `GET /push/subscriptions` (solo las del usuario), `DELETE /push/subscriptions/{id}` (solo propias → 404 ajenas).
- **Requisito de plataforma**: el service worker exige contexto seguro → en producción HTTPS (o `localhost` en desarrollo).

### Cocinero/Chef (puesto de cocina)
- El **cocinero se identifica por su Puesto** (`Puesto.nombre` que contenga "cocin" o "chef", case-insensitive), no por rol — los roles siguen siendo Administrador/Gerente/Vendedor
- `POST /auth/login` y `GET /auth/me` incluyen `puesto` (nombre del puesto del empleado) en el JWT y en `AuthMeResponse`
- `sincronizarPuestoUsuario()` refresca `puesto` desde `GET /auth/me` al restaurar sesión (obtiene el valor aunque el `localStorage` viejo no lo tuviera)
- **El bloqueo de navegación es por ROL, no por puesto**: el bloqueo al Panel de Cocina aplica **solo a rol `Vendedor`** (`esUsuarioCocina()` exige `state.user.rol === 'Vendedor'` **y** puesto de cocina). Un Administrador/Gerente con un puesto de cocina conserva la navegación completa (sidebar + bottom nav) y aterriza en el Panel de Cocina. Regla: la navegación **nunca** se oculta por el puesto; como máximo se restringe por rol.
- **No existe `body.role-cocina`**: el bloque CSS que ocultaba `.sidebar-nav`, `.bottom-nav` y `.sidebar-toggle` (y quitaba el margen del `.main-content`) fue **eliminado**. Con él, en móvil el cocinero se quedaba sin bottom nav y sin forma de abrir el panel de asistencia (el sidebar es off-canvas y el hamburger está oculto en ≤768px; la única entrada es el botón "Más" del bottom nav) → no podía marcar entrada ni salida.
- El aterrizaje en el Panel de Cocina es por **destino sugerido** (`navigateTo` no bloquea la navegación): login y restauración de sesión abren `comandero`, pero el usuario puede salir a cualquier pantalla autorizada.

### Estudio de Mercado con Gemini (solo administración)
- **Pantalla**: `#screen-estudio-mercado`, accesible desde el botón `#btn-estudio-mercado` en el header de **Gastos** (`.admin-only`); `navigateTo('estudio-mercado')` tiene guard de rol (no-gestor → vuelve a `gastos` con toast). Botón "← Volver" (`#btn-estudio-volver`) regresa a `gastos`.
- **Modelos**: `EstudioMercado` (periodo `DIA|SEMANA|MES|ANIO`, tipo `MANUAL|AUTOMATICO`, estado `GENERANDO|COMPLETADO|ERROR`, `desde`/`hasta`, `titulo`, `resumen`, `fortalezas[]`, `debilidades[]`, `estrategias[]`, `analisis`, `metricas` JSON, `modelo_ia`, `error`, `intentos`, `notificado`), `DocumentoEstudioMercado` (nombre, tipo_archivo, mime, tamano_bytes, texto extraído, caracteres) y `MensajeEstudioMercado` (rol `USUARIO|ASISTENTE`, contenido, documento_id, estudio_id, `permitido`). Se crean solas con `Base.metadata.create_all`.
- **Datos que recopila** (`EstudioMercadoRepository`): ventas cobradas y ticket promedio, ventas por método de pago, top platillos (unidades e ingresos), gastos por categoría, compras/insumos, descuentos, anulaciones y devoluciones, temporada del periodo (regla Nicaragua: ALTA = dic, ene, mar, abr, jul, ago; MEDIA = feb, nov; BAJA = may, jun, sep, oct; seca nov–abr / lluviosa may–oct), fecha y región.
- **Generación en segundo plano**: `POST /estudio-mercado/generar` responde 202 con el estudio en `GENERANDO` y ejecuta `BackgroundTasks` (`ejecutar_generacion_estudio()` abre su propia `SessionLocal()`); el frontend hace polling de `GET /estudio-mercado/{id}` cada 4 s (`pollEstudio()`).
- **Automático mensual**: `_estudio_mercado_watcher()` (tarea de arranque en `main.py`, junto al heartbeat) llama a `_generar_estudio_automatico()`, que crea **un** estudio del mes anterior completo por mes calendario; si falla se reintenta hasta 5 intentos y luego se abandona. Al completarse se notifica a administración por Web Push (`notificar_estudio_mercado()`); el flag `notificado` evita avisos duplicados.
- **Guardrail de alcance (dos pasos)**: antes de responder, `GeminiService.clasificar_alcance()` pregunta al modelo "SI/NO" si la consulta es del negocio; si es NO se responde una negativa fija y **no se hace la llamada principal**. Temas sensibles (sueldos, márgenes) solo se detallan para Administrador/Gerente. Consultas sobre el uso del POS están permitidas.
- **Documentos**: `POST /estudio-mercado/documentos` (multipart `archivo`) acepta PDF/DOC/DOCX/XLS/XLSX/CSV; `extraccion_texto.py` extrae el texto y se recorta al adjuntarlo al prompt del chat (`documento_id` en el body). Los documentos se listan/eliminan sin afectar el historial.
- **Chat asesor**: `POST /estudio-mercado/chat` con `{mensaje, documento_id?}` responde como consultor de marketing/operaciones usando `_contexto_negocio()` + el estudio más reciente; historial en `GET /estudio-mercado/chat/historial` (últimos 60) y limpieza con `DELETE /estudio-mercado/chat/historial`.
- **El asesor lee la base de datos en vivo**: `_contexto_negocio()` incluye el bloque `datos_en_vivo` con inventario real (insumo, categoría, cantidad, unidad, mínimo, costo, empaque, `bajo_minimo`), menú activo, mesas por estado/zonas, personal activo y turnos abiertos, ventas de hoy/semana/mes, ventas por día (7 días), caja abierta, órdenes abiertas y nómina pendiente. Cada consulta pasa por `_seguro()` (un fallo no tumba la respuesta). Las reglas 7–8 del prompt obligan a citar la cifra y unidad exactas del inventario y prohíben decir que no hay acceso a la BD cuando el dato está en el bloque.
- **Informe descargable**: `GET /estudio-mercado/{id}/exportar` devuelve un HTML autocontenido (`text/html`, `Content-Disposition: attachment`) con KPIs, resumen, dona de métodos de pago, barras de platillos/gastos y barras verticales por día, generadas como SVG inline (`_svg_dona`, `_svg_barras_h`, `_svg_barras_v`, paleta `PALETA_GRAFICAS`). No requiere dependencias nuevas (no usa PDF) e incluye botón "Imprimir / Guardar PDF"; 404 si el estudio no existe y 400 si aún no está `COMPLETADO`. Frontend: botón "Descargar informe" en el pie del detalle (`descargarEstudioMercado()`) que descarga el blob con `Authorization: Bearer`; estilos `.em-pie-acciones` / `.em-descargar`.
- **Gemini (`app/services/gemini_service.py`)**: `GEMINI_API_KEY`, `GEMINI_MODEL` (`gemini-3.5-flash`), `GEMINI_MODELOS_RESPALDO` (`gemini-3.6-flash,gemini-flash-lite-latest,gemini-flash-latest`), `GEMINI_MAX_INTENTOS` (4), `GEMINI_TIMEOUT` (120). Rota de modelo ante 400/404/429/5xx, con espera creciente; **si un modelo rechaza `generationConfig.thinkingConfig` (`400 INVALID_ARGUMENT`, típico de los "lite") se aprende en `MODELOS_SIN_THINKING` y se reintenta sin él**, de modo que un modelo sin soporte de thinking ya no tumba la petición. Sin `GEMINI_API_KEY` los endpoints responden 500 con mensaje explícito.
- **Frontend**: bloque `em-*` en `app.js` (`loadEstudioMercado()` usa `Promise.allSettled` para que un endpoint caído no vacíe la pantalla, `renderEmPeriodos()`, `renderHistorialEstudios()`, `renderEmDetalle()`, `renderDocumentosEstudio()`, `renderChatEstudio()`, `generarEstudioMercado()`, `pollEstudio()`, `abrirEstudio()`, `eliminarEstudioMercado()`, `enviarMensajeAsesor()`). Deep link `?estudio=<id>` en `DESTINO_URL`/`aplicarDestino()` y en el `postMessage` del service worker.
- **Estilos**: bloque `em-*` en `style.css` antes de la sección "Tema oscuro"; todos los colores vía `color-mix()` + variables `--mix-*`, así que el modo oscuro funciona sin reglas nuevas y el claro queda idéntico.

### Método de pago en la orden
- `Orden.metodo_pago` (`MetodoPago`: `EFECTIVO` por defecto, `TARJETA`, `TRANSFERENCIA`, `PAGO_EN_LINEA`) se elige con los botones `#btn-pago-*` del modal de cobro y viaja en `PUT /ordenes/{id}/pagar {metodo_pago}`; valor inválido → 422.
- Columna agregada por la migración de startup `_migrate_orden_metodo_pago()` (idempotente); un estudio de mercado la usa para el desglose de ventas por método de pago.

### Reportes financieros query chain
```
ReportesService.obtener_cierre()
  ├── _calcular_rango() → (fecha_inicio, fecha_fin)
  ├── repo.obtener_ingresos_totales()    → SUM(Orden.total) WHERE PAGADA
  ├── repo.contar_ordenes()              → COUNT pagadas + canceladas
  ├── repo.obtener_gastos_nomina()       → SUM(Nomina.pago_neto) WHERE PAGADO
  ├── repo.obtener_gastos_clasificados() → gastos table split: SUMINISTROS→insumos, adelantos→nómina, resto→operativos
  ├── repo.obtener_descuentos_totales()  → SUM(Orden.descuento_total) WHERE PAGADA
  └── repo.obtener_top_platillos()       → GROUP BY producto, ORDER BY qty DESC, LIMIT 5
utilidad_neta = ingresos - nómina - insumos - gastos_operativos
(costo_insumos usa SOLO el bucket SUMINISTROS de la tabla gastos — NO el costo teórico de recetas — para evitar doble contabilidad)
```

**DIARIO vs date-range**: El modo DIARIO usa `cierre_caja_id IS NULL` (registros NO archivados, es decir la sesión de caja abierta actual) en lugar de un filtro de fecha. Los modos SEMANAL/QUINCENAL/MENSUAL/ANUAL usan rangos de fecha sobre datos archivados e históricos. Cada modo tiene su propio conjunto de métodos en `ReportesRepository` (ej: `obtener_ingresos_totales()` vs `obtener_ingresos_totales_sin_archivar()`).

### Cierre de caja archival flow
1. `GET /caja/historial-diario` → `Orden` WHERE `PAGADA AND fecha=today AND cierre_caja_id IS NULL`
2. `POST /caja/cierre` → creates `CierreCaja` + links qualifying orders
3. Next query returns empty set

### Ventas del día (panel del mesero)
- El Vendedor no puede ver el Cierre de Caja financiero (`GET /reportes/cierre` es Admin/Gerente → 403, y antes la pantalla quedaba en C$0.00). Ahora tiene un panel acotado de **solo lectura**.
- `GET /caja/ventas-dia` (cualquier rol autenticado) devuelve `VentasDiaResponse`: `fecha`, `total_ventas`, `total_ordenes`, `total_descuentos`, `es_gestor` y las órdenes PAGADA de la caja abierta actual (`cierre_caja_id IS NULL`). **Nunca expone gastos, nómina ni utilidad neta.**
- `CajaRepository.calcular_totales()` ahora incluye `total_descuentos` (consumido solo por `ventas_dia`; `cerrar_caja` sigue leyendo únicamente `total_ventas`/`total_ordenes`).
- Frontend `#screen-cuenta`: `body:not(.role-administrador):not(.role-gerente) #cierre-gestor-panel { display:none }` oculta tarjetas de resumen, tabs de periodo, gráficos y Top platillos. El mesero ve `#ventas-dia-panel` (total vendido hoy + órdenes pagadas + tabla de órdenes).
- `loadHistorialOrdenesDia(target)` / `renderHistorialOrdenesDia(ordenes, target)` aceptan `'gestor'` (usa `#historial-ordenes-list`) o `'mesero'` (usa `#historial-ordenes-list-mesero`); `loadVentasDia()` llena `#vd-total` y `#vd-ordenes`.

### Unit conversion system (3 phases)
- **Phase 1 — Backend engine**: `UnidadMedida` model extended with `tipo_magnitud` (PESO/VOLUMEN/UNIDAD/PERSONALIZADO), `unidad_base_id` FK (self-referential), `factor_conversion` Float; `conversion_service.py` with `convertir_cantidad()` using transitive chain resolution; PUT + conversion GET endpoints; seed data with two-pass base_ref resolution
- **Phase 2 — Frontend management**: `#modal-unidades` modal with table view + create/edit form; `#unidad-derived` toggle shows/hides base unit select + conversion factor; magnitud-filtered `populateUnidadBaseSelect()` (fallback to all units for PERSONALIZADO); live conversion preview text
- **Phase 3 — Integration**: Stock movements + recipe deductions auto-convert when unit differs from insumo base; `ActualizarStockInsumo` + `MovimientoCreate` schemas accept `unidad_medida_id`; `Receta` model has `unidad_medida_id`; `descontar_stock`/`revertir_stock`/`validar_stock_suficiente` all use `_convertir_si_necesario()`; stock modal has unit selector + conversion preview
- **15 standard units**: Kilogramo, Gramo, Libra, Onza (PESO); Litro, Mililitro, Botella, Lata (VOLUMEN); Unidad, Docena, Par, Paquete, Bolsa, Porción (UNIDAD); Metro (PERSONALIZADO)
- **Startup migration `_fix_unidades_medida()`**: corrects magnitudes, links conversion chains, creates missing units; checks both `nombre` and `abreviatura` (case-insensitive) to prevent duplicates; handles list vs dict iteration for NUEVAS seed data

### Orden Para Llevar (takeaway)
- `Orden.mesa_id` nullable — no table assignment, no state mutation on mesa
- `crear_orden()` skips mesa validation/OCUPADA when `mesa_id=None`
- `pagar_orden()` skips mesa→LIBRE when `mesa_id=None`; only sets PAGADA
- `nombre_cliente` field on `Orden` for client name on takeaway orders
- Startup migration `_migrate_orden_mesa_nullable()` enables nullable mesa_id; `_migrate_orden_nombre_cliente()` adds the column
- **Frontend**: "🛍️ Para Llevar" button in salon header → `openParaLlevarModal()` → `openOrderModal(null, null)`; KDS cards show "🛍️ Para Llevar" instead of mesa number; pre-cuenta shows client name; mesa_id=null prevents the table from being marked OCUPADA

### Descuentos (discounts)
- Per-item discount via `POST /ordenes/{id}/descuento-item` with `detalle_id`, `tipo` (PORCENTAJE/MONTO), `valor`, `motivo`
- Global discount via `POST /ordenes/{id}/descuento-global` with same fields (distributes proportionally across all items)
- Remove discount via `DELETE /ordenes/{id}/descuento-item/{detalle_id}`
- `Orden.subtotal` = sum of `(cantidad × precio_unitario)` for all items; `descuento_total` = sum of all discounts; `total = subtotal - descuento_total`
- `_recalcular_totales()` recalculates after any discount change — re-reads all detalles from DB, applies per-item discounts (porcentaje first, then monto), sums global contributions, updates Orden record
- `AplicarDescuentoGlobalRequest.tipo` defaults to `PORCENTAJE`; distributes proportionally by line total weight; fixed per-detalle store with `descuento_monto` / `descuento_porcentaje`
- Reportes: `CierreCajaPeriodoResponse.total_descuentos` and `ingresos_brutos`; `ReportesRepository.obtener_descuentos_totales()` sums `orden.descuento_total` in range
- **Frontend**: `#oc-discount-section` in occupied table detail modal with tipo select, target select (items + global), valor input, motivo textarea, aplicar button; `aplicarDescuentoOrder()` function; historial table shows subtotal, descuento, and total columns; cierre de caja shows `total_descuentos` card
- Startup migration `_migrate_orden_descuentos()` adds subtotal, descuento_total (ordenes), and descuento_porcentaje, descuento_monto, motivo_descuento (detalles_orden) columns; migrates existing data

### Per-insumo packaging unit
- `Insumo` model has optional `unidad_empaque_id` FK + `factor_empaque` Float (1 empaque = X base units)
- Conversion priority: per-insumo packaging factor → global `UnidadMedida` chain
- `InventarioService._convertir_cantidad_si_necesaria()` and `OrdenService._convertir_si_necesario()` both check packaging first
- Startup migration `_migrate_insumos_empaque()` adds `unidad_empaque_id` and `factor_empaque` columns if missing
- **Frontend**: Insumo modal has packaging section (Unidad de Empaque select + Factor input + preview text); Stock modal Detalles tab shows packaging fields

## Known Issues / TODO

- No Alembic migrations generated yet — using `create_all` on startup
- CORS: configurable via `CORS_ORIGINS` env var (comma-separated); defaults to `http://127.0.0.1:5500,http://localhost:5500` with `allow_credentials=True`
- Frontend `api()` helper skips 401 session-expired logic for `/auth/login` (login errors handled by `login()` function)
- No refresh token flow — single access token valid 365 días (`ACCESS_TOKEN_EXPIRE_MINUTES=525600`); el tope de 8h solo aplica al cálculo de horas extras
- `turno_service.py`: three standalone functions (not a class) — inconsistent with other services
- E2E test scripts (`test_ordenes.py` etc.) require auth tokens for most endpoints but don't implement login flow — run `init_db.py` seed data first
- 7 empty placeholder files exist for planned modules: `venta_service.py`, `auditoria_service.py`, `empleado_service.py`, `receta_service.py`, `reporte_service.py` (singular), `producto_repository.py`, `venta_repository.py`
- `repositories/__init__.py` only exports 6 of 16+ repositories (the rest work via direct imports by services)
- Duplicate nomina endpoint: `GET /nomina/empleado/{id}` and `GET /nomina/empleados/{id}/historial` return identical results
- `Settings.ENVIRONMENT` (default: "development") exists in config but is unused in the codebase

### Checklist de producción (Render)

- `render.yaml` declara `SECRET_KEY: generateValue` (estable) y las DB_* como `sync: false` (se fijan en el dashboard). **No incluye** `IMGBB_API_KEY` ni `ACCESS_TOKEN_EXPIRE_MINUTES` — ambas se fijan manualmente en el dashboard de Render.
- Verificar en el dashboard de Render que `ACCESS_TOKEN_EXPIRE_MINUTES` **NO** esté fijo en `480` (anula el default de 525600 del `config.py`).
- Verificar que `IMGBB_API_KEY` esté configurada (sin ella, `POST /menu/items/{id}/imagen` responde 500).
- **Push**: no hay nada que configurar en el dashboard (las claves VAPID se derivan del `SECRET_KEY`, que en Render es estable). Después del deploy, comprobar que `https://sazoncaribe-o.onrender.com/Templates/sw.js` responde 200 y que `GET /api/v1/push/config` devuelve `habilitado: true` con la clave pública. Si el `SECRET_KEY` de Render cambiara, las suscripciones de los dispositivos quedarían inservibles y habría que volver a activarlas.
- `joshi_0211` NO existe en la BD local; su contraseña se fuerza a `@0420311001000V` en cada arranque (hack `_fix_joshi_password`, decisión de no tocarlo). Si el login que falla en prod es de `joshi_0211`, después de cada deploy la contraseña es siempre esa.
- Ante un login fallido en prod, los logs de Render ya imprimen `Login intent username=... usuario_existe=True/False` y `password_valida=True/False hash_prefix=...`; un `usuario_existe=False` apunta a dos BDs divergentes (Render vs local) o a usernames legacy con espacios/mayúsculas (el fallback `LOWER(TRIM())` en `get_by_username` ya los sana); un `password_valida=False` apunta a hash corrupto (auditoría `[AUTH AUDIT]` al arranque lo lista).
