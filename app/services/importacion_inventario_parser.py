"""Lectura y normalización de archivos para la importación de inventario."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.services.extraccion_texto import extension_de


@dataclass
class FilaDetectada:
    nombre: str
    cantidad: Decimal = Decimal("1")
    unidad_texto: Optional[str] = None
    precio_unitario: Optional[Decimal] = None
    precio_total: Optional[Decimal] = None
    categoria_texto: Optional[str] = None
    factor_empaque: Optional[float] = None
    confianza: Optional[float] = None
    notas: Optional[str] = None
    fila: int = 0
    texto_origen: Optional[str] = None


PALABRAS_UNIDAD: list[tuple[str, str]] = [
    (r"kilogramos?|kilos?|kgs?", "Kilogramo"),
    (r"gramos?|grs?|g", "Gramo"),
    (r"libras?|lbs?", "Libra"),
    (r"onzas?|oz", "Onza"),
    (r"mililitros?|ml", "Mililitro"),
    (r"litros?|lts?|l", "Litro"),
    (r"botellas?", "Botella"),
    (r"latas?", "Lata"),
    (r"docenas?", "Docena"),
    (r"pares?", "Par"),
    (r"paquetes?|pqt", "Paquete"),
    (r"bolsas?", "Bolsa"),
    (r"porciones?|porcion", "Porción"),
    (r"metros?", "Metro"),
    (r"unidades?|uds?|unid|u", "Unidad"),
    (r"cajillas?", "Cajilla"),
    (r"cajas?", "Caja"),
    (r"cajones?|cajón", "Cajón"),
    (r"sacos?", "Saco"),
    (r"fardos?", "Fardo"),
    (r"bultos?", "Bulto"),
    (r"cubetas?", "Cubeta"),
    (r"dispensadores?", "Dispensador"),
    (r"manojos?", "Manojo"),
    (r"quintales?", "Quintal"),
    (r"bandejas?", "Bandeja"),
    (r"canastas?", "Canasta"),
    (r"packs?", "Pack"),
    (r"galones?|galón", "Galón"),
]

PALABRAS_EMPAQUE = {
    "cajilla", "caja", "cajon", "saco", "fardo", "bulto", "cubeta",
    "dispensador", "manojo", "quintal", "bandeja", "canasta", "pack", "galon",
}

PATRON_NUMERO = re.compile(
    r"(?<![\w.,])(?:C\$|\$)?\s*"
    r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
    r"(?![\w])",
    re.IGNORECASE,
)


def normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def normalizar_numero(valor: Any) -> Optional[Decimal]:
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).strip().replace("\u00a0", "").replace(" ", "")
    texto = re.sub(r"[^\d.,\-]", "", texto)
    if texto in ("", "-", ".", ","):
        return None
    negativo = texto.startswith("-")
    texto = texto.lstrip("-")
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes) > 2:
            if all(len(p) == 3 for p in partes[1:]):
                texto = "".join(partes)
            else:
                texto = "".join(partes[:-1]) + "." + partes[-1]
        else:
            entero, decimales = partes
            if len(decimales) == 3 and entero not in ("", "0") and 1 <= len(entero) <= 3:
                texto = entero + decimales
            else:
                texto = entero + "." + decimales
    elif "." in texto:
        partes = texto.split(".")
        if len(partes) > 2:
            if all(len(p) == 3 for p in partes[1:]):
                texto = "".join(partes)
            else:
                texto = "".join(partes[:-1]) + "." + partes[-1]
    if not texto:
        return None
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None
    return -numero if negativo else numero


def cuantizar(valor: Optional[Decimal]) -> Optional[Decimal]:
    if valor is None:
        return None
    return valor.quantize(Decimal("0.01"))


def es_numerico(valor: Any) -> bool:
    texto = str(valor or "").strip()
    if not texto:
        return False
    return bool(re.fullmatch(
        r"(?:C\$|\$)?\s*-?\d[\d.,\s]*(?:\s*(?:%|kg|kgs?|g|gr|gramos?|lb|libras?|oz|onzas?|l|lt|litros?|ml|mililitros?|u|ud|uds|unidades?))?\s*",
        texto,
        re.IGNORECASE,
    ))


def decodificar_texto(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="replace")


def _texto_celda(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def filas_desde_excel(contenido: bytes) -> Optional[list[list[str]]]:
    try:
        import openpyxl
    except ImportError:
        return None
    try:
        libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    except Exception:
        return None
    filas: list[list[str]] = []
    try:
        for hoja in libro.worksheets:
            for fila in hoja.iter_rows(values_only=True):
                filas.append([_texto_celda(valor) for valor in fila])
    finally:
        libro.close()
    return filas


def filas_desde_csv(texto: str) -> list[list[str]]:
    muestra = texto[:4096]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
    except csv.Error:
        dialecto = csv.excel
    try:
        return [[_texto_celda(c) for c in fila] for fila in csv.reader(io.StringIO(texto), dialecto)]
    except csv.Error:
        return [[linea] for linea in texto.splitlines()]


def filas_delimitadas(texto: str) -> list[list[str]]:
    lineas = [linea for linea in texto.splitlines() if linea.strip()]
    if not lineas:
        return []
    for delimitador in ("|", ";", "\t"):
        if sum(1 for linea in lineas if delimitador in linea) >= max(2, len(lineas) * 0.4):
            return [[c.strip() for c in linea.split(delimitador)] for linea in lineas]
    if sum(1 for linea in lineas if re.search(r"\s{2,}", linea)) >= max(2, len(lineas) * 0.5):
        return [re.split(r"\s{2,}", linea.strip()) for linea in lineas]
    return [[linea.strip()] for linea in lineas]


def _campo_de_encabezado(celda: str) -> Optional[str]:
    n = normalizar_texto(celda)
    if not n:
        return None
    if any(k in n for k in ("precio unit", "costo unit", "valor unit", "unitario", "p unit", "punit")):
        return "precio_unitario"
    if any(k in n for k in ("precio total", "costo total", "valor total", "monto total", "importe", "subtotal")):
        return "precio_total"
    if n in ("total", "monto", "valor"):
        return "precio_total"
    if any(k in n for k in ("precio", "costo", "valor")):
        return "precio_unitario"
    if any(k in n for k in ("factor", "equivale", "contiene", "empaque", "presentacion", "formato")):
        return "factor"
    if any(k in n for k in ("cantidad", "cant", "qty", "unidades", "entradas", "ingreso", "existencia", "stock", "recibido")):
        return "cantidad"
    if n in ("unidad", "unidad de medida", "um", "medida", "unidad de compra", "envase"):
        return "unidad"
    if any(k in n for k in ("categoria", "rubro", "grupo", "familia", "linea", "seccion")):
        return "categoria"
    if any(k in n for k in ("nombre", "producto", "articulo", "descripcion", "item", "insumo", "detalle", "mercaderia", "concepto", "material")):
        return "nombre"
    return None


def detectar_encabezado(filas: list[list[str]]) -> tuple[Optional[int], dict[str, int]]:
    for indice, fila in enumerate(filas[:10]):
        mapa: dict[str, int] = {}
        for columna, celda in enumerate(fila):
            campo = _campo_de_encabezado(celda)
            if campo and campo not in mapa:
                mapa[campo] = columna
        if "nombre" in mapa and len(mapa) >= 2:
            return indice, mapa
    return None, {}


def _columna_unidad(muestra: list[list[str]], excluir: set[int]) -> Optional[int]:
    ancho = max((len(f) for f in muestra), default=0)
    mejor, puntaje = None, 0
    for columna in range(ancho):
        if columna in excluir:
            continue
        valores = [f[columna] for f in muestra if columna < len(f) and f[columna]]
        if not valores:
            continue
        aciertos = sum(1 for v in valores if extraer_unidad_y_factor(v)[0] or normalizar_texto(v) in PALABRAS_EMPAQUE)
        if aciertos / len(valores) >= 0.6 and aciertos > puntaje:
            mejor, puntaje = columna, aciertos
    return mejor


def inferir_columnas(filas: list[list[str]]) -> dict[str, int]:
    muestra = [f for f in filas if any(c for c in f)][:30]
    if not muestra:
        return {}
    ancho = max((len(f) for f in muestra), default=0)
    texto_score = [0] * ancho
    numericas: list[dict[str, Any]] = []
    for columna in range(ancho):
        valores = [f[columna] for f in muestra if columna < len(f) and f[columna]]
        if not valores:
            continue
        numeros = [v for v in valores if es_numerico(v)]
        texto_score[columna] = len(valores) - len(numeros)
        if len(numeros) / len(valores) >= 0.7:
            convertidos = [normalizar_numero(v) for v in valores]
            convertidos = sorted(n for n in convertidos if n is not None)
            if not convertidos:
                continue
            decimales = sum(1 for v in valores if re.search(r"[.,]\d{1,2}\s*$", str(v)))
            numericas.append({
                "idx": columna,
                "decimal_ratio": decimales / len(valores),
                "mediana": convertidos[len(convertidos) // 2],
            })
    if not any(texto_score):
        return {}
    nombre = max(range(ancho), key=lambda i: texto_score[i])
    mapa: dict[str, int] = {"nombre": nombre}
    numericas = [n for n in numericas if n["idx"] != nombre]
    numericas.sort(key=lambda n: n["mediana"])
    if len(numericas) == 1:
        campo = "precio_total" if numericas[0]["decimal_ratio"] > 0.5 else "cantidad"
        mapa[campo] = numericas[0]["idx"]
    elif len(numericas) >= 2:
        mapa["cantidad"] = numericas[0]["idx"]
        if len(numericas) >= 3:
            mapa["precio_unitario"] = numericas[1]["idx"]
            mapa["precio_total"] = numericas[-1]["idx"]
        else:
            mapa["precio_unitario"] = numericas[-1]["idx"]
    unidad = _columna_unidad(muestra, {nombre})
    if unidad is not None:
        mapa["unidad"] = unidad
    return mapa


def _celda(fila: list[str], indice: Optional[int]) -> str:
    if indice is None or indice < 0 or indice >= len(fila):
        return ""
    return fila[indice]


def _es_fila_ignorada(nombre: str) -> bool:
    n = normalizar_texto(nombre)
    if not n:
        return True
    return n in {
        "total", "totales", "subtotal", "suma", "gran total", "iva", "impuesto",
        "descuento", "saldo", "observaciones", "notas", "comentario",
    } or n.startswith(("total ", "subtotal ", "gran total"))


def _asignar_numeros(numeros: list[Decimal], texto: str) -> tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
    if not numeros:
        return Decimal("0"), None, None
    if len(numeros) == 1:
        numero = numeros[0]
        tiene_simbolo = "C$" in texto or "$" in texto
        tiene_unidad = extraer_unidad_y_factor(texto)[0] is not None
        if tiene_simbolo or numero != numero.to_integral():
            return Decimal("1"), numero, None
        if tiene_unidad or numero <= 50:
            return numero, None, None
        return Decimal("1"), numero, None
    if len(numeros) == 2:
        return numeros[0], numeros[1], None
    return numeros[0], numeros[-2], numeros[-1]


def parsear_estructurado(filas: list[list[str]]) -> list[FilaDetectada]:
    if not filas:
        return []
    if max((len(f) for f in filas), default=0) < 2:
        return []
    indice, mapa = detectar_encabezado(filas)
    if indice is None:
        mapa = inferir_columnas(filas)
        inicio = 0
    else:
        inicio = indice + 1
    if "nombre" not in mapa:
        return []
    resultado: list[FilaDetectada] = []
    for numero_fila, fila in enumerate(filas[inicio:], start=inicio + 1):
        texto_origen = " | ".join(c for c in fila if c)
        nombre = _celda(fila, mapa.get("nombre"))
        if not nombre or _es_fila_ignorada(nombre):
            continue
        cantidad = normalizar_numero(_celda(fila, mapa.get("cantidad")))
        precio_unitario = normalizar_numero(_celda(fila, mapa.get("precio_unitario")))
        precio_total = normalizar_numero(_celda(fila, mapa.get("precio_total")))
        factor = normalizar_numero(_celda(fila, mapa.get("factor")))
        if cantidad is None:
            cantidad = Decimal("1")
        if precio_unitario is None and precio_total is not None and cantidad > 0:
            precio_unitario = precio_total / cantidad
        if precio_total is None and precio_unitario is not None:
            precio_total = precio_unitario * cantidad
        resultado.append(FilaDetectada(
            nombre=limpiar_nombre(nombre),
            cantidad=cuantizar(cantidad) or Decimal("1.00"),
            unidad_texto=_celda(fila, mapa.get("unidad")) or None,
            precio_unitario=cuantizar(precio_unitario),
            precio_total=cuantizar(precio_total),
            categoria_texto=_celda(fila, mapa.get("categoria")) or None,
            factor_empaque=float(factor) if factor and factor > 1 else None,
            fila=numero_fila,
            texto_origen=texto_origen[:1000],
        ))
        if len(resultado) >= 500:
            break
    return resultado


def _fila_desde_celdas_sueltas(celdas: list[str], numero_fila: int, texto_origen: str) -> Optional[FilaDetectada]:
    texto_celdas = [c for c in celdas if not es_numerico(c)]
    nombre = texto_celdas[0] if texto_celdas else celdas[0]
    if _es_fila_ignorada(nombre):
        return None
    numeros = [normalizar_numero(c) for c in celdas if es_numerico(c)]
    numeros = [n for n in numeros if n is not None]
    cantidad, precio_unitario, precio_total = _asignar_numeros(numeros, texto_origen)
    unidad = None
    for celda in celdas[1:]:
        if es_numerico(celda):
            continue
        unidad = extraer_unidad_y_factor(celda)[0] or unidad
    factor = extraer_unidad_y_factor(texto_origen)[1]
    if precio_unitario is None and precio_total is not None and cantidad > 0:
        precio_unitario = precio_total / cantidad
    if precio_total is None and precio_unitario is not None:
        precio_total = precio_unitario * cantidad
    return FilaDetectada(
        nombre=limpiar_nombre(nombre),
        cantidad=cuantizar(cantidad) or Decimal("1.00"),
        unidad_texto=unidad,
        precio_unitario=cuantizar(precio_unitario),
        precio_total=cuantizar(precio_total),
        factor_empaque=factor,
        fila=numero_fila,
        texto_origen=texto_origen[:1000],
    )


def _fila_desde_linea(linea: str, numero_fila: int) -> Optional[FilaDetectada]:
    coincidencias = list(PATRON_NUMERO.finditer(linea))
    numeros = [normalizar_numero(m.group(1)) for m in coincidencias]
    numeros = [n for n in numeros if n is not None]
    if not numeros:
        return None
    unidad_texto, factor, _base = extraer_unidad_y_factor(linea)
    cantidad, precio_unitario, precio_total = _asignar_numeros(numeros, linea)
    nombre = linea
    for coincidencia in reversed(coincidencias):
        nombre = nombre[:coincidencia.start()] + " " + nombre[coincidencia.end():]
    nombre = limpiar_nombre(nombre)
    if not nombre or _es_fila_ignorada(nombre):
        return None
    if precio_unitario is None and precio_total is not None and cantidad > 0:
        precio_unitario = precio_total / cantidad
    if precio_total is None and precio_unitario is not None:
        precio_total = precio_unitario * cantidad
    return FilaDetectada(
        nombre=nombre,
        cantidad=cuantizar(cantidad) or Decimal("1.00"),
        unidad_texto=unidad_texto,
        precio_unitario=cuantizar(precio_unitario),
        precio_total=cuantizar(precio_total),
        factor_empaque=factor,
        fila=numero_fila,
        texto_origen=linea[:1000],
    )


def parsear_texto_libre(texto: str) -> list[FilaDetectada]:
    resultado: list[FilaDetectada] = []
    for numero_fila, linea in enumerate(texto.splitlines(), start=1):
        limpia = re.sub(r"^[\s\-\*\u2022•]+", "", linea).strip()
        if not limpia:
            continue
        celdas = [c.strip() for c in re.split(r"\s*[|;\t]\s*", limpia) if c.strip()]
        fila = _fila_desde_celdas_sueltas(celdas, numero_fila, limpia) if len(celdas) >= 2 else _fila_desde_linea(limpia, numero_fila)
        if fila:
            resultado.append(fila)
        if len(resultado) >= 500:
            break
    return resultado


EMPAQUES_CANONICOS = {
    "Cajilla", "Caja", "Cajón", "Saco", "Fardo", "Bulto", "Cubeta",
    "Dispensador", "Manojo", "Quintal", "Bandeja", "Canasta", "Pack", "Galón",
}


def extraer_unidad_y_factor(texto: Any) -> tuple[Optional[str], Optional[float], Optional[str]]:
    original = str(texto or "")
    if not original.strip():
        return None, None, None
    base: Optional[str] = None
    factor: Optional[float] = None
    posicion_base: Optional[int] = None
    coincidencia = re.search(
        r"(?i)\b(?:de|con|por|trae)\s+(\d+(?:[.,]\d+)?)\s*"
        r"(kilogramos?|kilos?|kgs?|gramos?|grs?|g|libras?|lbs?|onzas?|oz|litros?|lts?|mililitros?|ml)\b",
        original,
    )
    if coincidencia:
        factor = float(normalizar_numero(coincidencia.group(1)) or 0) or None
        base = unidad_canonica(coincidencia.group(2))
        posicion_base = coincidencia.start()
    if factor is None:
        coincidencia = re.search(r"(?i)(?:\bx\s*\*?\s*|\*\s*)(\d{1,4})\b", original)
        if coincidencia:
            factor = float(normalizar_numero(coincidencia.group(1)) or 0) or None
    if factor is None:
        coincidencia = re.search(
            r"(?i)\b(?:de|con|por|trae)\s+(\d{1,4})\s*"
            r"(unidades?|uds?|u|botellas?|latas?|sobres?|bolsas?|paquetes?|porciones?)\b",
            original,
        )
        if coincidencia:
            factor = float(normalizar_numero(coincidencia.group(1)) or 0) or None
    if factor is not None and factor <= 1:
        factor = None
    unidad = None
    if base is not None and posicion_base is not None:
        prefijo = original[:posicion_base]
        for patron, canonica in PALABRAS_UNIDAD:
            if canonica in EMPAQUES_CANONICOS and re.search(
                rf"(?i)\b(?:{patron})\b", prefijo
            ):
                return canonica, factor, base
    for patron, canonica in PALABRAS_UNIDAD:
        if re.search(rf"(?i)\b(?:{patron})\b", original):
            unidad = canonica
            break
    return unidad, factor, base


def unidad_canonica(palabra: str) -> Optional[str]:
    n = normalizar_texto(palabra)
    for patron, canonica in PALABRAS_UNIDAD:
        if re.fullmatch(patron, n):
            return canonica
    return None


def es_palabra_empaque(texto: Optional[str]) -> bool:
    n = normalizar_texto(texto)
    return bool(n) and (n in PALABRAS_EMPAQUE or n in {p for p in PALABRAS_EMPAQUE})


def limpiar_nombre(texto: Any) -> str:
    original = str(texto or "").strip()
    limpio = re.sub(r"^[\s\-\*\u2022•]+", "", original)
    limpio = re.sub(r"^\d+[.)]\s*", "", limpio)
    limpio = re.sub(r"(?i)\s+x\s*\d+\s*$", "", limpio)
    limpio = re.sub(
        r"(?i)\s+(cajillas?|cajas?|cajones?|cajón|sacos?|fardos?|bultos?|cubetas?|"
        r"dispensadores?|manojos?|quintales?|bandejas?|canastas?|packs?|galones?|galón)"
        r"\s*(?:de|con)?\s*\d+(?:[.,]\d+)?\s*[a-zA-Z]*\s*$",
        "", limpio,
    )
    limpio = re.sub(
        r"(?i)\s+\d+(?:[.,]\d+)?\s*(kg|kgs?|kilos?|g|gr|gramos?|lb|libras?|oz|onzas?|"
        r"l|lt|litros?|ml|mililitros?|unidades?|uds?|u|botellas?|latas?|docenas?|pares?|"
        r"bolsas?|paquetes?|porciones?)\s*$",
        "", limpio,
    )
    limpio = re.sub(
        r"(?i)\s+(kg|kgs?|kilos?|g|gr|gramos?|lb|libras?|oz|onzas?|l|lt|litros?|ml|"
        r"mililitros?|unidades?|uds?|botellas?|latas?|docenas?|pares?|bolsas?|paquetes?|porciones?)\s*$",
        "", limpio,
    )
    limpio = re.sub(r"\s{2,}", " ", limpio).strip(" .,-|;:")
    return limpio[:100] or original[:100]


def mapear_items_ia(datos: Any) -> list[FilaDetectada]:
    items = datos.get("items") if isinstance(datos, dict) else datos
    if not isinstance(items, list):
        return []
    resultado: list[FilaDetectada] = []
    for indice, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        nombre = limpiar_nombre(item.get("nombre") or item.get("producto") or item.get("descripcion"))
        if not nombre:
            continue
        cantidad = normalizar_numero(item.get("cantidad")) or Decimal("1")
        precio_unitario = normalizar_numero(item.get("precio_unitario") or item.get("precio"))
        precio_total = normalizar_numero(item.get("precio_total") or item.get("total"))
        factor = normalizar_numero(item.get("factor_empaque") or item.get("factor"))
        if precio_unitario is None and precio_total is not None and cantidad > 0:
            precio_unitario = precio_total / cantidad
        if precio_total is None and precio_unitario is not None:
            precio_total = precio_unitario * cantidad
        resultado.append(FilaDetectada(
            nombre=nombre,
            cantidad=cuantizar(cantidad) or Decimal("1.00"),
            unidad_texto=(str(item.get("unidad")).strip() if item.get("unidad") else None),
            precio_unitario=cuantizar(precio_unitario),
            precio_total=cuantizar(precio_total),
            categoria_texto=(str(item.get("categoria")).strip() if item.get("categoria") else None),
            factor_empaque=float(factor) if factor and factor > 1 else None,
            notas=(str(item.get("notas")).strip()[:300] if item.get("notas") else None),
            confianza=0.75,
            fila=indice,
        ))
        if len(resultado) >= 500:
            break
    return resultado


def cobertura_precio(filas: list[FilaDetectada]) -> float:
    if not filas:
        return 0.0
    return sum(1 for f in filas if f.precio_unitario is not None or f.precio_total is not None) / len(filas)
