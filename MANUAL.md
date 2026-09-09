# Manual De 3SD

3SD es un prototipo para Windows y Steam que usa SSDs extraibles como
cartuchos fisicos. El SSD no contiene codigo confiable para ejecutar; contiene
una identidad firmada que apunta a un juego de Steam mediante AppID.

El modelo rector es:

```text
Cartucho (SSD) -> 3SD -> Steam -> Juego
```

Steam conserva la autoridad sobre licencias, instalacion, actualizaciones,
integridad y ejecucion. 3SD solo valida el cartucho y solicita a Steam abrir o
instalar el juego asociado.

## Vision General

La experiencia buscada es cercana a una consola:

1. El usuario conecta un SSD preparado como cartucho.
2. El launcher detecta el disco.
3. Si el cartucho es valido, queda listo para abrir o instalar el juego.
4. Si el cartucho esta incompleto, modificado o no coincide con el dispositivo
   registrado, se rechaza antes de contactar a Steam.

Estado actual:

- UI principal con biblioteca de portadas.
- Tray app residente.
- Creacion y actualizacion de cartuchos.
- Deteccion de discos por polling.
- Validacion de `.cartridge/manifest.json` con firma HMAC-SHA256.
- Acciones Steam: abrir, instalar y modo automatico.
- Distribucion Python para pruebas internas, sin certificados locales.
- Inicio con Windows configurable desde la UI.

## Uso

Instalar dependencias para desarrollo:

```powershell
py -m pip install -e ".[dev]"
```

Abrir la ventana principal:

```powershell
3sd ui
```

Iniciar en modo tray:

```powershell
3sd tray --open-window --steam-action auto
```

Ejecutar pruebas:

```powershell
py -m pytest
```

Al usar el acceso directo o `Abrir-3SD.bat`, la app inicia el tray y abre la biblioteca.
Desde el tray se puede abrir la biblioteca, escanear cartuchos ya conectados o
salir completamente del proceso.

La biblioteca muestra cartuchos registrados en esta PC con portada, nombre y
estado simple. Las acciones de Steam solo se habilitan cuando el SSD de ese
cartucho esta insertado y validado.

## Cartuchos

Un cartucho es un SSD extraible con metadata minima firmada localmente:

```text
G:\
  .cartridge\
    manifest.json
    signature.sig
  SteamLibrary\
```

Ejemplo de `manifest.json`:

```json
{
  "schemaVersion": 1,
  "cartridgeId": "00000000-0000-4000-8000-000000000001",
  "displayName": "The Last of Us Part II Remastered",
  "platform": "STEAM",
  "appId": "2531310",
  "libraryPath": "SteamLibrary",
  "createdAt": "2026-07-23T00:00:00Z"
}
```

Campos principales:

- `schemaVersion`: version del formato. Actualmente `1`.
- `cartridgeId`: UUID estable del cartucho.
- `displayName`: nombre visible del juego.
- `platform`: por ahora siempre `STEAM`.
- `appId`: Steam AppID numerico.
- `libraryPath`: debe ser exactamente `SteamLibrary`.
- `createdAt`: fecha ISO-8601.

Crear cartucho desde CLI:

```powershell
3sd create --root G:\ --display-name "The Last of Us Part II Remastered" --app-id 2531310
```

Actualizar cartucho desde CLI:

```powershell
3sd update --root G:\ --display-name "Nuevo nombre" --app-id 123456
```

Reparar cartucho desde CLI:

```powershell
3sd repair --root G:\ --display-name "Nombre correcto" --app-id 123456
```

Desde la UI, el flujo equivalente esta en `Opciones`: seleccionar disco,
buscar o escribir nombre/AppID y presionar `Crear cartucho` o
`Actualizar cartucho`. Si el SSD aparece como invalido, usa `Reparar cartucho`
para reconstruir manifest, firma, registro local y eliminar metadata ejecutable
dentro de `.cartridge`.

No edites manualmente `manifest.json`. Si cambia el contenido exacto del
archivo, la firma deja de coincidir y el cartucho queda como
`INVALID_CARTRIDGE`.

## Arquitectura

Flujo principal:

```text
SSD cartucho -> DeviceMonitor -> CartridgeSessionService -> UI/Tray -> Steam
```

Capas:

- `domain`: modelos, estados, errores y reglas puras del manifest.
- `services`: logica de aplicacion para crear, actualizar, validar, registrar y
  observar cartuchos.
- `infrastructure`: integraciones con Windows, Steam, inicio con Windows,
  instancia unica y logging.
- `ui`: ventana principal, tray, popups, mensajes, portadas y view models.
- `app`: entrada CLI y wiring de comandos `ui`, `tray`, `create`, `update` y
  `startup`.

El registro local vive en:

```text
%USERPROFILE%\.3sd\registry.json
```

Contiene `cartridgeId`, `appId`, `volumeSerialNumber`, `capacityBytes` y
`displayName`. La UI sincroniza el registro con el manifest cuando un cartucho
valida como `READY`.

## Flujo De Estados

Insercion:

