"""Extracción de texto de documentos para el Estudio de Mercado."""

import io
import logging
import os
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

EXTENSIONES_PERMITIDAS = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xlsm",
    ".xls",
    ".csv",
    ".txt",
    ".md",
}

MAX_BYTES_DOCUMENTO = 25 * 1024 * 1024


class ErrorExtraccion(Exception):
    """El documento no se pudo leer; el mensaje es apto para el usuario."""


def extension_de(nombre: str) -> str:
    """Devuelve la extensión en minúsculas, con punto."""
    return os.path.splitext(nombre or "")[1].lower()


def _decodificar(contenido: bytes) -> str:
    for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="replace")


def _extraer_pdf(contenido: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover
        raise ErrorExtraccion("Falta la dependencia pypdf en el servidor.") from error
    try:
        lector = PdfReader(io.BytesIO(contenido))
        paginas = [(pagina.extract_text() or "") for pagina in lector.pages]
    except Exception as error:
        raise ErrorExtraccion(
            "No se pudo leer el PDF. Verifica que no esté dañado ni protegido con contraseña."
        ) from error
    return "\n".join(paginas)


def _extraer_docx(contenido: bytes) -> str:
    try:
        import docx
    except ImportError as error:  # pragma: no cover
        raise ErrorExtraccion("Falta la dependencia python-docx en el servidor.") from error
    try:
        documento = docx.Document(io.BytesIO(contenido))
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ErrorExtraccion(
            "El archivo .doc antiguo no se puede leer. "
            "Ábrelo en Word y guárdalo como .docx para volver a subirlo."
        ) from error
    except Exception as error:
        raise ErrorExtraccion("No se pudo leer el documento de Word.") from error

    partes = [parrafo.text for parrafo in documento.paragraphs if parrafo.text.strip()]
    for tabla in documento.tables:
        for fila in tabla.rows:
            celdas = [celda.text.strip() for celda in fila.cells]
            if any(celdas):
                partes.append(" | ".join(celdas))
    return "\n".join(partes)


def _extraer_excel(contenido: bytes) -> str:
    try:
        import openpyxl
    except ImportError as error:  # pragma: no cover
        raise ErrorExtraccion("Falta la dependencia openpyxl en el servidor.") from error
    try:
        libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True, read_only=True)
    except Exception as error:
        raise ErrorExtraccion(
            "No se pudo leer el archivo de Excel. "
            "Si es un .xls antiguo, guárdalo como .xlsx y vuelve a subirlo."
        ) from error

    partes: list[str] = []
    try:
        for hoja in libro.worksheets:
            partes.append(f"## Hoja: {hoja.title}")
            for fila in hoja.iter_rows(values_only=True):
                valores = [str(valor).strip() for valor in fila if valor not in (None, "")]
                if valores:
                    partes.append(" | ".join(valores))
    finally:
        libro.close()
    return "\n".join(partes)


def extraer_texto(nombre: str, contenido: bytes) -> tuple[str, str]:
    """Extrae el texto del documento.

    Devuelve ``(texto, tipo_archivo)``. Lanza :class:`ErrorExtraccion` con un
    mensaje en español cuando el formato no es soportado o el archivo está dañado.
    """
    extension = extension_de(nombre)
    if not extension:
        raise ErrorExtraccion(
            "El archivo no tiene extensión reconocible. Usa PDF, DOCX, XLSX, CSV o TXT."
        )
    if extension not in EXTENSIONES_PERMITIDAS:
        raise ErrorExtraccion(
            f"El formato {extension} no está soportado. Usa PDF, DOCX, XLSX, CSV o TXT."
        )
    if len(contenido) > MAX_BYTES_DOCUMENTO:
        raise ErrorExtraccion("El documento supera el máximo de 25 MB.")
    if not contenido:
        raise ErrorExtraccion("El archivo está vacío.")

    if extension == ".pdf":
        texto = _extraer_pdf(contenido)
    elif extension in (".docx", ".doc"):
        texto = _extraer_docx(contenido)
    elif extension in (".xlsx", ".xlsm", ".xls"):
        texto = _extraer_excel(contenido)
    else:
        texto = _decodificar(contenido)

    texto = texto.strip()
    if not texto:
        raise ErrorExtraccion(
            "No se encontró texto en el documento. "
            "Si es un PDF escaneado, súbelo como imagen o pega el contenido."
        )
    return texto, extension.lstrip(".").upper()
