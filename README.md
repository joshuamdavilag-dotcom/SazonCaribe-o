# Sazón Caribeño POS

Sistema de gestión para restaurante (**ERP / POS**) construido con **FastAPI + SQLAlchemy 2.x + Pydantic v2** y **MySQL** (PostgreSQL/SQLite soportados como fallback). Incluye un SPA en **Vanilla JS** para el personal y una **Carta Digital pública** (menú por QR, sin autenticación) para los clientes.

---

## Tabla de contenido

- [Características](#características)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Puesta en marcha](#puesta-en-marcha)
- [Variables de entorno](#variables-de-entorno)
- [Flujo de arranque](#flujo-de-arranque)
- [Roles y permisos (RBAC)](#roles-y-permisos-rbac)
- [Módulos y reglas de negocio](#módulos-y-reglas-de-negocio)
- [API](#api)
- [API pública (Carta Digital)](#api-pública-carta-digital)
- [Despliegue](#despliegue)
- [Pruebas](#pruebas)
- [Documentación adicional](#documentación-adicional)
- [Estado del proyecto](#estado-del-proyecto)

---

## Características

- **Salón**: mapa de mesas por zona, estados (LIBRE/OCUPADA/RESERVADA/MANTENIMIENTO), apodo temporal de mesa.
- **Órdenes / Comandas**: órdenes por mesa o para llevar, comandas editables, descuentos por producto y globales, pago con liberación automática de mesa, venta retroactiva.
- **KDS (Panel de Cocina)**: vista dedicada con botones "Empezar Preparación" / "Listo", auto-refresh y modo pantalla completa para cocineros.
- **Menú**: categorías dinámicas, platillos con imagen (multi-part → ImgBB), tiempo de preparación y recetas.
- **Inventario**: insumos, categorías, unidades de medida con conversión transitiva, empaques por insumo, movimientos (ENTRADA/SALIDA) y producción por lote (preparaciones).
- **Personal**: puestos, empleados, usuarios, plantillas de turno y habilitación dinámica de turnos para vendedores.
- **Asistencia**: check-in/check-out, horas extras, edición de horarios, anulación con auditoría, heartbeat y cierre automático de turnos huérfanos.
- **Nómina**: cálculo quincenal, adelantos de salario, pago y recalculación.
- **Caja**: historial del día, ventas del día (vista acotada para meseros), cierre de caja con archivado, anulación de pedidos y devolución de líneas con motivo.
- **Gastos**: CRUD de gastos operativos y gastos automáticos por consumo de insumos; edición y eliminación auditadas (borrado lógico con motivo).
- **Reportes**: cierre financiero por periodo (diario/semanal/quincenal/mensual/anual), utilidad neta, top platillos y descuentos.
- **Calendario**: planificación de disponibilidad de platillos y llegadas de insumos, más consulta de asistencias reales.
- **Cámaras**: registro, control de acceso y clips de video vía puente WebRTC.
- **Pagos en línea**: arquitectura de gateway con adaptador deshabilitado por defecto.
- **Auditoría**: bitácora de acciones sensibles (`RegistroAuditoria`).
- **Carta Digital pública**: menú filtrado y curado para clientes, sin exponer costos ni inventario.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.138.0 + Uvicorn |
| ORM | SQLAlchemy 2.x (`Mapped`, `mapped_column`, `relationship`) |
| Schemas | Pydantic v2 (`ConfigDict(from_attributes=True)`) |
| Base de datos | MySQL / MariaDB vía PyMySQL (PostgreSQL vía psycopg2, SQLite fallback) |
| Auth | python-jose (JWT HS256) + bcrypt directo |
| Migraciones | Alembic (declarado) + migraciones de arranque idempotentes en `app/main.py` |
| Imágenes | ImgBB API (vía `httpx`) + Pillow (resize/WebP) |
| Frontend | SPA Vanilla JS + CSS propio (sin build step) |
| HTTP client | httpx 0.28.1 |
| Pruebas | scripts E2E con `requests` + pytest |

---

## Arquitectura

Patrón por capas: **API → Service → Repository → Model**, con schemas Pydantic como contrato de entrada/salida.

```
Request HTTP
   │
   ▼
API (app/api/endpoints/*)        ← valida rol, arma dependencias, delega
   │
   ▼
Service (app/services/*)         ← reglas de negocio, lanza HTTPException
   │
   ▼
Repository (app/repositories/*)  ← SQLAlchemy, joinedload, queries
   │
   ▼
Model (app/models/*)             ← tablas y relaciones
```

Principios:

- Los **servicios** concentran las reglas de negocio y son los únicos que lanzan `HTTPException` (404/400/403) ante violaciones de reglas.
- Los **repositorios** solo acceden a datos (con `joinedload` para eager loading) y no conocen HTTP.
- Los **schemas** definen contratos; los de respuesta usan `from_attributes=True` para serializar ORM.
- El **frontend** consume exclusivamente `/api/v1/*` (ERP) o `/api/public/*` (carta), nunca la base de datos.

---

## Estructura del proyecto

```
app/
├── main.py                  # App FastAPI, CORS, registro de routers, mounts estáticos,
│                            #   migraciones de arranque, watchers (heartbeat, retención de clips)
├── core/
│   ├── config.py            # Settings (Pydantic Settings) leídos de .env
│   ├── database.py          # Engine, SessionLocal, Base, get_db(); detección de dialecto
│   ├── security.py          # bcrypt directo + JWT (SECRET_KEY/ALGORITHM/EXPIRACIÓN)
│   ├── tiempo.py            # Hora local Managua + día de negocio (ventana_dia_negocio)
│   └── vapid.py             # Claves VAPID derivadas de SECRET_KEY (Web Push)
├── api/
│   ├── deps.py              # get_current_user, requerir_rol(roles)
│   ├── auditoria.py         # Router de bitácora de auditoría
│   └── endpoints/           # Un archivo por dominio (personal, orden, caja, ...)
├── schemas/                 # Contratos Pydantic por dominio
├── models/                  # Modelos SQLAlchemy por dominio
├── repositories/            # Acceso a datos por dominio
├── services/                # Reglas de negocio por dominio
├── db/
│   ├── init_db.py           # Crea tablas y siembra datos de prueba (python -m app.db.init_db)
│   ├── cerrar_turnos_huerfanos.py  # Script manual de cierre de turnos
│   ├── actualizar_ejecutivos.py    # Ajusta precios/estructura de platos ejecutivos
│   └── restructurar_menu.py        # Reorganiza categorías/platillos del menú
└── Templates/               # Frontend servido por FastAPI
    ├── index.html           # SPA del ERP (personal autenticado)
    ├── css/style.css        # Design tokens + estilos del POS
    ├── js/app.js            # Toda la lógica del SPA
    ├── sw.js                # Service Worker de notificaciones push (Web Push)
    └── carta/               # Carta Digital pública (sin auth): index.html, css/, js/, img/
docs/
├── CALENDARIO.md            # Guía funcional y técnica del calendario
└── CAMARAS.md               # Guía del módulo de cámaras y puente WebRTC
tests/                       # Scripts E2E y tests unitarios
```

---

## Puesta en marcha

### Requisitos

- Python **3.12** (o compatible)
- MySQL/MariaDB en ejecución (o dejar `DATABASE_URL` vacío para usar SQLite local)

### Instalación

```bash
pip install -r requirements.txt
```

### Configurar entorno

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

### Inicializar la base de datos

```bash
python -m app.db.init_db
```

`init_db.py` crea todas las tablas y siembra catálogos, usuarios y datos de prueba (incluye empleados con asistencias/nóminas del periodo de prueba).

### Ejecutar

```bash
python -m app.main
# o
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

| Recurso | URL |
|---------|-----|
| ERP (SPA) | http://localhost:8000/Templates/index.html |
| Carta Digital | http://localhost:8000/carta/ |
| Swagger | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/healthcheck |

### Usuarios sembrados

| Usuario | Contraseña | Rol | Notas |
|---------|-----------|-----|-------|
| `joshi_0211` | `@0420311001000V` | Administrador | Auto-sembrado en arranque si la BD está vacía |
| `admin` | `password123` | Administrador | Sembrado por `init_db.py` |
| `gerente` | `password123` | Gerente | Sembrado por `init_db.py` |
| `mesero` | `password123` | Vendedor | Sembrado por `init_db.py` |

> Los usuarios Administrador y Gerente saltan la verificación de turno habilitado. Los **Vendedores** requieren que gerencia habilite su turno (`turno_habilitado=True`).

---

## Variables de entorno

Definidas en `app/core/config.py` (Pydantic Settings, archivo `.env`). Ver `.env.example`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | *(vacío)* | URL de conexión. Vacío ⇒ SQLite local. Acepta `mysql+pymysql://`, `postgresql://` |
| `SQLITE_PATH` | `./data/sazon_caribeno.db` | Archivo SQLite (solo si `DATABASE_URL` vacío) |
| `SECRET_KEY` | `your-secret-key-...` | Clave de firma JWT |
| `ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `525600` | Expiración del token (365 días) |
| `HARCA27_PASSWORD` | *(vacío)* | Contraseña opcional para crear la cuenta `Harca27` |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Servidor local |
| `DEBUG` | `true` | Modo depuración |
| `ENVIRONMENT` | `development` | Entorno |
| `HEARTBEAT_INTERVAL_SECONDS` | `300` | Intervalo del watcher de heartbeat |
| `HEARTBEAT_TIMEOUT_SECONDS` | `900` | Umbral para cerrar turnos huérfanos |
| `HORA_INICIO_DIA` | `7` | Hora de corte del día de negocio (7:00 AM → 7:00 AM) |
| `HOURS_PER_DAY` | `8` | Horas laborales por día |
| `OVERTIME_MULTIPLIER` | `1.0` | Multiplicador de horas extra (sin recargo) |
| `IVA_RATE` | `0.0` | IVA deshabilitado (precios netos) |
| `CORS_ORIGINS` | `http://127.0.0.1:5500,http://localhost:5500` | Orígenes permitidos (coma-separados) |
| `IMGBB_API_KEY` | *(vacío)* | API key de ImgBB para subir imágenes de platillos |
| `CAMERA_BRIDGE_BASE_URL` | *(vacío)* | Origen HTTPS del puente WebRTC (sin credenciales) |
| `CAMERA_STORAGE_DIR` | `app/data/camera-clips` | Directorio de clips de cámara |
| `CAMERA_ICE_SERVERS_JSON` | `[]` | Servidores STUN/TURN para WebRTC |
| `CAMERA_TURN_SHARED_SECRET` | *(vacío)* | Secreto compartido con Coturn |
| `PAYMENT_PROVIDER` | `disabled` | Proveedor de pagos activo |
| `PAYMENT_CURRENCY` | `NIO` | Moneda ISO 4217 |
| `PAYMENT_SUCCESS_URL` | *(vacío)* | URL de retorno tras pago exitoso |
| `PAYMENT_CANCEL_URL` | *(vacío)* | URL de retorno al cancelar checkout |
| `VAPID_PUBLIC_KEY` | *(derivada)* | Clave pública VAPID. Si se deja vacía se **deriva de `SECRET_KEY`** (determinista, estable entre reinicios) |
| `VAPID_PRIVATE_KEY` | *(derivada)* | Clave privada VAPID. Si se deja vacía se **deriva de `SECRET_KEY`** |
| `VAPID_SUBJECT` | `mailto:admin@sazoncaribeno.com` | Contacto del servidor de push (claim `sub` del JWT VAPID) |
| `PUSH_TTL` | `3600` | Segundos de vida de la notificación push (0 = entregar solo si el dispositivo está en línea) |
| `PUSH_TIMEOUT` | `15` | Timeout (segundos) de la llamada HTTP al servicio de push |

> **Las claves VAPID no necesitan configurarse en producción**: si `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` no están definidas, `app/core/vapid.py` las deriva de `SECRET_KEY` de forma determinista. Mientras `SECRET_KEY` no cambie (en Render es un valor generado y estable), las suscripciones de los dispositivos siguen siendo válidas entre reinicios. Si defines las claves a mano, deben ser un par coherente (las dos base64url de 65/32 bytes).

---

## Flujo de arranque

`app/main.py` ejecuta, al iniciar, una secuencia idempotente (pensada como red de seguridad porque las migraciones formales no siempre se corren en producción):

1. `Base.metadata.create_all()` — crea las tablas faltantes.
2. **Migraciones de columnas/estructura** (`_migrate_*`): agregan columnas y arreglan datos legacy si faltan. Son idempotentes (verifican `information_schema` antes de actuar). Ejemplos: `_migrate_orden_descuentos`, `_migrate_insumos_empaque`, `_migrate_usuarios_turno_habilitado`, `_migrate_menu_item_imagen_tiempo`.
3. **Arreglos y saneamiento** (`_fix_*`): corrigen cadenas de unidades, liberan mesas huérfanas, sanean turnos, fuerzan la contraseña de `joshi_0211` y archivan nombres de platos/usuarios eliminados.
4. **Auditoría de seguridad**: `_auditar_hashes()` reporta usuarios con hash no-bcrypt; `_auto_seed_admin()` / `_seed_harca27_admin()` crean cuentas administrativas si corresponde.
5. **Tareas de fondo**: `_heartbeat_watcher()` (cierra turnos huérfanos) y `_camera_clip_retention_watcher()` (depura clips antiguos).

> Estas funciones **no deben borrarse**: son la garantía de que la base de datos de producción mantenga su esquema sin depender de Alembic. Ver [Estado del proyecto](#estado-del-proyecto).

---

## Roles y permisos (RBAC)

Roles definidos en `RolEnum` (`app/schemas/personal.py`): **Administrador**, **Gerente**, **Vendedor**.

| Acción | Administrador | Gerente | Vendedor |
|--------|:-------------:|:-------:|:--------:|
| Leer la mayoría de endpoints | ✅ | ✅ | ✅ |
| Escribir menú / inventario | ✅ | ✅ | ❌ |
| Órdenes (crear, agregar/editar ítems) | ✅ | ✅ | ✅ |
| Pagar orden (libera mesa) | ✅ | ✅ | ✅ |
| Iniciar turno / check-in / check-out | ✅ | ✅ | ✅ |
| Gestionar plantillas de turno (CRUD) | ✅ | ✅ | ❌ |
| Habilitar turno de vendedores | ✅ | ✅ | ❌ |
| Dar de baja empleado | ✅ | ✅ | ❌ |
| Gastos operativos | ✅ | ✅ | ❌ |
| Consultar calendario | ✅ | ✅ | ✅ |
| Gestionar eventos de calendario | ✅ | ✅ | ❌ |
| Cierre de caja financiero (reportes) | ✅ | ✅ | ❌ |
| **Ver ventas del día (resumen)** | ✅ | ✅ | ✅ |
| Cerrar caja (archivar) | ✅ | ✅ | ❌ |
| Anular pedido / devolver ítem | ✅ | ✅ | ❌ |
| Editar / eliminar gasto (con motivo) | ✅ | ✅ | ❌ |
| Nómina | ✅ | ✅ | ❌ |
| Cámaras (gestión) | ✅ | ✅ | ❌ |
| Auditoría | ✅ | ✅ | ❌ |

Reglas de sesión adicionales:

- `get_current_user` valida en **cada petición** el usuario fresco de BD: si `activo == False` → `403 USUARIO_DESACTIVADO`; si es Vendedor con `turno_habilitado == False` → `403 TURNO_DESHABILITADO`. Esto invalida de inmediato las sesiones abiertas al deshabilitar un turno.
- El **cocinero** se identifica por su **Puesto** (nombre que contiene "cocin" o "chef"), no por rol. La app lo lleva directo al Panel de Cocina al iniciar sesión, pero **la navegación nunca se oculta por el puesto**: el bloqueo de navegación aplica solo al rol `Vendedor` y un Administrador/Gerente con puesto de cocina conserva sidebar y bottom nav completos.

---

## Módulos y reglas de negocio

Resumen de las reglas más relevantes. El detalle exhaustivo está en `AGENTS.md` y en `docs/`.

### Órdenes

- Máquina de estados: `PENDIENTE → PREPARANDO → ENTREGADA → PAGADA`; cualquier estado puede pasar a `CANCELADA` (revierte stock). Estados terminales: `PAGADA`, `CANCELADA`.
- **Una sola orden activa por mesa**. Los ítems nuevos se agregan con `POST /ordenes/{id}/items`.
- `mesa_id` es **nullable**: `NULL` = para llevar / venta directa (no marca mesa ocupada).
- **Edición de comanda**: `PUT /ordenes/{id}/items` reemplaza el contenido con el estado final deseado, ajustando inventario por diferencia y recalculando totales.
- **Pago**: `PUT /ordenes/{id}/pagar` marca `PAGADA` y libera la mesa y su apodo en una sola transacción.
- **Descuentos**: por línea (`descuento_porcentaje` / `descuento_monto`) o global (prorrateado). `Orden.total = subtotal − descuento_total`.

### Inventario

- Movimientos `ENTRADA`/`SALIDA` sobre `Insumo.cantidad_actual`.
- **Conversión de unidades** transitiva (`conversion_service.convertir_cantidad`) y **empaque por insumo** (`unidad_empaque_id` + `factor_empaque`).
- Cada `SALIDA` (manual o por receta) genera automáticamente un `Gasto` de categoría `SUMINISTROS`.
- **Producción por lote**: `PreparacionCocina` descuenta insumos cuyo `Receta.descuento_por_lote = True`.
- Cambiar la unidad base de un insumo exige un `factor_conversion_unidad` y convierte stock, costo y recetas vinculadas.

### Asistencia y turnos

- Timestamps en **hora local fija de Managua** (naive, sin conversión de zona).
- **Día de negocio** configurable (`HORA_INICIO_DIA`, default 7 AM): los turnos que cruzan medianoche pertenecen al servicio del día anterior.
- `iniciar_turno` es idempotente; no permite repetir el turno ya finalizado del día de negocio vigente.
- **Heartbeat**: los vendedores envían latidos; el watcher cierra turnos cuyo dueño ya no puede continuar (usuario inactivo / turno deshabilitado).
- **Cierres automáticos visibles**: todo cierre forzado (deshabilitación de turno o watcher) queda auditado como `TURNO_CERRADO_AUTOMATICAMENTE` con antes/después y causa; la API de habilitación de turnos informa cuántos turnos se cerraron (`turnos_cerrados`).
- **Check-out honesto**: si el turno ya fue cerrado automáticamente, `POST /asistencia/check-out` responde `409` con la hora de salida registrada y la causa (no un "éxito" engañoso); el empleado ve la advertencia y gerencia puede corregirla con Editar Horarios.
- **Habilitación de turnos con confirmation**: los botones de habilitación/deshabilitación masiva y por fila tienen etiquetas explícitas ("Habilitar Turnos (n/total)" / "Deshabilitar Turnos de Todos") y piden confirmación antes de deshabilitar, porque cerrar el turno de alguien es una acción forzosa.
- **Anulación**: `DELETE /asistencia/{id}` es borrado lógico con motivo obligatorio; los registros anulados no cuentan para nómina.

### Nómina

- `pago_base = salario_base / 2` (quincenal, fijo).
- `tarifa_hora = salario_base / 240`; `pago_neto = pago_base + horas_extras×tarifa_hora − adelantos` (mínimo 0).
- El salario es **por empleado** (`Empleado.salario_base`), no por puesto.
- Recalculación explícita con `recalcular=true` o `PUT /nomina/{id}/recalcular` sobre nóminas `PENDIENTE`.

### Caja y reportes

- **Caja abierta** = registros con `cierre_caja_id IS NULL`.
- `POST /caja/cierre` crea el `CierreCaja` y archiva órdenes pagadas y gastos pendientes.
- Panel del mesero (`GET /caja/ventas-dia`) muestra solo total vendido y órdenes; **nunca** gastos, nómina ni utilidad.
- `utilidad_neta = ingresos − nómina − insumos − gastos_operativos` (el costo de insumos usa solo el bucket `SUMINISTROS` para evitar doble contabilidad).

### Menú e imágenes

- `imagen_url` es **gestionado solo por el servidor**: se sube por `POST /menu/items/{id}/imagen` (multipart), se valida por contenido con Pillow, se comprime a WebP (≤1080 px) y se publica en ImgBB.
- Borrado lógico de platillos (`disponible=False`). Si no tiene ventas, un reinicio puede purgarlo; con ventas, se archiva renombrando el nombre.

### Notificaciones push (cocina ↔ salón)

Web Push con **VAPID** (`pywebpush`): el aviso llega al teléfono aunque la app esté cerrada o el navegador en segundo plano.

| Flujo | Quién recibe | Cuándo |
|-------|--------------|--------|
| Nueva comanda | Usuarios de **cocina** (su `Puesto` contiene "cocin"/"cosin"/"chef") | `POST /ordenes/`, `POST /ordenes/{id}/items`, `PUT /ordenes/{id}/items` |
| Comanda lista | El **mesero** que creó la orden (`orden.mesero_id`) | `PATCH /ordenes/{id}/estado` → `ENTREGADA` |

Reglas:

- **Solo se notifica a quien tiene el turno abierto** (asistencia activa y no anulada). Si el turno ya se cerró o fue anulado, no se entrega ninguna notificación.
- El mesero que creó la orden **no** recibe el aviso de cocina (evita autosnotificaciones).
- Los envíos corren como **tarea en segundo plano** (`BackgroundTasks`) con su propia sesión de BD: un fallo de push **jamás** rompe el flujo de la orden (queda solo en el log).
- Las suscripciones caducadas (respuesta `404`/`410` del servicio de push) se eliminan automáticamente.
- El service worker vive en `/Templates/sw.js` (ámbito `/Templates/`) y abre el ERP con enlace profundo: `?pantalla=comandero` para cocina, `?pantalla=salon&mesa=<id>` para el mesero.
- El cliente (JS) registra la suscripción con `POST /api/v1/push/subscribe` y la mantiene sincronizada en cada inicio de sesión.

---

## API

Todos los endpoints del ERP están bajo el prefijo **`/api/v1/`** y requieren autenticación (JWT `Bearer`) salvo el login y el healthcheck.

### Resumen por dominio

| Dominio | Prefijo | Ejemplos |
|---------|---------|----------|
| Auth | `/api/v1/auth` | `POST /login`, `GET /me`, `POST /verify` |
| Personal | `/api/v1/personal` | puestos, empleados, usuarios, reset-password, turnos masivos |
| Asistencia | `/api/v1/asistencia` | turnos, check-in/out, heartbeat, editar-horarios, anular |
| Nómina | `/api/v1/nomina` | calcular, generar, pagar, recalcular, adelantos |
| Inventario | `/api/v1/inventario` | insumos, movimientos, categorías, unidades, preparaciones |
| Menú | `/api/v1/menu` | items, categorías, imagen, recetas |
| Salón | `/api/v1/salon` | zonas, mesas, mapa, estado, apodo |
| Órdenes | `/api/v1/ordenes` | crear, items, estado, pagar, descuentos, retroactiva, anular, devolver-item |
| Caja | `/api/v1/caja` | historial-diario, ventas-dia, cierre |
| Gastos | `/api/v1/gastos` | CRUD con filtro por rango + editar/eliminar auditado |
| Descuentos | `/api/v1/descuentos` | descuentos frecuentes |
| Calendario | `/api/v1/calendario` | eventos + asistencias reales |
| Reportes | `/api/v1/reportes` | cierre financiero por periodo |
| Cámaras | `/api/v1/cameras` | cámaras, accesos, clips, tokens de stream |
| Pagos | `/api/v1/pagos` | disponibilidad, checkout, webhook |
| Auditoría | `/api/v1/auditoria` | bitácora paginada |
| Push | `/api/v1/push` | config, subscribe, unsubscribe, subscriptions |
| Backups | `/api/v1/backups` | gestión de copias de seguridad |

### Parámetros de filtrado habituales

| Endpoint | Parámetros |
|----------|-----------|
| `GET /ordenes/` | `?estado=&mesa_id=` |
| `GET /gastos/` | `?fecha_inicio=&fecha_fin=` |
| `GET /nomina/empleados/{id}/adelantos` | `?fecha_inicio=&fecha_fin=` |
| `GET /menu/items` | `?incluir_inactivos=true` (solo Admin/Gerente) |
| `GET /calendario/` | `?desde=&hasta=` (rango máximo 63 días) |
| `GET /reportes/cierre` | `?periodo=DIARIO|SEMANAL|QUINCENAL|MENSUAL|ANUAL` |

> La referencia interactiva completa está en **`/docs`** (Swagger UI) y **`/redoc`**.

---

## API pública (Carta Digital)

Endpoints de **solo lectura**, sin autenticación, para el menú de clientes por QR. Reutilizan los mismos modelos sin duplicar datos.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/public/menu` | Todos los platillos disponibles |
| GET | `/api/public/categories` | Todas las categorías |
| GET | `/api/public/menu/{categoria_id}` | Platillos disponibles por categoría |
| GET | `/api/public/item/{item_id}` | Detalle de un platillo disponible (404 si no existe/no disponible) |

**Seguridad**: los endpoints públicos solo serializan `id`, `nombre`, `descripcion`, `precio`, `disponible`, `imagen_url`, `tiempo_preparacion` y `categoria`. Nunca exponen costos, recetas, inventario, usuarios ni roles.

La Carta Digital (`app/Templates/carta/`, servida en `/carta/`) es un frontend **totalmente separado** del POS, sin autenticación y sin acceso al ERP.

---

## Despliegue

La configuración de Render está en `render.yaml`:

- **Runtime**: Python 3.12
- **Build**: `PIP_ONLY_BINARY=1 pip install --prefer-binary -r requirements.txt`
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Healthcheck**: `/healthcheck`

> En el dashboard de Render fija manualmente `IMGBB_API_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` y `SECRET_KEY`, y confirma las DB_*. Si `IMGBB_API_KEY` falta, la subida de imágenes responde 500.

> **Push (Web Push)**: no requiere variables adicionales. Las claves VAPID se derivan de `SECRET_KEY` (mientras no cambies esa variable, las suscripciones de los dispositivos siguen siendo válidas). Verifica que `https://sazoncaribe-o.onrender.com/Templates/sw.js` responde 200 después del despliegue.

### Frontend en producción: assets con URL estable y despliegue manual

- `app/Templates/index.html` carga `css/style.css` y `js/app.js` **sin parámetro de versión**: **la URL de los archivos nunca cambia**. El cache se resuelve con `Cache-Control: no-cache` + `ETag`/`304` (middleware `_revalidar_estaticos` en `app/main.py`), así que el navegador revalida en cada carga y nunca queda con un JS/CSS viejo **sin tocar ningún link**. No hay que subir ningún número de versión.
- El URL público es único y no debe cambiar: `https://sazoncaribe-o.onrender.com/Templates/index.html` (la Carta Digital vive en `/carta/`). Ojo: `sazoncaribeo.onrender.com` (sin guion) devuelve 404 de routing de Render; el dominio del servicio es `sazoncaribe-o`. Los enlaces profundos de las notificaciones (`?pantalla=…`, `?mesa=…`) se borran de la barra de direcciones al cargar la app: la URL visible siempre es la canónica.
- Si Render no despliega solo tras el push, haz **Manual Deploy → Clear build cache & deploy** en el servicio `sazoncaribe-o` y luego un hard-refresh (`Ctrl + Shift + R`) en el navegador.

---

## Pruebas

En `tests/` conviven dos tipos:

- **Scripts E2E con `requests`** que consumen la API en ejecución (por ejemplo `test_ordenes.py`, `test_calendario.py`, `test_cameras_api.py`). La mayoría requiere tener la API corriendo y datos sembrados (`python -m app.db.init_db`).
- **Tests unitarios / de integración** ejecutables con pytest (por ejemplo `test_horas_extras.py`, `test_nomina_calculator.py`, `test_password_auth.py`).

```bash
python -m app.db.init_db      # sembrar datos si el script lo requiere
python -m app.main            # API en http://localhost:8000
python tests/test_ordenes.py  # script E2E de ejemplo
# o, para los tests con pytest:
pytest tests/ -q
```

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| `AGENTS.md` | Referencia técnica exhaustiva: estructura, reglas de negocio, patrones y estado |
| `docs/CALENDARIO.md` | Guía funcional y técnica del calendario |
| `docs/CAMARAS.md` | Módulo de cámaras y puente WebRTC |
| `DOCUMENTACION_FRONTEND.md` | Notas sobre el frontend |
| `PRODUCT.md` | Descripción de producto |

---

## Estado del proyecto

- **Migraciones**: no se generan migraciones Alembic; el esquema se mantiene con `create_all` + migraciones de arranque idempotentes en `app/main.py`.
- **Tokens**: no hay flujo de refresh; un único access token de larga duración (365 días).
- **Pagos en línea**: la arquitectura de gateway existe pero permanece deshabilitada (`PAYMENT_PROVIDER=disabled`) hasta registrar un adaptador real.
- **Zona horaria**: asistencia usa hora local fija de Managua sin conversión; registros históricos previos al cambio están en UTC naive.
