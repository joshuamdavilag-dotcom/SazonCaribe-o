> Este documento describe el sistema tal como está implementado hoy. La versión anterior de esta especificación describía un sistema más pequeño y más ordenado; la realidad creció. Donde el documento y el código no coincidan, gana el código.

## Control de versiones del documento

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | Julio 2026 | Versión inicial: visión, arquitectura, requerimientos y reglas de negocio del POS. Varias secciones quedaron como borrador. |
| 2.0 | Noviembre 2026 | Documento completo: se corrigen datos desactualizados, se agregan los módulos construidos después (Carta Digital, importación inteligente, estudio de mercado, permisos por usuario, notificaciones push, cierre automático de caja, copias de seguridad, auditoría ampliada), se actualizan tecnologías, API, procesos y operación. |

---

## Tabla de contenido

1. Introducción
2. Análisis del negocio
3. Arquitectura del sistema
4. Requerimientos funcionales
5. Requerimientos no funcionales
6. Reglas de negocio
7. Modelo de datos
8. Diseño del backend
9. Diseño del frontend
10. Seguridad
11. API REST
12. Procesos del negocio
13. Operación y despliegue
14. Pruebas y calidad
15. Mantenimiento y notas del desarrollador
16. Anexos

---

# 1. Introducción

## 1.1 Visión del proyecto

Sazón Caribeño es un Sistema Integral de Gestión para Restaurantes cuyo propósito es digitalizar y centralizar la operación administrativa y operativa de un establecimiento gastronómico. El sistema cubre ventas, inventario, menú, personal, asistencia, nómina, gastos, caja, reportes, auditoría y la carta pública que ven los clientes.

La visión no cambió desde la primera versión; el alcance sí. Lo que empezó como un punto de venta con inventario terminó incluyendo herramientas que normalmente se compran por separado: un KDS para cocina, notificaciones al teléfono del personal, importación de facturas con inteligencia artificial, un asesor de mercado y copias de seguridad administradas desde el propio sistema.

## 1.2 Objetivo general

Administrar de forma centralizada los procesos operativos y administrativos del restaurante, integrando usuarios, personal, inventario, menú, punto de venta, gastos, nómina, caja y reportes en una plataforma web segura, eficiente y escalable, que reduzca el trabajo manual y entregue información confiable para la toma de decisiones.

## 1.3 Objetivos específicos

- Registrar ventas mediante un punto de venta que descuente inventario automáticamente.
- Mantener el inventario actualizado a partir de ventas, recetas, ajustes manuales, producción por lote e importaciones de compras.
- Administrar platillos, categorías, recetas y precios, con imágenes y traducciones al inglés.
- Gestionar personal, puestos, usuarios, permisos y plantillas de turno.
- Controlar la asistencia con verificación periódica y reglas claras de cierre.
- Calcular la nómina por días trabajados, horas extras y adelantos.
- Controlar gastos operativos y gastos automáticos generados por consumo de insumos.
- Consolidar la caja diaria y generar reportes financieros por periodo.
- Mantener una bitácora de auditoría de las operaciones sensibles.
- Publicar una carta digital para clientes, sin autenticación y sin exponer información interna.
- Entregar avisos al personal mediante notificaciones push.
- Ofrecer copias de seguridad y restauración sin depender del disco del servidor.
- Proporcionar un análisis de mercado asistido por inteligencia artificial con datos reales del negocio.

## 1.4 Alcance

Incluido en esta versión:

- ERP web para Administrador, Gerente y Vendedor.
- Perfil operativo de cocina identificado por puesto de trabajo.
- Punto de venta con mesas, para llevar, comandas múltiples, fusión de mesas, pagos parciales y descuentos.
- KDS con estados de preparación.
- Inventario con unidades, empaques, conversiones, producción por lote e importación de archivos.
- Menú con imágenes, recetas y traducciones.
- Personal, asistencia, turnos y nómina.
- Gastos, caja, reportes y auditoría.
- Calendario de planificación.
- Carta Digital pública con libro animado y selector de idioma.
- Notificaciones push, novedades del sistema y estudio de mercado.
- Copias de seguridad administradas desde el sistema.

Fuera de alcance en esta versión:

- Facturación fiscal electrónica ante la autoridad tributaria.
- Aplicación móvil nativa.
- Integración real con pasarelas de pago en línea (la arquitectura existe, el proveedor está deshabilitado).
- Multi-sucursal con consolidación contable.
- Control de asistencia por hardware biométrico.

## 1.5 Público objetivo y perfiles

El sistema está dirigido a restaurantes pequeños y medianos. Dentro del establecimiento se reconocen cuatro perfiles operativos:

| Perfil | Rol del sistema | Responsabilidad |
|--------|-----------------|-----------------|
| Administrador | Administrador | Configuración, usuarios, permisos, seguridad, copias de seguridad y supervisión general. |
| Gerente | Gerente | Inventario, personal, gastos, nómina, caja, reportes, menú y calendario. |
| Vendedor / mesero | Vendedor | Salón, comandas, cobros y su propio turno. |
| Cocinero / chef | Vendedor (con puesto de cocina) | Panel de cocina, cambios de estado de preparación y consulta de comandas. |

El cocinero no tiene un rol distinto: se identifica por el nombre de su puesto. Esta decisión evita duplicar la matriz de permisos y permite que un Administrador o Gerente con puesto de cocina conserve acceso completo.

## 1.6 Tecnologías utilizadas

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.12 | Lenguaje del backend |
| FastAPI | 0.138.0 | API REST y servidor de archivos estáticos |
| Uvicorn | 0.34.0 | Servidor ASGI |
| SQLAlchemy | 2.0.41 | ORM y acceso a datos |
| Pydantic | 2.10.6 | Validación y serialización |
| Pydantic Settings | 2.9.0 | Configuración desde `.env` |
| MySQL / MariaDB | 8.x | Base de datos principal en producción |
| PyMySQL | 1.2.0 | Controlador MySQL |
| PostgreSQL | 16+ | Alternativa de base de datos |
| psycopg2-binary | 2.9.10 | Controlador PostgreSQL |
| SQLite | 3.x | Base local de desarrollo y pruebas |
| python-jose | 3.5.0 | JWT HS256 |
| bcrypt | 4.2.0 | Hash de contraseñas |
| httpx | 0.28.1 | Cliente HTTP para ImgBB y Gemini |
| Pillow | 10+ | Validación, redimensionado y compresión WebP |
| pywebpush | 2.0.1 | Notificaciones Web Push con VAPID |
| pypdf, python-docx, openpyxl | 5.1, 1.1, 3.1 | Extracción de texto de documentos |
| tzdata | 2024.1+ | Zona horaria America/Managua |
| HTML5 | — | Estructura de las interfaces |
| CSS propio | — | Diseño del ERP y de la carta |
| Tailwind CSS | 3.4 (precompilado) | Utilidades del ERP |
| JavaScript ES6+ | — | Lógica del cliente |
| StPageFlip | vendorizado | Animación del libro de la carta |
| Git | — | Control de versiones |
| Render | — | Plataforma de despliegue |

Diferencias relevantes respecto a la versión anterior del documento:

- Ya no se usa Tailwind por CDN: se compila una hoja estática de ~30 KB y se sirve localmente.
- Alembic sigue declarado como dependencia, pero el esquema se mantiene con `create_all` y migraciones de arranque idempotentes.
- Python de producción es 3.12, no 3.14.
- La base puede ser MySQL, PostgreSQL o SQLite; la configuración se normaliza en `app/core/config.py`.

## 1.7 Glosario

| Término | Significado |
|---------|-------------|
| Comanda | Orden de consumo de una mesa o para llevar. |
| KDS | Kitchen Display System: pantalla de cocina. |
| Día de negocio | Ventana de 24 horas que empieza a la hora configurada (por defecto 7:00). |
| Heartbeat | Señal periódica que envía el cliente para demostrar que el turno sigue activo. |
| Override | Permiso concedido o retirado a un usuario por encima de los permisos de su rol. |
| Borrado lógico | Marcar un registro como inactivo o eliminado sin borrar la fila. |
| Cierre de caja | Proceso que archiva las órdenes y gastos de la sesión actual. |
| DTO | Objeto de transferencia de datos; aquí, un schema Pydantic. |
| VAPID | Protocolo de identificación del servidor para Web Push. |

---

# 2. Análisis del negocio

## 2.1 Descripción del restaurante

Sazón Caribeño prepara y comercializa alimentos y bebidas. Su operación diaria combina atención en mesas, ventas para llevar, compras de insumos, control de personal y seguimiento financiero. Muchas de estas actividades se afectan entre sí: una venta descuenta inventario, una salida de insumos genera un gasto y un turno mal cerrado distorsiona la nómina.

## 2.2 Problema identificado

La gestión manual o parcialmente digitalizada produce:

- Diferencias entre el inventario físico y el registrado.
- Ventas que no descuentan insumos y, por tanto, costos irreales.
- Dificultad para conocer la rentabilidad diaria.
- Asistencia registrada en papel o en hojas de cálculo sin control de horarios.
- Cálculos de nómina propensos a error.
- Gastos sin categoría ni trazabilidad.
- Acceso uniforme a funciones sensibles, sin separación de responsabilidades.
- Información dispersa que impide tomar decisiones oportunas.

## 2.3 Solución propuesta

Una plataforma web centralizada que integra los procesos en un solo flujo:

- El salón crea comandas y el inventario se descuenta con cada venta.
- La cocina recibe avisos y cambia el estado de preparación.
- El personal marca entrada y salida desde el mismo sistema.
- La gerencia controla gastos, caja y nómina con información trazable.
- Los clientes consultan la carta desde un código QR.
- La administración conserva evidencia de cada operación sensible.

## 2.4 Beneficios esperados

- Inventario actualizado automáticamente.
- Menos errores en nómina y en el cierre de caja.
- Trazabilidad de anulaciones, devoluciones, ediciones y cierres forzados.
- Mejor comunicación entre cocina y salón.
- Acceso remoto a reportes y copias de seguridad.
- Carta digital actualizada sin reimprimir ni regenerar imágenes.
- Base tecnológica preparada para nuevas integraciones.

## 2.5 Procesos cubiertos

| Proceso | Módulo responsable |
|---------|--------------------|
| Venta en mesa o para llevar | Órdenes y Salón |
| Preparación en cocina | KDS |
| Compra y entrada de insumos | Inventario e Importación |
| Consumo de insumos | Recetas y Producción por lote |
| Control de asistencia | Asistencia y Turnos |
| Pago de salarios | Nómina |
| Registro de gastos | Gastos |
| Cierre del día | Caja y Reportes |
| Consulta del menú por el cliente | Carta Digital |
| Auditoría y control interno | Auditoría y Copias de seguridad |

---

# 3. Arquitectura del sistema

## 3.1 Modelo general

La aplicación sigue un modelo cliente-servidor desacoplado. El frontend y el backend son componentes independientes que se comunican mediante una API REST en formato JSON. El backend sirve además los archivos estáticos del ERP y de la Carta Digital, por lo que el despliegue es una sola instancia.

```
Navegador del personal            Navegador del cliente
        │                                  │
        │  /                               │  /carta
        ▼                                  ▼
┌────────────────────────────────────────────────────┐
│                    FastAPI                         │
│  /api/v1/*   (autenticado)                         │
│  /api/public/* (solo lectura)                      │
│  /Templates/*  y  /carta/*  (estáticos)            │
└───────────────┬────────────────────────────────────┘
                │
                ▼
        SQLAlchemy + base de datos
```

## 3.2 Capas

| Capa | Responsabilidad | Ubicación |
|------|-----------------|-----------|
| Presentación | Interfaz del ERP | `app/Templates/index.html`, `css/`, `js/app.js` |
| Presentación pública | Carta Digital | `app/Templates/carta/` |
| API | Endpoints HTTP y validación de acceso | `app/api/endpoints/` |
| Servicios | Reglas de negocio | `app/services/` |
| Repositorios | Acceso a datos | `app/repositories/` |
| Modelos | Tablas y relaciones | `app/models/` |
| Esquemas | Contratos de entrada y salida | `app/schemas/` |
| Núcleo | Configuración, seguridad, tiempo, permisos | `app/core/` |

## 3.3 Despliegue

- Una instancia de Render ejecuta Uvicorn.
- La base de datos es MySQL (Aiven) o PostgreSQL; SQLite se usa en desarrollo y pruebas.
- Las imágenes se almacenan en ImgBB; el servidor guarda solo la URL.
- Las copias de seguridad se guardan en la base de datos (`backups_sistema`), porque el disco de Render es efímero.
- Los clips de cámara, si se usa el módulo, requieren almacenamiento persistente configurado aparte.

## 3.4 Estructura del proyecto

