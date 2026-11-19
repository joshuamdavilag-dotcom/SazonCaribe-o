"""
Controladores HTTP agrupados por dominio de negocio.
"""

from app.api.endpoints.personal import router as personal_router

__all__ = [
    "personal_router"
]
