"""Catálogo de permisos funcionales del sistema.

El control de acceso base sigue siendo por rol (Administrador/Gerente/Vendedor).
Sobre esa base, la administración puede conceder o quitar funciones puntuales a
un usuario concreto. Los overrides se guardan en ``Usuario.permisos`` (JSON) y
los valores por defecto de cada rol reproducen exactamente el RBAC histórico,
de modo que publicar esta función no cambia el acceso de nadie.

Reglas:
- ``Administrador`` conserva siempre todos los permisos (evita bloqueos).
- ``critico`` marca los permisos que solo un Administrador puede conceder o
  quitar (copias, auditoría, gestión de usuarios y de permisos).
"""

from typing import Any, Iterable

from app.schemas.personal import RolEnum

ADMINISTRADOR = RolEnum.ADMINISTRADOR.value
GERENTE = RolEnum.GERENTE.value
VENDEDOR = RolEnum.VENDEDOR.value

GRUPOS = [
    "Menú y Carta",
    "Inventario",
    "Caja y dinero",
    "Personal y nómina",
    "Administración",
]

PERMISOS: list[dict[str, Any]] = [
    {
        "clave": "menu_gestionar",
        "nombre": "Gestionar menú",
        "descripcion": "Crear, editar, desactivar y reactivar platillos y categorías.",
        "grupo": "Menú y Carta",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "menu_imagenes",
        "nombre": "Subir imágenes de platillos",
        "descripcion": "Cambiar la foto y el tiempo de preparación que ve el cliente.",
        "grupo": "Menú y Carta",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "produccion_cocina",
        "nombre": "Registrar producción del día",
        "descripcion": "Descontar insumos por lote desde Producción del Día.",
        "grupo": "Menú y Carta",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "inventario_gestionar",
        "nombre": "Gestionar inventario",
        "descripcion": "Insumos, proveedores, categorías y unidades de medida.",
        "grupo": "Inventario",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "inventario_movimientos",
        "nombre": "Mover stock",
        "descripcion": "Registrar entradas y salidas y ajustar la cantidad de un insumo.",
        "grupo": "Inventario",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "caja_cerrar",
        "nombre": "Cerrar caja",
        "descripcion": "Cerrar la caja del día y activar o desactivar el cierre automático.",
        "grupo": "Caja y dinero",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "gastos_gestionar",
        "nombre": "Gestionar gastos",
        "descripcion": "Registrar, editar y eliminar gastos operativos.",
        "grupo": "Caja y dinero",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "descuentos_gestionar",
        "nombre": "Gestionar descuentos",
        "descripcion": "Crear y editar el catálogo de descuentos predeterminados.",
        "grupo": "Caja y dinero",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "ordenes_anular",
        "nombre": "Anular pedidos y devolver ítems",
        "descripcion": "Anular una orden o devolver líneas, con motivo y auditoría.",
        "grupo": "Caja y dinero",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "personal_gestionar",
        "nombre": "Gestionar personal y usuarios",
        "descripcion": "Crear, editar y dar de baja empleados, usuarios y contraseñas.",
        "grupo": "Personal y nómina",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": True,
    },
    {
        "clave": "turnos_gestionar",
        "nombre": "Gestionar turnos",
        "descripcion": "Plantillas de turno y habilitación de turnos de vendedores.",
        "grupo": "Personal y nómina",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "nomina_gestionar",
        "nombre": "Gestionar nómina",
        "descripcion": "Calcular, recalcular y pagar nóminas, y registrar adelantos.",
        "grupo": "Personal y nómina",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "asistencia_admin",
        "nombre": "Corregir asistencias",
        "descripcion": "Editar horarios, horas extras y anular registros de asistencia.",
        "grupo": "Personal y nómina",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "permisos_gestionar",
        "nombre": "Gestionar permisos",
        "descripcion": "Abrir esta pantalla y conceder o quitar funciones a otros usuarios.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": True,
    },
    {
        "clave": "reportes_ver",
        "nombre": "Ver reportes financieros",
        "descripcion": "Cierre por periodo, ingresos, gastos, nómina y utilidad neta.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
    {
        "clave": "auditoria_ver",
        "nombre": "Ver auditoría",
        "descripcion": "Bitácora de cambios y movimientos sensibles del sistema.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": True,
    },
    {
        "clave": "backups_gestionar",
        "nombre": "Copias de seguridad",
        "descripcion": "Crear, descargar, restaurar y eliminar copias de la base de datos.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR],
        "critico": True,
    },
    {
        "clave": "correos_gestionar",
        "nombre": "Gestionar correos",
        "descripcion": "Destinatarios, tipos de correo y envío de informes.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": True,
    },
    {
        "clave": "estudio_mercado",
        "nombre": "Estudio de mercado",
        "descripcion": "Generar informes con IA, adjuntar documentos y usar el asesor.",
        "grupo": "Administración",
        "roles": [ADMINISTRADOR, GERENTE],
        "critico": False,
    },
]

PERMISOS_POR_CLAVE: dict[str, dict[str, Any]] = {
    permiso["clave"]: permiso for permiso in PERMISOS
}

CLAVES_PERMISOS: tuple[str, ...] = tuple(PERMISOS_POR_CLAVE)

PERMISOS_CRITICOS: frozenset[str] = frozenset(
    clave for clave, permiso in PERMISOS_POR_CLAVE.items() if permiso["critico"]
)


def catalogo() -> list[dict[str, Any]]:
    """Catálogo de permisos en el orden en que se muestra en la pantalla."""
    return [dict(permiso) for permiso in PERMISOS]


def es_permiso_valido(clave: str) -> bool:
    return clave in PERMISOS_POR_CLAVE


def es_critico(clave: str) -> bool:
    return clave in PERMISOS_CRITICOS


def permisos_por_defecto(rol: str | None) -> list[str]:
    """Permisos que otorga el rol cuando el usuario no tiene overrides."""
    if not rol:
        return []
    if rol == ADMINISTRADOR:
        return list(CLAVES_PERMISOS)
    return [
        permiso["clave"]
        for permiso in PERMISOS
        if rol in permiso["roles"]
    ]


def _overrides(usuario) -> dict[str, bool]:
    datos = getattr(usuario, "permisos", None)
    if not isinstance(datos, dict):
        return {}
    return {
        clave: bool(valor)
        for clave, valor in datos.items()
        if clave in PERMISOS_POR_CLAVE
    }


def permisos_efectivos(usuario) -> list[str]:
    """Permisos vigentes del usuario (rol + overrides).

    El Administrador siempre conserva el catálogo completo para que nunca pueda
    quedar fuera de la administración del sistema.
    """
    if getattr(usuario, "rol", None) == ADMINISTRADOR:
        return list(CLAVES_PERMISOS)
    efectivos = set(permisos_por_defecto(getattr(usuario, "rol", None)))
    for clave, concedido in _overrides(usuario).items():
        if concedido:
            efectivos.add(clave)
        else:
            efectivos.discard(clave)
    return [clave for clave in CLAVES_PERMISOS if clave in efectivos]


def tiene_permiso(usuario, clave: str) -> bool:
    """True si el usuario puede ejecutar la función indicada."""
    if getattr(usuario, "rol", None) == ADMINISTRADOR:
        return True
    if not es_permiso_valido(clave):
        return False
    return clave in permisos_efectivos(usuario)


def mapa_efectivo(usuario) -> dict[str, bool]:
    """Permisos del usuario como ``{clave: bool}`` (para la API y la UI)."""
    efectivos = set(permisos_efectivos(usuario))
    return {clave: clave in efectivos for clave in CLAVES_PERMISOS}


def normalizar_solicitud(valores: Iterable[str]) -> list[str]:
    """Descarta claves desconocidas de una lista de permisos."""
    return [clave for clave in valores if clave in PERMISOS_POR_CLAVE]
