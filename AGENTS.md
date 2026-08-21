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
│   ├── config.py            # Pydantic Settings (.env) — includes HEARTBEAT_TIMEOUT_SECONDS, IMGBB_API_KEY
│   ├── database.py          # Engine, SessionLocal, Base, get_db()
│   └── security.py          # bcrypt (direct) + JWT — SECRET_KEY/ALGORITHM/ACCESS_TOKEN_EXPIRE_MINUTES read from .env via Settings
├── api/
│   ├── deps.py              # get_current_user, requerir_rol(roles)
│   └── endpoints/           # API controllers (one file per domain)
│       ├── auth.py          # POST /auth/login, /auth/verify
│       ├── personal.py      # Puestos, empleados, usuarios CRUD
│       ├── asistencia.py    # Turnos, check-in/out, iniciar turno, heartbeat
│       ├── nomina.py        # Nómina y pagos
│       ├── inventario.py    # Proveedores, insumos, movimientos, catálogos de insumo
│       ├── menu.py          # Categorías, items, recetas
│       ├── menu_publico.py  # API pública Carta Digital (solo lectura, sin auth)
│       ├── salon.py         # Zonas, mesas, mapa
│       ├── orden.py         # Órdenes, agregar items, facturación, pagar, descuentos
│       ├── caja.py          # Historial diario, cierre de caja (archivado)
│       ├── gasto.py         # Gastos operativos CRUD
│       ├── reportes.py      # Reportes financieros por periodo
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
│   ├── reportes.py          # PeriodoEnum, CierreCajaPeriodoResponse (includes gastos_operativos)
│   ├── analitica.py         # CierreCajaResponse (legacy)
│   └── auth.py              # LoginRequest, TokenResponse
├── models/
│   ├── personal.py          # Puesto, Empleado, Usuario
│   ├── asistencia.py        # Turno (Matutino/Nocturno), Asistencia (audit columns + ultimo_heartbeat)
│   ├── nomina.py            # Nomina
│   ├── inventario.py        # Proveedor, Ingrediente, Insumo, MovimientoInventario
│   ├── menu.py              # CategoriaMenu, MenuItem (imagen_url, tiempo_preparacion), Receta
│   ├── salon.py             # Zona, Mesa, EstadoMesa
│   ├── orden.py             # Orden, DetalleOrden, EstadoOrden (mesa_id nullable for direct sales/para llevar; subtotal, descuento_total, nombre_cliente fields; descuento_porcentaje, descuento_monto, motivo_descuento on DetalleOrden)
│   ├── caja.py              # CierreCaja
│   ├── gasto.py             # Gasto, CategoriaGasto enum
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
│   ├── reportes_repository.py    # + obtener_gastos_clasificados(), obtener_descuentos_totales()
│   └── analitica_repository.py
├── services/
│   ├── personal_service.py
│   ├── asistencia_service.py     # + actualizar_heartbeat(), cerrar_turnos_stale(), crear_turno(), actualizar_turno(), eliminar_turno()
│   ├── nomina_service.py
│   ├── inventario_service.py     # SALIDA movements auto-generate Gasto records; _convertir_cantidad_si_necesaria() per-insumo packaging
│   ├── menu_service.py          # + consultas públicas reutilizables: obtener_menu_publico(), obtener_categorias_publicas(), obtener_item_publico_por_id(); subir_imagen() (upload multipart)
│   ├── preparacion_service.py   # Producción por lote: registrar_preparacion() valida stock, descuenta insumos (SALIDA + Gasto SUMINISTROS), crea DetallePreparacionCocina
│   ├── salon_service.py
│   ├── orden_service.py          # validar_stock_suficiente() + descontar_stock() + revertir_stock() + TRANSICIONES_VALIDAS; _convertir_si_necesario() per-insumo packaging; aplicar_descuento_item(), aplicar_descuento_global(), quitar_descuento_item(); _recalcular_totales()
│   ├── caja_service.py
│   ├── gasto_service.py          # registrar_gasto(), registrar_gasto_automatico()
│   ├── reportes_service.py       # Utilidad = ingresos - nómina - insumos - gastos_operativos; incluye descuentos en response
│   ├── conversion_service.py     # convertir_cantidad() — transitive chain resolution via _get_chain()
│   ├── turno_service.py          # Standalone functions
│   └── analitica_service.py
├── db/
│   └── init_db.py
├── Templates/
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js                 # Uses POST /ordenes/{id}/items for adding items (legacy PATCH removed); descuentos via POST /ordenes/{id}/descuento-{item,global}
│   └── carta/                    # Carta Digital pública (sin auth): index.html, css/style.css, js/app.js, img/ (hero, logos, placeholder) + img/platos/ (imágenes subidas por el ERP)
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
- IP validation: Vendedor restricted to `ALLOWED_IPS` env var (comma-separated, default `190.143.254.134,127.0.0.1,::1`); Admin/Gerente bypass; proxy header support (`CF-Connecting-IP`, `X-Forwarded-For`)
- No comments in code unless explicitly requested
- Spanish user-facing strings, English internal identifiers
- `RolEnum` defined in `app/schemas/personal.py`
- SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES read from `.env` via `get_settings()`
- Case-insensitive login: usernames normalized to lowercase (`strip().lower()`) at auth endpoint and user creation service

