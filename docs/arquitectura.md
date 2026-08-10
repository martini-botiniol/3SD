# Arquitectura

3SD busca una experiencia tipo consola: insertar un SSD preparado,
validarlo como cartucho y abrir o instalar el juego asociado en Steam.

El modelo rector del proyecto es:

```text
Cartucho (SSD) -> Launcher -> Steam -> Juego
```

No existe un camino directo desde el SSD hacia la ejecucion. El SSD representa
una identidad fisica autenticada que apunta a un AppID y a una biblioteca
gestionada por Steam.

```text
SSD cartucho -> DeviceMonitor -> CartridgeSessionService -> UI/Tray -> Steam
```

## Capas

### `domain`

Contiene modelos y reglas puras:

- `CartridgeManifest`
- `DeviceInfo`
- `RegisteredCartridge`
- estados de launcher
- errores conocidos
- validacion del manifest

No accede a Windows, Steam, Tkinter ni filesystem externo salvo parseo de datos
que recibe.

### `services`

Contiene la logica de aplicacion:

- `CartridgeCreationService`: prepara un SSD como cartucho.
- `CartridgeUpdateService`: cambia nombre/AppID de un cartucho existente.
- `CartridgeValidator`: valida estructura, firma, registro y dispositivo.
- `CartridgeWatchService`: transforma inserciones en estados de app.
- `CartridgeSessionService`: mantiene el cartucho activo.
- `DeviceMonitor`: compara snapshots de discos.
- `SteamIntegration`: valida AppID y coordina acciones Steam.
- `LocalRegistry`: registro JSON local de cartuchos conocidos.
- `SecurityService`: firma/verificacion HMAC.

### `infrastructure`

Contiene integraciones externas:

- `WindowsDeviceScanner`: unidades conectadas en Windows.
- `SteamClient`: URLs `steam://run/{appId}` y `steam://install/{appId}`.
- `SteamStoreSearchClient`: busqueda publica de juegos por nombre.
- `startup_shortcut`: inicio con Windows.
- `single_instance`: evita instancias duplicadas donde aplique.
- `logging_config`: logs locales.

### `ui`

Contiene experiencia de usuario:

- `main_window`: biblioteca, creacion/actualizacion, estado y acciones.
- `tray_app`: modo residente.
- `status_popup`: popup de estados.
- `view_models`: textos y modelos limpios para UI.
- `error_messages`: errores humanos.
- `cover_cache`: portadas desde Steam CDN con cache local.

### `app`

Entrada CLI y wiring:

- `ui`
- `tray`
- `create`
- `update`
- `startup`

## Flujo De Insercion

1. `DeviceMonitor` detecta un disco nuevo.
2. `CartridgeWatchService` revisa si existe `.cartridge`.
3. Si no existe `.cartridge`, se ignora.
4. Si ya existe otro cartucho activo, se avisa y el disco nuevo se ignora hasta
   remover el activo.
5. Si existe, emite `VALIDATING`.
6. `CartridgeValidator` verifica:
   - estructura
   - ausencia de ejecutables en metadata
   - schema del manifest
   - firma HMAC
   - `libraryPath` y AppID
   - registro local
   - serial/capacidad del dispositivo
7. Si todo es valido, se emite `READY`.
8. `CartridgeSessionService` marca ese cartucho como activo.
9. UI/tray pueden abrir o instalar desde Steam.

## Estados Principales

- `NOT_INSERTED`: no hay cartucho activo.
- `VALIDATING`: se esta leyendo/verificando el disco.
- `READY`: cartucho valido y listo.
- `OPENING`: solicitud de apertura enviada a Steam.
- `GAME_RUNNING`: Steam inicio el juego.
- `NOT_INSTALLED`: requiere instalacion mediante Steam.
- `INVALID_CARTRIDGE`: estructura, manifest o firma invalida.
- `DEVICE_MISMATCH`: el disco no coincide con el registro local.
- `STEAM_REQUIRED`: Steam no esta disponible.
- `ERROR`: error generico controlado.

## Reglas De Seguridad

- Steam conserva la autoridad sobre licencias, instalacion, actualizaciones,
  integridad y ejecucion.
- Abrir o instalar requiere que el SSD correspondiente este insertado y validado.
- V1 acepta unidades locales con letra de unidad y excluye unidades de red. No
  valida todavia si el dispositivo es estrictamente SSD.
- El SSD nunca se usa para ejecutar `.exe`, `.bat`, `.cmd`, `.ps1`, `.dll` o
  `.msi` dentro de `.cartridge`.
- El juego se abre por protocolo Steam, no por rutas en el SSD.
- El secreto HMAC vive solo en la PC local.
- El SSD contiene:

```text
.cartridge/
  manifest.json
  signature.sig
SteamLibrary/
```

El launcher es propietario solo de `.cartridge`. `SteamLibrary` pertenece
operativamente a Steam.

## Registro Local

El registro se guarda en:

```text
%USERPROFILE%\.cartridge-launcher\registry.json
```

Contiene cartuchos conocidos con:

- `cartridgeId`
- `appId`
- `volumeSerialNumber`
- `capacityBytes`
- `displayName`

La UI sincroniza el registro con el manifest cuando un cartucho valida como
`READY`, para reparar nombres antiguos o incompletos.

El objetivo de diseno es que el registro pueda migrar a SQLite en el futuro sin
cambiar el contrato de los servicios que lo consumen. Tambien queda pendiente
endurecer escritura atomica y validacion robusta al cargar.