```
app/
├── main.py                 # aplicación, routers, mounts, migraciones y watchers
├── core/                   # configuración y utilidades transversales
├── api/
│   ├── deps.py             # autenticación y autorización
│   ├── auditoria.py        # router de bitácora
│   └── endpoints/          # controladores por dominio
├── schemas/                # contratos Pydantic
├── models/                 # entidades SQLAlchemy
├── repositories/           # consultas y persistencia
├── services/               # reglas de negocio
├── utils/                  # cálculos auxiliares
├── db/                     # inicialización y siembra
└── Templates/              # ERP y Carta Digital
```

## 3.5 Flujo de una solicitud

1. El navegador envía una solicitud HTTP con el token en la cabecera `Authorization`.
2. FastAPI resuelve la dependencia `get_current_user`, que lee el usuario vigente de la base de datos.
3. `requerir_rol` o `requerir_permiso` valida el acceso.
4. El endpoint valida el cuerpo con un schema Pydantic y delega en el servicio.
5. El servicio aplica reglas de negocio y usa uno o varios repositorios.
6. El repositorio ejecuta la consulta con SQLAlchemy.
7. El servicio devuelve el resultado; el endpoint lo serializa con un schema de respuesta.
8. La respuesta viaja en JSON, comprimida con GZip si supera el umbral.

## 3.6 Tareas de fondo

`app/main.py` inicia tareas que corren mientras el proceso está vivo:

| Tarea | Frecuencia | Función |
|-------|-----------|---------|
| `_heartbeat_watcher` | 5 minutos | Cierra turnos cuyo dueño ya no puede continuar. |
| `_cierre_caja_watcher` | 1 minuto | Ejecuta el cierre automático de caja a medianoche. |
| `_camera_clip_retention_watcher` | Periódica | Depura clips antiguos de cámaras. |
| `_estudio_mercado_watcher` | 1 hora | Genera el estudio de mercado mensual. |
| `_novedades_watcher` | 1 hora | Siembra y difunde novedades pendientes. |

Ninguna de estas tareas es indispensable para que el sistema responda, pero todas son necesarias para que el sistema se comporte como se espera. No las apagues sin leer qué hacen.

## 3.7 Decisiones de diseño y deuda técnica

| Decisión | Motivo | Consecuencia |
|----------|--------|--------------|
| Migraciones de arranque en lugar de Alembic | El despliegue no ejecuta migraciones y la base ya tenía datos | Esquema consistente sin pasos manuales; el arranque tarda un poco más |
| SPA en Vanilla JS sin build | Evitar toolchain y despliegues más simples | `app.js` es grande; se compensa con secciones y caché por ETag |
| Un solo servicio de FastAPI | Menos infraestructura | Frontend y API comparten proceso y recursos |
| VAPID derivado de `SECRET_KEY` | Cero configuración en el panel de Render | Cambiar `SECRET_KEY` invalida las suscripciones |
| Copias dentro de la base | El disco de Render es efímero | La base crece con cada copia; se purgan las antiguas |
| Hora local naive para asistencia | Evitar conversiones que ya causaron errores | Los registros históricos antiguos quedaron en UTC |

---

# 4. Requerimientos funcionales

Los requerimientos se agrupan por módulo. Cada uno describe una capacidad observable por el usuario.

## 4.1 Autenticación y usuarios

- **RF-001.** El sistema debe permitir iniciar sesión con usuario y contraseña.
- **RF-002.** El login debe ser insensible a mayúsculas y espacios en el nombre de usuario.
- **RF-003.** El sistema debe rechazar usuarios inactivos con un mensaje claro.
- **RF-004.** El sistema debe rechazar vendedores con turno deshabilitado.
- **RF-005.** Debe existir un endpoint para consultar la sesión vigente y sus permisos.
- **RF-006.** El administrador debe poder crear usuarios y asociarlos a un empleado.
- **RF-007.** El administrador debe poder restablecer contraseñas.
- **RF-008.** El sistema debe permitir dar de baja usuarios y empleados conservando el historial.
- **RF-009.** La baja de un empleado debe exigir la contraseña del usuario que la ejecuta.
- **RF-010.** El sistema debe impedir que un usuario se dé de baja a sí mismo.

## 4.2 Permisos funcionales

- **RF-011.** El sistema debe ofrecer un catálogo de permisos agrupados por área.
- **RF-012.** Cada rol debe tener permisos por defecto.
- **RF-013.** La administración debe poder conceder o retirar permisos por usuario.
- **RF-014.** El sistema debe guardar solo las diferencias respecto al rol.
- **RF-015.** Los permisos críticos solo deben poder otorgarse desde una cuenta Administrador.
- **RF-016.** No se deben poder editar los permisos de la propia cuenta ni los de un Administrador.
- **RF-017.** La interfaz debe ocultar las funciones no autorizadas.
- **RF-018.** Los cambios de permisos deben aplicarse a la sesión en un máximo de 60 segundos o al volver a la pestaña.

## 4.3 Personal

- **RF-019.** El sistema debe administrar puestos de trabajo.
- **RF-020.** Cada empleado debe tener puesto, salario base y datos de contacto.
- **RF-021.** El salario debe ser propio del empleado, no del puesto.
- **RF-022.** El sistema debe conservar empleados dados de baja y permitir consultarlos.
- **RF-023.** El sistema debe identificar el perfil de cocina por el nombre del puesto.

## 4.4 Turnos y asistencia

- **RF-024.** El sistema debe permitir iniciar un turno desde una plantilla.
- **RF-025.** Iniciar turno debe ser idempotente ante doble clic o reenvío.
- **RF-026.** No se debe permitir repetir el turno ya finalizado del día de negocio.
- **RF-027.** El cliente debe enviar latidos periódicos mientras el turno esté abierto.
- **RF-028.** El sistema debe cerrar turnos huérfanos cuando el dueño ya no pueda continuar.
- **RF-029.** Todo cierre automático debe quedar auditado con causa y antes/después.
- **RF-030.** El sistema debe permitir editar horarios con motivo obligatorio.
- **RF-031.** El sistema debe permitir anular una asistencia con motivo y excluirla de la nómina.
- **RF-032.** El sistema debe permitir reactivar un turno cerrado por error.
- **RF-033.** El check-out de un turno ya cerrado debe informar la situación con un 409, no simular éxito.
- **RF-034.** El sistema debe consultar la asistencia activa desde la base de datos, no desde el navegador.
- **RF-035.** El día de negocio debe ser configurable y cruzar medianoche correctamente.

## 4.5 Inventario

- **RF-036.** El sistema debe administrar insumos, categorías, proveedores y unidades de medida.
- **RF-037.** Cada insumo debe tener unidad base, costo, stock actual y stock mínimo.
- **RF-038.** El sistema debe registrar movimientos de entrada y salida.
- **RF-039.** Cada salida debe generar un gasto de categoría SUMINISTROS.
- **RF-040.** El sistema debe convertir cantidades entre unidades compatibles.
- **RF-041.** El sistema debe soportar empaques por insumo con factor de conversión.
- **RF-042.** El sistema debe alertar cuando un insumo esté por debajo del mínimo.
- **RF-043.** Cambiar la unidad base debe convertir stock, costo y recetas vinculadas.
- **RF-044.** El sistema debe registrar producción por lote y descontar solo los insumos marcados para lote.
- **RF-045.** El sistema debe permitir ajustar stock manualmente con trazabilidad.

## 4.6 Importación inteligente de inventario

- **RF-046.** El sistema debe aceptar archivos Excel, CSV, TXT, PDF y DOCX.
- **RF-047.** El sistema debe detectar producto, cantidad, unidad, precio, categoría y empaque.
- **RF-048.** El sistema debe usar reglas y, si hace falta, inteligencia artificial para interpretar el archivo.
- **RF-049.** El sistema debe mostrar las filas detectadas antes de escribir nada.
- **RF-050.** El usuario debe poder editar o descartar cada fila.
- **RF-051.** La aplicación debe ser atómica: si una fila falla, no se escribe ninguna.
- **RF-052.** Aplicar una importación no debe generar gastos, solo movimientos de entrada.
- **RF-053.** El sistema debe conservar un historial de importaciones y abrir lotes aplicados en solo lectura.
- **RF-054.** El sistema debe evitar duplicar insumos, categorías o unidades existentes.

## 4.7 Menú y recetas

- **RF-055.** El sistema debe administrar categorías y platillos.
- **RF-056.** Cada platillo debe tener nombre, precio, categoría y disponibilidad.
- **RF-057.** El sistema debe permitir subir una imagen por platillo.
- **RF-058.** La imagen debe validarse por contenido, comprimirse y almacenarse en un servicio externo.
- **RF-059.** El sistema debe registrar tiempo de preparación.
- **RF-060.** El sistema debe administrar recetas con ingredientes y cantidades.
- **RF-061.** El sistema debe permitir marcar ingredientes que se descuentan por lote.
- **RF-062.** El sistema debe permitir traducciones al inglés de nombres y descripciones.
- **RF-063.** La eliminación de platillos debe ser lógica y conservar el historial de ventas.

## 4.8 Salón y mesas

- **RF-064.** El sistema debe administrar zonas y mesas.
- **RF-065.** Cada mesa debe tener estado, capacidad y posición en el mapa.
- **RF-066.** El sistema debe permitir asignar un apodo temporal a una mesa ocupada.
- **RF-067.** El apodo debe borrarse cuando la mesa vuelve a estar libre.
- **RF-068.** El sistema debe permitir fusionar mesas y deshacer la fusión.
- **RF-069.** La fusión no debe cancelar ni cobrar comandas.
- **RF-070.** El sistema debe liberar mesas huérfanas al iniciar.

## 4.9 Órdenes y pagos

- **RF-071.** El sistema debe crear comandas para mesa o para llevar.
- **RF-072.** Una mesa puede tener varias comandas activas.
- **RF-073.** El sistema debe permitir editar una comanda abierta con su estado final.
- **RF-074.** El inventario debe ajustarse por diferencia al editar.
- **RF-075.** El sistema debe validar stock suficiente antes de confirmar una comanda.
- **RF-076.** El sistema debe aplicar descuentos por línea y globales.
- **RF-077.** El sistema debe permitir pagos parciales y divididos.
- **RF-078.** Cada pago debe generar un comprobante interno imprimible.
- **RF-079.** Una comanda con pagos no debe poder editarse ni descontarse.
- **RF-080.** Al cancelar una comanda con pagos se deben registrar los asientos de reversión.
- **RF-081.** El sistema debe permitir anular pedidos y devolver líneas con motivo.
- **RF-082.** La anulación y la devolución deben quedar auditadas.
- **RF-083.** El sistema debe permitir ventas retroactivas con fecha.
- **RF-084.** El cobro debe liberar la mesa solo si no quedan otras comandas activas.

## 4.10 Caja

- **RF-085.** El sistema debe mostrar el historial de órdenes de la caja abierta.
- **RF-086.** El sistema debe permitir cerrar la caja y archivar órdenes y gastos.
- **RF-087.** El sistema debe permitir activar o desactivar el cierre automático.
- **RF-088.** El cierre automático debe ejecutarse una vez por día de Managua.
- **RF-089.** El cierre automático debe archivar gastos aunque no haya órdenes pagadas.
- **RF-090.** Una caja vacía no debe generar un cierre.
- **RF-091.** El mesero debe ver un resumen de ventas del día sin gastos, nómina ni utilidad.

## 4.11 Gastos

- **RF-092.** El sistema debe registrar gastos con fecha, categoría, monto y descripción.
- **RF-093.** El sistema debe filtrar gastos por rango de fechas.
- **RF-094.** El sistema debe permitir editar y eliminar gastos con motivo obligatorio.
- **RF-095.** La eliminación debe ser lógica y auditada.
- **RF-096.** Los gastos eliminados no deben aparecer en reportes ni en la caja.
- **RF-097.** Eliminar un gasto automático de suministros no debe devolver stock.

## 4.12 Nómina

- **RF-098.** El sistema debe calcular la nómina por días dentro de un rango.
- **RF-099.** El sistema debe calcular horas extras sobre la hora de salida programada.
- **RF-100.** El sistema debe descontar los adelantos registrados.
- **RF-101.** El sistema debe permitir pagar una nómina y conservar su estado.
- **RF-102.** El sistema debe permitir recalcular nóminas pendientes.
- **RF-103.** El sistema no debe recalcular una nómina ya pagada.

## 4.13 Reportes

- **RF-104.** El sistema debe generar cierres por día, semana, quincena, mes y año.
- **RF-105.** El sistema debe calcular ingresos, descuentos, nómina, insumos, gastos operativos y utilidad.
- **RF-106.** El sistema debe mostrar el top de platillos vendidos.
- **RF-107.** El sistema debe excluir órdenes anuladas y gastos eliminados.
- **RF-108.** El sistema debe distinguir la caja abierta de los datos históricos.

## 4.14 Auditoría