### Frontend / JS

- Vanilla JS SPA — no frameworks, no build step
- `API_BASE` auto-detects: local (`localhost`/`127.0.0.1`) → `http://127.0.0.1:8000/api/v1`, otherwise → `${location.origin}/api/v1` (works on Render)
- Token stored in `localStorage` as `pos_token`; user as `pos_user`
- Adding items to existing order uses `POST /ordenes/{id}/items` (legacy PATCH endpoint removed)
- Sidebar layout: 260px fixed sidebar + flex main content
- Card grids: `repeat(auto-fill, minmax(280px, 1fr))`
- All modals use `.modal-overlay.show` pattern
- `showToast(message, type)` for notifications
- Role-based nav: `.nav-locked` class for restricted items
- IP block modal: `#modal-ip-block` + `blockPOSAccess()` disables all actions
- Gastos screen: `#screen-gastos` with table (ID, Fecha, Categoría, Descripción, Monto, Registrado Por); modal `#modal-registrar-gasto` with fecha picker + categoría select + monto + descripción; `loadGastos()` fetches `GET /gastos/`, `guardarGasto()` posts `POST /gastos/`
- Salón: `#zona-filters` chip row dynamically populated from `GET /salon/zonas`; filters combine with estado chips via `applyTableFilters()`; zone CRUD in `#zonas-panel` (collapsible) within Gestionar Mesas modal; startup `_fix_orphaned_mesas()` auto-frees OCUPADA tables with no active orders; table detail modal shows "Forzar Libramiento" button when OCUPADA but no active order found
- Inventario: `#insumo-cat-filters` chip row dynamically populated from `GET /inventario/categorias-insumo`; filters items by `categoria_id`; `#modal-insumo` has ⚙️ toggle buttons for inline category and unit subpanels (`#cat-insumo-panel`, `#unidad-panel`); dynamic `<select>` populated from `GET /inventario/unidades-medida`; `loadInventory()` fetches both catalog endpoints + insumos + alerts; category cards show `categoria_nombre` badge; `#modal-stock` has two tabs (Movimiento/Detalles) — Movimiento tab adjusts stock via `PATCH /insumos/{id}/stock`, Detalles tab edits category/unit/stock_minimo via `PATCH /insumos/{id}`; gear subpanels for inline category/unit creation from stock modal
- KDS (Panel de Cocina): `#screen-comandero` with 3 filter tabs (`data-cocina-tab`: cocina/lista/historial), `#cocina-grid` card grid; `loadCocinaOrdenes()` → `renderCocinaCards()`; `cambiarEstadoKDS(id, estado)` → `PATCH /ordenes/{id}/estado`; cards show zone, mesa, mesero, elapsed time with urgency colors, and item list with `producto_nombre`
- Responsive design: Custom CSS (NOT Tailwind); mobile `<768px`, tablet `768-1024px`
- Dynamic Carta categories: Fetches from `GET /menu/categorias`; order modal category tabs rendered dynamically from same source
- C$ currency: All monetary values use `C$` (Córdobas nicaragüenses)
- Personal module: New employee modal has `telefono` field + `C$` salary label; `saveNuevoEmpleado()` sends `salario_base` + `telefono` in employee body; ⚙️ button next to Puesto select opens `#puesto-panel` (inline subpanel) to create new Puesto inline — `guardarPuesto()` posts `POST /personal/puestos`, reloads select, auto-selects new puesto
- Unidades de Medida: `#modal-unidades` management modal with table view + create/edit form; `#unidad-derived` toggle shows/hides base unit select + conversion factor; magnitud-filtered base unit select via `populateUnidadBaseSelect()` (falls back to all units for PERSONALIZADO magnitud); live conversion preview text
- Stock modal: Two-tab layout — Movimiento tab (adjust stock via `PATCH /insumos/{id}/stock` with unit selector + conversion preview) and Detalles tab (edit category/unit/stock_minimo via `PATCH /insumos/{id}` with packaging fields section); gear subpanels for inline category/unit creation
- Insumo modal: Packaging section with `Unidad de Empaque` select (`#insumo-unidad-empaque`) + `Factor` input; dynamic preview text ("1 Bolsa de Arroz equivale a 5 lb")
- Gestión de Turnos: `#modal-turnos` CRUD modal for shift templates (nombre, hora_entrada, horas_teoricas); auto-calculated `hora_salida` field (readonly, displays "(calculada)") derived from `entrada + horas_teoricas` via `calcularHoraSalida()` with midnight crossover; table with editar/eliminar actions; button in Personal header (Admin/Gerente only via `.admin-only` CSS class)
- Editar Horarios: `#modal-editar-horarios` modal with `<input type="time">` for entrada + salida; opens from 🕐 button in asistencias table; `openEditarHorariosModal()` converts UTC→local via `formatLocalTime()` logic; `confirmEditarHorarios()` posts `PUT /asistencia/{id}/editar-horarios` with `hora_entrada`, `hora_salida`, `motivo`; backend converts local→UTC by subtracting 6h (Nicaragua CST); recalculates horas extras if exit time provided; audit trail via `motivo_modificacion` + `modificado_por`
- Role-based CSS: `body:not(.role-administrador):not(.role-gerente) .admin-only { display: none !important; }` — Gerente can see admin-only elements (Gestionar Mesas, Gestión de Turnos buttons)
- `formatLocalTime(isoStr)` helper converts UTC datetime strings to Nicaragua local time (`es-NI` locale); all datetime strings from backend are naive UTC — helper appends `'Z'` if missing before parsing
- Reloj en vivo: `updateClock()` muestra hora actual en KDS (`#comandero-clock`) y Salón (`#salon-clock`), actualiza cada 30s via `setInterval`
- `cobrarOrden(ordenId)` — pago rápido desde KDS: PATCH estado a PAGADA + PUT mesa a LIBRE (si tiene mesa_id); alternativa al flujo de detalle de mesa ocupada
- `blockPOSAccess()` — al fallar validación de IP (403), deshabilita todos los elementos interactivos (botones, inputs, selects, formularios, navegación) con `pointer-events: none` + `opacity: 0.4`