```text
Disco insertado
  -> unidad de red
     -> ignorado
  -> ya hay otro cartucho activo
     -> avisar e ignorar hasta remover el activo
  -> no tiene .cartridge
     -> ignorado
  -> tiene .cartridge
     -> VALIDATING
        -> estructura minima
        -> manifest JSON y schema
        -> firma HMAC
        -> libraryPath y AppID
        -> asociacion con dispositivo
     -> READY
        -> activar sesion
        -> marcar biblioteca como Insertado
        -> permitir accion Steam
     -> INVALID_CARTRIDGE / DEVICE_MISMATCH
        -> mostrar error humano
```

Remocion:

```text
Disco removido
  -> no es el activo
     -> ignorado
  -> es el activo
     -> NOT_INSERTED
     -> limpiar activeCartridgeId
     -> limpiar proteccion de accion Steam
```

Estados operativos:

- `NOT_INSERTED`: no existe un cartucho activo.
- `VALIDATING`: se verifica estructura, firma y reglas.
- `READY`: cartucho valido y disponible.
- `OPENING`: solicitud de apertura enviada a Steam.
- `GAME_RUNNING`: Steam inicio el juego.
- `NOT_INSTALLED`: Steam requiere instalacion.
- `STEAM_REQUIRED`: Steam no esta disponible.
- `INVALID_CARTRIDGE`: estructura, manifest o firma no confiable.
- `DEVICE_MISMATCH`: el SSD no coincide con el registro local.
- `ERROR`: fallo inesperado.

## Seguridad

Reglas principales:

- 3SD nunca ejecuta `.exe`, `.bat`, `.cmd`, `.ps1`, `.dll` o `.msi` desde el
  SSD.
- Abrir e instalar se hacen con `steam://run/{appId}` y
  `steam://install/{appId}`.
- `libraryPath` debe ser exactamente `SteamLibrary`.
- `appId` debe ser numerico y estar entre `1` y `4294967295`.
- `.cartridge` esta reservado para metadata del launcher.
- V1 acepta unidades locales con letra de unidad y excluye unidades de red; aun
  no verifica si el dispositivo es estrictamente SSD.

`signature.sig` contiene HMAC-SHA256 del contenido exacto de `manifest.json`.
El secreto local vive en:

```text
%USERPROFILE%\.3sd\launcher.secret
```

El secreto no se copia al SSD. En V1, los cartuchos son confiables solo en la
PC que los creo.

## Preparacion, Actualizacion E Inicio Automatico

Requisitos: Windows, Python 3.11 o superior con Tcl/Tk, pip y venv, e internet
para descargar dependencias. La distribucion de pruebas fija Pillow, pystray,
pywin32 y six. No requiere certificados ni administrador en el uso diario.
La ejecucion con Python no garantiza superar todas las politicas de cada equipo.

Extrae el ZIP y ejecuta `Preparar-3SD.bat`. Si el interprete no esta en PATH,
define `THREE_SD_PYTHON` con su ruta completa. Tambien puedes ejecutar:

```powershell
python scripts/prepare_3sd.py
```

La ubicacion predeterminada es `%LOCALAPPDATA%\Programs\3SD`. Para pruebas
tecnicas existe `--install-directory`; los lanzadores del ZIP usan la ubicacion
predeterminada, por lo que con una ruta personalizada debes usar sus accesos directos.

Cada preparacion crea un entorno en `runtimes/<identificador>` en su ubicacion
definitiva. Instala una wheel, comprueba dependencias, Tkinter y el backend de la
bandeja, y solo entonces publica accesos directos y `installation.json`.
No depende del checkout ni de una instalacion editable. No copies entornos virtuales
entre equipos y no desinstales o muevas el Python base usado para prepararlos.

Puedes borrar la carpeta extraida. Para actualizar, extrae el ZIP nuevo y repite
la preparacion. Sal de la bandeja antes de empezar a usar la nueva version.
La version anterior permanece en disco; una preparacion fallida no cambia los
accesos de la version activa. Los entornos fallidos incluyen `failed.json`.
No se eliminan automaticamente entornos antiguos para conservar la recuperacion.

El inicio automatico usa un acceso directo en la carpeta Inicio del usuario.
Se activa en una instalacion nueva, conserva la configuracion al migrar y respeta
la desactivacion en actualizaciones. Puedes cambiarlo en Opciones o con los
comandos `startup enable`, `startup disable` y `startup status`, ejecutados con
el Python de la instalacion.

Tras reinicio, apagado/encendido o cierre de sesion, 3SD vuelve a ejecutarse
**al iniciar sesion**, en la bandeja, sin consola ni biblioteca abierta. Detecta
SSD ya conectados y conserva las acciones Steam existentes. No es un servicio
previo al inicio de sesion. Cerrar la biblioteca mantiene el tray; `Exit` termina
la aplicacion hasta su proxima apertura o inicio de sesion.

## Limpieza Del Flujo Anterior