- **RF-109.** El sistema debe registrar acciones sensibles con actor, fecha, antes y después.
- **RF-110.** La bitácora debe ser consultable por fecha y paginada.
- **RF-111.** Solo un Administrador debe poder eliminar un registro de la bitácora.
- **RF-112.** La eliminación de un registro debe dejar un evento de esa eliminación, sin copiar el contenido original.

## 4.15 Calendario

- **RF-113.** El sistema debe permitir planificar disponibilidad de platillos y llegadas de insumos.
- **RF-114.** Los eventos pueden cubrir varias fechas y tener horas opcionales.
- **RF-115.** Cualquier usuario autenticado debe poder consultar el calendario.
- **RF-116.** Solo Administrador y Gerente deben poder crear, editar o eliminar eventos.
- **RF-117.** El calendario debe mostrar asistencias reales sin permitir editarlas desde ahí.

## 4.16 Carta Digital

- **RF-118.** El sistema debe publicar una carta pública sin autenticación.
- **RF-119.** La carta debe leer los platillos disponibles desde la API pública.
- **RF-120.** La carta debe organizar los platillos por categorías y páginas.
- **RF-121.** La carta debe mostrar fotos, precios y tiempo de preparación cuando exista.
- **RF-122.** La carta debe ofrecer selector de idioma español e inglés.
- **RF-123.** El inglés debe usar traducciones de la base y recurrir al español si faltan.
- **RF-124.** Los precios deben mostrarse siempre en córdobas.
- **RF-125.** La carta debe permitir ampliar cada página para leer de cerca.
- **RF-126.** La carta debe funcionar en móvil, tableta y escritorio.
- **RF-127.** La carta debe actualizarse al recargar cuando cambia el menú.
- **RF-128.** La ruta pública debe ser configurable y los enlaces antiguos deben redirigir.

## 4.17 Notificaciones push

- **RF-129.** El sistema debe permitir activar avisos push por dispositivo.
- **RF-130.** Cada usuario debe elegir qué avisos recibe.
- **RF-131.** El sistema debe avisar a cocina cuando entra o se edita una comanda.
- **RF-132.** El sistema debe avisar al mesero cuando su comanda está lista.
- **RF-133.** El sistema debe respetar la regla de entrega fuera de turno.
- **RF-134.** Un fallo de push no debe interrumpir la operación de la orden.
- **RF-135.** Las suscripciones caducadas deben eliminarse automáticamente.
- **RF-136.** El aviso debe abrir el ERP en la pantalla correspondiente.

## 4.18 Estudio de mercado

- **RF-137.** El sistema debe generar estudios de mercado con métricas reales.
- **RF-138.** El estudio debe incluir fortalezas, debilidades, estrategias y análisis.
- **RF-139.** La generación debe correr en segundo plano y notificar al terminar.
- **RF-140.** El sistema debe generar un estudio automático mensual.
- **RF-141.** El usuario debe poder adjuntar documentos de contexto.
- **RF-142.** El sistema debe ofrecer un chat asesor con acceso a datos en vivo.
- **RF-143.** El chat debe rechazar consultas ajenas al negocio.
- **RF-144.** El estudio debe poder descargarse como informe con gráficas.
- **RF-145.** Sin clave de Gemini, el sistema debe responder con un error claro.

## 4.19 Copias de seguridad

- **RF-146.** El sistema debe generar copias completas de la base.
- **RF-147.** Las copias deben guardarse en la base de datos.
- **RF-148.** El sistema debe permitir descargar y eliminar copias.
- **RF-149.** El sistema debe permitir restaurar una copia subida.
- **RF-150.** El sistema debe crear una copia automática mensual y conservar solo las últimas.
- **RF-151.** La restauración debe registrar un evento de auditoría.

## 4.20 Novedades

- **RF-152.** El sistema debe publicar novedades versionadas.
- **RF-153.** La siembra de novedades debe ser idempotente.
- **RF-154.** Cada novedad debe enviarse por push una sola vez.
- **RF-155.** El usuario debe poder consultar el historial de novedades.
- **RF-156.** La interfaz debe indicar cuándo hay una versión nueva.

---

# 5. Requerimientos no funcionales

## 5.1 Seguridad

- Control de acceso basado en roles y permisos funcionales.
- Validación del usuario vigente en cada petición autenticada.
- Contraseñas con bcrypt; nunca en texto plano.
- Token JWT firmado con HS256.
- Cabeceras de seguridad en respuestas estáticas y dinámicas.
- CORS restringido a orígenes configurados.
- Registro de auditoría para operaciones sensibles.
- Rutas públicas limitadas y con campos explícitos.

## 5.2 Rendimiento

- Respuestas comunes por debajo de dos segundos en condiciones normales.
- Consultas de reportes con rangos de fecha indexados.
- Eager loading explícito para evitar el problema N+1.
- Compresión GZip en respuestas mayores a 800 bytes.
- Assets con URL estable y revalidación por ETag.
- Imágenes comprimidas y con carga diferida.

## 5.3 Disponibilidad

- El sistema debe operar durante el horario del restaurante.
- Las tareas de fondo deben tolerar reinicios y ejecutarse en el siguiente ciclo.
- El cierre automático debe recuperarse si el servicio estuvo dormido.

## 5.4 Escalabilidad

- Nuevos módulos deben poder agregarse sin reescribir los existentes.
- La API debe permitir clientes adicionales.
- La base debe soportar MySQL, PostgreSQL y SQLite sin cambios de código.

## 5.5 Mantenibilidad

- Organización por capas y por dominio.
- Schemas Pydantic como contrato único.
- Migraciones de arranque idempotentes.
- Pruebas automatizadas por módulo.
- Documentación técnica y de operación en el repositorio.

## 5.6 Usabilidad

- Interfaz en español, con identificadores internos en inglés.
- Diseño adaptable a móvil, tableta y escritorio.
- Mensajes de error claros y específicos.
- Confirmación en acciones destructivas.
- Modo claro y oscuro coherentes.

## 5.7 Integridad de la información

- Operaciones de escritura complejas en una sola transacción.
- Movimientos de inventario trazables.
- Borrado lógico cuando existe historial contable.
- Auditoría con antes y después.
- Restauración de copias con orden de claves foráneas.

## 5.8 Compatibilidad

- Navegadores modernos con soporte de ES6, Fetch y Service Worker.
- Web Push requiere HTTPS o localhost.
- La carta debe funcionar en iOS Safari y Android Chrome.

---

# 6. Reglas de negocio

Esta sección es la que más importa cuando alguien pregunta "¿por qué el sistema hizo eso?". Cada regla existe por una razón concreta, casi siempre porque algo salió mal antes.

## 6.1 Órdenes y comandas

### Máquina de estados

```
PENDIENTE ──► PREPARANDO ──► ENTREGADA ──► PAGADA
    │             │              │
    └─────────────┴──────────────┴──► CANCELADA
```

| Desde | Hacia permitido |
|-------|-----------------|
| PENDIENTE | PREPARANDO, CANCELADA |
| PREPARANDO | ENTREGADA, CANCELADA |
| ENTREGADA | PAGADA, CANCELADA |
| PAGADA | ninguno (terminal) |
| CANCELADA | ninguno (terminal) |

Una transición no permitida responde `400: No se puede cambiar de '{actual}' a '{nuevo}'`. PAGADA y CANCELADA son terminales: no se reabren ni se editan.

### Reglas específicas

- **Una mesa puede tener varias comandas activas** (comandas múltiples). Antes existía la regla de una sola orden activa por mesa; se eliminó cuando el restaurante empezó a dividir cuentas de verdad.
- **`mesa_id` nullable**: `NULL` significa para llevar o venta directa. No se valida mesa, no se marca ocupada y al cobrar no se libera nada.
- **Edición de comanda** (`PUT /ordenes/{id}/items`): el cuerpo representa el estado final deseado. Se actualizan las líneas con `detalle_id`, se agregan las que vienen sin él y se eliminan las que no aparecen. El inventario se ajusta por diferencia: aumentos descuentan, reducciones revierten.
- **Validación de stock**: antes de confirmar cualquier comanda se valida que todos los ingredientes con receta tengan existencia suficiente. Si falta, `400` y no se escribe nada.
- **Descuentos**: por línea (`descuento_porcentaje` / `descuento_monto` + motivo) o globales prorrateados por peso de línea. `subtotal` es la suma de líneas antes de descuento; `descuento_total` el total descontado; `total = subtotal − descuento_total`. Un descuento mayor al valor de la línea responde `400`.
- **Pagos parciales**: una comanda sigue abierta hasta saldar su total. Al completarse libera el grupo de mesas fusionadas. Una comanda con pagos registrados no se puede editar, ampliar ni descontar.
- **Cancelación con pagos**: se registra un asiento negativo por cada pago y el saldo neto queda en cero. La acción se audita como `COMANDA_CANCELADA`.
- **Anulación de pedido** (`POST /ordenes/{id}/anular`): borrado lógico (`anulada=True`) con motivo obligatorio. La orden sale de todos los totales, incluidos los históricos. No se puede anular una orden de una caja ya cerrada.
- **Devolución de líneas** (`POST /ordenes/{id}/devolver-item`): acumula `cantidad_devuelta` y recalcula totales prorrateando las unidades devueltas. No revierte inventario (decisión del negocio: la comida ya se consumió).
- **Venta retroactiva**: orden creada directamente como PAGADA con fecha personalizada, sin descontar inventario ni tocar mesas. Es un registro contable, no una venta real.

## 6.2 Inventario y recetas

- Todo movimiento es `ENTRADA` o `SALIDA` sobre `Insumo.cantidad_actual`. Cada `SALIDA` genera automáticamente un `Gasto` con categoría `SUMINISTROS` y monto `cantidad × costo_unitario`.
- **Conversión de unidades**: primero se intenta el empaque del insumo (`factor_empaque`), luego la cadena global de `UnidadMedida` (`unidad_base_id` + `factor_conversion`), resuelta de forma transitiva.
- **Cambio de unidad base**: exige `factor_conversion_unidad` y convierte en la misma operación el stock, el costo unitario y todas las líneas de `Receta.cantidad_necesaria`.
- **Producción por lote**: `PreparacionCocina` descuenta únicamente los insumos marcados con `Receta.descuento_por_lote = True`. Esos insumos no se descuentan por plato vendido, solo al registrar la producción.
- **Alertas de stock**: un insumo está crítico cuando `cantidad_actual <= stock_minimo`. A cero se muestra en rojo; por debajo del mínimo, en ámbar.
- **Importación de inventario**: nada se escribe hasta que el usuario confirma. La aplicación es atómica y no genera gastos, solo movimientos de entrada. Un empaque sin factor declarado deja la fila en `OMITIR` con una nota.

## 6.3 Menú

- Un platillo requiere categoría, nombre y precio. `disponible` controla su visibilidad en la carta pública.
- **Borrado lógico**: `DELETE /menu/items/{id}` marca `disponible=False`; nunca borra si hay ventas. La receta se conserva.
- **Liberación de nombres**: si el platillo no tiene ventas, se borra físicamente (con su receta en cascada). Si tiene historial, se renombra a `{nombre}_deleted_{id}` para poder reutilizar el nombre.
- **Imágenes**: `imagen_url` es gestionado solo por el servidor. Se valida por contenido con Pillow, se comprime a WebP (máximo 1080 px) y se publica en ImgBB con reintentos. El cliente nunca puede escribir una URL a mano.
- **Traducciones**: `nombre_en` / `descripcion_en` / `categorias_menu.nombre_en`. Si faltan, la carta muestra el español.

## 6.4 Salón

- Estados de mesa: LIBRE, OCUPADA, RESERVADA, MANTENIMIENTO.
- **Apodo temporal**: solo en mesas ocupadas, para rastrear al cliente cuando se cambia de mesa. Se borra automáticamente siempre que la mesa vuelve a LIBRE, por cualquier vía.
- **Fusión de mesas**: agrupa mesas con un `grupo_fusion_id` y un color. La fusión no cancela ni cobra comandas. Al desfusionar, las mesas con comandas activas quedan abiertas y ocupadas.
- **Mesas huérfanas**: al iniciar, `_fix_orphaned_mesas()` libera mesas marcadas OCUPADA sin comandas activas. También existe el botón "Forzar Libramiento" en la interfaz para el mismo caso.

## 6.5 Asistencia y turnos

