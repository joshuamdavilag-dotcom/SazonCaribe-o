"""Cliente de Gemini: generación de texto/JSON y clasificador de alcance."""

import json
import logging
import time
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# Errores transitorios: se reintenta con otro modelo / con espera.
CODIGOS_REINTENTO = (429, 500, 502, 503, 504)
# El modelo ya no está disponible para esta cuenta.
CODIGOS_MODELO_INVALIDO = (404,)

# Modelos que rechazan generationConfig.thinkingConfig (los "lite" lo hacen):
# se aprenden en la primera llamada y se omiten en las siguientes.
MODELOS_SIN_THINKING: set[str] = set()

SISTEMA_CLASIFICADOR = (
    "Eres el clasificador de alcance de un asistente interno de un restaurante. "
    "Devuelve SI si la consulta trata sobre el negocio del restaurante "
    "(ventas, ingresos, compras, insumos, inventario, menu, platillos, recetas, "
    "personal, turnos, nomina, gastos, caja, clientes, zonas/mesas, marketing, "
    "promociones, precios, competencia gastronomica, temporadas, finanzas, "
    "operacion del local) o sobre como usar este sistema POS. "
    "Devuelve NO si trata de cualquier otro tema (entretenimiento, deportes, "
    "politica, ciencia, programacion general, tareas escolares, chistes, etc.). "
    "Responde SOLO: SI o NO."
)


def _texto_de_respuesta(datos: dict) -> str:
    """Extrae el texto de una respuesta de generateContent."""
    candidatos = datos.get("candidates") or []
    if not candidatos:
        return ""
    partes = (candidatos[0].get("content") or {}).get("parts") or []
    fragmentos = [
        parte.get("text", "")
        for parte in partes
        if isinstance(parte, dict) and not parte.get("thought")
    ]
    return "".join(fragmentos).strip()