### Design Tokens (CSS)

| Token            | Value     | Usage                    |
|------------------|-----------|--------------------------|
| `--azul-marino`  | `#003366` | Primary, headers         |
| `--rojo-cangrejo`| `#E63946` | Alerts, destructive      |
| `--amarillo-solar`| `#FFB703`| Warnings, highlights     |
| `--turquesa-ola` | `#2A9D8F` | Success, secondary       |

## RBAC Rules

| Action                        | Administrador | Gerente | Vendedor |
|-------------------------------|:-------------:|:-------:|:--------:|
| Read all endpoints            | Y             | Y       | Y        |
| Menu/Inventario write         | Y             | Y       | N        |
| Ordenes (create, add items)   | Y             | Y       | Y        |
| Pagar orden (auto-libera mesa)| Y             | Y       | Y        |
| Iniciar turno (IP validated)  | Y (bypass)    | Y (bypass) | Y (must match ALLOWED_IPS) |
| Gestionar turnos (CRUD)       | Y             | Y       | N        |
| Gastos operativos             | Y             | Y       | N        |
| Cierre de caja (reportes)     | Y             | Y       | N        |
| Cerrar caja (archivar)        | Y             | Y       | N        |
| Nomina                        | Y             | Y       | N        |

## Business Rules

- **Payroll**: Biweekly (monthly_salary / 2); salary is per-employee (`Empleado.salario_base`), not per-puesto
- **Overtime**: (salary / 30 / 8) per hour over `horas_teoricas`
- **IVA**: Removed — menu prices are tax-inclusive; `IVA_RATE=0.0`
- **Turno**: Template (Matutino/Nocturno); Asistencia = actual check-in record
- **MenuItem**: Must have `categoria_id`, `nombre`, `precio`; `disponible` toggles visibility
- **Borrado lógico de platillos**: `DELETE /menu/items/{id}` does a SOFT DELETE — sets `disponible=False` (never `db.delete`). Receta e historial de ventas (`detalle_orden`) se conservan; el plato puede reactivarse editándolo. `IntegrityError` se captura y devuelve 400 con mensaje claro. `GET /menu/items` devuelve solo activos por defecto; `?incluir_inactivos=true` (solo Admin/Gerente) los incluye para Gestión de Menú. La unicidad de nombre verifica también inactivos.
- **CategoriaMenu**: Dynamic categories; delete guarded if category has associated platillos
- **Orden**: `mesa_id` nullable (para llevar / retroactive / direct sales) + array of `detalles` (each with `producto_id`, `cantidad`, optional `notas` for special instructions like "Sin cebolla", "poco cocido")
- **One-active-order-per-mesa**: Only ONE active order (PENDIENTE/PREPARANDO/ENTREGADA) per mesa. New items via `POST /ordenes/{id}/items`. Does NOT apply to para llevar (mesa_id null).
- **Pagar orden**: `PUT /ordenes/{id}/pagar` sets PAGADA + LIBRE in a single transaction. If mesa_id is null (para llevar), only sets PAGADA.
- **Orden state machine**: `PENDIENTE → PREPARANDO → ENTREGADA → PAGADA` (any state can also → CANCELADA). Invalid transitions return 400.
- **Adelantos de Salario**: `AdelantoSalario` model linked to Empleado + Nomina (via `total_adelantos`); auto-creates a `Gasto` (OPERATIVO) on registration; deducted from `pago_neto` in nomina calculations; API at `POST /nomina/adelantos`, `GET /nomina/empleados/{id}/adelantos`
- **Descuentos**: Per-item (`descuento_porcentaje` / `descuento_monto` + `motivo_descuento` on `DetalleOrden`) or global (distributed proportionally). `Orden.subtotal` is sum of line totals before discount; `descuento_total` is total discount; `Orden.total = subtotal - descuento_total`. Discounts applied via `POST /ordenes/{id}/descuento-item` and `POST /ordenes/{id}/descuento-global`. Removed via `DELETE /ordenes/{id}/descuento-item/{detalle_id}`. **Al crear/editar comanda**: el botón ✏️ de cada ítem del modal solicita un Descuento en C$ (`aplicarDescuentoItemModal()`), se envía como `descuento_monto` en `DetalleOrdenCreate` (create + `POST /ordenes/{id}/items`), y el backend lo aplica en `_procesar_detalles()` (valida que no exceda el total de la línea, 400 en caso contrario).
- **Cierre de caja**: `POST /caja/cierre` creates `CierreCaja` + links PAGADA orders AND all unarchived gastos via `cierre_caja_id` FK.
- **Mesa states**: LIBRE, OCUPADA, RESERVADA, MANTENIMIENTO
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
- **Nómina calculations**: Horas extras at 1.0x, no deducciones; `pago_neto = bruto + pago_horas_extras - total_adelantos`

