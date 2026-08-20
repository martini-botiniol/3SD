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
- Firma local de desarrollo para builds `.exe`.
- Inicio con Windows configurable desde la UI.

## Uso

Instalar dependencias para desarrollo:

```powershell
py -m pip install -e ".[build,dev]"
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

Al abrir el `.exe` sin argumentos, la app inicia el tray y abre la biblioteca.
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

## Build, Firma E Instalacion

Preparar, firmar, empaquetar e instalar en esta PC:

```powershell
.\Preparar-3SD.bat
```

El `.bat` es un lanzador corto que eleva permisos y ejecuta el flujo completo en
un solo script:

```powershell
.\scripts\prepare_3sd.ps1
```

Ese flujo crea `dist\3SD.exe`, exporta `dist\3SD-LocalDev.cer`, prepara
`dist\3SD-local-dev\` e instala en:

```text
%LOCALAPPDATA%\Programs\3SD
```

Antes de ejecutar `Preparar-3SD.bat`, Python debe estar disponible como `py` o
`python` en PATH. Si el build falla con `Python was not found`, instala Python
para Windows o ejecuta `prepare_3sd.ps1` manualmente pasando `-PythonExe` con
la ruta completa a `python.exe`.

Smart App Control puede bloquear ejecutables locales sin reputacion publica.
La firma self-signed y la confianza local ayudan en la PC de desarrollo, pero
no crean reputacion publica. Si `prepare_3sd.ps1` detecta que Windows bloquea
`3SD.exe`, deja los accesos directos configurados para abrir 3SD via Python en
vez de lanzar el `.exe` directamente y reporta `Modo de acceso directo: python`.

Ese modo es un fallback local/de desarrollo. Depende de que Python siga
disponible en la PC y de que el paquete este instalado desde este checkout con
`pip install -e`. En ese caso usa el acceso directo de escritorio/menu inicio;
abrir `3SD.exe` manualmente puede seguir mostrando el bloqueo de Smart App
Control.

Un instalador final publico no deberia depender del checkout local ni de una
instalacion editable de Python. Para publicar una version distribuible, la ruta
preferida es un binario o instalador firmado con reputacion suficiente para no
necesitar este fallback.

## Troubleshooting

`No module named PIL`:

```powershell
py -m pip install -e ".[build,dev]"
```

`No module named tkinter`: instala Python desde python.org con `tcl/tk and
IDLE`, reinstala dependencias y prueba:

```powershell
py -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('tk ok')"
```

Smart App Control bloquea el `.exe`:

```powershell
.\Preparar-3SD.bat
```

Si al terminar muestra `Modo de acceso directo: python`, abre 3SD desde el
acceso directo generado, no ejecutando `3SD.exe` directamente.

El tray no cierra:

```powershell
taskkill /F /IM 3SD.exe /T
```

Luego reconstruye:

```powershell
.\Preparar-3SD.bat
```

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