- **Hora local fija de Managua**: los timestamps son naive y no se convierten. Lo que llega del formulario es lo que queda en la base. Este es el punto donde más gente ha intentado "arreglar" algo que ya estaba bien.
- **Día de negocio**: ventana de 24 horas que corta a `HORA_INICIO_DIA` (7:00 por defecto). Un turno iniciado a la 1:00 de la madrugada pertenece al servicio del día anterior.
- **Iniciar turno es idempotente**: si ya hay una asistencia abierta se reutiliza; no se crean duplicados por doble clic. Si el turno del día de negocio ya se finalizó, `400 "Ya registraste y finalizaste tu turno hoy"`.
- **Heartbeat**: el cliente envía latidos cada 120 segundos. El watcher revisa cada 5 minutos y cierra turnos cuyo dueño ya no puede continuar (usuario inactivo, vendedor deshabilitado o sin usuario vinculado).
- **Cierre por deshabilitación**: deshabilitar a un vendedor con turno abierto cierra la asistencia en ese momento, con salida `max(último_heartbeat, ahora − 15 min)` o la hora de entrada si nunca hubo latido. Nunca se inventa tiempo.
- **Check-out sobre turno cerrado**: responde `409` con la hora registrada y la causa. No simula éxito. El empleado ve el aviso una sola vez.
- **Reactividad de turnos**: reabrir una asistencia cerrada por error exige que no haya otro turno abierto y limpia `observaciones`, `horas_extras` y deja `hora_salida_real` en nulo.
- **Anulación**: borrado lógico con motivo obligatorio. Los registros anulados no cuentan para nómina y no bloquean volver a marcar entrada el mismo día.
- **Editar horarios** conserva `horas_extras_originales` si estaba en nulo, para que la corrección de un cierre automático quede trazable.

## 6.6 Nómina

```
salario_diario  = salario_mensual / 30
pago_base       = salario_diario × días_del_rango
tarifa_hora     = salario_base / 240
pago_horas_extras = total_horas_extras × tarifa_hora
pago_neto       = max(0, pago_base + pago_horas_extras − total_adelantos)
```

- Se puede pagar cualquier cantidad de días: 3 días equivale al 10%, 7 días al 23.33%, 15 días al 50%, 30 días al 100%.
- El salario es del empleado (`Empleado.salario_base`), no del puesto.
- Las horas extras se calculan sobre la hora de salida programada del turno, nunca son negativas y se limitan a 99.99.
- **Recálculo**: `recalcular=true` actualiza una nómina PENDIENTE existente en vez de duplicarla. Una nómina PAGADA no se recalcula.
- Cada adelanto genera un `Gasto` de categoría `OPERATIVO` y se descuenta del pago neto.

## 6.7 Caja

- La **caja abierta** son los registros con `cierre_caja_id IS NULL`.
- `POST /caja/cierre` crea el `CierreCaja` y archiva órdenes PAGADAS y gastos pendientes en una sola transacción.
- **Cierre automático**: corre una vez por día local de Managua. Archiva gastos aunque no haya órdenes pagadas. Si la caja está completamente vacía no crea cierre. Si el servicio estuvo dormido a medianoche, se ejecuta al volver a arrancar.
- **Panel del mesero**: solo total vendido, cantidad de órdenes y descuentos del día. Nunca gastos, nómina ni utilidad neta.
- `utilidad_neta = ingresos − nómina − insumos − gastos_operativos`. El costo de insumos usa solo el bucket `SUMINISTROS`; el costo teórico de recetas no se suma para evitar doble contabilidad.

## 6.8 Gastos

- Categorías: OPERATIVO, MANTENIMIENTO, SUMINISTROS, SERVICIOS, IMPUESTOS, OTROS.
- Los gastos generados por consumo de insumos no tienen `registrado_por`: los crea el sistema.
- **Edición y eliminación** exigen motivo obligatorio. La eliminación es lógica y auditada. A diferencia de las órdenes, un gasto puede editarse aunque pertenezca a una caja cerrada (decisión explícita del negocio).
- Eliminar un gasto `SUMINISTROS` automático no devuelve stock.

## 6.9 Auditoría

- Se registran las operaciones sensibles con actor, acción, entidad, descripción y JSON de antes/después.
- Acciones registradas hoy: precios y descuentos, anulación de orden, devolución de ítem, edición y eliminación de gasto, cierre automático de turno, cierre automático de caja, reactivación de asistencia, cambios de permisos, importación aplicada, restauración de copia, eliminación de auditoría y purga masiva.
- Consulta solo para Administrador y Gerente. **Eliminar un registro es exclusivo del Administrador** y el borrado es físico, porque el objetivo es sacar un dato puntual del sistema. La baja deja un evento `AUDITORIA_ELIMINADA` con la cabecera del registro eliminado (fecha, actor, acción, entidad) pero nunca su contenido.

## 6.10 Carta Digital

- Solo lee `/api/public/*`, que no expone costos, recetas, inventario, usuarios ni roles.
- El libro agrupa por categoría, mide cuántos renglones caben realmente en una hoja, reparte parejo (9 platos van 5 + 4, nunca 7 + 2) y solo encadena una sección completa bajo subtítulo si cabe entera.
- Precios siempre en córdobas, en ambos idiomas.
- Bebidas y Extras se dibujan como lista compacta sin fotos.
- Los enlaces antiguos a `/carta` redirigen a la ruta configurada conservando subruta y query string.

## 6.11 Notificaciones y permisos

- Push opt-in: nadie recibe avisos si no los activó y eligió al menos un tipo.
- La entrega exige usuario activo y empleado activo; para vendedores, además turno habilitado.
- Los permisos efectivos son los del rol más los overrides del usuario. El rol Administrador conserva siempre el catálogo completo.
- Los permisos críticos solo los concede un Administrador. No se editan los permisos de la propia cuenta ni los de un Administrador.

---

# 7. Modelo de datos

La base tiene 32 tablas. Los nombres de tabla están en español plural; las clases y columnas técnicas mezclan inglés y español según el dominio. No hay una convención única, y renombrar ahora costaría más de lo que arregla.

## 7.1 Entidades principales

### Personal y acceso

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `puestos` | nombre, salario_base | Salario de referencia al crear empleados |
| `empleados` | nombre, apellido, cedula_identidad, telefono, email, puesto_id, fecha_ingreso, fecha_baja, salario_base, salario_base_al_baja, activo | El salario vive aquí, no en el puesto |
| `usuarios` | username, password_hash, rol, empleado_id, activo, turno_habilitado, avisos_fuera_de_turno, avisos_cocina, avisos_mesero, avisos_mesero_todas, permisos (JSON) | `permisos` guarda solo overrides |

### Mesas y órdenes

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `zonas` | nombre, descripcion | |
| `mesas` | numero, capacidad, estado, apodo, grupo_fusion_id, color_fusion, mesa_principal_id, zona_id | La fusión se representa con `grupo_fusion_id` |
| `ordenes` | mesa_id (nullable), mesero_id, estado, total, subtotal, descuento_total, nombre_cliente, metodo_pago, fecha_creacion, cierre_caja_id, anulada, motivo_anulacion, anulada_por, anulada_en | |
| `detalles_orden` | orden_id, producto_id, cantidad, precio_unitario, descuento_porcentaje, descuento_monto, motivo_descuento, notas, cantidad_devuelta, motivo_devolucion, devuelta_en | |
| `pagos_comanda` | orden_id, usuario_id, metodo_pago, monto, division_id, parte, cantidad, creado_en | Ledger de pagos parciales |
| `divisiones_pago_comanda` | orden_id, detalle_orden_id, cantidad, personas, inicio_cantidad, creada_por | Reparto de una línea entre personas |
| `pagos_online` | orden_id, proveedor, referencia, clave_idempotencia, estado, monto, moneda, checkout_url | Proveedor deshabilitado por defecto |

### Menú e inventario

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `categorias_menu` | nombre, descripcion, nombre_en | |
| `menu_items` | nombre, descripcion, nombre_en, descripcion_en, precio, disponible, imagen_url, tiempo_preparacion, categoria_id | |
| `recetas` | menu_item_id, insumo_id, cantidad_necesaria, unidad_medida_id, descuento_por_lote | |
| `categorias_insumo` | nombre | |
| `unidades_medida` | nombre, abreviatura, tipo_magnitud, unidad_base_id, factor_conversion | Cadena transitiva |
| `proveedores` | nombre, contacto_nombre, telefono, email | |
| `insumos` | nombre, cantidad_actual, unidad_medida_id, stock_minimo, categoria_id, costo_unitario, unidad_empaque_id, factor_empaque | |
| `movimientos_inventario` | insumo_id, tipo, cantidad, motivo, fecha | ENTRADA / SALIDA |
| `preparaciones_cocina` | asistencia_id, notas, fecha, registrado_por | Producción por lote |
| `detalles_preparaciones_cocina` | preparacion_id, insumo_id, cantidad, costo_total | |
| `ingredientes` | nombre, unidad_medida, stock_actual, stock_minimo, costo_unitario, proveedor_id | Modelo legado, aún en el esquema |

### Caja, gastos y dinero

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `cierres_caja` | fecha_cierre, total_ventas, total_ordenes, cerrado_por | `cerrado_por` nulo en cierre automático |
| `gastos` | concepto, monto, categoria, fecha, registrado_por, insumo_id, cierre_caja_id, eliminado, motivo_eliminacion, eliminado_por, eliminado_en | |
| `nominas` | empleado_id, fecha_inicio, fecha_fin, salario_base_mensual, salario_semanal_teorico, salario_quincenal_teorico, salario_periodo_teorico, total_horas_extras, pago_horas_extras, pago_neto, estado, fecha_pago, total_adelantos | |
| `adelantos_salario` | empleado_id, monto, fecha, observacion, registrado_por_id, gasto_id | |
| `descuentos_frecuentes` | nombre, tipo, valor, activo | Catálogo global de promociones |

### Asistencia

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `turnos` | nombre, hora_entrada, hora_salida, horas_teoricas | Plantillas |
| `asistencias` | empleado_id, turno_id, fecha, hora_entrada_real, hora_salida_real, horas_extras, observaciones, ip_origen, horas_extras_originales, motivo_modificacion, modificado_por, ultimo_heartbeat, anulada | |

### Sistema

| Tabla | Campos relevantes | Notas |
|-------|-------------------|-------|
| `registros_auditoria` | ocurrido_en, actor_id, actor_username, actor_rol, accion, entidad_tipo, entidad_id, descripcion, antes (JSON), despues (JSON) | |
| `configuracion_sistema` | clave (PK), valor, actualizado_en | Cierre automático de caja |
| `backups_sistema` | nombre, origen, creado_en, total_registros, tamano_bytes, contenido (LONGTEXT), creado_por | El contenido vive en la base |
| `push_suscripciones` | usuario_id, endpoint (unique), p256dh, auth, user_agent, creada_en, ultimo_envio_en | |
| `novedades_sistema` | version (unique), titulo, resumen, detalle (JSON), publicada_en, notificada, notificada_en | |
| `eventos_calendario` | tipo, titulo, color_etiqueta, descripcion, fecha_inicio, fecha_fin, hora_inicio, hora_fin, estado, menu_item_id, insumo_id, proveedor_id, cantidad_esperada, creado_por_id | |
| `estudios_mercado` | periodo, tipo, estado, desde, hasta, titulo, resumen, fortalezas, debilidades, estrategias, analisis, metricas (JSON), modelo_ia, error, intentos, notificado | |
| `documentos_estudio_mercado` | nombre, tipo_archivo, mime, tamano_bytes, texto, caracteres, subido_por_id | |
| `mensajes_estudio_mercado` | usuario_id, rol, contenido, documento_id, estudio_id, permitido | |
| `importaciones_inventario` | nombre_archivo, tipo_archivo, hash_archivo, estado, modelo_ia, resumen (JSON), error, creada_por, aplicada_en | |
| `detalles_importacion_inventario` | importacion_id, fila, texto_origen, nombre_detectado, cantidad, unidad_texto, precio_unitario, precio_total, categoria_texto, insumo_id, accion, categoria_id, unidad_medida_id, unidad_empaque_id, factor_empaque, stock_minimo, confianza, notas, aplicado | |
| `camaras`, `accesos_camaras`, `clips_camaras` | nombre, slug, activa; permisos por usuario; clips con fragmentos | Módulo opcional |

## 7.2 Relaciones clave

```
Puesto 1 ── n Empleado 1 ── 1 Usuario
Empleado 1 ── n Asistencia n ── 1 Turno
Empleado 1 ── n Nomina
Empleado 1 ── n AdelantoSalario n ── 1 Gasto

Zona 1 ── n Mesa
Mesa 1 ── n Orden n ── n MenuItem (via DetalleOrden)
Orden 1 ── n PagoComanda
Orden 1 ── n DivisionPagoComanda
CierreCaja 1 ── n Orden
CierreCaja 1 ── n Gasto

CategoriaMenu 1 ── n MenuItem 1 ── n Receta n ── 1 Insumo
CategoriaInsumo 1 ── n Insumo n ── 1 UnidadMedida (base y empaque)
Insumo 1 ── n MovimientoInventario
PreparacionCocina 1 ── n DetallePreparacionCocina n ── 1 Insumo

ImportacionInventario 1 ── n DetalleImportacionInventario
EstudioMercado 1 ── n MensajeEstudio n ── 0..1 DocumentoEstudio
Usuario 1 ── n PushSuscripcion
```