## API Endpoints Summary

| Method | Path                                        | Auth     | RBAC              |
|--------|---------------------------------------------|----------|--------------------|
| POST   | /api/v1/auth/login                          | No       | —                  |
| GET    | /api/v1/personal/puestos                    | Yes      | Any                |
| POST   | /api/v1/personal/puestos                    | Yes      | Admin, Gerente     |
| POST   | /api/v1/personal/empleados                  | Yes      | Admin, Gerente     |
| GET    | /api/v1/personal/empleados                  | Yes      | Any                |
| PUT    | /api/v1/personal/empleados/{id}             | Yes      | Admin, Gerente     |
| POST   | /api/v1/personal/usuarios                   | Yes      | Admin, Gerente     |
| GET    | /api/v1/personal/usuarios                   | Yes      | Any                |
| PUT    | /api/v1/personal/usuarios/{id}/reset-password | Yes    | Admin, Gerente     |
| POST   | /api/v1/asistencia/turnos                   | Yes      | Admin, Gerente     |
| GET    | /api/v1/asistencia/turnos                   | Yes      | Any                |
| POST   | /api/v1/asistencia/turnos/iniciar/{id} | Yes      | Any (IP validated) |
| PUT    | /api/v1/asistencia/turnos/{id}         | Yes      | Admin, Gerente     |
| DELETE | /api/v1/asistencia/turnos/{id}         | Yes      | Admin, Gerente     |
| POST   | /api/v1/asistencia/turnos/heartbeat/{id} | Yes      | Any                |
| POST   | /api/v1/asistencia/check-in                 | Yes      | Any                |
| POST   | /api/v1/asistencia/check-out                | Yes      | Any                |
| GET    | /api/v1/asistencia/empleados/{id}/historial | Yes      | Any                |
| PUT    | /api/v1/asistencia/{id}/horas-extras        | Yes      | Admin, Gerente     |
| PUT    | /api/v1/asistencia/{id}/editar-horarios     | Yes      | Admin, Gerente     |
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
| POST   | /api/v1/salon/zonas                         | Yes      | Admin, Gerente     |
| GET    | /api/v1/salon/zonas                         | Yes      | Any                |
| DELETE | /api/v1/salon/zonas/{id}                    | Yes      | Admin, Gerente     |
| POST   | /api/v1/ordenes/                            | Yes      | Any                |
| POST   | /api/v1/ordenes/retroactiva                  | Yes      | Admin, Gerente     |
| GET    | /api/v1/ordenes/                            | Yes      | Any                |
| GET    | /api/v1/ordenes/{id}                        | Yes      | Any                |
| PATCH  | /api/v1/ordenes/{id}/estado                 | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/items                  | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/descuento-item         | Yes      | Any                |
| POST   | /api/v1/ordenes/{id}/descuento-global       | Yes      | Any                |
| DELETE | /api/v1/ordenes/{id}/descuento-item/{detalle_id} | Yes  | Any                |
| PUT    | /api/v1/ordenes/{id}/pagar                  | Yes      | Any                |
| GET    | /api/v1/caja/historial-diario               | Yes      | Any                |
| POST   | /api/v1/caja/cierre                         | Yes      | Admin, Gerente     |
| POST   | /api/v1/gastos/                             | Yes      | Admin, Gerente     |
| GET    | /api/v1/gastos/                             | Yes      | Admin, Gerente     |
| GET    | /api/v1/reportes/cierre?periodo=            | Yes      | Admin, Gerente     |
| GET    | /api/v1/nomina/pendientes                   | Yes      | Any                |
| POST   | /api/v1/nomina/calcular                     | Yes      | Any                |
| POST   | /api/v1/nomina/generar                      | Yes      | Admin, Gerente     |
| PUT    | /api/v1/nomina/{id}/pagar                   | Yes      | Admin, Gerente     |
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

