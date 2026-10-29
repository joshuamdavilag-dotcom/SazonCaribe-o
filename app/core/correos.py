"""Catálogo de correos del sistema y secciones activables.

Cada tipo de correo declara qué bloques de información puede compartir. La
gerencia decide, tipo por tipo, si el envío está activo y qué secciones se
incluyen. Los datos marcados como ``sensible`` (nómina y sueldos) nunca se
envían si no se activan de forma explícita.
"""

from typing import Any

TIPOS_CORREO: list[dict[str, Any]] = [
    {
        "clave": "manual",
        "nombre": "Envío manual",
        "descripcion": "Se prepara y se envía cuando gerencia lo decide.",
        "programado": False,
        "evento": False,
    },
    {
        "clave": "cierre_caja",
        "nombre": "Cierre de caja",
        "descripcion": "Resumen del día al cerrar la caja (manual o automático).",
        "programado": False,
        "evento": True,
    },
    {
        "clave": "resumen_semanal",
        "nombre": "Resumen semanal",
        "descripcion": "Se envía los lunes con los últimos 7 días.",
        "programado": True,
        "evento": False,
    },
    {
        "clave": "resumen_mensual",
        "nombre": "Resumen mensual",
        "descripcion": "Se envía el día 1 con el mes anterior completo.",
        "programado": True,
        "evento": False,
    },
    {
        "clave": "stock_bajo",
        "nombre": "Alerta de stock bajo",
        "descripcion": "Insumos por debajo del mínimo (una vez al día).",
        "programado": True,
        "evento": False,
    },
    {
        "clave": "estudio_mercado",
        "nombre": "Estudio de mercado listo",
        "descripcion": "Aviso cuando la IA termina un estudio de mercado.",
        "programado": False,
        "evento": True,
    },
    {
        "clave": "auditoria",
        "nombre": "Avisos de auditoría",
        "descripcion": "Anulaciones, devoluciones y cambios sensibles del día.",
        "programado": True,
        "evento": False,
    },
]

SECCIONES: list[dict[str, Any]] = [
    {
        "clave": "ventas",
        "nombre": "Resumen de ventas",
        "descripcion": "Órdenes cobradas, ingresos, ticket promedio y descuentos.",
        "sensible": False,
    },
    {
        "clave": "metodos_pago",
        "nombre": "Métodos de pago",
        "descripcion": "Cuánto entró por efectivo, tarjeta, transferencia y en línea.",
        "sensible": False,
    },
    {
        "clave": "top_platillos",
        "nombre": "Platillos más vendidos",
        "descripcion": "Ranking por unidades e ingresos.",
        "sensible": False,
    },
    {
        "clave": "gastos",
        "nombre": "Gastos por categoría",
        "descripcion": "Compras y gastos operativos del periodo.",
        "sensible": False,
    },
    {
        "clave": "inventario",
        "nombre": "Insumos bajo el mínimo",
        "descripcion": "Existencias actuales y costo de reposición estimado.",
        "sensible": False,
    },
    {
        "clave": "anulaciones",
        "nombre": "Anulaciones y devoluciones",
        "descripcion": "Órdenes anuladas y líneas devueltas del periodo.",
        "sensible": False,
    },
    {
        "clave": "nomina",
        "nombre": "Nómina pagada (sensible)",
        "descripcion": "Pagos de personal del periodo. Se oculta por defecto.",
        "sensible": True,
    },
    {
        "clave": "estudio",
        "nombre": "Resumen del estudio de mercado",
        "descripcion": "Hallazgos, fortalezas y recomendaciones de la IA.",
        "sensible": False,
    },
    {
        "clave": "auditoria",
        "nombre": "Movimientos auditados",
        "descripcion": "Últimos cambios registrados en la bitácora.",
        "sensible": False,
    },
]

SECCIONES_POR_CLAVE: dict[str, dict[str, Any]] = {
    seccion["clave"]: seccion for seccion in SECCIONES
}

TIPOS_POR_CLAVE: dict[str, dict[str, Any]] = {
    tipo["clave"]: tipo for tipo in TIPOS_CORREO
}

SECCIONES_POR_TIPO: dict[str, list[str]] = {
    "manual": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
        "nomina",
        "estudio",
        "auditoria",
    ],
    "cierre_caja": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
        "nomina",
    ],
    "resumen_semanal": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
        "nomina",
    ],
    "resumen_mensual": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
        "nomina",
    ],
    "stock_bajo": ["inventario", "gastos"],
    "estudio_mercado": ["estudio", "ventas", "metodos_pago", "top_platillos"],
    "auditoria": ["auditoria", "anulaciones", "ventas"],
}

DEFAULTS_POR_TIPO: dict[str, list[str]] = {
    "manual": ["ventas", "metodos_pago", "top_platillos", "gastos", "inventario"],
    "cierre_caja": ["ventas", "metodos_pago", "top_platillos", "gastos", "anulaciones"],
    "resumen_semanal": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
    ],
    "resumen_mensual": [
        "ventas",
        "metodos_pago",
        "top_platillos",
        "gastos",
        "inventario",
        "anulaciones",
    ],
    "stock_bajo": ["inventario"],
    "estudio_mercado": ["estudio"],
    "auditoria": ["auditoria"],
}

HORAS_POR_DEFECTO: dict[str, int] = {
    "resumen_semanal": 8,
    "resumen_mensual": 8,
    "stock_bajo": 9,
    "auditoria": 18,
}

TIPOS_PROGRAMADOS: frozenset[str] = frozenset(
    tipo["clave"] for tipo in TIPOS_CORREO if tipo["programado"]
)

TIPOS_EVENTO: frozenset[str] = frozenset(
    tipo["clave"] for tipo in TIPOS_CORREO if tipo["evento"]
)

ASUNTO_POR_TIPO: dict[str, str] = {
    "manual": "Informe de Sazón Caribeño",
    "cierre_caja": "Cierre de caja",
    "resumen_semanal": "Resumen semanal",
    "resumen_mensual": "Resumen mensual",
    "stock_bajo": "Alerta de stock bajo",
    "estudio_mercado": "Estudio de mercado listo",
    "auditoria": "Avisos de auditoría",
}


def secciones_disponibles(tipo: str) -> list[dict[str, Any]]:
    """Secciones que puede activar un tipo de correo."""
    claves = SECCIONES_POR_TIPO.get(tipo, [])
    return [SECCIONES_POR_CLAVE[clave] for clave in claves if clave in SECCIONES_POR_CLAVE]


def secciones_por_defecto(tipo: str) -> list[str]:
    """Secciones que se activan al crear la configuración de un tipo."""
    disponibles = {seccion["clave"] for seccion in secciones_disponibles(tipo)}
    return [clave for clave in DEFAULTS_POR_TIPO.get(tipo, []) if clave in disponibles]


def normalizar_secciones(tipo: str, secciones: list[str] | None) -> tuple[list[str], list[str]]:
    """Devuelve (válidas, inválidas) para el tipo indicado."""
    disponibles = {seccion["clave"] for seccion in secciones_disponibles(tipo)}
    solicitadas = list(dict.fromkeys(secciones or []))
    validas = [clave for clave in solicitadas if clave in disponibles]
    invalidas = [clave for clave in solicitadas if clave not in disponibles]
    return validas, invalidas


def es_sensible(clave: str) -> bool:
    seccion = SECCIONES_POR_CLAVE.get(clave)
    return bool(seccion and seccion.get("sensible"))