Ejecuta primero la preparacion Python. La limpieza esta separada y no se ejecuta
cada vez que se prepara la aplicacion. Inventario sin cambios:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File scripts/cleanup_legacy.ps1
```

La politica indicada se limita a ese proceso de PowerShell; no cambia la configuracion persistente de Windows. Para aplicar, agrega `-Apply`. Para incluir los artefactos del checkout, agrega
`-ProjectDirectory` con su ruta completa. El script se copia tambien a la carpeta
instalada, por lo que no depende de conservar el ZIP.

Solo identifica certificados `CN=3SD Local Dev`, autofirmados y con uso de firma
de codigo, corroborados por las firmas o certificados exportados de 3SD. Si no
quedan esos archivos, deja los certificados pendientes; tras verificar el inventario
puede pasarse una huella exacta mediante `-Thumbprint`. Nunca busca nombres parciales.

Retira las copias identificadas en los almacenes de usuario y equipo y las claves
privadas asociadas si existen. La limpieza de LocalMachine requiere ejecutar este
paso en PowerShell como administrador, conservando el usuario y la ruta de instalacion
originales. No modifica las protecciones de Windows ni instala certificados.

Antes de borrar verifica la instalacion Python y guarda un inventario; despues
registra el resultado de cada elemento en `legacy-cleanup-report.json`. Los fallos
de permisos o archivos en uso quedan pendientes (codigo de salida 2). Cierra el
3SD anterior desde su bandeja y repite el paso si su EXE sigue en uso.

Se conservan `%USERPROFILE%\.3sd`, `launcher.secret`, el registro y todos los SSD.
Las firmas HMAC de cartuchos son independientes de los certificados de Windows.
La portabilidad de cartuchos entre PCs no forma parte de esta migracion.

## Retirar La Distribucion De Pruebas

Desactiva `Iniciar con Windows`, sal de 3SD y elimina sus accesos directos de
escritorio/menu Inicio. Elimina exclusivamente `%LOCALAPPDATA%\Programs\3SD`
despues de confirmar que es la carpeta de esta instalacion. Los datos y el secreto
en `%USERPROFILE%\.3sd` permanecen para futuras instalaciones. Python puede
seguir siendo utilizado por otras aplicaciones y no se desinstala con 3SD.

## Troubleshooting

`No module named PIL`:

```powershell
py -m pip install -e ".[dev]"
```

`No module named tkinter`: instala Python desde python.org con `tcl/tk and
IDLE`, reinstala dependencias y prueba:

```powershell
py -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('tk ok')"
```

La aplicacion no inicia o falta una dependencia: ejecuta `Diagnosticar-3SD.bat`.
Usa `Diagnosticar-3SD.bat --run` para conservar una consola durante el arranque.
Repite la preparacion para reparar; revisa `launcher.log` y cualquier error de
politica de Windows por separado.

La portada dice `Juego sin nombre`: conecta el cartucho y espera `READY`, usa
`Actualizar cartucho` o ejecuta `update` desde CLI.

La portada no carga: las portadas vienen de Steam CDN; si no hay internet o
Steam no tiene imagen, la UI usa fallback visual.

Steam no abre el juego: revisa que Steam este instalado/disponible, que el
AppID sea correcto y que la accion no haya sido bloqueada por repeticion.

`INVALID_SIGNATURE`: el manifest fue modificado o no coincide con
`signature.sig`; usa `Reparar cartucho`.

`DEVICE_MISMATCH`: el cartucho no coincide con el disco registrado en esta PC;
puede pasar si se copio `.cartridge` a otro SSD o cambio el registro local. Si
el SSD es tuyo y quieres confiarlo en esta PC, usa `Reparar cartucho`.

## Pendientes V1

Producto y UI:

- Definir icono final.
- Revisar textos finales de UI.
- Probar flujo completo con al menos dos SSD/cartuchos reales.
- Validar cambio rapido de cartuchos.
- Pulir responsive en pantallas pequenas.
- Mejorar selector de busqueda Steam con portadas/resultados mas claros.
- Agregar indicador visual mas claro del cartucho activo.
- Revisar estados vacios: sin discos, sin internet, sin Steam, sin cartuchos.

Tray y Steam:

- Confirmar comportamiento despues de varios ciclos abrir/cerrar ventana.
- Validar con juegos reales instalados y no instalados.
- Mejorar mensaje cuando Steam recibe la orden pero no inicia nada visible.
- Evaluar deteccion mas robusta de juego instalado.
- Observar transiciones `OPENING -> GAME_RUNNING -> READY` cuando sea posible.

Cartuchos y persistencia:

- Hacer mas guiado el flujo de actualizacion.
- Pulir confirmaciones de reparacion para explicar cuando se reescribe metadata.
- Evaluar deteccion estricta de SSD en una version futura.
- Definir migracion futura a SQLite sin cambiar contratos de servicios.
- Evaluar exportar/importar registro local solo con portabilidad segura entre
  PCs.

## Icono Y Assets

Cuando tengas el icono final, ponlo en:

```text
assets\3SD.ico
```

Tamanos recomendados dentro del `.ico`: 16x16, 32x32, 48x48 y 256x256.