### Menu categories (dynamic)
- `CategoriaMenu` model (id, nombre, descripcion) with `MenuItem.categoria_id` FK
- `GET /menu/categorias` → all categories; `POST /menu/categorias` → create; `DELETE /menu/categorias/{id}` → delete (guarded: 400 if category has platillos)
- **Frontend**: `#screen-menu-mgmt` has `#menu-mgmt-cat-filters` chip row dynamically populated from `GET /menu/categorias`; `#modal-dish` has ⚙️ toggle button → `#cat-panel` (collapsible) with input + save + list with delete buttons; `loadCategorias()` fetches categories, `guardarCategoriaMenu()` posts, `eliminarCategoriaMenu()` deletes; filter logic via `activeMgmtCatFilter` + `applyMenuMgmtFilter()`

### Subida de imágenes y tiempo de preparación (Carta Digital)
- `MenuItem` model has `imagen_url` (String 500, nullable) and `tiempo_preparacion` (Integer nullable, minutos) — documented in the model comments
- **`imagen_url` is server-managed ONLY**: it is NOT accepted in `MenuItemCreate`/`MenuItemUpdate`; clients can never write paths/URLs manually
- `POST /menu/items/{id}/imagen` (Admin/Gerente) receives multipart field `archivo`; `MenuService.subir_imagen()` validates MIME + extension (PNG/JPEG/WebP/GIF), size ≤ 5 MB, optimizes the image via `MenuService._procesar_imagen_webp()` (EXIF transpose, resize to max width 1080px keeping aspect ratio, convert to WebP quality 80% — Pillow), encodes the result to Base64, uploads it to ImgBB API (`POST https://api.imgbb.com/1/upload` with `IMGBB_API_KEY`), extracts the permanent URL from the response (`data.url`), and persists it in `imagen_url`; corrupt files raise 400
- **ImgBB integration**: Uses `httpx` to POST to ImgBB with `key` + Base64 `image` param; no `expiration` param = permanent storage; timeout 30s; errors raise HTTPException 502 with descriptive messages; missing `IMGBB_API_KEY` raises 500
- **Optimización de imágenes (Carta Digital)**: todas las imágenes subidas se almacenan ya comprimidas (WebP q80, ≤1080px de ancho) para carga rápida; el frontend usa `loading="lazy"` + `decoding="async"` en platillos/tarjetas y un skeleton shimmer CSS (`.card-media`/`.cat-card`/`.modal-media` sin `.img-loaded`) que se detiene vía listener capture de eventos `load`/`error` en `app.js`
- **Backward compatibility**: Existing images stored locally at `/carta/img/platos/` still work — `imagen_url` accepts any URL format; Carta Digital's `imgFor(item)` handles both local and external URLs
- `MenuItemResponse` and `MenuItemPublicoResponse` expose `imagen_url` + `tiempo_preparacion`; `MenuItemCreate`/`MenuItemUpdate` accept `tiempo_preparacion` only
- Startup migration `_migrate_menu_item_imagen_tiempo()` (idempotent via `information_schema`) adds both columns
- **Frontend POS**: `#modal-dish` has file input `#dish-image` (accept png/jpeg/webp/gif) + `#dish-prep-time` (minutes) + live preview (`previewDishImage()`); `saveDish()` sends `tiempo_preparacion` in the JSON body and, if a file was chosen, uploads it after save via `uploadDishImage()` (`FormData` + `Content-Type: undefined` so fetch sets the multipart boundary); `renderMenuMgmt()` shows thumbnail + "⏱️ ~N min"
- **Carta Digital**: `imgFor(item)` returns `item.imagen_url` or the local placeholder `img/placeholder-dish.svg`; `openModal()` shows "Preparación: ~N min" in the timer pill (falls back to category); hero/logos are local assets in `app/Templates/carta/img/` — no remote images, no Stitch dependencies

