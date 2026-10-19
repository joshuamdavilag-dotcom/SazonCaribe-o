# Cámaras de seguridad

El POS muestra los streams autorizados mediante WebRTC/WHEP. RTSP se mantiene dentro de la red del local: no se guarda en la base de datos ni se publica al navegador. Los clips se graban manualmente desde el stream visible y se guardan en el almacenamiento persistente del servidor POS.

## API

Todas las rutas, excepto `/authorize`, usan autenticación POS. Los endpoints de gestión son exclusivos de Administrador/Gerente; el acceso a cámaras y clips se filtra por permisos individuales de usuario.

| Método | Ruta bajo `/api/v1/cameras` | Uso |
|---|---|---|
| `GET` | `/` | Listar cámaras visibles al usuario |
| `POST` | `/` | Crear cámara (Administrador/Gerente) |
| `PATCH` | `/{camera_id}` | Editar nombre, ruta o estado (Administrador/Gerente) |
| `PUT` | `/{camera_id}/access` | Reemplazar permisos individuales (Administrador/Gerente) |
| `GET` | `/eligible-users` | Listar vendedores activos (Administrador/Gerente) |
| `GET` | `/storage` | Consultar espacio y uso de clips (Administrador/Gerente) |
| `POST` | `/{camera_id}/stream-token` | Emitir JWT WebRTC acotado a cámara y de 5 minutos |
| `POST` | `/authorize` | Callback sin token POS para validar la lectura del puente |
| `GET` | `/clips` | Listar clips completos de cámaras autorizadas |
| `POST` | `/{camera_id}/clips` | Crear una grabación manual |
| `PUT` | `/{camera_id}/clips/{clip_id}/chunks/{sequence}` | Añadir fragmento de hasta 16 MiB |
| `POST` | `/{camera_id}/clips/{clip_id}/finish` | Finalizar y publicar el clip |
| `DELETE` | `/{camera_id}/clips/{clip_id}` | Cancelar una grabación |
| `GET` | `/clips/{clip_id}/video` | Reproducir un clip completo autorizado |
| `DELETE` | `/clips/{clip_id}` | Eliminar un clip autorizado |

El modelo persistente está en `app/models/camera.py`, los contratos y validación en `app/schemas/camera.py`, las rutas HTTP en `app/api/endpoints/cameras.py` y las reglas de autorización/retención en `app/services/camera_service.py`.

## Requisitos de red

1. Instalar MediaMTX en una PC/servidor del local con acceso LAN al NVR o a las cámaras.
2. Asignar un DNS público al puente y configurar TLS válido para el host.
3. Publicar el endpoint WebRTC por HTTPS (TCP 8889 o un reverse proxy) y el transporte WebRTC UDP (8189). Si el router/ISP bloquea el UDP, hace falta una ruta TURN accesible; sin una ruta de medios entrante, el video no puede llegar desde fuera del local.
4. No publicar el RTSP de cámaras (normalmente TCP 554), la API de administración de MediaMTX ni el panel del NVR. No usar port-forward del puerto RTSP a Internet.
5. El puente debe poder llamar por HTTPS al endpoint de autenticación del POS.

Ejemplo mínimo de `mediamtx.yml` (ajustar certificado, rutas RTSP, IP/DNS y el dominio del POS):

```yaml
authMethod: http
authHTTPAddress: https://POS_DOMINIO/api/v1/cameras/authorize

webrtcAddress: :8889
webrtcEncryption: yes
webrtcServerKey: /etc/mediamtx/tls/key.pem
webrtcServerCert: /etc/mediamtx/tls/cert.pem
webrtcAllowOrigins:
  - https://POS_DOMINIO
webrtcAdditionalHosts:
  - CAMARAS_DOMINIO
webrtcLocalUDPAddress: :8189
webrtcLocalTCPAddress: :8189

paths:
  entrada-principal:
    source: rtsp://USUARIO_NVR:CONTRASENA_NVR@192.168.1.20:554/ruta-del-stream
    sourceOnDemand: yes
```

Los valores RTSP sensibles existen únicamente en el archivo local de MediaMTX; protegerlo con permisos del sistema operativo y no subirlo a Git. Para cada cámara agregada en el POS, declarar una ruta MediaMTX con el mismo identificador (solo minúsculas, números, guion y guion bajo). Por ejemplo, el identificador `entrada-principal` corresponde a `https://CAMARAS_DOMINIO:8889/entrada-principal/whep`.

En la configuración de MediaMTX, `authHTTPAddress` usa la API del POS en cada apertura del stream. El navegador solicita un JWT restringido a una cámara, válido por 5 minutos, y lo envía como contraseña HTTP Basic del puente. El endpoint autoriza únicamente lecturas de una ruta activa y verifica los permisos actuales del usuario. No reutilizar el token normal de sesión para el stream. La respuesta WHEP debe exponer la cabecera `Location` por CORS para que el navegador pueda cerrar correctamente la sesión al desconectarse.

## Configuración del POS en Render

