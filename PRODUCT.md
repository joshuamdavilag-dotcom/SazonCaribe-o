# PRODUCT.md

# Módulo: Carta Digital

## Estado

En Diseño

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

# Flujo del Cliente

1. Escanear el código QR.
2. Acceder a la URL pública `/menu`.
3. Visualizar la portada del restaurante.
4. Seleccionar "Ver Menú".
5. Explorar las categorías disponibles.
6. Consultar el detalle de cada platillo (fotografía, descripción, precio y disponibilidad).

# Restricciones de la Versión 1

- El acceso será completamente público.
- No requerirá autenticación.
- No permitirá realizar pedidos.
- No permitirá pagos.
- No permitirá reservas.
- Toda la información será administrada desde el ERP.
- El menú público compartirá la misma base de datos que el sistema administrativo.