### UTC timezone handling
- All `datetime.now()` calls in asistencia-related code use `datetime.now(timezone.utc).replace(tzinfo=None)` to store naive UTC
- Files: `asistencia_service.py`, `turno_service.py`, `asistencia_repository.py`
- Frontend helper `formatLocalTime(isoStr)` in `app.js` treats all datetime strings as UTC (appends `'Z'` if missing) and formats with `es-NI` locale
- All locale references use `es-NI` (Nicaragua, UTC-6) instead of `es-CO` (Colombia, UTC-5)
- MySQL `DATETIME` type strips timezone info on read; stored values remain correct UTC
- `security.py` uses `datetime.now(timezone.utc)` for JWT token expiration (timezone-aware)

### Heartbeat auto-close background task
- `POST /asistencia/turnos/heartbeat/{id}` — updates `Asistencia.ultimo_heartbeat` timestamp
- Background `_heartbeat_watcher()` task runs every `HEARTBEAT_INTERVAL_SECONDS` (default: 300s / 5 min), queries `get_activas_sin_heartbeat()` for turnos with no heartbeat in `HEARTBEAT_TIMEOUT_SECONDS`
- Stale turnos are auto-closed with `hora_salida_real = ultimo_heartbeat` and hours calculated normally
- Configurable via `.env`: `HEARTBEAT_INTERVAL_SECONDS` (BG check interval, default 300s) and `HEARTBEAT_TIMEOUT_SECONDS` (stale threshold, default 900s / 15 min)
- **Frontend**: `enviarHeartbeat()` fires every 2 min via `setInterval` — only for Vendedor role with active shift (`state.currentAsistencia` set); silently ignored on error; cleared on logout

