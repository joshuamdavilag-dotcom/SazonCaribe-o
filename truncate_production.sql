-- ============================================================
-- TRUNCADO TOTAL PARA PRODUCCIÓN — Sazón Caribeño POS
-- Fecha: 2026-07-16
-- Descripción: Vaciado absoluto de todas las tablas operativas
--              y maestras. Conserva ÚNICAMENTE el usuario
--              'admin' (Administrador) para acceso al panel.
-- ============================================================

-- 1. Desactivar verificación de llaves foráneas
SET FOREIGN_KEY_CHECKS = 0;

-- 2. Limpiar empleado_id del admin para evitar FK dangling
UPDATE usuarios SET empleado_id = NULL WHERE username = 'admin';

-- 3. Eliminar todos los usuarios excepto admin
DELETE FROM usuarios WHERE username != 'admin';

-- 4. TRUNCATE de todas las tablas (orden respetando dependencias)
--    Operaciones y finanzas primero (tablas dependientes)
TRUNCATE TABLE detalles_orden;
TRUNCATE TABLE ordenes;
TRUNCATE TABLE cierres_caja;
TRUNCATE TABLE gastos;
TRUNCATE TABLE nominas;
TRUNCATE TABLE movimientos_inventario;
TRUNCATE TABLE recetas;

--    Asistencia
TRUNCATE TABLE asistencias;
TRUNCATE TABLE turnos;

--    Estructura física
TRUNCATE TABLE mesas;
TRUNCATE TABLE zonas;

--    Menú y carta
TRUNCATE TABLE menu_items;
TRUNCATE TABLE categorias_menu;

--    Inventario y catálogos
TRUNCATE TABLE insumos;
TRUNCATE TABLE ingredientes;
TRUNCATE TABLE categorias_insumo;
TRUNCATE TABLE unidades_medida;
TRUNCATE TABLE proveedores;

--    Personal (empleados y puestos)
TRUNCATE TABLE empleados;
TRUNCATE TABLE puestos;

-- 5. Reactivar verificación de llaves foráneas
SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- VERIFICACIÓN FINAL
-- ============================================================
SELECT '=== ESTADO FINAL ===' AS info;

SELECT 'usuarios restantes:' AS tabla;
SELECT id, username, rol, activo FROM usuarios;

SELECT 'Conteo de tablas:' AS info;
SELECT 'asistencias' AS tabla, COUNT(*) AS filas FROM asistencias
UNION ALL SELECT 'categorias_insumo', COUNT(*) FROM categorias_insumo
UNION ALL SELECT 'categorias_menu', COUNT(*) FROM categorias_menu
UNION ALL SELECT 'cierres_caja', COUNT(*) FROM cierres_caja
UNION ALL SELECT 'detalles_orden', COUNT(*) FROM detalles_orden
UNION ALL SELECT 'empleados', COUNT(*) FROM empleados
UNION ALL SELECT 'gastos', COUNT(*) FROM gastos
UNION ALL SELECT 'ingredientes', COUNT(*) FROM ingredientes
UNION ALL SELECT 'insumos', COUNT(*) FROM insumos
UNION ALL SELECT 'menu_items', COUNT(*) FROM menu_items
UNION ALL SELECT 'mesas', COUNT(*) FROM mesas
UNION ALL SELECT 'movimientos_inventario', COUNT(*) FROM movimientos_inventario
UNION ALL SELECT 'nominas', COUNT(*) FROM nominas
UNION ALL SELECT 'ordenes', COUNT(*) FROM ordenes
UNION ALL SELECT 'proveedores', COUNT(*) FROM proveedores
UNION ALL SELECT 'puestos', COUNT(*) FROM puestos
UNION ALL SELECT 'recetas', COUNT(*) FROM recetas
UNION ALL SELECT 'turnos', COUNT(*) FROM turnos
UNION ALL SELECT 'unidades_medida', COUNT(*) FROM unidades_medida
UNION ALL SELECT 'usuarios', COUNT(*) FROM usuarios
UNION ALL SELECT 'zonas', COUNT(*) FROM zonas;
