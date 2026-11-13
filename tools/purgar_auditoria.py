"""Mueve a un archivo aparte los registros de auditoría de un usuario y los elimina.

Herramienta de mantenimiento para sacar de la base de datos los registros de la
bitácora que gerencia pidió archivar (por ejemplo, los de un usuario puntual al
editar horas de entrada/salida). Reglas de seguridad:

1. Por defecto SOLO muestra qué haría (simulación): no escribe ni borra nada.
2. Con ``--aplicar`` primero escribe un archivo JSON + CSV, lo verifica contra la
   base y solo entonces borra, todo dentro de una transacción.
3. Deja un único registro resumen ``AUDITORIA_PURGADA`` en la bitácora (sin los
   datos movidos) para que la limpieza no quede invisible. Se puede omitir con
   ``--sin-registro``.

Uso (apuntando a la base con la variable DATABASE_URL del entorno):

    python -m tools.purgar_auditoria --usuario hariffc
    python -m tools.purgar_auditoria --usuario hariffc --aplicar

Opciones útiles:

    --accion ASISTENCIA_REACTIVADA   filtrar por acción (repetible)
    --desde 2026-01-01 --hasta 2026-11-13
    --salida C:/respaldo/auditoria_hariffc
    --incluir-asistencias            además limpia motivo_modificacion /
                                     modificado_por de las asistencias que ese
                                     usuario editó (los valores quedan en el archivo)
    --si                             no pedir confirmación interactiva
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Asistencia, RegistroAuditoria, Usuario


ACCION_RESUMEN = "AUDITORIA_PURGADA"


def _url_enmascarada(url: str) -> str:
    """Oculta la contraseña de la URL de conexión antes de imprimirla."""
    return re.sub(r"(://[^:/@]+:)[^@]+@", r"\1***@", url)


def _fin_exclusivo(fecha: date) -> datetime:
    """Devuelve el inicio del día siguiente (rango inclusivo en días)."""
    return datetime.combine(fecha + timedelta(days=1), time.min)


def _serializar(valor: Any) -> Any:
    """Convierte fechas y decimales a texto para el archivo de respaldo."""
    if isinstance(valor, datetime):
        return valor.isoformat(sep=" ")
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (bytes, bytearray)):
        return valor.decode("utf-8", errors="replace")
    return valor


def _fila_a_dict(instancia: Any, columnas: list[str]) -> dict[str, Any]:
    return {columna: _serializar(getattr(instancia, columna)) for columna in columnas}


def _escribir_archivo(destino: Path, datos: dict[str, Any]) -> tuple[Path, Path]:
    """Escribe el respaldo en JSON y CSV y devuelve ambas rutas."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    ruta_json = destino.with_suffix(".json")
    ruta_csv = destino.with_suffix(".csv")

    ruta_json.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    filas = datos["registros_auditoria"] + datos["asistencias"]
    campos = sorted({clave for fila in filas for clave in fila})
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as manejador:
        escritor = csv.DictWriter(manejador, fieldnames=campos)
        escritor.writeheader()
        for fila in filas:
            escritor.writerow(fila)

    return ruta_json, ruta_csv


def _colectar(
    db: Session,
    usuarios: list[str],
    acciones: list[str],
    desde: date | None,
    hasta: date | None,
    incluir_asistencias: bool,
) -> tuple[list[RegistroAuditoria], list[Asistencia], list[Usuario]]:
    """Selecciona los registros de bitácora (y asistencias) del filtro indicado."""
    consulta_usuarios = select(Usuario).where(Usuario.username.in_(usuarios))
    usuarios_bd = list(db.scalars(consulta_usuarios))
    if not usuarios_bd:
        return [], [], []

    ids = [usuario.id for usuario in usuarios_bd]
    nombres = [usuario.username for usuario in usuarios_bd]

    consulta = select(RegistroAuditoria).where(
        RegistroAuditoria.actor_username.in_(nombres)
    )
    if acciones:
        consulta = consulta.where(RegistroAuditoria.accion.in_(acciones))
    if desde is not None:
        consulta = consulta.where(
            RegistroAuditoria.ocurrido_en >= datetime.combine(desde, time.min)
        )
    if hasta is not None:
        consulta = consulta.where(RegistroAuditoria.ocurrido_en < _fin_exclusivo(hasta))
    consulta = consulta.order_by(RegistroAuditoria.id)

    asistencias: list[Asistencia] = []
    if incluir_asistencias:
        consulta_asistencias = select(Asistencia).where(
            Asistencia.modificado_por.in_(ids)
        )
        if desde is not None:
            consulta_asistencias = consulta_asistencias.where(
                Asistencia.hora_entrada_real >= datetime.combine(desde, time.min)
            )
        if hasta is not None:
            consulta_asistencias = consulta_asistencias.where(
                Asistencia.hora_entrada_real < _fin_exclusivo(hasta)
            )
        asistencias = list(db.scalars(consulta_asistencias.order_by(Asistencia.id)))

    return list(db.scalars(consulta)), asistencias, usuarios_bd