## 7.3 Índices de rendimiento

Creados por `_migrate_indices_rendimiento()` en el arranque, solo si faltan:

| Índice | Columnas |
|--------|----------|
| `ix_ordenes_estado_cierre` | estado, cierre_caja_id, anulada |
| `ix_ordenes_estado_fecha` | estado, fecha_creacion |
| `ix_detalles_orden_producto` | producto_id |
| `ix_gastos_cierre_eliminado` | cierre_caja_id, eliminado |
| `ix_gastos_fecha` | fecha |
| `ix_nominas_estado_fecha_pago` | estado, fecha_pago |
| `ix_asistencias_empleado_entrada` | empleado_id, hora_entrada_real |
| `ix_cierres_caja_fecha` | fecha_cierre |

Las consultas de reportes usan rangos semiabiertos `[inicio 00:00, fin+1 00:00)` sobre columnas `DateTime`; se eliminó `func.date(columna)` justamente para que el índice se pueda usar.

## 7.4 Estrategia de migración

No se ejecutan migraciones de Alembic. El esquema se mantiene con:

1. `Base.metadata.create_all()` al iniciar.
2. Funciones `_migrate_*` idempotentes que revisan `information_schema` antes de alterar.
3. Funciones `_fix_*` que corrigen datos legacy.

Es una decisión consciente: el despliegue en Render no ejecuta un paso de migración y la base ya tenía datos cuando se adoptó el esquema. Alembic está en `requirements.txt`, pero no se usa todavía.

---

# 8. Diseño del backend

## 8.1 Estructura de capas

```
app/
├── main.py          aplicación, routers, mounts, migraciones, watchers
├── core/            configuración, base de datos, seguridad, tiempo, permisos, VAPID, novedades
├── api/
│   ├── deps.py      get_current_user, requerir_rol, requerir_permiso
│   └── endpoints/   un archivo por dominio
├── schemas/         contratos Pydantic
├── models/          entidades SQLAlchemy 2.x
├── repositories/    consultas
├── services/        reglas de negocio
├── utils/           cálculos auxiliares
└── db/              inicialización y siembra
```

## 8.2 Núcleo (`app/core`)

| Archivo | Responsabilidad |
|---------|-----------------|
| `config.py` | `Settings` con Pydantic Settings; normaliza `postgres://` a `postgresql://` y cae a SQLite si `DATABASE_URL` está vacío |
| `database.py` | Engine, `SessionLocal`, `Base`, `get_db()`. Usa `StaticPool` solo para SQLite en memoria |
| `security.py` | bcrypt directo + JWT HS256; `verificar_password()` tolera hashes corruptos devolviendo `False` |
| `tiempo.py` | `ahora_local()`, `hoy_local()`, `ventana_dia_negocio()` con `ZoneInfo("America/Managua")` |
| `permisos.py` | Catálogo de 18 permisos y resolución de overrides |
| `vapid.py` | Claves VAPID derivadas de `SECRET_KEY` |
| `slug.py` | Generador de slugs públicos estilo Render |
| `novedades.py` | Fuente de verdad de las novedades |

## 8.3 Dependencias de seguridad

```python
get_current_user(token)      # decodifica el JWT y relee el usuario de la base
requerir_rol([roles])        # 403 si el rol no está en la lista
requerir_permiso(clave)      # 403 si el permiso efectivo no está concedido
```

`get_current_user` valida en cada petición:

- token válido, `sub` numérico, usuario existente;
- `activo == True`, o `403 USUARIO_DESACTIVADO`;
- si es Vendedor, `turno_habilitado == True`, o `403 TURNO_DESHABILITADO`.

El rol y los permisos se leen de la base, nunca del token. Un usuario eliminado físicamente produce `401`.

## 8.4 Servicios principales

| Servicio | Responsabilidad |
|----------|-----------------|
| `orden_service.py` | Máquina de estados, stock, descuentos, pagos, anulación. El corazón del sistema |
| `caja_service.py` | Cierre manual y automático, toggle persistente |
| `asistencia_service.py` | Heartbeat, cierres automáticos, reactivación, anulación |
| `nomina_service.py` | Cálculo por días, horas extras, adelantos, recálculo |
| `inventario_service.py` | Movimientos, conversión, empaque, gasto automático |
| `menu_service.py` | CRUD de menú, publicación pública, subida de imágenes |
| `preparacion_service.py` | Producción por lote y descuento de insumos |
| `importacion_inventario_service.py` | Analizar, aplicar y descartar importaciones |
| `reportes_service.py` | Cierre financiero por periodo |
| `auditoria_service.py` | Registro de eventos con actor o como sistema |
| `backup_service.py` | Volcado y restauración completa |
| `estudio_mercado_service.py` | Generación del estudio, chat y exportación |
| `gemini_service.py` | Cliente Gemini con rotación de modelos y reintentos |
| `push_service.py` | Suscripciones, preferencias y envíos |
| `calendario_service.py` | CRUD de eventos y consulta de asistencias |
| `conversion_service.py` | Conversión transitiva entre unidades |

## 8.5 Repositorios

Cada repositorio encapsula las consultas de su dominio y usa `joinedload` explícito donde hace falta. Desde el perfilado de rendimiento, las relaciones que no se necesitan en cada lectura usan `lazy="select"`, y `UsuarioRepository.get_by_id_con_perfil()` resuelve usuario, empleado y puesto en una sola consulta. Antes, `get_current_user` arrastraba asistencias, nóminas y adelantos en cada petición: 6 o 7 `SELECT` para leer un simple perfil.

## 8.6 Patrones y convenciones

- Los servicios lanzan `HTTPException` para violaciones de reglas; los repositorios no conocen HTTP.
- Los schemas de respuesta usan `ConfigDict(from_attributes=True)`.
- Los identificadores internos van en inglés; los mensajes al usuario, en español.
- Operaciones de escritura complejas se ejecutan dentro de una sola transacción; si una fila falla, se revierte todo (importación de inventario es el ejemplo canónico).
- Las tareas en segundo plano abren su propia `SessionLocal()`: nunca comparten sesión con la petición que las originó.

## 8.7 Tareas de fondo

| Tarea | Frecuencia | Qué hace |
|-------|-----------|----------|
| `_heartbeat_watcher` | 5 minutos | Cierra turnos huérfanos y audita el cierre |
| `_cierre_caja_watcher` | 1 minuto | Cierre de caja automático a medianoche |
| `_camera_clip_retention_watcher` | Periódica | Depura clips antiguos |
| `_estudio_mercado_watcher` | 1 hora | Genera el estudio mensual y reintenta hasta 5 veces |
| `_novedades_watcher` | 1 hora | Siembra y difunde novedades pendientes |

---

# 9. Diseño del frontend

## 9.1 ERP (SPA)

- **Un solo archivo de lógica**: `app/Templates/js/app.js` (unas 11 600 líneas). No hay build step. Es una decisión deliberada: compilar traería un toolchain y el equipo es pequeño.
- **Sin framework**: Vanilla JS con funciones por pantalla y un objeto `state` global.
- **Navegación**: `navigateTo(pantalla)` muestra la sección correspondiente y valida permisos contra `PERMISOS_PANTALLA`.
- **API**: el interceptor `api()` agrega el token, usa `cache: 'no-store'`, muestra toasts de error y maneja los `401` y `403` de sesión.
- **Detección de API_BASE**: local usa `http://127.0.0.1:8000/api/v1`; en cualquier otro origen, `${location.origin}/api/v1`.
- **Estilos**: `css/style.css` con design tokens propios y Tailwind precompilado en `css/tailwind.min.css`.
- **Modo oscuro**: `data-theme="dark"` en `<html>`, preferencia en `localStorage` y colores derivados con `color-mix()` y variables `--mix-*`.
- **Service worker**: `sw.js` registrado con scope `/Templates/` para notificaciones push y enlaces profundos.

## 9.2 Estructura de la interfaz

| Elemento | Descripción |
|----------|-------------|
| Sidebar fija | 260 px en escritorio, off-canvas en móvil |
| Topbar | Reloj global, tema, avisos y perfil |
| Bottom nav | Navegación móvil, incluye el acceso al panel de asistencia |
| Pantallas | Salón, Comandas, Carta, Inventario, Personal, Nómina, Caja, Gastos, Calendario, Auditoría, Estudio de mercado, Copias |
| Modales | Patrón `.modal-overlay.show` |
| Toasts | `showToast(mensaje, tipo)` |

## 9.3 Design tokens

| Variable | Valor | Uso |
|----------|-------|-----|
| `--azul-marino` | `#003366` | Principal y encabezados |
| `--rojo-cangrejo` | `#E63946` | Alertas y acciones destructivas |
| `--amarillo-solar` | `#FFB703` | Advertencias y destacados |
| `--turquesa-ola` | `#2A9D8F` | Éxito y secundario |

Regla obligatoria del modo oscuro: no escribir colores literales nuevos en reglas que deban adaptarse. Usar `color-mix(in srgb, <color-claro> var(--mix-pct), var(--mix-base))`.

## 9.4 Carta Digital

- `index.html`, `css/estilo.css` y `js/menu-libro.js`, más StPageFlip vendorizado.
- Motor: agrupar, medir capacidad real con una hoja oculta, repartir parejo, encadenar secciones y dibujar.
- Hoja de 1200 × 1800 px dibujada una vez y escalada con `transform: scale()`.
- Fotos en cola de 4 en paralelo, priorizando las hojas cercanas a la visible; un plato sin foto dibuja su inicial.
- Visor de zoom que clona la hoja para que el texto se pueda ampliar nítido.
- Gestos táctiles con Touch Events para iOS; ratón y lápiz con Pointer Events.

## 9.5 Rendimiento del frontend

- Assets con URL estable y revalidación por ETag (`304`), nunca `?v=`.
- Imágenes y fuentes locales con caché de 7 días.
- `preconnect` a fuentes y CDN, `defer` en scripts.
- GZip en respuestas mayores a 800 bytes.
- Imágenes de platillos con `loading="lazy"`, `decoding="async"` y esqueleto de carga.

---

# 10. Seguridad

## 10.1 Superficie de ataque

| Ruta | Acceso | Observación |
|------|--------|-------------|
| `/api/v1/*` | Autenticado | Todo salvo el login |
| `POST /api/v1/auth/login` | Público | Punto de entrada |
| `/api/public/*` | Público | Solo lectura, campos públicos |
| `GET /` | Público | SPA del ERP |
| `/Templates/*`, `/carta/*` | Público | Estáticos |
| `/healthcheck` | Público | Monitoreo |
| `/docs`, `/redoc`, `/openapi.json` | Público | Riesgo conocido |
| `POST /api/v1/pagos/webhooks/{provider}` | Público con firma | Proveedor deshabilitado |

## 10.2 Autenticación

- Login con username normalizado a minúsculas y sin espacios; repositorio con doble pasada tolerante para filas legacy.
- Contraseñas con bcrypt; `verificar_password()` captura hashes corruptos y devuelve `False` en vez de reventar con 500.
- JWT HS256 con `sub` en texto (requisito de python-jose) y expiración de 365 días.
- El token no transporta rol ni permisos: se leen de la base en cada petición.

## 10.3 Autorización

- Roles por defecto más overrides por usuario.
- Los endpoints cubiertos usan `requerir_permiso(clave)`; los módulos fuera de alcance siguen con `requerir_rol`.
- El frontend oculta lo no autorizado, pero la defensa real está en el backend.

## 10.4 Protecciones aplicadas

- CORS restringido a orígenes configurados con `allow_credentials=True`.
- Cabeceras `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` y `Strict-Transport-Security` bajo HTTPS.
- Sin inyección SQL: todo pasa por el ORM parametrizado.
- Sin traversal en los mounts estáticos.
- Los endpoints públicos no exponen costos, recetas, inventario, usuarios ni roles.
- Las contraseñas nunca salen en respuestas.
- Validación de imágenes por contenido, no por extensión.

## 10.5 Riesgos abiertos

| Riesgo | Impacto | Mitigación pendiente |
|--------|---------|----------------------|
| Sin límite de intentos en login | Fuerza bruta | Rate limiting por IP y usuario |
| Mensajes de login diferenciados | Enumeración de usuarios | Unificar mensaje (decisión de UX pendiente) |
| `/docs` público | Exposición del contrato | Deshabilitar en producción |
| Contraseña de `joshi_0211` forzada en arranque | Credencial conocida | Rotar y eliminar el mecanismo |
| Credenciales en el repositorio | Fuga | Rotar y usar variables de entorno |
| Token de 365 días sin refresh | Sesión muy larga | Un access token corto y refresh |
| Log imprime prefijo del hash | Información parcial | Eliminar el detalle |

Ninguno de estos riesgos es un fallo de diseño; son deudas conscientes con fecha pendiente. El sistema se usa en un restaurante, no en un banco, pero eso no debería ser el argumento para dejarlos ahí.

