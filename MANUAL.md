# Manual de 3SD 0.2

## Experiencia de uso

El flujo es `SSD → 3SD → Steam → Juego`. 3SD debe permanecer abierto en la bandeja.
Cerrar la biblioteca conserva la bandeja; Salir termina la aplicación.
El modo por defecto es automático. Un juego instalado en la biblioteca del SSD
se abre mediante Steam; una instalación ausente o incompleta se deriva a Steam.
Una cuenta sin licencia, una sesión cerrada o una descarga pendiente puede requerir
intervención dentro de Steam: 3SD no elude esas condiciones.

La primera vez que Steam ve una biblioteca en una PC puede ser necesario añadir
`X:\SteamLibrary` en Parámetros > Almacenamiento. 3SD muestra la ruta concreta y
no edita `libraryfolders.vdf` ni fuerza silenciosamente el destino de instalación.
El procedimiento se basa en la [ayuda de Steam](https://help.steampowered.com/en/faqs/view/4578-18A7-C819-8620).
Si el mismo AppID existe en varias bibliotecas, 3SD comprueba el SSD, pero Steam
conserva la elección final de la instalación que ejecuta. La confirmación se busca
en la biblioteca del cartucho; revisa Steam si el inicio no se confirma.

## Crear, actualizar y convertir

En **Opciones de cartucho**, abre **Crear cartucho** o **Actualizar cartucho**.
En el formulario, selecciona primero el disco y busca el juego o introduce su nombre y AppID.
Crear genera un cartucho V2. Actualizar conserva UUID y fecha de creación y cambia
el juego; puede hacerse desde cualquier PC con 3SD compatible.

Un V1 válido en su PC puede seguir utilizándose. Para compartirlo, abre
**Reparar cartucho > Preparar para usar en cualquier PC** y selecciona el SSD.
No hace falta la PC creadora:
la acción acepta expresamente metadata antigua cuya firma puede no verificarse
localmente. Se validan los campos y se guardan `manifest.json.v1.bak` y
`signature.sig.v1.bak`, cuando exista firma. Una conexión nunca convierte el SSD.

```powershell
3sd create --root G:\ --display-name "Juego" --app-id 111
3sd update --root G:\ --display-name "Otro juego" --app-id 222
3sd convert --root G:\
3sd repair --root G:\ --display-name "Juego" --app-id 111
```

Reparar es una acción explícita para metadata dañada. Conserva una copia del
manifiesto anterior y desactiva metadata ejecutable conservando copia `.disabled`.
No modifica los archivos del juego. Si la versión o la clave pertenecen a una
versión desconocida, actualiza 3SD: no se permite sobrescribirla como reparación.
Un error de registro posterior al guardado no invalida el manifiesto: tras recuperar
el registro, vuelve a conectar o escanear para registrarlo.

## Formato portátil V2

```text
G:\
  .cartridge/
    manifest.json
    manifest.previous.json      (respaldo de la escritura anterior)
    manifest.json.v1.bak         (tras conversión)
    signature.sig.v1.bak         (si V1 incluía firma)
    write.lock                  (coordinación de escritores)
  SteamLibrary/
    steamapps/
```

El manifiesto contiene `schemaVersion: 2`, UUID `cartridgeId`, nombre no vacío,
`platform: STEAM`, AppID decimal positivo de 32 bits, `libraryPath: SteamLibrary`
y fecha ISO-8601 con zona horaria. `authorization` contiene:

- `version: 1` y `keyId: 3sd-portable-2026-01`.
- `nonce`: 12 bytes aleatorios, representados en Base64.
- `ciphertext`: datos cifrados y etiqueta de autenticación, en Base64.

Se utiliza AES-256-GCM con la clave de aplicación estable. El contenido cifrado
incluye marcador `3SD-CARTRIDGE`, versión 2, UUID y AppID. Los datos adicionales
autenticados son todo el manifiesto salvo `authorization`, serializado como JSON
UTF-8, claves ordenadas, sin espacios y sin escapar caracteres Unicode.
Se rechazan claves JSON duplicadas, NaN y manifiestos de más de 64 KiB.
Cambiar un campo o copiar una autorización entre cartuchos invalida el conjunto;
cambiar únicamente espacios o el orden de las claves JSON no cambia su significado.
La API utilizada sigue la [documentación AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/).

No se genera una clave común nueva al instalar o compilar. Cualquier rotación
futura debe conservar lectura de los `keyId` anteriores. El nonce sí cambia en
cada escritura. No se necesita una clave privada del usuario ni una PC de origen.
La clave común está distribuida con 3SD y puede extraerse: identifica compatibilidad
e integridad, no demuestra emisión oficial frente a una falsificación deliberada.

V2 sin autorización o con autenticación fallida se rechaza, aunque exista una
firma V1 al lado. Formatos, versiones de autorización o claves desconocidas piden
actualizar la aplicación. Nunca se hace fallback de un V2 inválido a V1.

La firma HMAC-SHA256 de V1 continúa en `signature.sig` y depende del antiguo
`launcher.secret` local. Los secretos nuevos de ese mecanismo heredado usan DPAPI
en Windows; los antiguos Base64 siguen siendo legibles. Leer un cartucho externo
no crea ni modifica secretos. V2 no necesita `launcher.secret`.

## Detección, estados y desconexión

Se exploran unidades locales D: a Z: cada dos segundos, excluyendo unidades de red.
Todavía no se comprueba si el hardware es estrictamente SSD. Se compara identidad
del volumen y capacidad, además de cambios del archivo de manifiesto. Si el adaptador
no reporta identidad o el cambio completo ocurre entre dos consultas sin diferencias
observables, el polling puede no detectarlo.

Hay un cartucho activo. Los adicionales quedan en espera y se evalúan al retirar
el actual. Los cambios cancelan esperas y resultados de la sesión anterior. Se
revalida el cartucho y la presencia del dispositivo antes de enviar una acción.

Los mensajes distinguen validación, solicitud enviada, juego iniciado, inicio no
confirmado y necesidad de instalación/configuración. La confirmación usa procesos
bajo el directorio del juego o una actualización reciente de `LastPlayed`; es una
observación heurística, no una sesión de juego controlada por 3SD.

Antes de desconectar el SSD, termina juegos y descargas que lo utilicen. Retirar
un disco mientras se escribe puede dañar datos. 3SD cancela sus tareas pendientes,
pero no expulsa físicamente el volumen ni termina procesos del juego a la fuerza.

## Persistencia y recuperación

`%USERPROFILE%\.3sd` contiene registro local, respaldo, caché y logs rotativos.
El registro no concede propiedad de un cartucho V2 a una PC. Se registra
automáticamente tras validarlo, tanto desde la ventana como desde la bandeja.

Las actualizaciones del registro se serializan entre hilos y procesos. Se guarda
`registry.json.bak` antes de reemplazar un registro válido. Si el principal está
corrupto, se informa y se lee el respaldo; una escritura posterior conserva el
archivo dañado como `registry.json.corrupt`. Sin respaldo válido se muestra un
error y se evita sustituirlo por una biblioteca vacía. Conserva esos archivos para
recuperación; no los borres para ocultar el error.

V2 guarda datos y autorización en un único archivo temporal, sincroniza y reemplaza
el manifiesto. Si el reemplazo falla, el anterior permanece disponible en condiciones
normales del sistema de archivos. Esto no garantiza recuperación frente a daño físico
o corrupción del sistema de archivos. Tras reconectar, repite la operación explícita.

## Instalación y distribución

El paquete autónomo incluye Python, Tcl/Tk y dependencias. Extrae el ZIP completo y
abre `3SD.exe` o `Instalar-3SD.bat`. Instala generaciones en
`%LOCALAPPDATA%\Programs\3SD\packages`, comprueba el ejecutable antes de activar
accesos directos y conserva la generación anterior. No importa certificados ni
cambia políticas de Windows. Una firma comercial pública queda fuera de este build.

En instalaciones nuevas se activa inicio con Windows; las actualizaciones conservan
la preferencia existente. Cierra la bandeja antes de empezar a usar una actualización.
La desinstalación retira accesos e inicio automático; por estar el ejecutable en uso,
se pide cerrar 3SD y eliminar la carpeta de instalación. Los datos `.3sd` y SSD se
conservan. No se eliminan instalaciones Python anteriores de forma automática.

La alternativa Python mantiene `Preparar-3SD.bat`, `Abrir-3SD.bat` y
`Diagnosticar-3SD.bat`. Requiere Python 3.11+ con Tcl/Tk, pip y venv e internet
para preparar. No depende de una instalación editable ni del checkout una vez
publicada. Los entornos anteriores se conservan para recuperación.

```powershell
python -m pip install -e ".[dev,build]"
python -m pytest
python scripts/package_standalone.py
python scripts/package_3sd.py
```

El constructor autónomo exige Tcl/Tk operativo, ejecuta pruebas y verifica
`3SD.exe self-check` antes de generar el ZIP. El inventario de dependencias del
build acompaña el paquete. Usar un entorno limpio evita dependencias accidentales.

## Arquitectura y validación

`domain` define tipos y validación; `services` administra cartuchos, autorización,
sesiones y acciones; `infrastructure` integra Steam, Windows y persistencia;
`ui` mantiene Tk y entrega resultados de trabajadores al hilo principal;
`app` ofrece consola y composición de servicios.

Las pruebas automatizadas utilizan directorios temporales y clientes simulados;
no prueban licencias o juegos reales. Consulta [ACCEPTANCE.md](docs/ACCEPTANCE.md)
para los escenarios y la validación física pendiente en dos PCs y dos SSD.


### Operaciones desde el centro de control

Abre **Opciones de cartucho**, recogida por defecto. Encontrarás **Crear cartucho**,
**Actualizar cartucho** y la sección **Reparar cartucho**, con **Reparar** y
**Preparar para usar en cualquier PC**. Windows y Actividad también empiezan recogidas.

Cada operación abre un único formulario: selecciona explícitamente el SSD y después
el juego por búsqueda o por nombre y AppID. Actualizar muestra el juego actual cuando
puede leerse; Reparar precarga sus datos y pide confirmación dentro del formulario.
Preparar conserva el juego y no solicita uno nuevo. No se conserva una selección de
juego entre operaciones.

Cancelar, Escape y X cierran el formulario antes de guardar. Durante la escritura,
espera a que termine antes de cerrar o desconectar el SSD. Los errores y el progreso
aparecen en el propio formulario. Las notificaciones no abren otra ventana mientras
está activo. Al terminar, se cierra y se actualiza la biblioteca.

Al expulsar el cartucho activo, la bandeja muestra el aviso de desconexión aunque
la biblioteca esté abierta. El aviso permanece tres segundos antes de mostrar el
siguiente evento. Mientras hay un formulario de cartucho abierto, se registra el
evento sin abrir otra ventana; ese aviso no se reproduce al cerrar el formulario.
