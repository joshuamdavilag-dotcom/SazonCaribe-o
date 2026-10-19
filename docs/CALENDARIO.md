# Calendario de planificación

## Propósito y alcance

El calendario permite al restaurante coordinar planes operativos en un solo
lugar:

- Planificar cuándo se espera tener disponible un platillo.
- Planificar la llegada de un insumo, su proveedor y la cantidad esperada.
- Consultar las asistencias registradas para conocer quién marcó entrada y a
  qué hora, además de la salida si ya está registrada.

Es una herramienta interna autenticada. No programa turnos futuros, no registra
asistencia y no modifica la disponibilidad efectiva del menú ni el inventario.
Una llegada planificada es solo una previsión; las existencias se actualizan
mediante los flujos existentes de inventario.

## Acceso y roles

| Operación | Administrador | Gerente | Vendedor |
|---|:---:|:---:|:---:|
| Consultar eventos y asistencias (solo lectura) | Sí | Sí | Sí |
| Crear, editar y eliminar eventos | Sí | Sí | No |

Los empleados con rol `Vendedor` pueden consultar los eventos y asistencias
desde el calendario, pero no crear, editar ni eliminar eventos. La interfaz
oculta sus acciones de escritura y muestra un aviso de solo lectura. La
protección también se aplica en el backend: los endpoints de escritura
requieren `Administrador` o `Gerente`, de modo que una petición directa de un
Vendedor no puede alterar los eventos.

La consulta usa `get_current_user`, por lo que requiere el token del POS y
respeta la validación normal de usuario activo y turno habilitado. La respuesta
de asistencias incluye nombres de empleados y horarios reales; por eso esta
API no es pública ni se monta en `/api/public`.

## Interfaz

La entrada **Calendario** del sidebar abre `#screen-calendario`. La vista:

- Empieza en el mes actual; los controles permiten ir al mes anterior,
  siguiente o volver a hoy.
- Presenta la cuadrícula semanal de lunes a domingo y marca el día actual.
- Resalta el día actual en celeste y el día activo con un contorno azul.
- Un clic en un día abre debajo el detalle completo, incluso cuando hay más
  eventos o asistencias de los que caben en la celda. Gerencia puede mantener
  pulsado un día durante aproximadamente medio segundo para iniciar selección
  múltiple; después puede tocar otros días, incluso no consecutivos. La barra
  de selección muestra el total y permite limpiar, cancelar o crear un mismo
  evento en todos los días marcados, sin ocupar las fechas intermedias.
- Diferencia visualmente disponibilidad de platillos, llegadas de insumos y
  asistencias.
- Muestra las asistencias reales con empleado, turno, entrada y salida (o
  “En curso” si aún no hay salida).
- Permite crear un evento con fecha preseleccionada desde la acción `+` del día;
  **Nuevo evento** usa la fecha actual por defecto. Los administradores y
  gerentes pueden pulsar un evento para editarlo. Cada evento permite escoger
  una etiqueta de seis colores, visible tanto en la cuadrícula como en el
  detalle; los eventos anteriores a esta función conservan colores de respaldo.
- Se adapta a móvil; el sidebar del POS se abre desde **Más** en la navegación
  inferior.

El formulario tiene dos tipos:

1. **Disponibilidad de platillo**: platillo, título, período, horas opcionales,
   estado y notas.
2. **Llegada de insumo**: insumo, título, período, horas opcionales, estado y,
   de forma opcional, proveedor, cantidad esperada y notas. La cantidad se
   expresa en la unidad base indicada por el catálogo del insumo.

Los estados posibles son `PLANIFICADO`, `REALIZADO` y `CANCELADO`. Marcar un
evento `REALIZADO` registra `completado_en`; volverlo a otro estado limpia ese
marcador. La edición reemplaza los campos editables completos del evento
(método `PUT`), por lo que el formulario envía también los campos opcionales
vacíos como `null`.

## Modelo persistente

`EventoCalendario` se guarda en `eventos_calendario` y contiene:

| Campo | Tipo / regla | Uso |
|---|---|---|
| `id` | Entero, PK autoincremental | Identificador |
| `tipo` | `DISPONIBILIDAD_PLATILLO` o `LLEGADA_INSUMO` | Clase de plan |
| `titulo` | Texto, requerido, máximo 120 caracteres | Etiqueta del evento |
| `color_etiqueta` | `azul`, `turquesa`, `ambar`, `rosa`, `violeta` o `gris` | Color persistente de la etiqueta |
| `descripcion` | Texto opcional | Notas |
| `fecha_inicio` | Fecha requerida | Primer día incluido |
| `fecha_fin` | Fecha opcional | Último día incluido; si falta, evento de un día |
| `hora_inicio`, `hora_fin` | Hora opcional, ambas juntas | Intervalo horario |
| `estado` | `PLANIFICADO`, `REALIZADO` o `CANCELADO` | Estado operativo |
| `menu_item_id` | FK opcional a `menu_items.id` | Platillo planificado |
| `insumo_id` | FK opcional a `insumos.id` | Insumo esperado |
| `proveedor_id` | FK opcional a `proveedores.id` | Proveedor de la entrega |
| `cantidad_esperada` | Decimal opcional, máximo 2 decimales | Cantidad en unidad base |
| `creado_por_id` | FK requerida a `usuarios.id` | Usuario que creó el evento |
| `creado_en`, `actualizado_en` | Fecha/hora local del restaurante | Auditoría temporal |
| `completado_en` | Fecha/hora local opcional | Momento en que pasa a realizado |

Hay un índice por `fecha_inicio`. La consulta también incluye eventos de varios
días cuyo intervalo se solapa con el rango solicitado. El modelo se registra en
`app/models/__init__.py`; `Base.metadata.create_all` crea la columna en
instalaciones nuevas. En bases existentes, la migración idempotente de startup
agrega `color_etiqueta` como columna nullable sin alterar eventos ya guardados.

## API

Base URL: `/api/v1/calendario`. Todas las rutas requieren autenticación.

| Método | Ruta | Rol | Resultado |
|---|---|---|---|
| `GET` | `/` | Cualquier usuario autenticado | Eventos y asistencias para un rango |
| `POST` | `/eventos` | Administrador, Gerente | Crea un evento (`201`) |
| `POST` | `/eventos/masivo` | Administrador, Gerente | Crea un evento por cada fecha exacta seleccionada (`201`) |
| `PUT` | `/eventos/{evento_id}` | Administrador, Gerente | Reemplaza los datos del evento |
| `DELETE` | `/eventos/{evento_id}` | Administrador, Gerente | Elimina el evento (`204`) |

### Consulta por rango

`GET /api/v1/calendario/?desde=2026-10-01&hasta=2026-10-31`

- Ambos parámetros son fechas ISO `YYYY-MM-DD` y son requeridos.
- `desde` debe ser anterior o igual a `hasta`.
- El rango máximo es de 63 días calendario, contando los extremos.
- Un rango invertido o superior a ese límite responde `400`.
- Los errores normales de validación de parámetros de FastAPI responden `422`.

Forma de la respuesta:

```json
{
  "eventos": [
    {
      "id": 12,
      "tipo": "LLEGADA_INSUMO",
      "titulo": "Entrega de pescado",
      "color_etiqueta": "ambar",
      "descripcion": "Confirmar recepción con cocina",
      "fecha_inicio": "2026-10-08",
      "fecha_fin": null,
      "hora_inicio": "09:00:00",
      "hora_fin": "10:00:00",
      "estado": "PLANIFICADO",
      "menu_item_id": null,
      "menu_item_nombre": null,
      "insumo_id": 4,
      "insumo_nombre": "Pescado",
      "insumo_unidad_medida": "Libra",
      "proveedor_id": 2,
      "proveedor_nombre": "Distribuidora Caribe",
      "cantidad_esperada": "12.50",
      "creado_por_id": 1,
      "creado_en": "2026-10-06T16:00:00",
      "actualizado_en": "2026-10-06T16:00:00",
      "completado_en": null
    }
  ],
  "asistencias": [
    {
      "id": 44,
      "empleado_id": 7,
      "empleado_nombre": "Ana Caribe",
      "turno_nombre": "Matutino",
      "fecha": "2026-10-08",
      "hora_entrada_real": "2026-10-08T08:02:00",
      "hora_salida_real": null
    }
  ]
}
```

La colección `eventos` puede estar vacía y `asistencias` solo contiene filas
no anuladas de `asistencias` entre `desde` y `hasta`, inclusivamente. La
asistencia se filtra por la columna calendario `fecha`; el detalle presenta la
hora local almacenada sin conversiones de zona horaria.

### Crear y actualizar eventos

`POST /api/v1/calendario/eventos` y
`PUT /api/v1/calendario/eventos/{evento_id}` aceptan el mismo objeto:

```json
{
  "tipo": "DISPONIBILIDAD_PLATILLO",
  "titulo": "Disponible para el almuerzo",
  "color_etiqueta": "turquesa",
  "descripcion": null,
  "fecha_inicio": "2026-10-08",
  "fecha_fin": null,
  "hora_inicio": "11:00:00",
  "hora_fin": "15:00:00",
  "estado": "PLANIFICADO",
  "menu_item_id": 6,
  "insumo_id": null,
  "proveedor_id": null,
  "cantidad_esperada": null
}
```

