"""Servicio de importación inteligente de inventario."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.importacion_inventario import (
    AccionImportacion,
    DetalleImportacionInventario,
    EstadoImportacion,
    ImportacionInventario,
)
from app.models.inventario import (
    CategoriaInsumo,
    Insumo,
    MovimientoInventario,
    UnidadMedida,
)
from app.models.personal import Usuario
from app.schemas.importacion_inventario import (
    ImportacionAplicarRequest,
    ImportacionAplicarResponse,
    ImportacionInventarioResponse,
    ImportacionInventarioResumenResponse,
)
from app.services.auditoria_service import AuditoriaService
from app.services.conversion_service import convertir_cantidad
from app.services.extraccion_texto import ErrorExtraccion, extension_de, extraer_texto
from app.services.gemini_service import GeminiService
from app.services.importacion_inventario_parser import (
    FilaDetectada,
    cobertura_precio,
    cuantizar,
    decodificar_texto,
    es_palabra_empaque,
    extraer_unidad_y_factor,
    filas_delimitadas,
    filas_desde_csv,
    filas_desde_excel,
    limpiar_nombre,
    mapear_items_ia,
    normalizar_texto,
    parsear_estructurado,
    parsear_texto_libre,
    unidad_canonica,
)

logger = logging.getLogger(__name__)

UMBRAL_COINCIDENCIA = 0.86
UNIDAD_POR_DEFECTO = "Unidad"
MAX_FILAS = 500
MAX_BYTES = 25 * 1024 * 1024

SISTEMA_IMPORTACION = (
    "Eres un asistente experto en inventarios de restaurantes. "
    "Extrae del documento los artículos comprados o recibidos. Responde SOLO JSON válido con la forma "
    '{"items":[{"nombre":"Coca Cola","cantidad":2,"unidad":"cajilla","factor_empaque":24,'
    '"precio_unitario":480,"precio_total":960,"categoria":"Bebidas"}]}. '
    "Reglas: cantidad es el número de empaques o unidades recibidas (no el contenido del empaque); "
    "factor_empaque es cuántas unidades base trae un empaque (x24 = 24, un saco de 100 lb = 100) y null si no aplica; "
    "precio_unitario es el precio de UNA unidad tal como aparece (si solo viene el total, usa total/cantidad); "
    "no inventes artículos; omite totales, subtotales, impuestos, encabezados y textos que no sean productos; "
    "usa la moneda y los números tal como aparecen."
)


class ImportacionInventarioService:
    def __init__(self, db: Session, gemini: Optional[GeminiService] = None) -> None:
        self.db = db
        self.gemini = gemini or GeminiService()
        self.settings = get_settings()

    # =========================================================================
    # Análisis
    # =========================================================================

    def analizar(self, nombre_archivo: str, contenido: bytes, actor: Optional[Usuario]) -> ImportacionInventarioResponse:
        if not contenido:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
        if len(contenido) > MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo supera el máximo de 25 MB. Divídelo o comprímalo antes de subirlo.",
            )
        nombre = (nombre_archivo or "archivo").strip()[:255]
        filas, modelo = self._detectar(nombre, contenido)

        lote = ImportacionInventario(
            nombre_archivo=nombre,
            tipo_archivo=extension_de(nombre).lstrip(".").upper() or "DESCONOCIDO",
            hash_archivo=hashlib.sha256(contenido).hexdigest(),
            estado=EstadoImportacion.ANALIZANDO,
            modelo_ia=modelo,
            creada_por=getattr(actor, "id", None),
        )
        self.db.add(lote)
        self.db.flush()

        insumos = list(self.db.execute(select(Insumo)).scalars().all())
        categorias = list(self.db.execute(select(CategoriaInsumo)).scalars().all())
        unidades = list(self.db.execute(select(UnidadMedida)).scalars().all())

        detalles: list[DetalleImportacionInventario] = []
        for fila in filas[:MAX_FILAS]:
            detalle = self._enriquecer_fila(fila, insumos, categorias, unidades)
            detalle.importacion_id = lote.id
            self.db.add(detalle)
            detalles.append(detalle)
        self.db.flush()

        lote.estado = EstadoImportacion.REVISION
        lote.resumen = self._resumen(detalles, modelo)
        self.db.commit()
        self.db.refresh(lote)
        return ImportacionInventarioResponse.model_validate(lote)

    def _detectar(self, nombre: str, contenido: bytes) -> tuple[list[FilaDetectada], Optional[str]]:
        extension = extension_de(nombre)
        texto = ""
        filas: list[FilaDetectada] = []

        if extension in (".xlsx", ".xlsm", ".xls"):
            estructura = filas_desde_excel(contenido)
            if estructura:
                filas = parsear_estructurado(estructura)
        elif extension == ".csv":
            texto = decodificar_texto(contenido)
            filas = parsear_estructurado(filas_desde_csv(texto))
        elif extension in (".txt", ".md"):
            texto = decodificar_texto(contenido)
            filas = parsear_estructurado(filas_delimitadas(texto))
        else:
            texto, _tipo = self._extraer_texto(nombre, contenido)
            filas = parsear_estructurado(filas_delimitadas(texto))

        if not filas:
            if not texto:
                texto, _tipo = self._extraer_texto(nombre, contenido)
            filas = parsear_estructurado(filas_delimitadas(texto)) or parsear_texto_libre(texto)

        modelo: Optional[str] = None
        if self._debe_usar_ia(extension, filas):
            if not texto:
                texto, _tipo = self._extraer_texto(nombre, contenido)
            limite = self.settings.GEMINI_MAX_CARACTERES_DOCUMENTO
            mensaje = f"Archivo: {nombre}\n\nContenido:\n{texto[:limite]}"
            try:
                datos, modelo_usado = self.gemini.generar_json(
                    mensaje,
                    sistema=SISTEMA_IMPORTACION,
                    temperatura=0.1,
                    max_tokens=8192,
                )
                filas_ia = mapear_items_ia(datos)
                if filas_ia and (
                    not filas
                    or len(filas_ia) >= len(filas)
                    or cobertura_precio(filas_ia) > cobertura_precio(filas)
                ):
                    filas = filas_ia
                    modelo = modelo_usado
            except HTTPException as exc:
                logger.warning("[IMPORTACION] La IA no respondió para %s: %s", nombre, exc.detail)
                if not filas:
                    raise

        if not filas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se detectaron artículos en el archivo. Revisa que incluya nombres de productos "
                    "y cantidades, o pega el contenido en un TXT con una línea por producto."
                ),
            )
        return filas, modelo

    def _extraer_texto(self, nombre: str, contenido: bytes) -> tuple[str, str]:
        try:
            return extraer_texto(nombre, contenido)
        except ErrorExtraccion as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def _debe_usar_ia(self, extension: str, filas: list[FilaDetectada]) -> bool:
        if not self.gemini.disponible:
            return False
        if extension in (".pdf", ".doc", ".docx"):
            return True
        if not filas:
            return True
        return cobertura_precio(filas) < 0.5

    # =========================================================================
    # Enriquecimiento y matching
    # =========================================================================

    def _enriquecer_fila(
        self,
        fila: FilaDetectada,
        insumos: list[Insumo],
        categorias: list[CategoriaInsumo],
        unidades: list[UnidadMedida],
    ) -> DetalleImportacionInventario:
        notas: list[str] = []
        nombre = limpiar_nombre(fila.nombre)
        cantidad = fila.cantidad if fila.cantidad is not None else Decimal("0")
        unidad_nombre, factor_nombre, base_hint = extraer_unidad_y_factor(fila.nombre)
        unidad_col = factor_col = None
        if fila.unidad_texto:
            unidad_col, factor_col, base_col = extraer_unidad_y_factor(fila.unidad_texto)
            base_hint = base_hint or base_col
        unidad_texto = unidad_col or unidad_nombre or fila.unidad_texto
        factor = fila.factor_empaque or factor_col or factor_nombre
        if factor is not None and factor <= 1:
            factor = None

        mapa_unidades = self._mapa_unidades(unidades)
        unidad_resuelta = self._resolver_unidad(unidad_texto, unidades, mapa_unidades)
        unidad_base_hint = self._resolver_unidad(base_hint, unidades, mapa_unidades) if base_hint else None
        unidad_defecto = self._unidad_por_defecto(unidades, mapa_unidades)

        insumo, confianza = self._match_insumo(nombre, insumos)
        categoria = self._match_categoria(fila.categoria_texto, categorias)
        empaque_actual = mapa_unidades.get(normalizar_texto(unidad_texto)) if unidad_texto else None

        accion = AccionImportacion.CREAR
        unidad_medida_id: Optional[int] = None
        unidad_empaque_id: Optional[int] = None
        factor_empaque: Optional[float] = None
        categoria_id: Optional[int] = categoria.id if categoria else None
        stock_minimo = Decimal("5.00")

        if insumo:
            accion = AccionImportacion.ACTUALIZAR
            stock_minimo = insumo.stock_minimo or Decimal("5.00")
            unidad_medida_id = insumo.unidad_medida_id
            unidad_empaque_id = insumo.unidad_empaque_id
            factor_empaque = insumo.factor_empaque
            if categoria_id is None and fila.categoria_texto:
                notas.append(f"Categoría '{fila.categoria_texto}' no existe; se creará al aplicar.")
            elif categoria_id is None:
                categoria_id = insumo.categoria_id
            if unidad_resuelta and not self._es_empaque(unidad_resuelta, unidad_texto, factor):
                unidad_medida_id = unidad_resuelta.id
            if self._es_empaque(unidad_resuelta, unidad_texto, factor):
                empaque_coincide = (
                    insumo.unidad_empaque_id
                    and empaque_actual
                    and empaque_actual.id == insumo.unidad_empaque_id
                )
                if factor is None and empaque_coincide:
                    factor = insumo.factor_empaque
                factor_empaque = factor or factor_empaque
                if empaque_actual:
                    unidad_empaque_id = empaque_actual.id
                if unidad_base_hint:
                    unidad_medida_id = unidad_base_hint.id
                if factor is None:
                    notas.append(f"Indica cuántas unidades base trae 1 {unidad_texto or 'empaque'}.")
                    accion = AccionImportacion.OMITIR
            if not self._es_empaque(unidad_resuelta, unidad_texto, factor) and factor and factor > 1:
                notas.append("El empaque del archivo difiere del registrado; revisa el factor.")
        else:
            base = unidad_base_hint or (unidad_resuelta if not self._es_empaque(unidad_resuelta, unidad_texto, factor) else None) or unidad_defecto
            if base:
                unidad_medida_id = base.id
            if self._es_empaque(unidad_resuelta, unidad_texto, factor):
                if empaque_actual and base and empaque_actual.id != base.id:
                    unidad_empaque_id = empaque_actual.id
                elif unidad_texto and es_palabra_empaque(unidad_texto):
                    notas.append(f"Se creará la unidad de empaque '{_titulo(unidad_texto)}'.")
                factor_empaque = factor
                if factor is None:
                    notas.append(f"Indica cuántas unidades base trae 1 {unidad_texto or 'empaque'}.")
                    accion = AccionImportacion.OMITIR
            if fila.categoria_texto and categoria_id is None:
                notas.append(f"Se creará la categoría '{_titulo(fila.categoria_texto)}'.")

        if not unidad_medida_id and unidad_defecto:
            unidad_medida_id = unidad_defecto.id
        if cantidad <= 0:
            notas.append("La cantidad es cero; la fila no se aplicará.")
            accion = AccionImportacion.OMITIR

        return DetalleImportacionInventario(
            fila=fila.fila,
            texto_origen=fila.texto_origen,
            nombre_detectado=nombre,
            cantidad=cuantizar(cantidad) or Decimal("0.00"),
            unidad_texto=unidad_texto,
            precio_unitario=fila.precio_unitario,
            precio_total=fila.precio_total,
            categoria_texto=fila.categoria_texto,
            insumo_id=insumo.id if insumo else None,
            accion=accion,
            categoria_id=categoria_id,
            unidad_medida_id=unidad_medida_id,
            unidad_empaque_id=unidad_empaque_id,
            factor_empaque=float(factor) if factor else None,
            stock_minimo=stock_minimo,
            confianza=round(confianza, 3) if confianza is not None else (0.75 if fila.confianza else 0.5),
            notas=(" · ".join(notas + ([fila.notas] if fila.notas else [])))[:300] or None,
        )

    def _es_empaque(self, unidad: Optional[UnidadMedida], texto: Optional[str], factor: Optional[float]) -> bool:
        if not texto:
            return False
        n = normalizar_texto(texto)
        if n not in _PALABRAS_EMPAQUE_NORMALIZADAS:
            return False
        if factor is not None and factor > 1:
            return True
        return unidad is None or unidad.unidad_base_id is None

    @staticmethod
    def _mapa_unidades(unidades: list[UnidadMedida]) -> dict[str, UnidadMedida]:
        mapa: dict[str, UnidadMedida] = {}
        for unidad in unidades:
            mapa[normalizar_texto(unidad.nombre)] = unidad
            mapa[normalizar_texto(unidad.abreviatura)] = unidad
        return mapa

    def _resolver_unidad(
        self,
        texto: Optional[str],
        unidades: list[UnidadMedida],
        mapa: dict[str, UnidadMedida],
    ) -> Optional[UnidadMedida]:
        if not texto:
            return None
        n = normalizar_texto(texto)
        if n in mapa:
            return mapa[n]
        canonica = unidad_canonica(texto)
        if canonica and normalizar_texto(canonica) in mapa:
            return mapa[normalizar_texto(canonica)]
        mejor: Optional[UnidadMedida] = None
        mejor_ratio = 0.0
        for unidad in unidades:
            ratio = SequenceMatcher(None, n, normalizar_texto(unidad.nombre)).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = unidad, ratio
        return mejor if mejor_ratio >= 0.9 else None

    def _unidad_por_defecto(
        self,
        unidades: list[UnidadMedida],
        mapa: dict[str, UnidadMedida],
    ) -> Optional[UnidadMedida]:
        clave = normalizar_texto(UNIDAD_POR_DEFECTO)
        if clave in mapa:
            return mapa[clave]
        return unidades[0] if unidades else None

    def _match_insumo(self, nombre: str, insumos: list[Insumo]) -> tuple[Optional[Insumo], Optional[float]]:
        n = normalizar_texto(nombre)
        if not n:
            return None, None
        for insumo in insumos:
            if normalizar_texto(insumo.nombre) == n:
                return insumo, 1.0
        mejor: Optional[Insumo] = None
        mejor_ratio = 0.0
        for insumo in insumos:
            otro = normalizar_texto(insumo.nombre)
            ratio = SequenceMatcher(None, n, otro).ratio()
            if len(n) >= 4 and len(otro) >= 4 and (n in otro or otro in n):
                ratio = max(ratio, 0.92)
            if ratio > mejor_ratio:
                mejor, mejor_ratio = insumo, ratio
        if mejor_ratio >= UMBRAL_COINCIDENCIA:
            return mejor, mejor_ratio
        return None, mejor_ratio or None

    def _match_categoria(self, texto: Optional[str], categorias: list[CategoriaInsumo]) -> Optional[CategoriaInsumo]:
        if not texto:
            return None
        n = normalizar_texto(texto)
        if not n:
            return None
        for categoria in categorias:
            if normalizar_texto(categoria.nombre) == n:
                return categoria
        mejor: Optional[CategoriaInsumo] = None
        mejor_ratio = 0.0
        for categoria in categorias:
            ratio = SequenceMatcher(None, n, normalizar_texto(categoria.nombre)).ratio()
            if ratio > mejor_ratio:
                mejor, mejor_ratio = categoria, ratio
        return mejor if mejor_ratio >= UMBRAL_COINCIDENCIA else None

    def _resumen(self, detalles: list[DetalleImportacionInventario], modelo: Optional[str]) -> dict[str, Any]:
        categorias_nuevas = sorted({
            _titulo(d.categoria_texto)
            for d in detalles
            if d.categoria_texto and d.categoria_id is None
        })
        empaques_nuevos = sorted({
            _titulo(d.unidad_texto)
            for d in detalles
            if d.unidad_texto and d.unidad_empaque_id is None
            and es_palabra_empaque(d.unidad_texto)
            and d.factor_empaque
        })
        return {
            "filas": len(detalles),
            "crear": sum(1 for d in detalles if d.accion == AccionImportacion.CREAR),
            "actualizar": sum(1 for d in detalles if d.accion == AccionImportacion.ACTUALIZAR),
            "omitir": sum(1 for d in detalles if d.accion == AccionImportacion.OMITIR),
            "con_precio": sum(1 for d in detalles if d.precio_unitario is not None or d.precio_total is not None),
            "modelo_ia": modelo,
            "categorias_nuevas": categorias_nuevas,
            "empaques_nuevos": empaques_nuevos,
        }

    # =========================================================================
    # Consulta
    # =========================================================================

    def listar(self) -> list[ImportacionInventarioResumenResponse]:
        lotes = self.db.execute(
            select(ImportacionInventario).order_by(ImportacionInventario.id.desc()).limit(30)
        ).scalars().all()
        return [ImportacionInventarioResumenResponse.model_validate(lote) for lote in lotes]

    def obtener(self, importacion_id: int) -> ImportacionInventarioResponse:
        lote = self._lote(importacion_id)
        return ImportacionInventarioResponse.model_validate(lote)

    def eliminar(self, importacion_id: int) -> None:
        lote = self._lote(importacion_id)
        if lote.estado == EstadoImportacion.APLICADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede eliminar una importación ya aplicada.",
            )
        self.db.delete(lote)
        self.db.commit()

    def _lote(self, importacion_id: int) -> ImportacionInventario:
        lote = self.db.get(ImportacionInventario, importacion_id)
        if not lote:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la importación con ID {importacion_id}",
            )
        return lote

    # =========================================================================
    # Aplicación
    # =========================================================================

    def aplicar(
        self,
        importacion_id: int,
        payload: ImportacionAplicarRequest,
        actor: Usuario,
    ) -> ImportacionAplicarResponse:
        lote = self._lote(importacion_id)
        if lote.estado == EstadoImportacion.APLICADA:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta importación ya fue aplicada al inventario.",
            )
        detalles_lote = {detalle.id: detalle for detalle in lote.detalles}
        if not detalles_lote:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La importación no tiene filas para aplicar.",
            )

        creadas = 0
        actualizadas = 0
        omitidas = 0
        movimientos = 0
        aplicadas: list[dict[str, Any]] = []
        fila_actual = 0

        try:
            for item in payload.detalles:
                fila_actual = item.id
                detalle = detalles_lote.get(item.id)
                if detalle is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"La fila con ID {item.id} no pertenece a esta importación.",
                    )
                fila_actual = detalle.fila or detalle.id
                if item.accion == AccionImportacion.OMITIR.value or item.cantidad <= 0:
                    detalle.accion = AccionImportacion.OMITIR
                    omitidas += 1
                    continue

                nombre = " ".join(str(item.nombre or "").split()).strip()[:100]
                if not nombre:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"La fila {fila_actual} no tiene nombre de artículo.",
                    )

                insumo = self._insumo_objetivo(detalle, item, nombre)
                categoria = self._resolver_categoria(item.categoria_id, item.categoria_nombre)

                if insumo is not None:
                    unidad_base_id = insumo.unidad_medida_id
                else:
                    unidad_base_id = self._unidad_base_por_defecto(item.unidad_medida_id)

                empaque = self._resolver_empaque(item.unidad_empaque_id, item.unidad_empaque_nombre)
                if empaque is not None and empaque.id == unidad_base_id:
                    empaque = None
                factor = self._factor_empaque(empaque, item.factor_empaque, insumo)
                if empaque is not None and factor is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"La fila {fila_actual} usa el empaque '{empaque.nombre}' "
                            "pero no indica cuántas unidades base contiene."
                        ),
                    )

                cantidad_base = self._cantidad_base(
                    item.cantidad, empaque.id if empaque else None, factor, unidad_base_id
                )
                if cantidad_base <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"La fila {fila_actual} tiene una cantidad inválida.",
                    )
                cantidad_base = self._dec(cantidad_base)
                costo_base = self._costo_base(item, cantidad_base)
                stock_minimo = self._decimal(item.stock_minimo)

                es_nuevo = insumo is None
                if es_nuevo:
                    insumo = Insumo(
                        nombre=nombre,
                        cantidad_actual=Decimal("0.00"),
                        unidad_medida_id=unidad_base_id,
                        stock_minimo=stock_minimo or Decimal("5.00"),
                        categoria_id=categoria.id if categoria else None,
                        costo_unitario=costo_base or Decimal("0.00"),
                        unidad_empaque_id=empaque.id if empaque else None,
                        factor_empaque=factor,
                    )
                    self.db.add(insumo)
                    self.db.flush()
                    creadas += 1
                else:
                    insumo.unidad_medida_id = unidad_base_id
                    if categoria is not None:
                        insumo.categoria_id = categoria.id
                    if stock_minimo is not None:
                        insumo.stock_minimo = stock_minimo
                    if costo_base is not None:
                        insumo.costo_unitario = costo_base
                    if empaque is not None:
                        insumo.unidad_empaque_id = empaque.id
                    if factor is not None:
                        insumo.factor_empaque = factor
                    actualizadas += 1

                insumo.cantidad_actual = self._dec(
                    (insumo.cantidad_actual or Decimal("0")) + cantidad_base
                )
                self.db.add(
                    MovimientoInventario(
                        insumo_id=insumo.id,
                        tipo="ENTRADA",
                        cantidad=cantidad_base,
                        motivo=f"Importación #{lote.id} {lote.nombre_archivo}"[:100],
                    )
                )
                movimientos += 1

                detalle.accion = (
                    AccionImportacion.CREAR if es_nuevo else AccionImportacion.ACTUALIZAR
                )
                detalle.insumo_id = insumo.id
                detalle.categoria_id = categoria.id if categoria else detalle.categoria_id
                detalle.unidad_medida_id = unidad_base_id
                detalle.unidad_empaque_id = empaque.id if empaque else None
                detalle.factor_empaque = factor
                detalle.aplicado = True
                aplicadas.append(
                    {
                        "fila": fila_actual,
                        "insumo_id": insumo.id,
                        "insumo": insumo.nombre,
                        "cantidad_base": str(cantidad_base),
                        "costo_unitario": str(insumo.costo_unitario),
                    }
                )

            resumen = dict(lote.resumen or {})
            resumen.update(
                {
                    "aplicadas": len(aplicadas),
                    "creadas": creadas,
                    "actualizadas": actualizadas,
                    "omitidas": omitidas,
                    "movimientos": movimientos,
                }
            )
            lote.estado = EstadoImportacion.APLICADA
            lote.aplicada_en = datetime.now()
            lote.resumen = resumen
            lote.error = None
            AuditoriaService.registrar(
                self.db,
                actor,
                "IMPORTACION_INVENTARIO_APLICADA",
                "importacion_inventario",
                lote.id,
                (
                    f"Importación '{lote.nombre_archivo}': {creadas} artículos creados, "
                    f"{actualizadas} actualizados, {omitidas} omitidos, "
                    f"{movimientos} movimientos de entrada."
                ),
                antes={"estado": EstadoImportacion.REVISION.value},
                despues={
                    "estado": EstadoImportacion.APLICADA.value,
                    "creadas": creadas,
                    "actualizadas": actualizadas,
                    "omitidas": omitidas,
                    "movimientos": movimientos,
                },
            )
            self.db.commit()
        except HTTPException:
            self.db.rollback()
            raise
        except Exception as error:
            self.db.rollback()
            logger.exception("[IMPORTACION] Error al aplicar la importación %s", importacion_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se pudo aplicar la fila {fila_actual}. "
                    "No se guardó ningún cambio; revisa los datos e intenta de nuevo."
                ),
            ) from error

        self.db.refresh(lote)
        return ImportacionAplicarResponse(
            importacion_id=lote.id,
            creadas=creadas,
            actualizadas=actualizadas,
            omitidas=omitidas,
            total_movimientos=movimientos,
            resumen=dict(lote.resumen or {}),
        )

    def _insumo_objetivo(
        self,
        detalle: DetalleImportacionInventario,
        item,
        nombre: str,
    ) -> Optional[Insumo]:
        if item.accion == AccionImportacion.ACTUALIZAR.value and detalle.insumo_id:
            insumo = self.db.get(Insumo, detalle.insumo_id)
            if insumo is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"El insumo de la fila {detalle.fila or detalle.id} "
                        "ya no existe en el inventario."
                    ),
                )
            return insumo
        clave = normalizar_texto(nombre)
        for insumo in self.db.execute(select(Insumo)).scalars().all():
            if normalizar_texto(insumo.nombre) == clave:
                return insumo
        return None

    def _resolver_categoria(
        self,
        categoria_id: Optional[int],
        categoria_nombre: Optional[str],
    ) -> Optional[CategoriaInsumo]:
        if categoria_id:
            categoria = self.db.get(CategoriaInsumo, categoria_id)
            if categoria is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se encontró la categoría con ID {categoria_id}.",
                )
            return categoria
        nombre = _titulo(categoria_nombre)[:50]
        if not nombre:
            return None
        clave = normalizar_texto(nombre)
        for categoria in self.db.execute(select(CategoriaInsumo)).scalars().all():
            if normalizar_texto(categoria.nombre) == clave:
                return categoria
        categoria = CategoriaInsumo(nombre=nombre)
        self.db.add(categoria)
        self.db.flush()
        return categoria

    def _resolver_empaque(
        self,
        empaque_id: Optional[int],
        empaque_nombre: Optional[str],
    ) -> Optional[UnidadMedida]:
        if empaque_id:
            unidad = self.db.get(UnidadMedida, empaque_id)
            if unidad is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se encontró la unidad de empaque con ID {empaque_id}.",
                )
            return unidad
        nombre = _titulo(empaque_nombre)[:50]
        if not nombre:
            return None
        unidades = list(self.db.execute(select(UnidadMedida)).scalars().all())
        clave = normalizar_texto(nombre)
        for unidad in unidades:
            if normalizar_texto(unidad.nombre) == clave:
                return unidad
        unidad = UnidadMedida(
            nombre=nombre,
            abreviatura=self._abreviatura_unica(nombre, unidades),
            tipo_magnitud="UNIDAD",
            unidad_base_id=None,
            factor_conversion=1.0,
        )
        self.db.add(unidad)
        self.db.flush()
        return unidad

    @staticmethod
    def _abreviatura_unica(nombre: str, unidades: list[UnidadMedida]) -> str:
        existentes = {(unidad.abreviatura or "").lower() for unidad in unidades}
        letras = "".join(c for c in normalizar_texto(nombre) if c.isalpha()).upper() or "UND"
        base = letras[:4]
        candidato = base
        contador = 1
        while candidato.lower() in existentes:
            sufijo = str(contador)
            candidato = base[: max(1, 4 - len(sufijo))] + sufijo
            contador += 1
        return candidato[:10]

    def _unidad_base_por_defecto(self, unidad_id: Optional[int]) -> int:
        if unidad_id:
            unidad = self.db.get(UnidadMedida, unidad_id)
            if unidad is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se encontró la unidad de medida con ID {unidad_id}.",
                )
            return unidad.id
        unidades = list(self.db.execute(select(UnidadMedida)).scalars().all())
        mapa = self._mapa_unidades(unidades)
        unidad = mapa.get(normalizar_texto(UNIDAD_POR_DEFECTO))
        if unidad is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Falta la unidad de medida base 'Unidad'. "
                    "Crea esa unidad en Inventario antes de importar."
                ),
            )
        return unidad.id

    @staticmethod
    def _factor_empaque(
        empaque: Optional[UnidadMedida],
        factor: Optional[float],
        insumo: Optional[Insumo],
    ) -> Optional[float]:
        if empaque is None:
            return None
        if factor and factor > 1:
            return float(factor)
        if (
            insumo is not None
            and insumo.unidad_empaque_id == empaque.id
            and insumo.factor_empaque
        ):
            return float(insumo.factor_empaque)
        return None

    def _cantidad_base(
        self,
        cantidad: Decimal,
        empaque_id: Optional[int],
        factor: Optional[float],
        unidad_base_id: int,
    ) -> Decimal:
        if empaque_id is None:
            return cantidad
        if factor and factor > 1:
            return cantidad * Decimal(str(factor))
        resultado = convertir_cantidad(
            self.db, float(cantidad), empaque_id, unidad_base_id
        )
        return Decimal(str(resultado))

    def _costo_base(self, item, cantidad_base: Decimal) -> Optional[Decimal]:
        total = self._decimal(item.precio_total)
        if total is None and item.precio_unitario is not None:
            total = self._decimal(Decimal(item.precio_unitario) * item.cantidad)
        if total is None or cantidad_base <= 0:
            return None
        return self._dec(total / cantidad_base)

    @staticmethod
    def _decimal(valor: Optional[Decimal]) -> Optional[Decimal]:
        if valor is None:
            return None
        return Decimal(str(valor))

    @staticmethod
    def _dec(valor: Decimal) -> Decimal:
        return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_PALABRAS_EMPAQUE = {
    "cajilla", "caja", "cajon", "saco", "fardo", "bulto", "cubeta",
    "dispensador", "manojo", "quintal", "bandeja", "canasta", "pack", "galon",
}
_PALABRAS_EMPAQUE_NORMALIZADAS = {normalizar_texto(p) for p in _PALABRAS_EMPAQUE}


def _titulo(texto: Any) -> str:
    limpio = " ".join(str(texto or "").split()).strip()
    return limpio[:1].upper() + limpio[1:].lower() if limpio else ""