## 10.6 Auditoría como control

La bitácora no es solo trazabilidad: es el control compensatorio de varias operaciones destructivas. Si alguien anula una orden, devuelve una línea, elimina un gasto o cierra un turno a la fuerza, queda registrado con antes y después. La única forma de borrar un registro es ser Administrador, y esa baja también deja huella.

---

# 11. API REST

Todos los endpoints del ERP viven bajo `/api/v1/`. La referencia interactiva completa está en `/docs` (Swagger UI) mientras esa ruta siga pública.

## 11.1 Convenciones

- Autenticación: cabecera `Authorization: Bearer <token>`.
- Cuerpos y respuestas en JSON, salvo subida de archivos (`multipart/form-data`) y descarga de informes o copias.
- Errores con el formato estándar de FastAPI: `{"detail": "..."}`.
- Los identificadores de recurso son enteros, salvo `CameraClip.id` y `EstudioMercado` en algunos flujos que usan UUID como texto.
- Los listados devuelven arreglos; los paginados devuelven un objeto con `total` y los elementos.

## 11.2 Endpoints por módulo

### Autenticación

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/auth/login` | Público | Devuelve token, usuario, rol, puesto y permisos |
| GET | `/auth/me` | Autenticado | Sesión vigente con permisos efectivos |

### Personal

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/personal/puestos` | Admin, Gerente | Crear puesto |
| GET | `/personal/puestos` | Autenticado | Listar puestos |
| POST | `/personal/empleados` | Admin, Gerente | Crear empleado |
| GET | `/personal/empleados` | Autenticado | Listar empleados |
| GET | `/personal/empleados/bajas` | Admin, Gerente | Empleados dados de baja |
| PUT | `/personal/empleados/{id}` | Admin, Gerente | Editar empleado |
| DELETE | `/personal/empleados/{id}` | Admin, Gerente | Baja lógica con contraseña de quien ejecuta |
| POST | `/personal/usuarios` | Admin, Gerente | Crear usuario |
| GET | `/personal/usuarios` | Autenticado | Listar usuarios |
| DELETE | `/personal/usuarios/{id}` | Admin, Gerente | Baja o borrado con liberación de nombre |
| PUT | `/personal/usuarios/{id}/reset-password` | Admin, Gerente | Restablecer contraseña |
| PATCH | `/personal/usuarios/turno-masivo` | Admin, Gerente | Habilitar o deshabilitar turnos de todos los vendedores |
| PATCH | `/personal/usuarios/{id}/turno` | Admin, Gerente | Habilitar o deshabilitar turno individual |
| PATCH | `/personal/usuarios/{id}/avisos` | Admin, Gerente | Preferencias de notificación |
| GET | `/personal/permisos/catalogo` | Admin, Gerente | Catálogo de permisos |
| GET | `/personal/usuarios/{id}/permisos` | Admin, Gerente | Permisos del usuario |
| PUT | `/personal/usuarios/{id}/permisos` | Admin, Gerente | Conjunto final de permisos |

### Asistencia y turnos

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/asistencia/turnos` | Admin, Gerente | Crear plantilla de turno |
| GET | `/asistencia/turnos` | Autenticado | Listar plantillas |
| PUT | `/asistencia/turnos/{id}` | Admin, Gerente | Editar plantilla |
| DELETE | `/asistencia/turnos/{id}` | Admin, Gerente | Eliminar plantilla |
| POST | `/asistencia/turnos/iniciar/{id}` | Autenticado | Iniciar turno desde plantilla |
| POST | `/asistencia/turnos/heartbeat/{id}` | Autenticado | Enviar latido |
| POST | `/asistencia/check-in` | Autenticado | Marcar entrada |
| POST | `/asistencia/check-out` | Autenticado | Marcar salida; `409` si ya se cerró |
| GET | `/asistencia/activa` | Autenticado | Asistencia abierta del usuario |
| GET | `/asistencia/empleados/{id}/historial` | Autenticado | Historial del empleado |
| PUT | `/asistencia/{id}/horas-extras` | Admin, Gerente | Ajustar horas extras |
| PUT | `/asistencia/{id}/editar-horarios` | Admin, Gerente | Corregir entrada y salida con motivo |
| DELETE | `/asistencia/{id}` | Admin, Gerente | Anular asistencia con motivo |
| POST | `/asistencia/{id}/reactivar` | `asistencia_admin` | Reabrir turno cerrado por error |

### Nómina

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/nomina/generar` | Admin, Gerente | Generar nómina del periodo |
| POST | `/nomina/calcular` | Autenticado | Calcular o recalcular |
| GET | `/nomina/pendientes` | Autenticado | Nóminas pendientes |
| PUT | `/nomina/{id}/pagar` | Admin, Gerente | Marcar como pagada |
| PUT | `/nomina/{id}/recalcular` | Admin, Gerente | Recalcular una pendiente |
| GET | `/nomina/empleados/{id}/historial` | Autenticado | Historial de nóminas |
| GET | `/nomina/empleado/{id}` | Autenticado | Igual que el anterior (duplicado conocido) |
| POST | `/nomina/adelantos` | Admin, Gerente | Registrar adelanto |
| GET | `/nomina/empleados/{id}/adelantos` | Autenticado | Adelantos con filtro de fecha |

### Inventario

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/inventario/proveedores` | Admin, Gerente | Crear proveedor |
| GET | `/inventario/proveedores` | Autenticado | Listar proveedores |
| POST | `/inventario/ingredientes` | Admin, Gerente | Crear ingrediente legado |
| GET | `/inventario/ingredientes` | Autenticado | Listar ingredientes legados |
| GET | `/inventario/ingredientes/alertas` | Autenticado | Alertas de ingredientes |
| POST | `/inventario/movimientos` | Admin, Gerente | Registrar movimiento |
| GET | `/inventario/ingredientes/{id}/historial` | Autenticado | Historial de un ingrediente |
| GET | `/inventario/insumos` | Autenticado | Listar insumos |
| GET | `/inventario/insumos/alertas` | Autenticado | Insumos bajo mínimo |
| GET | `/inventario/insumos/lote-ids` | Autenticado | Insumos marcados para lote |
| GET | `/inventario/insumos/{id}` | Autenticado | Detalle de insumo |
| POST | `/inventario/insumos` | Admin, Gerente | Crear insumo |
| PATCH | `/inventario/insumos/{id}/stock` | Admin, Gerente | Ajustar stock |
| PATCH | `/inventario/insumos/{id}` | Admin, Gerente | Editar insumo |
| GET | `/inventario/categorias-insumo` | Autenticado | Categorías |
| POST | `/inventario/categorias-insumo` | Admin, Gerente | Crear categoría |
| DELETE | `/inventario/categorias-insumo/{id}` | Admin, Gerente | Eliminar si no tiene insumos |
| GET | `/inventario/unidades-medida` | Autenticado | Unidades |
| POST | `/inventario/unidades-medida` | Admin, Gerente | Crear unidad |
| PUT | `/inventario/unidades-medida/{id}` | Admin, Gerente | Editar unidad |
| DELETE | `/inventario/unidades-medida/{id}` | Admin, Gerente | Eliminar si no tiene insumos |
| GET | `/inventario/unidades-medida/convertir` | Autenticado | Conversión entre unidades |
| POST | `/inventario/preparaciones` | Admin, Gerente | Producción por lote |
| GET | `/inventario/preparaciones` | Autenticado | Preparaciones del día |

### Importación de inventario

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/inventario/importaciones/analizar` | `inventario_gestionar` | Subir archivo y analizarlo |
| GET | `/inventario/importaciones/` | `inventario_gestionar` | Últimos 30 lotes |
| GET | `/inventario/importaciones/{id}` | `inventario_gestionar` | Detalle del lote |
| POST | `/inventario/importaciones/{id}/aplicar` | `inventario_gestionar` | Aplicar cambios confirmados |
| DELETE | `/inventario/importaciones/{id}` | `inventario_gestionar` | Descartar lote en revisión |

### Menú

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/menu/categorias` | Admin, Gerente | Crear categoría |
| GET | `/menu/categorias` | Autenticado | Listar categorías |
| DELETE | `/menu/categorias/{id}` | Admin, Gerente | Eliminar si no tiene platillos |
| POST | `/menu/items` | Admin, Gerente | Crear platillo |
| GET | `/menu/items` | Autenticado | Listar; `incluir_inactivos=true` para gestión |
| GET | `/menu/items/{id}` | Autenticado | Detalle |
| PUT | `/menu/items/{id}` | Admin, Gerente | Editar |
| DELETE | `/menu/items/{id}` | Admin, Gerente | Borrado lógico o físico con liberación de nombre |
| POST | `/menu/items/{id}/imagen` | Admin, Gerente | Subir imagen multipart |

### Salón

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/salon/zonas` | Admin, Gerente | Crear zona |
| GET | `/salon/zonas` | Autenticado | Listar zonas |
| DELETE | `/salon/zonas/{id}` | Admin, Gerente | Eliminar si no tiene mesas |
| GET | `/salon/mapa` | Autenticado | Mapa completo con estados |
| POST | `/salon/mesas` | Admin, Gerente | Crear mesa |
| GET | `/salon/mesas` | Autenticado | Listar mesas |
| PUT | `/salon/mesas/{id}` | Admin, Gerente | Editar mesa |
| DELETE | `/salon/mesas/{id}` | Admin, Gerente | Eliminar mesa |
| PATCH | `/salon/mesas/{id}/estado` | Autenticado | Cambiar estado; libera apodo si pasa a LIBRE |
| PATCH | `/salon/mesas/{id}/apodo` | Autenticado | Asignar o limpiar apodo |
| POST | `/salon/mesas/fusionar` | Autenticado | Fusionar mesas |
| POST | `/salon/mesas/{id}/separar` | Autenticado | Separar una mesa del grupo |
| POST | `/salon/mesas/{id}/desfusionar` | Autenticado | Disolver el grupo |
| PATCH | `/salon/mesas/{id}/estado` | Autenticado | Forzar libramiento de mesa huérfana |

### Órdenes

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/ordenes/` | Autenticado | Crear comanda |
| POST | `/ordenes/retroactiva` | Admin, Gerente | Venta con fecha pasada |
| GET | `/ordenes/` | Autenticado | Listar con filtros y límite |
| GET | `/ordenes/{id}` | Autenticado | Detalle |
| PATCH | `/ordenes/{id}/estado` | Autenticado | Cambiar estado según la máquina |
| POST | `/ordenes/{id}/items` | Autenticado | Agregar ítems |
| PUT | `/ordenes/{id}/items` | Autenticado | Reemplazar contenido de la comanda |
| PUT | `/ordenes/{id}/pagar` | Autenticado | Cobrar y liberar mesa |
| GET | `/ordenes/{id}/pagos` | Autenticado | Pagos, saldo y divisiones |
| POST | `/ordenes/{id}/pagos/cotizar-division` | Autenticado | Repartir una cantidad entre personas |
| POST | `/ordenes/{id}/pagos` | Autenticado | Registrar abono o parte |
| POST | `/ordenes/{id}/anular` | Admin, Gerente | Anular con motivo |
| POST | `/ordenes/{id}/devolver-item` | Admin, Gerente | Devolver unidades de una línea |
| POST | `/ordenes/{id}/descuento-item` | Autenticado | Descuento por línea |
| POST | `/ordenes/{id}/descuento-global` | Autenticado | Descuento global prorrateado |
| DELETE | `/ordenes/{id}/descuento-item/{detalle_id}` | Autenticado | Quitar descuento de línea |

### Caja

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| GET | `/caja/historial-diario` | Autenticado | Órdenes de la caja abierta |
| GET | `/caja/ventas-dia` | Autenticado | Resumen acotado para el mesero |
| POST | `/caja/cierre` | Admin, Gerente | Cerrar y archivar |
| GET | `/caja/cierre-automatico` | Autenticado | Estado del cierre automático |
| PUT | `/caja/cierre-automatico` | Admin, Gerente | Activar o desactivar |

### Gastos

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/gastos/` | Admin, Gerente | Registrar gasto |
| GET | `/gastos/` | Admin, Gerente | Listar con filtro de fechas |
| PUT | `/gastos/{id}` | Admin, Gerente | Editar con motivo |
| DELETE | `/gastos/{id}` | Admin, Gerente | Eliminar con motivo (lógico) |

### Descuentos, calendario y reportes

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| GET | `/descuentos/` | Autenticado | Catálogo; `solo_activos=true` |
| POST | `/descuentos/` | Admin, Gerente | Crear descuento frecuente |
| PUT | `/descuentos/{id}` | Admin, Gerente | Editar |
| DELETE | `/descuentos/{id}` | Admin, Gerente | Eliminar |
| GET | `/calendario/` | Autenticado | Eventos y asistencias; máximo 63 días |
| POST | `/calendario/eventos` | Admin, Gerente | Crear evento |
| POST | `/calendario/eventos/masivo` | Admin, Gerente | Crear varios eventos |
| PUT | `/calendario/eventos/{id}` | Admin, Gerente | Editar evento |
| DELETE | `/calendario/eventos/{id}` | Admin, Gerente | Eliminar evento |
| GET | `/reportes/cierre` | Admin, Gerente | Cierre financiero por periodo |
| GET | `/analitica/cierre-caja` | Admin, Gerente | Cierre legacy |