Para asignar el mismo evento a fechas no consecutivas, se usa
`POST /api/v1/calendario/eventos/masivo` con el mismo contenido y `fechas`
como una lista de al menos dos fechas distintas (máximo 63). Por ejemplo:

```json
{
  "tipo": "DISPONIBILIDAD_PLATILLO",
  "titulo": "Disponible para el almuerzo",
  "color_etiqueta": "turquesa",
  "fecha_inicio": "2026-10-08",
  "fecha_fin": null,
  "fechas": ["2026-10-08", "2026-10-12"],
  "menu_item_id": 6
}
```

La API crea una fila independiente por cada día marcado, todas dentro de una
transacción: o se guardan todas o ninguna. Cada fila tiene `fecha_fin: null`,
así que los días intermedios no reciben el evento. Los colores fuera de la
paleta se rechazan con `422`; fechas duplicadas también se rechazan. Por
consistencia con la consulta de calendario, el intervalo entre la fecha
seleccionada más temprana y la más tardía tampoco puede superar 63 días.

Reglas de validación:

- `titulo` se recorta y no puede quedar vacío; límite de 120 caracteres.
- `descripcion` admite hasta 2,000 caracteres.
- `fecha_fin` no puede preceder `fecha_inicio`.
- Las horas deben enviarse ambas o dejarse ambas vacías. Si el evento es de un
  solo día, `hora_fin` debe ser posterior a `hora_inicio`.
- Una disponibilidad requiere `menu_item_id` y no admite campos de entrega.
- Una llegada requiere `insumo_id` y no admite `menu_item_id`. Proveedor y
  cantidad son opcionales; la cantidad, si existe, debe ser positiva, con
  máximo 10 dígitos y 2 decimales.
- Los IDs referenciados se verifican contra los catálogos existentes. Una
  referencia inexistente responde `404`.
- Un evento no encontrado al editar o borrar responde `404`.
- Los datos inválidos responden `422`; un rol sin autorización responde `403`.

Al crear se registra `creado_por_id` desde el usuario autenticado. El cliente
no puede asignar ese campo ni los campos de auditoría. `creado_en` y
`actualizado_en` usan `ahora_local()` (hora local de Managua); `actualizado_en`
se actualiza con cada edición.

## Flujo interno

El módulo sigue la arquitectura API → Service → Repository → Model:

1. `app/api/endpoints/calendario.py` valida rango y roles.
2. `app/services/calendario_service.py` aplica reglas de negocio, construye la
   respuesta combinada y valida referencias antes de guardar.
3. `app/repositories/calendario_repository.py` consulta eventos, nombres de
   catálogo, unidad del insumo y asistencia real.
4. `app/models/calendario.py` define persistencia y enums; los contratos Pydantic
   están en `app/schemas/calendario.py`.
5. `app/main.py` registra `/api/v1/calendario` y carga el modelo antes de
   `create_all`.
6. `app/Templates/index.html`, `app/Templates/js/app.js` y
   `app/Templates/css/style.css` proporcionan el módulo de la SPA.

La consulta del mes carga los días visibles de la cuadrícula (normalmente entre
28 y 42 días) en una sola llamada, junto con sus asistencias. Los nombres
relacionados se obtienen con joins, no con una consulta por cada elemento. La
interfaz carga platillos, insumos y proveedores una sola vez por sesión de
página y reutiliza esos catálogos al crear o editar eventos.

## Límites operativos y objetivos

Este módulo se diseñó para un restaurante (single-tenant), carga baja de
aproximadamente una escritura por diez lecturas y una previsión de hasta 1
consulta por segundo en el percentil 99. La lectura y la escritura son
síncronas dentro del FastAPI existente; no se añadió caché, cola ni servicio
externo. La ventana de consulta queda limitada para acotar el trabajo de la
base de datos.

Objetivos acordados para el servicio, no garantías medidas por este cambio:

| Indicador | Objetivo |
|---|---:|
| Latencia p50 API | 60 ms |
| Latencia p95 API | < 500 ms |
| Latencia p99 API | ≤ 500 ms |
| Disponibilidad mensual | 99.5 % |
| RPO | 0 |
| RTO | 4 horas |

La información de asistencia y empleados es interna y contiene datos
personales. Mantener la consulta autenticada, limitar edición a gerencia y no
exponer la ruta en la Carta Digital pública son requisitos del módulo. La
gerencia es responsable de revisar incidentes.

## Pruebas

Pruebas de regresión del módulo: `tests/test_calendario.py`.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_calendario.py -v
```

La suite valida eventos de ambos tipos, relaciones de catálogo, persistencia,
transición a realizado y borrado, etiquetas de color, creación masiva en días
no consecutivos, rechazo de eventos inválidos, límite del rango y omisión de
asistencias anuladas.
