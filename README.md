# Sazón Caribeño POS

Sistema integral de gestión para restaurantes (**ERP / POS**) construido con **FastAPI + SQLAlchemy 2.x + Pydantic v2** y base de datos **MySQL/MariaDB** (PostgreSQL y SQLite soportados como alternativas). Incluye un SPA en **Vanilla JS** para el personal y una **Carta Digital pública** (menú por QR, sin autenticación) para los clientes.

> Nota honesta: esto empezó siendo un POS y terminó siendo un pequeño ERP. Si vienes buscando el archivo donde está "todo", no existe. Aquí todo está en su sitio, más o menos.

---

## Tabla de contenido

- [Características](#características)
- [Stack tecnológico](#stack-tecnológico)
- [Arquitectura](#arquitectura)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Puesta en marcha](#puesta-en-marcha)
- [Variables de entorno](#variables-de-entorno)
- [Flujo de arranque](#flujo-de-arranque)
- [Roles y permisos](#roles-y-permisos)
- [Módulos y reglas de negocio](#módulos-y-reglas-de-negocio)
- [Carta Digital](#carta-digital)
- [API](#api)
- [Despliegue](#despliegue)
- [Pruebas](#pruebas)
- [Documentación adicional](#documentación-adicional)
- [Estado del proyecto y deuda técnica](#estado-del-proyecto-y-deuda-técnica)
- [Notas del desarrollador](#notas-del-desarrollador)

---

## Características

- **Salón**: mapa de mesas por zona, estados (LIBRE, OCUPADA, RESERVADA, MANTENIMIENTO), apodo temporal del cliente, fusión de mesas con colores y desfusión sin cerrar comandas.
- **Órdenes y comandas**: varias comandas por mesa o para llevar, edición completa de la comanda, descuentos por línea y globales, pagos parciales y divididos, comprobantes individuales, anulación y devolución de líneas con auditoría, venta retroactiva.
- **KDS (Panel de Cocina)**: vista con botones "Empezar preparación" y "Listo", tiempos de espera con semáforo, auto-refresco y perfil de cocinero por puesto.
- **Menú y recetas**: categorías y platillos dinámicos, imagen subida a ImgBB con compresión WebP, tiempo de preparación, recetas con conversión de unidades, producción por lote.
- **Inventario**: insumos, categorías, unidades con conversión transitiva, empaque por insumo, movimientos ENTRADA/SALIDA, alertas de stock y **importación inteligente** desde Excel, CSV, TXT, PDF o DOCX con apoyo de IA.
- **Personal**: puestos, empleados, usuarios, plantillas de turno, habilitación individual o masiva de turnos y permisos funcionales por usuario.
- **Asistencia**: check-in/check-out, heartbeat, día de negocio configurable, cierre automático auditado, reactivación de turnos, edición de horarios y anulación con motivo.
- **Nómina**: prorrateo por día (1 a 30 días), horas extras, adelantos, pago y recálculo de nóminas pendientes.
- **Caja**: historial del día, panel acotado de ventas para meseros, cierre manual y cierre automático a medianoche, anulación de pedidos y devolución de líneas.
- **Gastos**: CRUD con filtros, gastos automáticos por consumo de insumos, edición y eliminación lógica auditadas.
- **Reportes**: cierre financiero por periodo, utilidad neta, descuentos, top de platillos y desglose de gastos.
- **Auditoría**: bitácora paginada con antes/después, consulta para administración y eliminación de registros solo por Administrador.
- **Calendario**: planificación de disponibilidad de platillos y llegadas de insumos, más consulta de asistencias reales.
- **Notificaciones push**: Web Push con VAPID, preferencias por usuario (cocina, mesero, todas, fuera de turno) y service worker con enlaces profundos.
- **Estudio de mercado**: generación mensual o manual con Gemini, métricas reales del negocio, documentos adjuntos, chat asesor e informe HTML descargable con gráficas SVG.
- **Copias de seguridad**: volcado completo dentro de la base de datos, descarga, restauración y copia automática mensual.
- **Carta Digital pública**: libro de páginas que se voltean, generado en el navegador desde la API, con selector ES/EN, fotos progresivas y visor de zoom.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.138.0 + Uvicorn |
| ORM | SQLAlchemy 2.x (`Mapped`, `mapped_column`, `relationship`) |
| Schemas | Pydantic v2 (`ConfigDict(from_attributes=True)`) |
| Base de datos | MySQL/MariaDB vía PyMySQL (PostgreSQL vía psycopg2, SQLite local) |
| Auth | python-jose (JWT HS256) + bcrypt directo |
| Migraciones | `create_all` + migraciones de arranque idempotentes en `app/main.py` (Alembic está declarado, pero no se usa todavía) |
| Imágenes | ImgBB API vía `httpx` + Pillow (validación, resize y WebP) |
| Frontend | SPA Vanilla JS + CSS propio, sin build step |
| Utilidades CSS | Tailwind precompilado (`css/tailwind.min.css`, ~30 KB) |
| Push | `pywebpush` 2.0.1 + VAPID derivado de `SECRET_KEY` |
| IA | Google Gemini (rotación de modelos y reintentos) |
| Libro de la carta | StPageFlip vendorizado (sin CDN) |
| Zona horaria | `tzdata` + `ZoneInfo("America/Managua")` |
| Pruebas | pytest (177 pruebas) |

---

## Arquitectura

Patrón por capas: **API → Service → Repository → Model**, con schemas Pydantic como contrato de entrada y salida.

```
Solicitud HTTP
   │
   ▼
API (app/api/endpoints/*)        valida token, rol o permiso y delega
   │
   ▼
Service (app/services/*)         reglas de negocio; lanza HTTPException
   │
   ▼
Repository (app/repositories/*)  SQLAlchemy, joinedload, consultas
   │
   ▼
Model (app/models/*)             tablas y relaciones
```

Principios que sí se respetan:

- Los **servicios** concentran las reglas de negocio y son los que lanzan `HTTPException` (400/403/404) ante violaciones.
- Los **repositorios** solo acceden a datos y no conocen HTTP.
- Los **schemas** definen contratos; los de respuesta usan `from_attributes=True`.
- El **frontend** consume `/api/v1/*` (ERP) o `/api/public/*` (carta), nunca la base de datos.

Principios que se respetan "cuando se puede":

- La capa API no debería tener lógica de negocio. En la práctica hay endpoints que calculan cosas; están marcados en la documentación técnica para no repetir el pecado.

---

## Estructura del proyecto

```
app/
├── main.py                  # App FastAPI, CORS, routers, mounts, migraciones de arranque y watchers
├── core/
│   ├── config.py            # Settings (Pydantic Settings) leídos de .env
│   ├── database.py          # Engine, SessionLocal, Base, get_db()
│   ├── security.py          # bcrypt directo + JWT
│   ├── tiempo.py            # Hora local Managua y día de negocio
│   ├── permisos.py          # Catálogo de 18 permisos y resolución de overrides
│   ├── vapid.py             # Claves VAPID derivadas de SECRET_KEY
│   ├── slug.py              # Generador de slugs públicos estilo Render
│   └── novedades.py         # Fuente de verdad de las novedades del sistema
├── api/
│   ├── deps.py              # get_current_user, requerir_rol, requerir_permiso
│   ├── auditoria.py         # Router de bitácora
│   └── endpoints/           # Un archivo por dominio (personal, orden, caja, ...)
├── schemas/                 # Contratos Pydantic por dominio
├── models/                  # Modelos SQLAlchemy por dominio
├── repositories/            # Acceso a datos por dominio
├── services/                # Reglas de negocio por dominio
├── utils/
│   └── calculations.py      # Cálculo de horas extras
├── db/
│   ├── init_db.py           # Crea tablas y siembra datos de prueba
│   ├── traducciones.py      # Siembra inicial de traducciones EN
│   ├── traducciones_carta.json
│   ├── actualizar_ejecutivos.py
│   ├── cerrar_turnos_huerfanos.py
│   └── restructurar_menu.py
└── Templates/               # Frontend servido por FastAPI
    ├── index.html           # SPA del ERP
    ├── css/style.css        # Design tokens, componentes y modo oscuro
    ├── css/tailwind.min.css # Utilidades precompiladas
    ├── js/app.js            # Lógica del SPA
    ├── sw.js                # Service Worker de Web Push
    └── carta/               # Carta Digital pública
        ├── index.html
        ├── css/estilo.css
        ├── js/menu-libro.js
        ├── vendor/page-flip.browser.js
        └── img/
docs/
├── CALENDARIO.md
├── CAMARAS.md
└── DOCUMENTACION_TECNICA.md
tests/                       # 30 archivos de pruebas, 177 casos con pytest
tools/
└── purgar_auditoria.py      # Archivo masivo de auditoría con respaldo previo
```

---

## Puesta en marcha

### Requisitos

- Python **3.12** o superior (producción usa 3.12)
- MySQL/MariaDB en ejecución, o dejar `DATABASE_URL` vacío para usar SQLite local

### Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### Configurar entorno

```bash
cp .env.example .env
# Editar .env con credenciales y claves
```

### Inicializar la base de datos

```bash
python -m app.db.init_db
```

`init_db.py` crea todas las tablas y siembra catálogos, usuarios y datos de prueba.

### Ejecutar

```bash
python -m app.main
# o
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

| Recurso | URL |
|---------|-----|
| ERP (SPA) | http://localhost:8000/ |
| Carta Digital | http://localhost:8000/carta/ |
| Documentación interactiva | http://localhost:8000/docs |
| Healthcheck | http://localhost:8000/healthcheck |

### Usuarios sembrados

| Usuario | Contraseña | Rol | Notas |
|---------|-----------|-----|-------|
| `joshi_0211` | `@0420311001000V` | Administrador | Auto-sembrado en arranque si la base está vacía |
| `admin` | `password123` | Administrador | Sembrado por `init_db.py` |
| `gerente` | `password123` | Gerente | Sembrado por `init_db.py` |
| `mesero` | `password123` | Vendedor | Sembrado por `init_db.py` |

> Las cuentas de prueba son para desarrollo. Cámbialas antes de publicar el sistema en producción. Sí, esto va en serio.

---

## Variables de entorno

Definidas en `app/core/config.py` (Pydantic Settings, archivo `.env`). Ver `.env.example`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | *(vacío)* | URL de conexión. Vacío usa SQLite. Acepta `mysql+pymysql://` y `postgresql://` |
| `SQLITE_PATH` | `./data/sazon_caribeno.db` | Archivo SQLite cuando `DATABASE_URL` está vacío |
| `SECRET_KEY` | `your-secret-key-...` | Firma de JWT y base de derivación VAPID |
| `ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `525600` | Expiración del token (365 días) |
| `HARCA27_PASSWORD` | *(vacío)* | Contraseña opcional para crear la cuenta `Harca27` |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Servidor local |
| `DEBUG` | `true` | Modo depuración |
| `ENVIRONMENT` | `development` | Entorno |
| `HEARTBEAT_INTERVAL_SECONDS` | `300` | Intervalo del watcher de heartbeat |
| `HEARTBEAT_TIMEOUT_SECONDS` | `900` | Umbral para cerrar turnos huérfanos |
| `AUTO_CERRAR_TURNOS` | `false` | Cierre automático de turnos (hoy se controla por usuario, no por esta bandera) |
| `HORA_INICIO_DIA` | `7` | Hora de corte del día de negocio (7:00 a 7:00) |
| `HOURS_PER_DAY` | `8` | Horas laborales por día |
| `OVERTIME_MULTIPLIER` | `1.0` | Multiplicador de horas extra (sin recargo) |
| `IVA_RATE` | `0.0` | IVA deshabilitado: los precios ya lo incluyen |
| `CORS_ORIGINS` | `http://127.0.0.1:5500,http://localhost:5500` | Orígenes permitidos, separados por coma |
| `CARTA_RUTA_PUBLICA` | `/carta` | Ruta pública de la Carta Digital |
| `IMGBB_API_KEY` | *(vacío)* | API key de ImgBB para imágenes de platillos |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | *(derivadas)* | Claves VAPID. Si faltan se derivan de `SECRET_KEY` |
| `VAPID_SUBJECT` | `mailto:admin@sazoncaribeno.com` | Contacto del servidor push |
| `PUSH_TTL` | `3600` | Vida de la notificación push en segundos |
| `PUSH_TIMEOUT` | `15` | Timeout del envío push |
| `CAMERA_BRIDGE_BASE_URL` | *(vacío)* | Origen HTTPS del puente WebRTC |
| `CAMERA_STORAGE_DIR` | `app/data/camera-clips` | Directorio de clips de cámaras |
| `CAMERA_ICE_SERVERS_JSON` | `[]` | Servidores STUN/TURN |
| `CAMERA_TURN_SHARED_SECRET` | *(vacío)* | Secreto compartido con Coturn |
| `GEMINI_API_KEY` | *(vacío)* | API key de Google AI Studio |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Modelo principal |
| `GEMINI_MODELOS_RESPALDO` | `gemini-3.6-flash,...` | Modelos de respaldo separados por coma |
| `GEMINI_TIMEOUT` | `120` | Espera por respuesta |
| `GEMINI_MAX_INTENTOS` | `4` | Intentos totales rotando modelos |
| `GEMINI_MAX_CARACTERES_DOCUMENTO` | `120000` | Texto máximo enviado a la IA por documento |
| `ESTUDIO_MERCADO_DIA` | `1` | Día del mes para el estudio automático |
| `ESTUDIO_MERCADO_HORA` | `6` | Hora local desde la que corre el estudio automático |
| `ESTUDIO_MERCADO_INTERVALO_SEGUNDOS` | `3600` | Frecuencia del watcher de estudio |
| `PAYMENT_PROVIDER` | `disabled` | Proveedor de pagos; deshabilitado por defecto |
| `PAYMENT_CURRENCY` | `NIO` | Moneda ISO 4217 |
| `PAYMENT_SUCCESS_URL` / `PAYMENT_CANCEL_URL` | *(vacío)* | URLs de retorno del checkout |

> Las claves VAPID no requieren configuración manual: `app/core/vapid.py` las deriva de `SECRET_KEY` de forma determinista. Mientras `SECRET_KEY` no cambie, las suscripciones de los dispositivos siguen siendo válidas.

---

## Flujo de arranque

`app/main.py` ejecuta una secuencia idempotente al iniciar, pensada como red de seguridad porque las migraciones formales no siempre se corren en producción:

1. `Base.metadata.create_all()` crea las tablas faltantes.
2. **Migraciones de columnas y estructura** (`_migrate_*`): agregan columnas y corrigen datos legacy. Verifican `information_schema` antes de actuar.
3. **Saneamiento** (`_fix_*`): cadenas de unidades, mesas huérfanas, turnos, nombres archivados y contraseña de `joshi_0211`.
4. **Auditoría de seguridad**: `_auditar_hashes()` reporta hashes no bcrypt y se crean las cuentas administrativas si corresponde.
5. **Siembra de novedades y traducciones**: `_sembrar_novedades()` y `_sembrar_traducciones_carta()` solo rellenan lo que falta.
6. **Tareas de fondo**: heartbeat, cierre automático de caja, retención de clips, estudio de mercado mensual y difusión de novedades.

> Estas funciones no deben borrarse sin reemplazarlas: son la garantía de que la base de producción mantenga su esquema.

---

## Roles y permisos

Roles definidos en `RolEnum` (`app/schemas/personal.py`): **Administrador**, **Gerente**, **Vendedor**. Además existen **18 permisos funcionales** que se pueden conceder o quitar por usuario.

### Matriz de roles por defecto

| Acción | Administrador | Gerente | Vendedor |
|--------|:-------------:|:-------:|:--------:|
| Leer la mayoría de endpoints | Sí | Sí | Sí |
| Menú e inventario (escritura) | Sí | Sí | No |
| Órdenes (crear, editar, agregar ítems) | Sí | Sí | Sí |
| Pagar orden y liberar mesa | Sí | Sí | Sí |
| Iniciar turno, check-in y check-out | Sí | Sí | Sí |
| Gestionar plantillas de turno | Sí | Sí | No |
| Habilitar turnos de vendedores | Sí | Sí | No |
| Dar de baja empleados | Sí | Sí | No |
| Gastos operativos | Sí | Sí | No |
| Consultar calendario | Sí | Sí | Sí |
| Gestionar eventos de calendario | Sí | Sí | No |
| Cierre de caja financiero | Sí | Sí | No |
| Ver ventas del día (resumen) | Sí | Sí | Sí |
| Cerrar caja (archivar) | Sí | Sí | No |
| Anular pedido o devolver ítem | Sí | Sí | No |
| Editar o eliminar gasto | Sí | Sí | No |
| Nómina | Sí | Sí | No |
| Auditoría | Sí | Sí | No |
| Copias de seguridad | Sí | No | No |

### Permisos funcionales

- Catálogo en `app/core/permisos.py`, agrupado en cinco áreas: Menú y Carta, Inventario, Caja y dinero, Personal y nómina, Administración.
- `Usuario.permisos` guarda solo los overrides (`{clave: true/false}`); `NULL` significa "los del rol".
- Los permisos críticos (`personal_gestionar`, `permisos_gestionar`, `auditoria_ver`, `backups_gestionar`) solo los concede un Administrador.
- El rol Administrador conserva siempre el catálogo completo.
- La UI bloquea elementos con `data-permiso` y `navigateTo()` valida contra `PERMISOS_PANTALLA`; el backend usa `requerir_permiso(clave)`.

### Reglas de sesión

- `get_current_user` valida en cada petición el usuario fresco de base de datos:
  - `activo == False` devuelve `403 USUARIO_DESACTIVADO`.
  - Vendedor con `turno_habilitado == False` devuelve `403 TURNO_DESHABILITADO`.
- El **cocinero** se identifica por su **puesto** (nombre que contiene "cocin", "cosin" o "chef"), no por rol.
- La navegación nunca se oculta por el puesto; como máximo se restringe por rol.

---

## Módulos y reglas de negocio

Resumen de las reglas más relevantes. El detalle exhaustivo está en `AGENTS.md` y en `docs/DOCUMENTACION_TECNICA.md`.

### Órdenes y comandas

- Máquina de estados: `PENDIENTE → PREPARANDO → ENTREGADA → PAGADA`; cualquier estado activo puede pasar a `CANCELADA`, que revierte stock.
- `mesa_id` es nullable: `NULL` significa para llevar o venta directa y no marca mesa ocupada.
- Varias comandas por mesa o fusión de mesas. La mesa solo vuelve a LIBRE cuando se cobra o cancela la última comanda.
- Edición de comanda con `PUT /ordenes/{id}/items`: el cuerpo es el estado final deseado; el inventario se ajusta por diferencia.
- Una comanda con pagos registrados no se puede editar, ampliar ni descontar.
- Descuentos por línea o globales (prorrateados). `total = subtotal − descuento_total`.
- Anulación y devolución de líneas son borrado lógico y auditado; nunca `db.delete`.

### Inventario

- Movimientos ENTRADA/SALIDA sobre `Insumo.cantidad_actual`.
- Conversión transitiva de unidades y empaque por insumo (`unidad_empaque_id` + `factor_empaque`).
- Cada SALIDA manual o por receta genera un `Gasto` de categoría `SUMINISTROS`.
- Producción por lote: `PreparacionCocina` descuenta solo los insumos con `Receta.descuento_por_lote = True`.
- Cambiar la unidad base de un insumo exige factor de conversión y convierte stock, costo y recetas.
- Importación inteligente: analiza el archivo, propone filas editables y solo escribe cuando el usuario confirma, todo en una transacción.

### Asistencia y turnos

- Timestamps en hora local fija de Managua, sin conversión de zona.
- Día de negocio configurable (`HORA_INICIO_DIA`, por defecto 7:00). Un turno iniciado a la 1:00 pertenece al servicio del día anterior.
- `iniciar_turno` es idempotente y no permite repetir el turno ya finalizado del día de negocio.
- Heartbeat: el watcher cierra turnos cuyo dueño ya no puede continuar (usuario inactivo o turno deshabilitado).
- Todo cierre forzado queda auditado como `TURNO_CERRADO_AUTOMATICAMENTE` con causa y antes/después.
- Check-out sobre un turno ya cerrado devuelve `409` con la hora registrada y la causa; nunca un éxito engañoso.
- Anulación de asistencia: borrado lógico con motivo obligatorio; los registros anulados no cuentan para nómina.

### Nómina

- `salario_diario = salario_mensual / 30`; `pago_base = salario_diario × días_del_rango`.
- Se puede pagar cualquier cantidad de días: 3 días es 10%, 7 días es 23.33%, 15 días es 50%, 30 días es 100%.
- `tarifa_hora = salario_base / 240` (sin recargo); `pago_neto = pago_base + horas_extras × tarifa_hora − adelantos`, con mínimo 0.
- El salario es por empleado (`Empleado.salario_base`), no por puesto.
- Recálculo explícito con `recalcular=true` o `PUT /nomina/{id}/recalcular` sobre nóminas PENDIENTES.

### Caja y reportes

- Caja abierta son los registros con `cierre_caja_id IS NULL`.
- `POST /caja/cierre` crea el `CierreCaja` y archiva órdenes pagadas y gastos pendientes.
- El cierre automático corre a medianoche de Managua y archiva también gastos aunque no haya órdenes pagadas.
- El panel del mesero muestra solo total vendido y órdenes; nunca gastos, nómina ni utilidad.
- `utilidad_neta = ingresos − nómina − insumos − gastos_operativos`; el costo de insumos usa solo el bucket `SUMINISTROS` para evitar doble contabilidad.

### Menú e imágenes

- `imagen_url` lo gestiona solo el servidor: se sube por `POST /menu/items/{id}/imagen`, se valida por contenido con Pillow, se comprime a WebP (máximo 1080 px) y se publica en ImgBB.
- Borrado lógico de platillos (`disponible=False`). Si no tiene ventas, un reinicio puede purgarlo; con ventas, se archiva renombrando el nombre.
- Traducciones EN editables desde el sistema (`nombre_en`, `descripcion_en`, `categorias_menu.nombre_en`).

### Notificaciones push

| Flujo | Quién recibe | Cuándo |
|-------|--------------|--------|
| Nueva comanda | Usuarios con `avisos_cocina` activo | Al crear o editar una comanda |
| Comanda lista | Mesero de la orden con `avisos_mesero` activo | Al pasar a ENTREGADA |
| Comanda de otro mesero | Quien tenga `avisos_mesero_todas` | Al pasar a ENTREGADA |
| Novedad del sistema | Usuarios activos | Al publicar una versión |
| Estudio de mercado | Administración | Al completarse un estudio |

- El envío corre en segundo plano: un fallo de push nunca rompe el flujo de la orden.
- Las suscripciones caducadas (404/410) se eliminan automáticamente.
- El service worker vive en `/Templates/sw.js` y abre el ERP con enlaces profundos.

---

## Carta Digital

La carta pública es un **libro de páginas que se voltean**, dibujado en el navegador con los datos reales del menú. No hay imágenes fijas que regenerar: crear, editar, ocultar o borrar un platillo en Gestión de Menú se refleja al recargar la carta.

- Fuentes de datos: `GET /api/public/menu` y `GET /api/public/categories`.
- Motor: `app/Templates/carta/js/menu-libro.js` (agrupa, mide capacidad real, reparte parejo, encadena secciones, carga fotos en cola de 4 y reintenta fallos transitorios).
- Hoja de 1200 × 1800 dibujada una vez y escalada con `transform: scale()`, sin reflow.
- Bebidas y Extras se muestran como lista compacta sin fotos y comparten hojas.
- Selector ES/EN con traducciones en base de datos y respaldo al español.
- Visor de zoom a pantalla completa que clona la hoja, con gestos táctiles para iOS.
- Ruta pública configurable con `CARTA_RUTA_PUBLICA`; los enlaces viejos a `/carta` redirigen conservando la subruta.

---

## API

Todos los endpoints del ERP están bajo **`/api/v1/`** y requieren JWT `Bearer` salvo el login y el healthcheck.

### Resumen por dominio

| Dominio | Prefijo | Ejemplos |
|---------|---------|----------|
| Auth | `/api/v1/auth` | `POST /login`, `GET /me` |
| Personal | `/api/v1/personal` | puestos, empleados, usuarios, permisos, turnos masivos |
| Asistencia | `/api/v1/asistencia` | turnos, check-in/out, heartbeat, editar-horarios, anular, reactivar |
| Nómina | `/api/v1/nomina` | calcular, generar, pagar, recalcular, adelantos |
| Inventario | `/api/v1/inventario` | insumos, movimientos, categorías, unidades, preparaciones, importaciones |
| Menú | `/api/v1/menu` | items, categorías, imagen, recetas |
| Salón | `/api/v1/salon` | zonas, mesas, mapa, estado, apodo, fusión |
| Órdenes | `/api/v1/ordenes` | crear, items, estado, pagar, pagos parciales, descuentos, retroactiva, anular, devolver-item |
| Caja | `/api/v1/caja` | historial-diario, ventas-dia, cierre, cierre-automatico |
| Gastos | `/api/v1/gastos` | CRUD con filtros y operaciones auditadas |
| Descuentos | `/api/v1/descuentos` | catálogo de descuentos frecuentes |
| Calendario | `/api/v1/calendario` | eventos y asistencias reales |
| Reportes | `/api/v1/reportes` | cierre financiero por periodo |
| Auditoría | `/api/v1/auditoria` | bitácora paginada y eliminación (solo Administrador) |
| Push | `/api/v1/push` | config, preferencias, subscribe, subscriptions |
| Backups | `/api/v1/backups` | crear, listar, descargar, restaurar, eliminar |
| Estudio de mercado | `/api/v1/estudio-mercado` | generar, listar, detalle, exportar, documentos, chat |
| Novedades | `/api/v1/novedades` | historial de versiones |
| Cámaras | `/api/v1/cameras` | cámaras, accesos, clips, tokens de stream |
| Pagos | `/api/v1/pagos` | disponibilidad, checkout, webhook |

### Parámetros de filtrado habituales

| Endpoint | Parámetros |
|----------|-----------|
| `GET /ordenes/` | `?estado=&mesa_id=&solo_activas=&limite=` |
| `GET /gastos/` | `?fecha_inicio=&fecha_fin=` |
| `GET /nomina/empleados/{id}/adelantos` | `?fecha_inicio=&fecha_fin=` |
| `GET /menu/items` | `?incluir_inactivos=true` (solo Admin/Gerente) |
| `GET /calendario/` | `?desde=&hasta=` (máximo 63 días) |
| `GET /reportes/cierre` | `?periodo=DIARIO\|SEMANAL\|QUINCENAL\|MENSUAL\|ANUAL` |

> La referencia interactiva completa está en `/docs` (Swagger UI) y `/redoc`. En producción esas rutas son públicas; ver "Estado del proyecto".

### API pública de la Carta Digital

Solo lectura, sin autenticación, con campos públicos (sin costos, recetas, inventario, usuarios ni roles):

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/public/menu` | Todos los platillos disponibles |
| GET | `/api/public/categories` | Todas las categorías |
| GET | `/api/public/menu/{categoria_id}` | Platillos disponibles por categoría |
| GET | `/api/public/item/{item_id}` | Detalle de un platillo disponible |

---

## Despliegue

La configuración de Render está en `render.yaml`:

- **Runtime**: Python 3.12
- **Build**: `PIP_ONLY_BINARY=1 pip install --prefer-binary -r requirements.txt`
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Healthcheck**: `/healthcheck`

Checklist de producción:

1. `SECRET_KEY` estable y distinto al de desarrollo. Si cambia, se invalidan los JWT y las suscripciones push.
2. `IMGBB_API_KEY` configurada; sin ella la subida de imágenes responde 500.
3. `ACCESS_TOKEN_EXPIRE_MINUTES` no debe estar fijado en 480; el valor correcto es 525600.
4. Verificar que `/Templates/sw.js` responde 200 y que `GET /api/v1/push/config` devuelve `habilitado: true`.
5. Si `CARTA_RUTA_PUBLICA` no es `/carta`, los enlaces antiguos redirigen automáticamente.
6. Tras el despliegue, comprobar el healthcheck y el login con una cuenta real.

> En Render el filesystem es efímero. Por eso las copias de seguridad se guardan dentro de la base de datos y no en disco.

---

## Pruebas

La suite usa pytest y no toca la base real de producción:

```bash
python -m pytest tests -q
```

Cobertura actual: **177 pruebas en 30 archivos**. Cubren autenticación, permisos, menú, inventario e importación, órdenes y pagos, fusión de mesas, cierre automático, auditoría, backups, calendario, carta digital, traducciones, seguridad y casos de regresión.

Para pruebas manuales de la API se puede levantar el servidor y usar `/docs`; no hay scripts E2E con `requests` en la suite actual.

---

## Documentación adicional

| Documento | Contenido |
|-----------|-----------|
| `AGENTS.md` | Referencia técnica exhaustiva: estructura, reglas, patrones y estado |
| `docs/DOCUMENTACION_TECNICA.md` | Especificación funcional y técnica completa del sistema (v2.0) |
| `Sazon caribeño.pdf` | Especificación en PDF, generada desde `docs/DOCUMENTACION_TECNICA.md` |
| `docs/archivo/` | Versiones anteriores de la especificación (v1.0, julio 2026) |
| `docs/CALENDARIO.md` | Guía funcional y técnica del calendario |
| `docs/CAMARAS.md` | Módulo de cámaras y puente WebRTC |
| `DOCUMENTACION_FRONTEND.md` | Notas del frontend |
| `PRODUCT.md` | Descripción de producto |

---

## Estado del proyecto y deuda técnica

Lo que está pendiente, dicho sin adornos:

- **Migraciones**: no se generan migraciones Alembic. El esquema se mantiene con `create_all` y migraciones de arranque idempotentes en `app/main.py`. Funciona, pero no es lo que un manual llamaría "buena práctica".
- **Tokens**: no hay refresh token. Un único access token de 365 días; la sesión se corta por desactivación de usuario o turno, no por expiración.
- **Pagos en línea**: la arquitectura del gateway existe, pero permanece deshabilitada hasta registrar un adaptador real.
- **Seguridad pendiente**: `POST /auth/login` no tiene límite de intentos; los mensajes distinguen "no existe el usuario" de "contraseña incorrecta"; `/docs`, `/redoc` y `/openapi.json` son públicos.
- **Credenciales**: la contraseña de `joshi_0211` se fuerza en cada arranque por compatibilidad histórica. Debe rotarse y eliminarse ese mecanismo.
- **Cámaras**: el módulo existe y tiene pruebas, pero depende de un puente WebRTC externo y de almacenamiento persistente para clips.
- **Zona horaria**: los registros históricos anteriores al cambio a hora local están en UTC naive (6 horas de diferencia).
- **Código heredado**: hay archivos de utilidades sueltos en la raíz (`check_*.py`, `test_*.py`, `truncate_production.*`) que no forman parte de la aplicación y deberían moverse a `tools/` o eliminarse.
- **Módulos vacíos**: `usuario_service.py` y algunos `__init__.py` no exportan lo que aparentan.

---

## Notas del desarrollador

Un par de cosas que conviene saber antes de abrir un archivo al azar:

- El corazón del sistema es `app/services/orden_service.py`. Si algo se rompe en ventas, casi siempre es ahí. Si funciona, no lo toques.
- `app/main.py` tiene más funciones de arranque que una navidad. No son decorativas: son la migración real. Si las borras, la base de producción se queda a medias.
- Las fechas de asistencia son hora local de Managua sin zona horaria. No agregues `Z`, no conviertas, no "arregles" eso: está así a propósito.
- El motor de la Carta Digital mide cuántos platillos caben en una hoja antes de dibujarlos. Si cambias el CSS de la carta, vuelve a probar la paginación: no hay números mágicos que ajustar, pero sí un medidor que se ofende fácilmente.
- El modo oscuro se resuelve con variables `--mix-*` y `color-mix()`. Escribir un color literal nuevo es la forma más rápida de que el tema claro se vea distinto y alguien lo note.
- No hay build step para el frontend. Es Vanilla JS a propósito. Sí, 16 mil líneas en un solo archivo. No, todavía no vale la pena partirlo sin pruebas de regresión.
- Las imágenes de varios platillos son el logo del restaurante. No es un bug del sistema; es lo que hay cargado en el menú.
- Si algo falla y no sabes por qué, revisa primero el inventario y luego el turno. El 80% de los tickets raros vienen de ahí.
- Este documento y el código se actualizan a mano. Si encuentras una contradicción, gana el código. Suerte para quien lea esto dentro de seis meses.

---

Hecho para Sazón Caribeño. Autor original: Joshua Davila. Sin licencia definida: úsalo, mantenlo y no culpes al compilador.