1. Agregar manualmente un **Persistent Disk** al servicio web de Render. El disco tiene costo y tamaño finito; se omite deliberadamente de `render.yaml` para no modificar facturación automáticamente. Montarlo, por ejemplo, en `/var/data`.
2. En las variables de entorno del servicio establecer:
   - `CAMERA_STORAGE_DIR=/var/data/camera-clips`
   - `CAMERA_BRIDGE_BASE_URL=https://CAMARAS_DOMINIO:8889`
   - `CAMERA_ICE_SERVERS_JSON` como arreglo JSON de URLs STUN/TURN que permitan negociar medios desde redes externas, sin usuarios ni contraseñas permanentes. Ejemplo de forma: `[{"urls":"stun:turn.ejemplo.com:3478"},{"urls":"turns:turn.ejemplo.com:5349"}]`.
   - Si se usa TURN, `CAMERA_TURN_SHARED_SECRET` con el secreto aleatorio configurado también en Coturn. El POS genera credenciales TURN temporales (5 minutos) solo para el usuario ya autorizado. No reutilizar la contraseña del NVR.
3. Configurar en MediaMTX el host HTTPS público del POS en `authHTTPAddress` y `webrtcAllowOrigins`.
4. Hacer una copia de seguridad diaria del Persistent Disk para el RPO acordado de 24 horas. El objetivo de recuperación de 4 horas requiere una persona responsable y un procedimiento de restauración; el servicio de la aplicación no crea snapshots del proveedor.

`CAMERA_BRIDGE_BASE_URL` debe ser un origen HTTPS, sin ruta ni credenciales. En desarrollo local se permite `http://localhost`/`http://127.0.0.1`. El POS solo almacena el nombre, el identificador de ruta y permisos; nunca la URL RTSP ni las contraseñas de la cámara.

## Uso y almacenamiento de clips

- Administrador/Gerente crean cámaras y asignan acceso individual a vendedores activos. Administrador/Gerente pueden ver todas; cada vendedor solo ve las cámaras asignadas.
- El clip captura el video que recibe el navegador; no se solicita ni se guarda audio.
- No hay duración máxima por clip. Los fragmentos se suben cada 5 segundos, por lo que el video no se acumula completo en la memoria del navegador.
- Se conservan clips completos durante 7 días; una tarea automática borra clips vencidos cada hora. Una grabación abandonada se elimina después de 24 horas.
- El disco es finito: para preservar al menos 512 MiB libres, el POS rechaza nuevos fragmentos si el espacio llega a ese umbral. Ampliar el Persistent Disk o borrar clips para continuar. La capacidad, el bitrate de cámaras y el número de personas simultáneas determinan el tamaño requerido.
- La retirada del permiso impide abrir nuevos streams, iniciar clips o consultar/borrar clips de esa cámara. Desactivar una cámara bloquea nuevos streams y clips, pero conserva sus clips históricos mientras el usuario mantenga el permiso. Los streams que ya estaban abiertos deben desconectarse en el navegador; el puente vuelve a comprobar los permisos al establecer una conexión.

## Verificación antes de publicar

Las pruebas automatizadas usan una base SQLite temporal y un directorio temporal; no acceden a la base de datos productiva ni necesitan cámaras físicas o MediaMTX:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cameras.py tests\test_cameras_api.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
node --check app\Templates\js\app.js
git diff --check
```

`tests/test_cameras_api.py` envía exactamente **30 solicitudes HTTP** a las rutas del módulo y verifica autenticación, RBAC, validación, ciclo de vida de cámaras, emisión/denegación de tokens, autorización del puente, grabación por fragmentos, reproducción y revocación de permisos. Es una prueba funcional local; no certifica la conectividad WebRTC, MediaMTX, TURN ni el disco de Render.

## Puesta en producción

1. Configurar primero el puente, DNS/TLS, medios WebRTC y reglas STUN/TURN indicadas arriba.
2. Adjuntar el Persistent Disk de Render y fijar sus variables; `render.yaml` omite intencionalmente ese recurso para evitar cambios de facturación.
3. Desplegar la versión y verificar `/healthcheck`, inicio de sesión y las rutas de cámaras con usuarios de prueba autorizados/no autorizados.
4. Desde una red externa al local, validar conexión, desconexión, audio desactivado, grabación/reproducción/eliminación de un clip y espacio disponible.
5. Confirmar snapshots diarios del disco y restauración documentada antes de declarar cumplidos RPO/RTO.

## Objetivos operativos iniciales

Para una instalación de un solo local, hasta 8 cámaras y 4 espectadores simultáneos, se dimensiona inicialmente el API de control para 10 QPS p99 y una relación aproximada de 10 lecturas por escritura; son estimaciones, no métricas observadas. El video circula por WebRTC y los fragmentos de clip por el API, así que el ancho de banda del local, del puente y del servicio cloud debe medirse durante la puesta en marcha.

- Objetivo del API de control: p50 ≤ 60 ms, p95 ≤ 200 ms y p99 ≤ 500 ms. No incluye el tiempo de negociación WebRTC ni la latencia de Internet.
- Disponibilidad objetivo del POS/API: 99.5% mensual; Gerencia consume el presupuesto de error y prioriza la reparación si se incumple. La disponibilidad del video depende además del puente y la conectividad del local.
- Recuperación de clips: RPO ≤ 24 horas y RTO ≤ 4 horas, condicionado a snapshots diarios del disco y a ejecutar el procedimiento de restauración.