class GeminiService:
    """Acceso a Gemini con rotación de modelos y reintentos."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: Optional[str] = None,
        modelos_respaldo: Optional[str] = None,
        timeout: Optional[int] = None,
        max_intentos: Optional[int] = None,
    ) -> None:
        ajustes = get_settings()
        self.api_key = (
            ajustes.GEMINI_API_KEY if api_key is None else api_key
        ).strip()
        self.modelo = (modelo or ajustes.GEMINI_MODEL).strip()
        respaldo = (
            ajustes.GEMINI_MODELOS_RESPALDO if modelos_respaldo is None else modelos_respaldo
        )
        self.modelos_respaldo = [
            nombre.strip() for nombre in (respaldo or "").split(",") if nombre.strip()
        ]
        self.timeout = timeout or ajustes.GEMINI_TIMEOUT
        self.max_intentos = max(1, max_intentos or ajustes.GEMINI_MAX_INTENTOS)

    @property
    def disponible(self) -> bool:
        """Indica si hay una API key configurada."""
        return bool(self.api_key)

    def _modelos(self) -> list[str]:
        modelos: list[str] = []
        for nombre in [self.modelo, *self.modelos_respaldo]:
            if nombre and nombre not in modelos:
                modelos.append(nombre)
        return modelos

    def exigir_configuracion(self) -> None:
        """Lanza 503 si falta la API key."""
        if not self.disponible:
            raise HTTPException(
                status_code=503,
                detail=(
                    "El asistente de IA no está configurado. "
                    "Agrega GEMINI_API_KEY en las variables de entorno."
                ),
            )

    @staticmethod
    def _payload(
        sistema: Optional[str],
        mensaje: str,
        json_mode: bool,
        temperatura: float,
        max_tokens: int,
        con_thinking: bool = True,
    ) -> dict:
        configuracion: dict[str, Any] = {
            "temperature": temperatura,
            "maxOutputTokens": max_tokens,
        }
        if con_thinking:
            # Los modelos Flash piensan antes de responder y agotan el cupo
            # de salida cuando se pide una respuesta corta.
            configuracion["thinkingConfig"] = {"thinkingBudget": 0}
        if json_mode:
            configuracion["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": mensaje}]}],
            "generationConfig": configuracion,
        }
        if sistema:
            payload["systemInstruction"] = {"parts": [{"text": sistema}]}
        return payload

    def _post(self, modelo: str, payload: dict) -> httpx.Response:
        with httpx.Client(timeout=self.timeout) as cliente:
            return cliente.post(
                f"{BASE_URL}/{modelo}:generateContent",
                params={"key": self.api_key},
                json=payload,
            )

    def generar(
        self,
        mensaje: str,
        sistema: Optional[str] = None,
        json_mode: bool = False,
        temperatura: float = 0.4,
        max_tokens: int = 4096,
    ) -> tuple[str, str]:
        """Genera una respuesta. Devuelve ``(texto, modelo_usado)``.

        Rota entre el modelo principal y los de respaldo ante 429/5xx/400, y
        reintenta con espera creciente. Los modelos que rechazan
        ``thinkingConfig`` se detectan y se reintentan sin él. Si todo falla
        lanza HTTPException 502.
        """
        self.exigir_configuracion()

        modelos = self._modelos()
        ultimo_error = "sin respuesta del proveedor"
        intentos = max(self.max_intentos, len(modelos))

        for intento in range(intentos):
            modelo = modelos[intento % len(modelos)]
            con_thinking = modelo not in MODELOS_SIN_THINKING
            payload = self._payload(
                sistema, mensaje, json_mode, temperatura, max_tokens, con_thinking
            )
            try:
                respuesta = self._post(modelo, payload)
            except httpx.HTTPError as error:
                ultimo_error = f"error de red con {modelo}: {error}"
                logger.warning("[GEMINI] %s", ultimo_error)
                time.sleep(min(2 * (intento + 1), 8))
                continue

            if respuesta.status_code == 400 and con_thinking:
                try:
                    estado_error = (respuesta.json().get("error") or {}).get("status")
                except Exception:
                    estado_error = None
                if estado_error == "INVALID_ARGUMENT":
                    MODELOS_SIN_THINKING.add(modelo)
                    logger.warning(
                        "[GEMINI] %s no acepta thinkingConfig; se reintenta sin él", modelo
                    )
                    try:
                        respuesta = self._post(
                            modelo,
                            self._payload(
                                sistema,
                                mensaje,
                                json_mode,
                                temperatura,
                                max_tokens,
                                False,
                            ),
                        )
                    except httpx.HTTPError as error:
                        ultimo_error = f"error de red con {modelo}: {error}"
                        logger.warning("[GEMINI] %s", ultimo_error)
                        continue

            if respuesta.status_code == 200:
                datos = respuesta.json()
                texto = _texto_de_respuesta(datos)
                if texto:
                    return texto, modelo
                candidato = (datos.get("candidates") or [{}])[0]
                ultimo_error = (
                    f"{modelo} no devolvió texto "
                    f"(finishReason={candidato.get('finishReason')})"
                )
                logger.warning("[GEMINI] %s", ultimo_error)
                continue

            detalle = ""
            try:
                detalle = respuesta.json()["error"]["message"]
            except Exception:
                detalle = respuesta.text[:200]
            ultimo_error = f"{modelo} respondió HTTP {respuesta.status_code}: {detalle}"

            if respuesta.status_code in CODIGOS_MODELO_INVALIDO:
                logger.warning("[GEMINI] Modelo no disponible: %s", modelo)
                continue

            if respuesta.status_code == 400:
                logger.warning("[GEMINI] Solicitud rechazada por %s: %s", modelo, detalle)
                continue

            if respuesta.status_code in CODIGOS_REINTENTO:
                logger.warning("[GEMINI] %s", ultimo_error)
                time.sleep(min(2 * (intento + 1), 8))
                continue

            logger.error("[GEMINI] Error no recuperable: %s", ultimo_error)
            raise HTTPException(
                status_code=502,
                detail=f"Gemini rechazó la solicitud: {detalle or respuesta.status_code}",
            )

        logger.error("[GEMINI] Se agotaron los intentos: %s", ultimo_error)
        raise HTTPException(
            status_code=502,
            detail=(
                "No se pudo obtener respuesta de la IA en este momento. "
                "Intenta de nuevo en unos minutos."
            ),
        )

    def generar_json(
        self,
        mensaje: str,
        sistema: Optional[str] = None,
        temperatura: float = 0.3,
        max_tokens: int = 8192,
    ) -> tuple[dict, str]:
        """Genera y parsea una respuesta JSON. Devuelve ``(datos, modelo_usado)``."""
        texto, modelo = self.generar(
            mensaje,
            sistema=sistema,
            json_mode=True,
            temperatura=temperatura,
            max_tokens=max_tokens,
        )
        try:
            return json.loads(texto), modelo
        except json.JSONDecodeError:
            pass

        limpio = texto.strip()
        if limpio.startswith("```"):
            limpio = limpio.split("```", 2)[1] if limpio.count("```") >= 2 else limpio
            if limpio.lstrip().lower().startswith("json"):
                limpio = limpio.lstrip()[4:]
        inicio = limpio.find("{")
        fin = limpio.rfind("}")
        if inicio != -1 and fin > inicio:
            try:
                return json.loads(limpio[inicio : fin + 1]), modelo
            except json.JSONDecodeError:
                pass

        logger.error("[GEMINI] Respuesta no parseable como JSON: %s", texto[:400])
        raise HTTPException(
            status_code=502,
            detail="La IA devolvió un análisis con formato inválido. Intenta de nuevo.",
        )

    def es_consulta_del_negocio(self, mensaje: str) -> bool:
        """Clasifica si la consulta pertenece al negocio o al sistema POS."""
        texto, _modelo = self.generar(
            mensaje,
            sistema=SISTEMA_CLASIFICADOR,
            temperatura=0,
            max_tokens=16,
        )
        respuesta = texto.strip().upper()
        if respuesta.startswith("NO"):
            return False
        if respuesta.startswith("SI") or respuesta.startswith("SÍ"):
            return True
        logger.warning(
            "[GEMINI] Clasificador con respuesta ambigua (%r); se permite la consulta",
            texto[:40],
        )
        return True
