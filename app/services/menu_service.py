import base64
import time
import uuid
from io import BytesIO
from typing import Optional, List

import httpx
from PIL import Image, ImageOps
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings

from app.repositories.menu_repository import MenuRepository
from app.repositories.inventario_repository import InsumoRepository
from app.schemas.menu import (
    CategoriaMenuCreate,
    CategoriaMenuResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate
)
from app.schemas.menu_publico import (
    CategoriaMenuPublicaResponse,
    MenuItemPublicoResponse,
)


IMAGEN_ANCHO_MAX = 1080
IMAGEN_WEBP_CALIDAD = 80
IMAGEN_MAX_BYTES = 15 * 1024 * 1024   # 15 MB — el pipeline re-encodea a WebP ≤1080px de todos modos
IMGBB_INTENTOS = 3
IMGBB_BACKOFF_SEGUNDOS = 1.5


class MenuService:
    """
    Servicio de lógica de negocio para el módulo de menú.

    Coordina las operaciones de categorías, platos y recetas,
    validando la existencia de ingredientes en inventario.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa el servicio con las dependencias necesarias.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db
        self.menu_repo = MenuRepository(db)
        self.insumo_repo = InsumoRepository(db)

    # =========================================================================
    # Categorías
    # =========================================================================

    def crear_categoria(
        self,
        categoria_in: CategoriaMenuCreate
    ) -> CategoriaMenuResponse:
        """
        Crea una nueva categoría del menú.

        Args:
            categoria_in: Datos de la categoría a crear.

        Returns:
            CategoriaMenuResponse con la categoría creada.

        Raises:
            HTTPException 400: Si ya existe una categoría con ese nombre.
        """
        categorias = self.menu_repo.obtener_categorias()
        for cat in categorias:
            if cat.nombre.lower() == categoria_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe una categoría con el nombre '{categoria_in.nombre}'"
                )

        categoria_creada = self.menu_repo.crear_categoria(categoria_in)
        return CategoriaMenuResponse.model_validate(categoria_creada)

    def obtener_categorias(self) -> List[CategoriaMenuResponse]:
        """
        Lista todas las categorías del menú.

        Returns:
            Lista de CategoriaMenuResponse.
        """
        categorias = self.menu_repo.obtener_categorias()
        return [CategoriaMenuResponse.model_validate(c) for c in categorias]

    def eliminar_categoria(self, categoria_id: int) -> None:
        categoria = self.menu_repo.obtener_categoria_por_id(categoria_id)
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la categoría con ID {categoria_id}"
            )
        count = self.menu_repo.contar_items_por_categoria(categoria_id)
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar la categoría '{categoria.nombre}': tiene {count} platillo(s) asociado(s). Reasigna o elimina los platillos primero."
            )
        self.menu_repo.eliminar_categoria(categoria_id)

    # =========================================================================
    # Platos y Recetas
    # =========================================================================

    def crear_menu_item(
        self,
        item_in: MenuItemCreate
    ) -> MenuItemResponse:
        """
        Crea un nuevo plato en el menú con su receta.

        Flujo de validación:
        1. Verifica que la categoría exista.
        2. Si tiene ingredientes, verifica que cada uno exista en inventario.
        3. Si todo es válido, crea el plato con su receta.

        Args:
            item_in: Datos del plato y su receta (opcional).

        Returns:
            MenuItemResponse con el plato creado.

        Raises:
            HTTPException 404: Si la categoría o algún ingrediente no existe.
            HTTPException 400: Si ya existe un plato con ese nombre.
        """
        from app.models.menu import CategoriaMenu
        from sqlalchemy import select

        statement = select(CategoriaMenu).where(
            CategoriaMenu.id == item_in.categoria_id
        )
        categoria = self.db.execute(statement).scalar_one_or_none()

        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró la categoría con ID {item_in.categoria_id}"
            )

        if item_in.receta:
            for receta in item_in.receta:
                insumo = self.insumo_repo.get_by_id(
                    receta.insumo_id
                )
                if not insumo:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"El insumo con ID {receta.insumo_id} "
                            f"no existe en el inventario"
                        )
                    )

        items_existentes = self.menu_repo.obtener_items(
            incluir_inactivos=True
        )
        for item in items_existentes:
            if item.nombre.lower() == item_in.nombre.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un plato con el nombre '{item_in.nombre}'"
                )

        item_creado = self.menu_repo.crear_menu_item(item_in)
        return MenuItemResponse.model_validate(item_creado)

    def obtener_items(
        self,
        categoria_id: Optional[int] = None,
        incluir_inactivos: bool = False
    ) -> List[MenuItemResponse]:
        """
        Obtiene los platos del menú.

        Args:
            categoria_id: Si se proporciona, filtra por esta categoría.
            incluir_inactivos: Si True, incluye platos desactivados (borrado lógico).

        Returns:
            Lista de MenuItemResponse con sus recetas e ingredientes.
        """
        items = self.menu_repo.obtener_items(
            categoria_id,
            incluir_inactivos=incluir_inactivos
        )
        return [MenuItemResponse.model_validate(i) for i in items]

    def obtener_item_por_id(self, item_id: int) -> MenuItemResponse:
        """
        Obtiene un plato del menú por su ID.

        Args:
            item_id: ID del plato.

        Returns:
            MenuItemResponse con el plato y sus relaciones.

        Raises:
            HTTPException 404: Si el plato no existe.
        """
        item = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )
        return MenuItemResponse.model_validate(item)

    def actualizar_menu_item(
        self,
        item_id: int,
        item_in: MenuItemUpdate
    ) -> MenuItemResponse:
        """
        Actualiza un plato del menú con datos parciales.

        Flujo de validación:
        1. Verifica que el plato exista.
        2. Si se cambia la categoría, verifica que la nueva exista.
        3. Si se cambia la receta, verifica que cada ingrediente exista.
        4. Verifica unicidad del nombre si se está cambiando.

        Args:
            item_id: ID del plato a actualizar.
            item_in: Datos parciales a actualizar.

        Returns:
            MenuItemResponse con el plato actualizado.

        Raises:
            HTTPException 404: Si el plato, categoría o ingrediente no existe.
            HTTPException 400: Si el nombre ya está en uso por otro plato.
        """
        existing = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )

        if item_in.categoria_id is not None:
            from app.models.menu import CategoriaMenu
            from sqlalchemy import select
            statement = select(CategoriaMenu).where(
                CategoriaMenu.id == item_in.categoria_id
            )
            categoria = self.db.execute(statement).scalar_one_or_none()
            if not categoria:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontró la categoría con ID {item_in.categoria_id}"
                )

        if item_in.ingredientes_receta is not None:
            for receta in item_in.ingredientes_receta:
                insumo = self.insumo_repo.get_by_id(
                    receta.insumo_id
                )
                if not insumo:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=(
                            f"El insumo con ID {receta.insumo_id} "
                            f"no existe en el inventario"
                        )
                    )

        if item_in.nombre is not None and item_in.nombre.lower() != existing.nombre.lower():
            items_existentes = self.menu_repo.obtener_items(
                incluir_inactivos=True
            )
            for item in items_existentes:
                if item.id != item_id and item.nombre.lower() == item_in.nombre.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ya existe otro plato con el nombre '{item_in.nombre}'"
                    )

        item_actualizado = self.menu_repo.actualizar_menu_item(item_id, item_in)
        return MenuItemResponse.model_validate(item_actualizado)

    def eliminar_platillo(self, item_id: int) -> dict:
        """
        Elimina un plato del menú con la regla borrar/archivar.

        - Sin historial de ventas: lo elimina físicamente (junto con su
          receta vía cascada ORM). El nombre queda libre de inmediato.
        - Con historial de ventas: lo archiva renombrando su ``nombre`` a
          ``{nombre}_deleted_{id}`` y marcándolo ``disponible = False``.
          El historial se conserva y el nombre original queda libre para
          reutilizarse en un plato nuevo.

        Args:
            item_id: ID del plato a eliminar.

        Returns:
            Dict con ``resultado`` ('eliminado' | 'archivado') y ``mensaje``.

        Raises:
            HTTPException 404: Si el plato no existe.
        """
        from sqlalchemy.exc import IntegrityError

        existing = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )

        ventas = self.menu_repo.contar_ventas(item_id)
        if ventas == 0:
            try:
                self.menu_repo.eliminar_menu_item_fisico(item_id)
            except IntegrityError:
                self.db.rollback()
                return self._archivar_platillo(item_id, existing.nombre)
            return {
                "resultado": "eliminado",
                "mensaje": (
                    f"'{existing.nombre}' fue eliminado permanentemente "
                    f"(no tenía ventas registradas)."
                ),
            }

        return self._archivar_platillo(item_id, existing.nombre)

    def _archivar_platillo(self, item_id: int, nombre: str) -> dict:
        """
        Archiva un plato conservando su historial: libera el nombre original
        renombrándolo con el sufijo ``_deleted_{id}`` (idempotente) y lo marca
        no disponible. Si el nombre ya existe (colisión), agrega un sufijo corto.

        Args:
            item_id: ID del plato a archivar.
            nombre: Nombre actual del plato.

        Returns:
            Dict con ``resultado`` 'archivado' y ``mensaje``.
        """
        from sqlalchemy.exc import IntegrityError

        sufijo = f"_deleted_{item_id}"
        max_len = 100
        nombre_archivo = self._nombre_archivado(nombre, item_id, max_len)

        try:
            self.menu_repo.marcar_archivado(item_id, nombre_archivo)
        except IntegrityError:
            self.db.rollback()
            parte = nombre[: max(1, max_len - 8 - len(sufijo))]
            nombre_archivo = f"{parte}_{uuid.uuid4().hex[:6]}{sufijo}"
            self.menu_repo.marcar_archivado(item_id, nombre_archivo)

        return {
            "resultado": "archivado",
            "mensaje": (
                f"'{nombre}' fue archivado: tiene historial de ventas, se "
                f"conservó bajo '{nombre_archivo}' y el nombre original quedó "
                f"disponible para un nuevo plato."
            ),
        }

    def _nombre_archivado(self, valor: str, pk: int, max_len: int) -> str:
        """
        Genera el nombre archivado ``{valor}_deleted_{pk}`` truncando la base
        para respetar el largo máximo de la columna.

        Args:
            valor: Nombre original.
            pk: ID del registro (sufijo de unicidad).
            max_len: Largo máximo de la columna.

        Returns:
            El nombre archivado, o el mismo valor si ya tenía el sufijo.
        """
        sufijo = f"_deleted_{pk}"
        if valor.endswith(sufijo):
            return valor
        return f"{valor[: max_len - len(sufijo)]}{sufijo}"

    def _procesar_imagen_webp(self, contenido: bytes) -> bytes:
        """
        Optimiza la imagen antes de enviarla a ImgBB.

        Pipeline:
        1. Corrige la orientación EXIF (fotos de celular).
        2. Redimensiona a un ancho máximo de 1080px manteniendo el aspect ratio.
        3. Convierte a WebP con calidad 80%.

        Args:
            contenido: Bytes de la imagen original.

        Returns:
            Bytes de la imagen optimizada en formato WebP.

        Raises:
            HTTPException 400: Si el archivo no es una imagen válida.
        """
        try:
            prerender = Image.open(BytesIO(contenido))
            prerender.verify()
            img = Image.open(BytesIO(contenido))
            img = ImageOps.exif_transpose(img) or img

            if img.width > IMAGEN_ANCHO_MAX:
                alto = round(img.height * IMAGEN_ANCHO_MAX / img.width)
                img = img.resize(
                    (IMAGEN_ANCHO_MAX, alto),
                    Image.Resampling.LANCZOS
                )

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")

            buffer = BytesIO()
            img.save(
                buffer,
                format="WEBP",
                quality=IMAGEN_WEBP_CALIDAD,
                method=6
            )
            return buffer.getvalue()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo no contiene una imagen válida"
            )

    def subir_imagen(self, item_id: int, archivo) -> MenuItemResponse:
        """
        Sube y asigna la imagen de un plato a ImgBB (almacenamiento permanente).

        El gerente selecciona un archivo desde el ERP; el servidor lo optimiza
        (resize + WebP) y lo envía a ImgBB, almacenando la URL pública en la
        base de datos. Las imágenes son permanentes y sobreviven redeployes.

        Flujo:
        1. Verifica que el plato exista.
        2. Valida tamaño <= 15 MB.
        3. Valida la imagen por CONTENIDO con Pillow (independiente de MIME/extensión).
        4. Optimiza la imagen: ancho máximo 1080px + WebP calidad 80%.
        5. Codifica a Base64 y envía a ImgBB (con reintentos ante fallos transitorios).
        6. Extrae la URL de la respuesta exitosa.
        7. Persiste imagen_url y retorna el plato actualizado.

        Args:
            item_id: ID del plato.
            archivo: UploadFile con la imagen a almacenar.

        Returns:
            MenuItemResponse con la imagen asignada.

        Raises:
            HTTPException 404: Si el plato no existe.
            HTTPException 400: Si el archivo no es una imagen válida o excede 15 MB.
            HTTPException 502: Si ImgBB retorna un error o no responde.
            HTTPException 500: Si IMGBB_API_KEY no está configurada.
        """
        settings = get_settings()

        item = self.menu_repo.obtener_menu_item_por_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato con ID {item_id}"
            )

        if not archivo or not getattr(archivo, "filename", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se recibió ningún archivo de imagen"
            )

        contenido = archivo.file.read()
        if len(contenido) > IMAGEN_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen supera el tamaño máximo de 15 MB"
            )

        if not settings.IMGBB_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="IMGBB_API_KEY no configurada en el servidor"
            )

        # Validación por contenido: Pillow decide si el archivo es una imagen
        # (ignora MIME/extensión, que varía según el dispositivo). Formatos no
        # soportados (p. ej. HEIC sin convertir) lanzan 400 con mensaje claro.
        contenido_optimizado = self._procesar_imagen_webp(contenido)
        b64_image = base64.b64encode(contenido_optimizado).decode("utf-8")

        # Reintentos con backoff ante fallos transitorios de red o 5xx de ImgBB.
        response = None
        for intento in range(IMGBB_INTENTOS):
            try:
                response = httpx.post(
                    "https://api.imgbb.com/1/upload",
                    data={
                        "key": settings.IMGBB_API_KEY,
                        "image": b64_image,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500 or intento == IMGBB_INTENTOS - 1:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Error de ImgBB: {e.response.status_code}"
                    )
            except httpx.RequestError:
                if intento == IMGBB_INTENTOS - 1:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="No se pudo conectar con ImgBB"
                    )
            time.sleep(IMGBB_BACKOFF_SEGUNDOS * (intento + 1))

        result = response.json()
        if not result.get("success"):
            error_msg = result.get("error", {}).get("message", "Error desconocido de ImgBB")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ImgBB rechazó la imagen: {error_msg}"
            )

        imagen_url = result["data"]["url"]

        item_actualizado = self.menu_repo.actualizar_imagen_url(
            item_id,
            imagen_url
        )
        return MenuItemResponse.model_validate(item_actualizado)

    # =========================================================================
    # Consultas públicas (futura Carta Digital) — solo lectura
    # =========================================================================

    def obtener_categorias_publicas(self) -> List[CategoriaMenuPublicaResponse]:
        """
        Lista las categorías del menú para consumo público.

        Reutiliza la consulta existente del repositorio. Solo expone datos de
        exhibición (id, nombre, descripción), sin información administrativa.

        Returns:
            Lista de CategoriaMenuPublicaResponse.
        """
        categorias = self.menu_repo.obtener_categorias()
        return [
            CategoriaMenuPublicaResponse.model_validate(c)
            for c in categorias
        ]

    def obtener_menu_publico(
        self,
        categoria_id: Optional[int] = None
    ) -> List[MenuItemPublicoResponse]:
        """
        Lista los platos disponibles para la carta pública.

        Reutiliza la consulta pública del repositorio, que no carga recetas ni
        insumos (información interna del inventario). Solo devuelve platos con
        ``disponible = True``.

        Args:
            categoria_id: Si se proporciona, filtra por esta categoría.

        Returns:
            Lista de MenuItemPublicoResponse.
        """
        items = self.menu_repo.obtener_items_publicos(categoria_id)
        return [MenuItemPublicoResponse.model_validate(i) for i in items]

    def obtener_item_publico_por_id(self, item_id: int) -> MenuItemPublicoResponse:
        """
        Obtiene un plato disponible por su ID para la carta pública.

        Args:
            item_id: ID del plato.

        Returns:
            MenuItemPublicoResponse con los datos de exhibición del plato.

        Raises:
            HTTPException 404: Si el plato no existe o no está disponible.
        """
        item = self.menu_repo.obtener_item_publico_por_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el plato disponible con ID {item_id}"
            )
        return MenuItemPublicoResponse.model_validate(item)
