# PRODUCT.md

# Módulo: Carta Digital

## Estado

Implementado (Versión 1.0)

---

# Funcionalidades completadas

- ✅ Carta Digital Pública
- ✅ Navegación por categorías
- ✅ API Pública desacoplada
- ✅ Visualización únicamente de productos disponibles
- ✅ Detalle de platillos
- ✅ Gestión de imágenes desde el ERP
- ✅ Tiempo de preparación
- ✅ Placeholder automático
- ✅ Acceso mediante QR a la URL pública `/carta/`

---

# Objetivo

Permitir que cualquier cliente consulte el menú del restaurante mediante un código QR utilizando información administrada directamente desde el ERP.

---

# Problema que resuelve

Actualmente el restaurante no posee un menú físico adecuado.

Los meseros deben dictar los platos disponibles, lo que provoca:

- pérdida de tiempo
- mala experiencia para el cliente
- dificultad para actualizar precios
- dificultad para mostrar fotografías de los platillos

La Carta Digital resolverá este problema permitiendo acceder al menú desde un código QR.

---

# Usuarios

## Cliente

Escanea el QR y consulta el menú.

## Administrador

Gestiona toda la información desde el ERP.

---

# Objetivos del Cliente

- Encontrar rápidamente un plato.
- Conocer el precio.
- Ver fotografías.
- Leer la descripción.
- Saber si el plato está disponible.

---

# Objetivos del Administrador

- Crear categorías.
- Crear platos.
- Editar precios.
- Editar descripciones.
- Subir fotografías.
- Cambiar disponibilidad.
- Organizar el orden del menú.
- Gestionar tiempo de preparación de platillos.
- Gestionar unidades de medida y conversiones.
- Gestionar categorías de insumos.
- Registrar gastos operativos.
- Generar reportes financieros por periodo.
- Gestionar adelantos de salario.

---

# Fuera del alcance (Versión 1)

- Pedidos en línea
- Carrito de compras
- Pagos
- Reservaciones
- Opiniones
- Registro de usuarios
- Inicio de sesión

---

# Integración

Toda la información proviene del módulo Gestión de Menú del ERP.

No existirá una segunda base de datos.

No existirá un segundo panel administrativo.

# Distribución

- La carta se sirve en la URL pública `/carta/` (FastAPI sirve `app/Templates/carta/` como archivos estáticos).
- El código QR lo genera el restaurante (cualquier generador de QR) apuntando a `/carta/`; el QR no se genera dentro del sistema.
- Las imágenes de los platos se suben desde el ERP (Gestión de Menú) y se sirven por `/carta/img/platos/`.
- La carta es de solo lectura: nunca usa `/api/v1` ni expone costos, recetas o inventario.

# Flujo del Cliente

1. Escanear el código QR (apunta a la URL pública `/carta/`).
2. Acceder a la carta digital.
3. Visualizar la portada del restaurante (hero de escritorio o bienvenida móvil).
4. Seleccionar "Ver Menú" o una categoría del bento.
5. Explorar las categorías disponibles (chips, navegación o bento).
6. Consultar el detalle de cada platillo (fotografía, descripción, precio, disponibilidad y tiempo de preparación).

# Restricciones de la Versión 1

- El acceso será completamente público.
- No requerirá autenticación.
- No permitirá realizar pedidos.
- No permitirá pagos.
- No permitirá reservas.
- Toda la información será administrada desde el ERP.
- El menú público compartirá la misma base de datos que el sistema administrativo.

---

# Estado actual del producto

- ✅ ERP administrativo (POS)
- ✅ Gestión de inventario
- ✅ Gestión de menú
- ✅ Gestión de personal
- ✅ Gestión de gastos
- ✅ Cierre de caja
- ✅ Carta Digital pública
- ✅ API pública
- ✅ Gestión de imágenes
- ✅ Preparación para fotografías reales
- ✅ Asistencia y Gestión de Turnos (check-in/out, heartbeat, turnos CRUD)
- ✅ Nómina y Adelantos de Salario
- ✅ Órdenes (state machine, descuentos por ítem/global, para llevar, venta retroactiva)
- ✅ KDS — Panel de Cocina (estados, tiempos, cobro rápido)
- ✅ Producción por lote (Preparación de Cocina)
- ✅ Sistema de Unidades de Medida y Conversiones
- ✅ Categorías de Insumo dinámicas
- ✅ Reportes financieros por periodo (diario, semanal, quincenal, mensual, anual)
- ✅ Unidad de empaque por insumo (factor de conversión por producto)

---

# Próximas funcionalidades (Backlog)

- Fotografías reales
- SEO
- Caché de la API pública
- Compartir en redes
- Promociones (catálogo en Carta Digital — diferente al sistema de descuentos por orden ya implementado)
- Destacados (platos destacados en la Carta Digital)
- Menú bilingüe
- Analytics QR
- Panel de estadísticas
- Horarios automáticos de la carta (mostrar/ocultar menú por horario del día — diferente a la Gestión de Turnos de personal)
- Banner de eventos