### Gestión de Turnos CRUD
- `POST /asistencia/turnos` → create shift template (nombre, hora_entrada, horas_teoricas)
- `PUT /asistencia/turnos/{id}` → update (Admin/Gerente only)
- `DELETE /asistencia/turnos/{id}` → delete (Admin/Gerente only)
- `TurnoUpdate` schema for PUT body; `TurnoResponse` for list
- **Frontend**: `#modal-turnos` with inline CRUD; `calcularHoraSalida()` auto-computes `hora_salida` from `hora_entrada + horas_teoricas` using modulo 1440 for midnight crossover; `hora_salida` field is readonly/calculated

### KDS (Kitchen Display System)
- `OrdenRepository.obtener_ordenes_filtradas()` eager-loads `Orden.mesa.zona` and `Orden.mesero` for KDS card display
- `DetalleOrdenResponse` includes `producto_nombre` — populated via `@model_validator` from eager-loaded `DetalleOrden.producto` relationship
- Frontend `renderCocinaCards()` filters by tab: cocina (PENDIENTE/PREPARANDO), lista (ENTREGADA), historial (PAGADA/CANCELADA)
- `cambiarEstadoKDS(id, estado)` calls `PATCH /ordenes/{id}/estado` — validates against `TRANSICIONES_VALIDAS` state machine

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
- No refresh token flow — single 8h access token
- `turno_service.py`: three standalone functions (not a class) — inconsistent with other services
- E2E test scripts (`test_ordenes.py` etc.) require auth tokens for most endpoints but don't implement login flow — run `init_db.py` seed data first
- 7 empty placeholder files exist for planned modules: `venta_service.py`, `auditoria_service.py`, `empleado_service.py`, `receta_service.py`, `reporte_service.py` (singular), `producto_repository.py`, `venta_repository.py`
- `repositories/__init__.py` only exports 6 of 16+ repositories (the rest work via direct imports by services)
- Duplicate nomina endpoint: `GET /nomina/empleado/{id}` and `GET /nomina/empleados/{id}/historial` return identical results
- `Settings.ENVIRONMENT` (default: "development") exists in config but is unused in the codebase
