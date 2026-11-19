"""Extrae un volcado de una base PostgreSQL y lo compara con otro ya existente.

Sirve para recuperar la ventana de datos perdida tras restaurar una copia
equivocada: se apunta a la instancia recuperada por PITR (Render), se genera un
payload con el mismo formato que produce `BackupService.generar_payload()` y se
compara contra el estado actual para saber exactamente qué filas faltan.

Solo lectura: nunca escribe en la base de origen ni en la de referencia.

Uso:
    python -m tools.recuperar_ventana volcar --url "postgresql://usuario:clave@host/base" --salida docs/archivo/recuperacion/pitr.json
    python -m tools.recuperar_ventana comparar --origen docs/archivo/recuperacion/pitr.json --referencia docs/archivo/recuperacion/PROD_estado_actual.json
"""

import argparse
import json
import sys
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra todas las tablas en Base.metadata)
from app.core.database import Base

TABLA_EXCLUIDA = "backups_sistema"


def _serializar(valor: Any) -> Any:
    """Convierte valores de la base en algo que JSON pueda guardar."""
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, Enum):
        return valor.value
    return valor


def volcar(url: str, salida: Path) -> Dict[str, Any]:
    """Recorre todas las tablas del sistema y guarda un payload restaurable."""
    motor = create_engine(url, pool_pre_ping=True)
    tablas: Dict[str, List[Dict[str, Any]]] = {}
    with Session(motor) as db:
        for tabla in Base.metadata.sorted_tables:
            if tabla.name == TABLA_EXCLUIDA:
                continue
            filas = [
                {col: _serializar(fila[col]) for col in fila.keys()}
                for fila in db.execute(select(tabla)).mappings()
            ]
            tablas[tabla.name] = filas

    payload = {
        "metadata": {
            "sistema": "Sazón Caribeño POS",
            "version": "2.0",
            "fecha_creacion": datetime.now().isoformat(),
            "origen": "recuperacion_pitr",
            "total_registros": sum(len(f) for f in tablas.values()),
            "tablas": list(tablas.keys()),
        },
        "datos": tablas,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


def comparar(origen: Path, referencia: Path) -> int:
    """Lista las filas que están en el volcado y no en la referencia."""
    datos_origen = json.loads(origen.read_text(encoding="utf-8"))["datos"]
    datos_ref = json.loads(referencia.read_text(encoding="utf-8"))["datos"]

    total_faltantes = 0
    for nombre in sorted(datos_origen):
        filas = datos_origen.get(nombre) or []
        ref = {_clave(fila): _firma(fila) for fila in (datos_ref.get(nombre) or [])}
        faltan = [f for f in filas if _clave(f) not in ref]
        cambiadas = [
            f for f in filas
            if _clave(f) in ref and ref[_clave(f)] != _firma(f)
        ]
        if not faltan and not cambiadas:
            continue
        total_faltantes += len(faltan)
        print(f"{nombre}: {len(faltan)} nuevas, {len(cambiadas)} modificadas")
        for fila in faltan[:5]:
            print(f"   + id={fila.get('id')} {_resumen(nombre, fila)}")

    if not total_faltantes:
        print("Sin diferencias: el volcado y la referencia tienen las mismas filas.")
    else:
        print(f"Total de filas ausentes en la referencia: {total_faltantes}")
    return total_faltantes


def _clave(fila: Dict[str, Any]) -> Any:
    """Identifica una fila por su id o, si no lo tiene, por su contenido."""
    if "id" in fila:
        return fila["id"]
    return _firma(fila)


def _firma(fila: Dict[str, Any]) -> str:
    """Serializa la fila de forma estable (evita falsos cambios por NaN)."""
    return json.dumps(fila, sort_keys=True, ensure_ascii=False)


def _resumen(tabla: str, fila: Dict[str, Any]) -> str:
    """Devuelve una línea legible con los campos más útiles de la fila."""
    campos = {
        "ordenes": ("fecha_creacion", "estado", "total"),
        "detalles_orden": ("orden_id", "producto_id", "cantidad"),
        "gastos": ("fecha", "categoria", "monto", "concepto"),
        "asistencias": ("empleado_id", "fecha_hora_entrada_real"),
        "movimientos_inventario": ("insumo_id", "tipo", "cantidad"),
        "cierres_caja": ("fecha_cierre", "total_ventas"),
        "pagos_comanda": ("orden_id", "monto", "creado_en"),
    }.get(tabla, ())
    partes = [f"{c}={fila.get(c)}" for c in campos if fila.get(c) is not None]
    return " ".join(partes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recuperación de una ventana de datos")
    sub = parser.add_subparsers(dest="accion", required=True)

    p_volcar = sub.add_parser("volcar", help="Genera un payload desde una base")
    p_volcar.add_argument("--url", required=True, help="Cadena de conexión SQLAlchemy")
    p_volcar.add_argument("--salida", required=True, help="Archivo JSON de destino")

    p_comparar = sub.add_parser("comparar", help="Compara dos payloads")
    p_comparar.add_argument("--origen", required=True)
    p_comparar.add_argument("--referencia", required=True)

    args = parser.parse_args()

    if args.accion == "volcar":
        payload = volcar(args.url, Path(args.salida))
        meta = payload["metadata"]
        print(f"Volcado escrito en {args.salida}: {meta['total_registros']} registros, {len(meta['tablas'])} tablas")
        return 0

    return 1 if comparar(Path(args.origen), Path(args.referencia)) else 0


if __name__ == "__main__":
    sys.exit(main())
