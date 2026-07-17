"""
TRUNCADO TOTAL PARA PRODUCCIÓN — Sazón Caribeño POS
Fecha: 2026-07-16
Vaciado absoluto de todas las tablas. Re-crea usuario admin con employee mínimo.
"""

import pymysql
from datetime import date

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "sazon_caribeno",
    "charset": "utf8mb4",
}

TABLES_TO_WIPE = [
    "detalles_orden",
    "ordenes",
    "cierres_caja",
    "gastos",
    "nominas",
    "movimientos_inventario",
    "recetas",
    "asistencias",
    "turnos",
    "mesas",
    "zonas",
    "menu_items",
    "categorias_menu",
    "insumos",
    "ingredientes",
    "categorias_insumo",
    "unidades_medida",
    "proveedores",
    "usuarios",
    "empleados",
    "puestos",
]


def run_wipe():
    conn = pymysql.connect(**DB_CONFIG, autocommit=False)
    cur = conn.cursor()

    try:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        print("[OK] FOREIGN_KEY_CHECKS desactivado")

        total_deleted = 0
        for table in TABLES_TO_WIPE:
            cur.execute(f"DELETE FROM `{table}`")
            deleted = cur.rowcount
            total_deleted += deleted
            print(f"  {table:30s} -> {deleted:>5} fila(s)")

        conn.commit()
        print(f"\n[OK] COMMIT — Total: {total_deleted} fila(s) eliminadas en {len(TABLES_TO_WIPE)} tablas")

        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("[OK] FOREIGN_KEY_CHECKS reactivado")

        print("\n--- Re-creando usuario admin ---")

        cur.execute(
            "INSERT INTO puestos (nombre, salario_base) VALUES (%s, %s)",
            ("Administrador", 15000.00),
        )
        puesto_id = cur.lastrowid
        print(f"  Puesto creado: ID={puesto_id}")

        cur.execute(
            "INSERT INTO empleados (nombre, apellido, cedula_identidad, puesto_id, fecha_ingreso, salario_base, activo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            ("Admin", "Sistema", "000-000000-0000X", puesto_id, date.today(), 15000.00, 1),
        )
        empleado_id = cur.lastrowid
        print(f"  Empleado creado: ID={empleado_id}")

        cur.execute(
            "INSERT INTO usuarios (username, password_hash, rol, empleado_id, activo) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                "admin",
                "$2b$12$CLrtutKLbvXZFjZoy/vgBe.HlNPtQFpSsSoC8CKNiMdal7/Ti8gkG",
                "Administrador",
                empleado_id,
                1,
            ),
        )
        print(f"  Usuario admin creado: ID={cur.lastrowid} (username='admin', password='password123')")

        conn.commit()
        print("[OK] Admin re-creado correctamente")

        print("\n" + "=" * 50)
        print("VERIFICACION FINAL")
        print("=" * 50)

        print("\nUsuarios:")
        cur.execute("SELECT id, username, rol, activo FROM usuarios")
        for row in cur.fetchall():
            print(f"  ID={row[0]} | {row[1]} | Rol={row[2]} | Activo={row[3]}")

        print("\nConteo de filas por tabla:")
        for table in TABLES_TO_WIPE:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            cnt = cur.fetchone()[0]
            status = "VACIA" if cnt == 0 else f"{cnt} FILAS"
            print(f"  {table:30s} {cnt:>5}  {status}")

        print("\n" + "=" * 50)
        print("TRUNCADO COMPLETADO — Base lista para produccion")
        print("Credenciales: admin / password123")
        print("=" * 50)

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        print("Rollback ejecutado")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_wipe()