### Auditoría, copias y novedades

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| GET | `/auditoria/` | Admin, Gerente | Bitácora paginada |
| DELETE | `/auditoria/{id}` | Administrador | Borrado físico con motivo |
| POST | `/backups/crear` | Administrador | Generar copia |
| GET | `/backups/` | Administrador | Listar copias |
| GET | `/backups/estado` | Administrador | Estado de la copia automática |
| GET | `/backups/descargar/{id}` | Administrador | Descargar contenido |
| DELETE | `/backups/{id}` | Administrador | Eliminar copia |
| POST | `/backups/subir-y-restaurar` | Administrador | Restaurar copia subida |
| GET | `/novedades/` | Autenticado | Historial de versiones |

### Push

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| GET | `/push/config` | Autenticado | Clave pública VAPID y disponibilidad |
| GET | `/push/preferencias` | Autenticado | Preferencias propias |
| PATCH | `/push/preferencias` | Autenticado | Actualizar preferencias propias |
| POST | `/push/subscribe` | Autenticado | Registrar suscripción |
| POST | `/push/unsubscribe` | Autenticado | Eliminar suscripción por endpoint |
| GET | `/push/subscriptions` | Autenticado | Suscripciones propias |
| DELETE | `/push/subscriptions/{id}` | Autenticado | Eliminar suscripción propia |

### Estudio de mercado

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/estudio-mercado/generar` | Admin, Gerente | Generar en segundo plano (202) |
| GET | `/estudio-mercado/` | Admin, Gerente | Listar estudios |
| GET | `/estudio-mercado/{id}` | Admin, Gerente | Detalle |
| GET | `/estudio-mercado/{id}/exportar` | Admin, Gerente | Informe HTML con gráficas |
| DELETE | `/estudio-mercado/{id}` | Admin, Gerente | Eliminar estudio |
| POST | `/estudio-mercado/documentos` | Admin, Gerente | Subir documento |
| GET | `/estudio-mercado/documentos` | Admin, Gerente | Listar documentos |
| DELETE | `/estudio-mercado/documentos/{id}` | Admin, Gerente | Eliminar documento |
| POST | `/estudio-mercado/chat` | Admin, Gerente | Consultar al asesor |
| GET | `/estudio-mercado/chat/historial` | Admin, Gerente | Últimos 60 mensajes |
| DELETE | `/estudio-mercado/chat/historial` | Admin, Gerente | Limpiar historial |

### Cámaras y pagos

| Método | Ruta | Acceso | Descripción |
|--------|------|--------|-------------|
| POST | `/cameras/authorize` | Público con JWT de propósito | Autorizar stream |
| GET | `/cameras/eligible-users` | Admin, Gerente | Usuarios elegibles |
| GET | `/cameras/storage` | Admin, Gerente | Estado del almacenamiento |
| GET | `/cameras/` | Admin, Gerente | Listar cámaras |
| POST | `/cameras/` | Admin, Gerente | Crear cámara |
| PATCH | `/cameras/{id}` | Admin, Gerente | Editar cámara |
| PUT | `/cameras/{id}/access` | Admin, Gerente | Asignar accesos |
| POST | `/cameras/{id}/stream-token` | Admin, Gerente | Token de stream |
| GET | `/cameras/clips` | Autenticado | Listar clips |
| GET | `/cameras/clips/{id}/video` | Autenticado | Descargar clip |
| DELETE | `/cameras/clips/{id}` | Admin, Gerente | Eliminar clip |
| POST | `/cameras/{id}/clips` | Autenticado | Iniciar grabación |
| PUT | `/cameras/{id}/clips/{clip_id}/chunks/{seq}` | Autenticado | Subir fragmento |
| POST | `/cameras/{id}/clips/{clip_id}/finish` | Autenticado | Cerrar grabación |
| GET | `/pagos/disponibilidad` | Autenticado | Disponibilidad del gateway |
| POST | `/pagos/ordenes/{id}/checkout` | Autenticado | Iniciar pago en línea |
| GET | `/pagos/{id}` | Autenticado | Estado del pago |
| POST | `/pagos/webhooks/{provider}` | Firma obligatoria | Notificación del proveedor |

### API pública

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/public/menu` | Platillos disponibles |
| GET | `/api/public/categories` | Categorías |
| GET | `/api/public/menu/{categoria_id}` | Platillos por categoría |
| GET | `/api/public/item/{item_id}` | Detalle de platillo disponible |

## 11.3 Códigos de respuesta

| Código | Uso |
|--------|-----|
| 200 | Operación exitosa |
| 201 | Recurso creado (importaciones, algunas altas) |
| 202 | Aceptado para proceso en segundo plano (estudio de mercado) |
| 204 | Eliminación sin contenido |
| 400 | Violación de regla de negocio |
| 401 | Token inválido, expirado o credenciales incorrectas |
| 403 | Rol o permiso insuficiente; usuario desactivado; turno deshabilitado |
| 404 | Recurso inexistente |
| 409 | Conflicto de estado (check-out sobre turno cerrado) |
| 422 | Validación de schema |
| 500 | Error no controlado (clave de servicio ausente, por ejemplo) |
| 502 | Fallo de servicio externo (ImgBB) |

---

# 12. Procesos del negocio

## 12.1 Venta en mesa

1. El mesero abre el salón y elige una mesa libre.
2. Crea una comanda con platillos y notas.
3. El backend valida stock, descuenta insumos, genera movimientos y gastos de suministros.
4. La comanda aparece en el KDS como PENDIENTE.
5. Cocina la pasa a PREPARANDO y luego a ENTREGADA.
6. Al pasar a ENTREGADA se notifica al mesero por push.
7. El mesero cobra, elige método de pago y la mesa vuelve a LIBRE si no quedan comandas activas.
8. La orden queda disponible para el cierre de caja.

## 12.2 Comanda dividida

1. El mesero consulta pagos: saldo, ítems disponibles y divisiones pendientes.
2. Cotiza la división de una línea entre N personas; las unidades sobrantes van a las primeras partes.
3. Registra cada abono con su método.
4. La comanda sigue abierta hasta saldar el total.
5. Al completarse se libera el grupo de mesas fusionadas.
6. Cada pago genera comprobante interno.

## 12.3 Anulación de una venta

1. Administrador o Gerente abre el historial de la caja.
2. Elige la orden y pulsa anular.
3. Escribe el motivo (obligatorio).
4. El sistema marca `anulada=True`, la excluye de todos los totales y registra `ORDEN_ANULADA` con antes y después.
5. Si había pagos parciales, se registran asientos negativos.

## 12.4 Devolución de líneas

1. Se elige la línea y la cantidad a devolver.
2. El motivo es obligatorio.
3. Se acumula `cantidad_devuelta` y se recalculan subtotal, descuento y total prorrateando.
4. Se registra `ITEM_DEVUELTO`.
5. No se devuelve inventario.

## 12.5 Compra de insumos con importación

1. Gerencia sube la factura en Excel, CSV, TXT, PDF o DOCX.
2. El parser detecta filas con reglas; si el archivo es difícil, consulta a Gemini.
3. El sistema propone filas editables con producto, cantidad, unidad, empaque, precios y categoría.
4. El usuario corrige o descarta filas.
5. Al confirmar, se valida todo el lote y se escribe en una transacción: insumos, stock, movimientos y auditoría.
6. No se genera gasto: es una entrada de inventario, no un consumo.

## 12.6 Producción por lote

1. Cocina registra la preparación del día con insumos y cantidades.
2. Se valida stock y se descuentan los insumos.
3. Se generan movimientos SALIDA y gastos SUMINISTROS.
4. Los platos con receta marcada `descuento_por_lote` no vuelven a descontar esos insumos al venderse.

## 12.7 Asistencia de un turno

1. El empleado elige una plantilla y marca entrada.
2. El backend determina el día de negocio según `HORA_INICIO_DIA`.
3. Si ya hay una asistencia abierta, la reutiliza.
4. Mientras el turno está abierto, el cliente envía latidos cada 120 segundos.
5. Al marcar salida se calculan horas y horas extras.
6. Si el turno ya fue cerrado automáticamente, el check-out responde `409` explicando la hora y la causa.

## 12.8 Cierre de nómina

1. Gerencia elige los días a pagar (1 a 7, 15, 30 o personalizado).
2. El sistema calcula el pago base prorrateado y suma horas extras.
3. Resta adelantos y muestra el neto.
4. Si ya existía una nómina pendiente, se puede recalcular.
5. Al pagar, se marca `PAGADO` y se registra la fecha.

## 12.9 Cierre de caja

1. Gerencia revisa el historial del día y las ventas del mesero.
2. Ejecuta el cierre manual o deja que el automático lo haga a medianoche.
3. Se crea `CierreCaja` y se archivan órdenes pagadas y gastos pendientes.
4. El siguiente historial aparece vacío: la caja nueva empieza en cero.
5. El cierre automático deja un evento `CIERRE_CAJA_AUTOMATICO` en la bitácora.

## 12.10 Estudio de mercado

1. Gerencia solicita un estudio o espera el automático mensual.
2. El sistema recopila métricas reales: ventas, ticket, métodos de pago, top de platos, gastos, compras, descuentos, anulaciones y temporada.
3. La generación corre en segundo plano y notifica al completarse.
4. El chat asesor responde con datos en vivo del inventario, menú, mesas, personal y ventas.
5. El informe se descarga como HTML autocontenido con gráficas SVG e incluye botón de impresión.

## 12.11 Restauración de una copia

1. El Administrador descarga o sube un archivo de copia.
2. El sistema borra de hijos a padres e inserta de padres a hijos respetando las claves foráneas.
3. Convierte fechas ISO y reajusta secuencias en PostgreSQL.
4. Registra `RESTAURAR_BACKUP` usando una instantánea del actor, porque su propia fila pudo haber sido reemplazada.

---

# 13. Operación y despliegue

## 13.1 Requisitos del entorno

- Python 3.12 o superior.
- MySQL/MariaDB en producción; PostgreSQL o SQLite como alternativas.
- HTTPS para Web Push y para el service worker.
- Variables de entorno del listado del anexo A.

## 13.2 Instalación local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python -m app.db.init_db
python -m app.main
```

| Recurso | URL |
|---------|-----|
| ERP | `http://localhost:8000/` |
| Carta Digital | `http://localhost:8000/carta/` |
| Swagger | `http://localhost:8000/docs` |
| Healthcheck | `http://localhost:8000/healthcheck` |

## 13.3 Despliegue en Render

`render.yaml` declara:

- runtime Python 3.12;
- build `PIP_ONLY_BINARY=1 pip install --prefer-binary -r requirements.txt`;
- start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`;
- healthcheck en `/healthcheck`;
- `SECRET_KEY` generado y estable;
- variables de base de datos marcadas como `sync: false` para fijarlas en el panel.

## 13.4 Checklist de producción

1. `SECRET_KEY` estable y distinto al de desarrollo. Si cambia, se invalidan los JWT y las suscripciones push.
2. `IMGBB_API_KEY` configurada. Sin ella, subir imágenes responde 500.
3. `ACCESS_TOKEN_EXPIRE_MINUTES` no debe estar fijado en 480; el valor correcto es 525600.
4. `/Templates/sw.js` responde 200 y `GET /api/v1/push/config` devuelve `habilitado: true`.
5. La ruta de la carta responde y los enlaces antiguos redirigen.
6. El login funciona con una cuenta real y el healthcheck responde.
7. Las tareas de fondo arrancaron (revisar logs de heartbeat y cierre de caja).
8. La copia automática mensual está programada.

## 13.5 Diagnóstico de problemas frecuentes

| Síntoma | Causa probable | Qué revisar |
|---------|----------------|-------------|
| Login falla solo en producción | Base distinta o hash corrupto | Logs `Login intent` con `usuario_existe` y `password_valida` |
| Imágenes no suben | Falta `IMGBB_API_KEY` | Variables del panel |
| Push no llega | Suscripción vieja o `SECRET_KEY` cambió | `GET /push/config` y volver a activar |
| Caja con totales raros | Gastos u órdenes de días anteriores sin archivar | Historial y cierre automático |
| Turno no cierra | Usuario deshabilitado o sin latidos | Heartbeat y estado del usuario |
| Carta sin fotos | URLs externas caídas o plato sin imagen | `imagen_url` en el menú |
| Nómina con montos viejos | Nómina pendiente de esquema anterior | Botón de recálculo |

## 13.6 Copias de seguridad

- Se guardan en la tabla `backups_sistema`, no en disco.
- Se conservan las últimas 24; la automática se crea cada 30 días.
- La restauración es destructiva: reemplaza el contenido actual. Se recomienda descargar una copia antes.
- En Render el filesystem es efímero: cualquier archivo local se pierde en el siguiente despliegue.

---

# 14. Pruebas y calidad

## 14.1 Suite automatizada

```bash
python -m pytest tests -q
```

Cobertura: **177 pruebas en 30 archivos**. Todas corren con SQLite en memoria y `dependency_overrides`; ninguna toca la base real de producción.

| Archivo | Qué cubre |
|---------|-----------|
| `test_seguridad.py` | JWT inválido, rol insuficiente, rutas protegidas |
| `test_password_auth.py` | Login, hashes y mensajes |
| `test_permisos.py` | Defaults, overrides, críticos y autoedición |
| `test_personal_bajas.py` | Bajas lógicas y liberación de nombres |
| `test_menu.py` | CRUD de menú y categorías |
| `test_menu_ingles.py` | Columnas EN, fallback y siembra idempotente |
| `test_ordenes.py` | Creación, estados y reglas |
| `test_ordenes_filtros.py` | Filtros y límites del listado |
| `test_pagos.py` | Cobro y liberación de mesas |
| `test_pagos_comanda.py` | Pagos parciales y divisiones |
| `test_multi_comanda.py` | Varias comandas por mesa |
| `test_fusion_mesas.py` | Fusión y desfusión |
| `test_salon.py` | Zonas, mesas y mapa |
| `test_horas_extras.py` | Cálculo de extras |
| `test_nomina_calculator.py` | Prorrateo y fórmulas |
| `test_cierre_automatico.py` | Cierre de caja automático |
| `test_auditoria_eliminar.py` | Borrado de bitácora solo Admin |
| `test_purgar_auditoria.py` | Herramienta de purga con respaldo |
| `test_backups.py` | Generación, restauración y límites |
| `test_calendario.py` | Eventos y asistencias |
| `test_carta.py` | HTML, motor, gestos y assets legacy |
| `test_entrada_sistema.py` | Raíz, caché, assets y carta |
| `test_importacion_inventario.py` | Parser, empaques y aplicación |
| `test_novedades.py` | Siembra y difusión única |
| `test_reactivar_asistencia.py` | Reapertura de turnos |
| `test_cameras.py`, `test_cameras_api.py` | Módulo de cámaras |
| `test_slug.py` | Generación de slugs |
| `test_bugfixes.py`, `test_error_handling.py` | Regresiones |

## 14.2 Verificación manual

- Pruebas visuales de la carta con Playwright y Edge headless en escritorio y móvil, en ambos idiomas y con el visor abierto.
- Revisión de la paginación de la carta después de cualquier cambio de CSS: el medidor se ofende rápido.
- Pruebas de API desde `/docs`.

## 14.3 Calidad del código

- Sin linter configurado de forma obligatoria.
- Convenciones: identificadores internos en inglés, mensajes en español, sin comentarios salvo que aporten.
- Docstrings en servicios y repositorios; el resto se documenta en este archivo.
- Deuda reconocida: `app.js` es grande y no hay pruebas de frontend automatizadas; la carta sí tiene pruebas estructurales.

---

# 15. Mantenimiento y notas del desarrollador

## 15.1 Dónde tocar según el problema

| Si el problema es... | Revisar primero |
|----------------------|-----------------|
| Ventas, totales o estados | `app/services/orden_service.py` |
| Inventario descuadrado | `inventario_service.py`, `orden_service.py` y recetas |
| Turnos que no cierran | `asistencia_service.py` y el heartbeat del cliente |
| Nómina con montos raros | `nomina_service.py` y `utils/calculations.py` |
| Caja que no cuadra | `caja_service.py` y `reportes_repository.py` |
| Carta que no pagina bien | `menu-libro.js` y su medidor |
| Notificaciones que no llegan | `push_service.py`, VAPID y el service worker |
| Importación que falla | `importacion_inventario_service.py` y el parser |
| Estudio de mercado en error | `gemini_service.py` y la clave de API |

## 15.2 Reglas que no se deben romper

- No agregar `?v=` a los assets: la caché se resuelve con ETag.
- No convertir las fechas de asistencia: son hora local naive por diseño.
- No escribir colores literales nuevos en reglas que deban adaptarse al modo oscuro.
- No borrar las funciones `_migrate_*` de `app/main.py`: son la migración real.
- No borrar `app/Templates/carta/img/`: hay pruebas que verifican rutas legacy.
- No exponer costos, recetas ni inventario en la API pública.
- No usar `db.delete` donde haya historial contable: borrado lógico.
- No cambiar la fórmula de nómina sin recalcular las pendientes.

## 15.3 Cómo agregar un módulo nuevo

1. Modelo en `app/models/`.
2. Schemas en `app/schemas/`.
3. Repositorio en `app/repositories/`.
4. Servicio con las reglas en `app/services/`.
5. Endpoints en `app/api/endpoints/` con `requerir_permiso` o `requerir_rol`.
6. Registrar el router en `app/main.py`.
7. Si agrega columnas, una función `_migrate_*` idempotente.
8. Permiso en `app/core/permisos.py` si aplica.
9. Pantalla en el SPA y entrada de navegación con `data-permiso`.
10. Pruebas en `tests/` y actualización de este documento.

## 15.4 Deuda técnica abierta

| Tema | Estado |
|------|--------|
| Migraciones Alembic | No se generan; se usan migraciones de arranque |
| Refresh token | No existe; token único de 365 días |
| Rate limiting en login | Pendiente |
| Documentación interactiva pública | Pendiente de proteger en producción |
| Contraseña forzada de `joshi_0211` | Pendiente de eliminar |
| Archivos sueltos en la raíz | `check_*.py`, `test_*.py`, `truncate_production.*`, `get_token.py` |
| Módulo de cámaras | Depende de un puente WebRTC externo |
| Pagos en línea | Arquitectura lista, proveedor deshabilitado |
| Duplicado de endpoints de nómina | Dos rutas devuelven lo mismo |
| `repositories/__init__.py` | Exporta solo una parte de los repositorios |
| Registros históricos en UTC | Anteriores al cambio a hora local |
| `Settings.ENVIRONMENT` | Declarado pero sin uso |

## 15.5 Notas honestas

- Este documento se escribe a mano. Si contradice al código, gana el código.
- El sistema creció más rápido que su documentación. La versión 2.0 de este documento intenta cerrar esa brecha, no ocultarla.
- Hay decisiones que parecen raras hasta que se conoce la historia: la hora local naive, las migraciones de arranque, el SPA sin build. Todas tienen una razón.
- Si algo funciona y no sabes por qué, antes de "limpiarlo" busca en la bitácora y en el historial de commits. Probablemente alguien ya lo rompió una vez.
- Suerte para quien lea esto dentro de seis meses. Que encuentre el archivo que busca antes de la tercera taza de café.

---

# 16. Anexos

## Anexo A. Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | vacío | URL de conexión; vacío usa SQLite |
| `SQLITE_PATH` | `./data/sazon_caribeno.db` | Archivo SQLite |
| `SECRET_KEY` | valor de ejemplo | Firma JWT y base de VAPID |
| `ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `525600` | Expiración del token |
| `HARCA27_PASSWORD` | vacío | Cuenta opcional de soporte |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Servidor local |
| `DEBUG` | `true` | Depuración |
| `ENVIRONMENT` | `development` | Entorno |
| `HEARTBEAT_INTERVAL_SECONDS` | `300` | Intervalo del watcher |
| `HEARTBEAT_TIMEOUT_SECONDS` | `900` | Umbral de abandono |
| `AUTO_CERRAR_TURNOS` | `false` | Bandera heredada |
| `HORA_INICIO_DIA` | `7` | Corte del día de negocio |
| `HOURS_PER_DAY` | `8` | Horas por día |
| `OVERTIME_MULTIPLIER` | `1.0` | Multiplicador de extras |
| `IVA_RATE` | `0.0` | IVA deshabilitado |
| `CORS_ORIGINS` | dos orígenes locales | Orígenes permitidos |
| `CARTA_RUTA_PUBLICA` | `/carta` | Ruta pública de la carta |
| `IMGBB_API_KEY` | vacío | Subida de imágenes |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | derivadas | Claves push |
| `VAPID_SUBJECT` | `mailto:admin@sazoncaribeno.com` | Contacto push |
| `PUSH_TTL` / `PUSH_TIMEOUT` | `3600` / `15` | Parámetros push |
| `CAMERA_*` | varios | Módulo de cámaras |
| `GEMINI_API_KEY` | vacío | Estudio de mercado |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Modelo principal |
| `GEMINI_MODELOS_RESPALDO` | lista | Modelos de respaldo |
| `GEMINI_TIMEOUT` / `GEMINI_MAX_INTENTOS` | `120` / `4` | Reintentos |
| `GEMINI_MAX_CARACTERES_DOCUMENTO` | `120000` | Texto máximo por documento |
| `ESTUDIO_MERCADO_DIA` / `_HORA` / `_INTERVALO_SEGUNDOS` | `1` / `6` / `3600` | Estudio automático |
| `PAYMENT_PROVIDER` | `disabled` | Gateway de pagos |
| `PAYMENT_CURRENCY` | `NIO` | Moneda |
| `PAYMENT_SUCCESS_URL` / `PAYMENT_CANCEL_URL` | vacío | Retorno del checkout |

## Anexo B. Usuarios sembrados

| Usuario | Contraseña | Rol | Notas |
|---------|-----------|-----|-------|
| `joshi_0211` | `@0420311001000V` | Administrador | Auto-sembrado; contraseña forzada en arranque |
| `admin` | `password123` | Administrador | `init_db.py` |
| `gerente` | `password123` | Gerente | `init_db.py` |
| `mesero` | `password123` | Vendedor | `init_db.py` |

Cambiar estas credenciales antes de publicar. La advertencia está repetida a propósito.

## Anexo C. Acciones de auditoría registradas

| Acción | Origen |
|--------|--------|
| `PRECIO_ASIGNADO`, `PRECIO_ACTUALIZADO` | Menú |
| `DESCUENTO_*` | Descuentos |
| `ORDEN_ANULADA` | Anulación de pedido |
| `ITEM_DEVUELTO` | Devolución de línea |
| `COMANDA_CANCELADA` | Cancelación con pagos |
| `GASTO_EDITADO`, `GASTO_ELIMINADO` | Gastos |
| `TURNO_CERRADO_AUTOMATICAMENTE` | Asistencia |
| `ASISTENCIA_REACTIVADA` | Reactivación |
| `CIERRE_CAJA_AUTOMATICO` | Caja |
| `PERMISOS_ACTUALIZADOS` | Permisos |
| `IMPORTACION_INVENTARIO_APLICADA` | Importación |
| `RESTAURAR_BACKUP` | Copias |
| `AUDITORIA_ELIMINADA` | Borrado de bitácora |
| `AUDITORIA_PURGADA` | Purga masiva |

## Anexo D. Estructura de carpetas completa

```
SazonCaribe-o/
├── AGENTS.md
├── README.md
├── PRODUCT.md
├── DOCUMENTACION_FRONTEND.md
├── render.yaml
├── requirements.txt
├── tailwind.config.js
├── tailwind.input.css
├── app/
│   ├── main.py
│   ├── core/
│   ├── api/
│   │   ├── deps.py
│   │   ├── auditoria.py
│   │   └── endpoints/
│   ├── schemas/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── utils/
│   ├── db/
│   └── Templates/
│       ├── index.html
│       ├── css/
│       ├── js/
│       ├── Imagenes/
│       ├── sw.js
│       └── carta/
├── docs/
│   ├── CALENDARIO.md
│   ├── CAMARAS.md
│   └── DOCUMENTACION_TECNICA.md
├── tests/
└── tools/
    └── purgar_auditoria.py
```

## Anexo E. Glosario

| Término | Definición |
|---------|-----------|
| Comanda | Orden de consumo de una mesa o para llevar |
| KDS | Kitchen Display System |
| Día de negocio | Ventana de 24 horas con corte configurable |
| Heartbeat | Señal periódica de turno activo |
| Override | Permiso concedido o retirado sobre el rol |
| Borrado lógico | Marcar inactivo o eliminado sin borrar la fila |
| Cierre de caja | Archivado de órdenes y gastos de la sesión |
| DTO | Schema Pydantic de entrada o salida |
| VAPID | Identificación del servidor para Web Push |
| Bucket | Clasificación de gastos en reportes |

---

**Fin del documento.**

Versión 2.0 — noviembre 2026.

Autor original del sistema: Joshua Davila.

Si llegaste hasta aquí, ya sabes más del sistema que la mayoría de quienes lo usan a diario. Eso es responsabilidad: úsala bien.
