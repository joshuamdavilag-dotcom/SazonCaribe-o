"""Novedades del sistema (control de cambios visible para el equipo).

Cada vez que se publica una actualización se agrega una entrada al inicio de
``NOVEDADES`` con un ``version`` nuevo. Al arrancar, ``NovedadService``
siembra las entradas que falten en la base de datos y envía un aviso push a
todos los usuarios la primera vez.

Reglas:
- ``version`` es único y no se reutiliza.
- ``publicada_en`` ordena el historial (formato ISO: ``YYYY-MM-DDTHH:MM``).
- El texto es para el usuario final: sin nombres de tablas ni de archivos.
"""

NOVEDADES = [
    {
        "version": "1.2.0",
        "publicada_en": "2026-10-28T18:00",
        "titulo": "Notificaciones más limpias y avisos de novedades",
        "resumen": (
            "El panel de notificaciones quedó más ordenado: los ajustes de "
            "avisos ahora se pliegan, cada aviso se puede descartar y cada "
            "actualización del sistema avisa a todo el equipo con su resumen."
        ),
        "detalle": [
            "Los ajustes de avisos push están dentro de un botón desplegable, así la lista de notificaciones se ve completa.",
            "Cada aviso tiene una ✕ para descartarlo y hay un botón para limpiar de una vez todos los que ya viste.",
            "Ya no se repiten el reloj y la fecha en varias partes de la misma pantalla.",
            "Cada actualización del sistema se publica como novedad y llega por notificación a todos los usuarios con un resumen de lo que cambió.",
        ],
    },
    {
        "version": "1.1.0",
        "publicada_en": "2026-10-28T12:00",
        "titulo": "El sistema abre y navega más rápido",
        "resumen": (
            "La primera carga y el cambio entre pantallas son más rápidos, y "
            "el Cierre de Caja responde mejor aunque el histórico sea grande."
        ),
        "detalle": [
            "El ERP ya no descarga la librería de estilos desde internet: ahora usa una hoja propia mucho más liviana.",
            "El sistema, los estilos y las respuestas de la API viajan comprimidos: se descargan hasta 4 veces más rápido.",
            "Las imágenes y logos quedan guardados en el navegador 7 días.",
            "Se optimizaron las consultas de reportes, caja y los índices de la base de datos.",
        ],
    },
    {
        "version": "1.0.0",
        "publicada_en": "2026-10-27T20:00",
        "titulo": "Cierre de caja automático",
        "resumen": (
            "La caja se cierra sola todos los días a medianoche (hora de "
            "Managua) y la venta del día queda archivada sin intervención."
        ),
        "detalle": [
            "Nuevo interruptor en Cierre de Caja para activar o desactivar el cierre automático.",
            "El cierre archiva las órdenes pagadas y los gastos del día, aunque no haya ventas registradas.",
            "Cada cierre automático queda en la bitácora de auditoría.",
        ],
    },
]