def _confirmar(resumen: str, aplicar: bool, saltar: bool) -> bool:
    if not aplicar:
        return False
    if saltar:
        return True
    print()
    print(resumen)
    print()
    print("Escribe BORRAR para mover estos datos al archivo y eliminarlos del sistema:")
    try:
        respuesta = input("> ").strip().upper()
    except EOFError:
        return False
    return respuesta == "BORRAR"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Archiva en un archivo y elimina los registros de auditoría indicados."
    )
    parser.add_argument(
        "--usuario",
        action="append",
        required=True,
        help="Nombre de usuario (actor) cuyos registros se van a mover. Repetible.",
    )
    parser.add_argument(
        "--accion",
        action="append",
        default=[],
        help="Acción de bitácora a incluir (repetible). Sin esta opción van todas.",
    )
    parser.add_argument("--desde", type=date.fromisoformat, help="Fecha inicial (YYYY-MM-DD).")
    parser.add_argument("--hasta", type=date.fromisoformat, help="Fecha final (YYYY-MM-DD).")
    parser.add_argument(
        "--salida",
        type=Path,
        help="Ruta base del archivo de respaldo (sin extensión).",
    )
    parser.add_argument(
        "--incluir-asistencias",
        action="store_true",
        help="También archiva y limpia motivo_modificacion/modificado_por de las asistencias.",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Ejecuta el borrado (sin esta opción solo se muestra la simulación).",
    )
    parser.add_argument("--si", action="store_true", help="No pedir confirmación interactiva.")
    parser.add_argument(
        "--sin-registro",
        action="store_true",
        help="No dejar el registro resumen AUDITORIA_PURGADA en la bitácora.",
    )

    args = parser.parse_args(argv)

    if args.desde and args.hasta and args.desde > args.hasta:
        print("[ERROR] --desde no puede ser posterior a --hasta", file=sys.stderr)
        return 2

    usuarios = [nombre.strip() for nombre in args.usuario if nombre.strip()]
    destino = args.salida or Path("respaldo").joinpath(
        "auditoria_" + "_".join(usuarios) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )

    print("Base de datos:", _url_enmascarada(get_settings().DATABASE_URL))
    db = SessionLocal()
    try:
        registros, asistencias, usuarios_bd = _colectar(
            db, usuarios, args.accion, args.desde, args.hasta, args.incluir_asistencias
        )

        if not usuarios_bd:
            print("[ERROR] No existe ningún usuario con ese nombre:", ", ".join(usuarios))
            return 3

        print("Usuarios encontrados:", ", ".join(f"{u.username} (#{u.id})" for u in usuarios_bd))
        print("Registros de bitácora a mover:", len(registros))
        if args.accion:
            print("Acciones filtradas:", ", ".join(args.accion))
        if args.incluir_asistencias:
            print("Asistencias con auditoría a limpiar:", len(asistencias))

        if not registros and not asistencias:
            print("[OK] No hay nada que mover con ese filtro.")
            return 0

        for registro in registros[:15]:
            print(
                f"  #{registro.id} {registro.ocurrido_en} {registro.accion} "
                f"{registro.entidad_tipo} {registro.entidad_id} — {registro.descripcion[:60]}"
            )
        if len(registros) > 15:
            print(f"  … y {len(registros) - 15} más")

        resumen = (
            f"Se moverán a un archivo y se eliminarán {len(registros)} registro(s) de "
            f"bitácora de {', '.join(usuarios)}"
            + (f" y se limpiará la auditoría de {len(asistencias)} asistencia(s)" if asistencias else "")
            + f".\nArchivo de respaldo: {destino}.json / .csv"
        )

        if not _confirmar(resumen, args.aplicar, args.si):
            if args.aplicar:
                print("[CANCELADO] No se borró nada.")
                return 1
            print()
            print("[SIMULACIÓN] No se escribió ni se borró nada. Repite con --aplicar.")
            return 0

        datos = {
            "generado_en": datetime.now().isoformat(sep=" ", timespec="seconds"),
            "motivo": "Limpieza de registros de auditoría solicitada por gerencia",
            "filtros": {
                "usuarios": usuarios,
                "acciones": args.accion,
                "desde": args.desde.isoformat() if args.desde else None,
                "hasta": args.hasta.isoformat() if args.hasta else None,
                "incluir_asistencias": args.incluir_asistencias,
            },
            "total_registros_auditoria": len(registros),
            "total_asistencias": len(asistencias),
            "registros_auditoria": [
                _fila_a_dict(
                    registro,
                    [
                        "id",
                        "ocurrido_en",
                        "actor_id",
                        "actor_username",
                        "actor_rol",
                        "accion",
                        "entidad_tipo",
                        "entidad_id",
                        "descripcion",
                        "antes",
                        "despues",
                    ],
                )
                for registro in registros
            ],
            "asistencias": [
                _fila_a_dict(
                    asistencia,
                    [
                        "id",
                        "empleado_id",
                        "turno_id",
                        "fecha",
                        "hora_entrada_real",
                        "hora_salida_real",
                        "horas_extras",
                        "horas_extras_originales",
                        "motivo_modificacion",
                        "modificado_por",
                        "observaciones",
                        "anulada",
                    ],
                )
                for asistencia in asistencias
            ],
        }

        ruta_json, ruta_csv = _escribir_archivo(destino, datos)
        guardado = json.loads(ruta_json.read_text(encoding="utf-8"))
        if len(guardado["registros_auditoria"]) != len(registros) or len(
            guardado["asistencias"]
        ) != len(asistencias):
            print("[ERROR] El archivo no coincide con lo seleccionado. No se borró nada.", file=sys.stderr)
            return 4
        print(f"[OK] Respaldo escrito: {ruta_json} y {ruta_csv}")

        ids_registros = [registro.id for registro in registros]
        for inicio in range(0, len(ids_registros), 500):
            lote = ids_registros[inicio : inicio + 500]
            for registro in db.scalars(
                select(RegistroAuditoria).where(RegistroAuditoria.id.in_(lote))
            ):
                db.delete(registro)

        for asistencia in asistencias:
            asistencia.motivo_modificacion = None
            asistencia.modificado_por = None

        if not args.sin_registro:
            usuario_actor = usuarios_bd[0]
            db.add(
                RegistroAuditoria(
                    actor_id=usuario_actor.id,
                    actor_username=usuario_actor.username,
                    actor_rol=str(usuario_actor.rol),
                    accion=ACCION_RESUMEN,
                    entidad_tipo="auditoria",
                    entidad_id=None,
                    descripcion=(
                        f"Se archivaron y eliminaron {len(registros)} registro(s) de "
                        f"bitácora de {', '.join(usuarios)}; respaldo en {ruta_json.name}"
                    ),
                    antes={"registros_auditoria": len(registros), "asistencias": len(asistencias)},
                    despues={"archivo": ruta_json.name, "eliminados": len(registros)},
                )
            )

        db.commit()
        print(f"[OK] Eliminados {len(registros)} registro(s) de bitácora y limpiadas {len(asistencias)} asistencia(s).")
        if not args.sin_registro:
            print("[OK] Registro resumen AUDITORIA_PURGADA guardado en la bitácora.")
        return 0
    except Exception as error:  # pragma: no cover - protección ante fallos de BD
        db.rollback()
        print("[ERROR] No se borró nada:", error, file=sys.stderr)
        return 5
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
