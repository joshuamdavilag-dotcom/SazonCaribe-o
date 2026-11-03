# Correos del sistema

La pantalla **Correos del Sistema** permite administrar destinatarios, elegir qué información incluye cada tipo de correo, revisar una vista previa, enviar informes y consultar el historial.

## Destinatarios

- Los usuarios activos con rol **Gerente**, empleado activo y correo en su perfil reciben automáticamente los envíos.
- El correo se agrega o edita desde **Personal**, en el perfil del empleado. La dirección se normaliza a minúsculas y se valida.
- También se pueden agregar destinatarios externos en la pantalla de Correos y seleccionarlos por tipo de envío. Las direcciones repetidas se consolidan.
- Un correo de prueba se envía únicamente a la dirección indicada y no incluye datos del negocio.

## Información compartida

Cada tipo de correo guarda su propia selección de secciones y destinatarios externos. Nómina y otros datos sensibles no se incluyen en la configuración inicial; solo se comparten si una persona autorizada los selecciona explícitamente. Si no se selecciona ninguna sección, el mensaje no incluye datos.

Los envíos automáticos usan la configuración guardada. La pantalla permite guardar cambios, revisar una vista previa y enviar el tipo elegido inmediatamente. Los correos automáticos quedan en la cola persistente y se procesan desde el watcher del servidor; los errores aparecen en el historial.

## Tipos de envío

El catálogo está definido en `app/core/correos.py`:

- **Cierre de caja** y **estudio de mercado listo**: se disparan por evento.
- **Resumen semanal**, **resumen mensual**, **stock bajo** y **auditoría**: se evalúan de forma programada.
- **Envío manual**: se inicia desde la pantalla.

Los tipos automáticos solo se pueden activar cuando existe al menos un destinatario efectivo: un gerente activo con correo o un destinatario externo activo seleccionado.

## Requisitos

Configurar en el entorno del servidor:

- `BREVO_API_KEY`
- `CORREO_REMITENTE` (dirección verificada en Brevo)
- Opcionalmente `CORREO_REMITENTE_NOMBRE`, `CORREO_TIMEOUT` y `CORREO_MAX_INTENTOS`

La pantalla y sus endpoints requieren el permiso `correos_gestionar`. La migración de arranque agrega la columna nullable `empleados.email` a instalaciones existentes.
