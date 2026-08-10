# Cartuchos

Un cartucho es un SSD extraible con metadata minima firmada localmente.

## Estructura En Disco

```text
G:\
  .cartridge\
    manifest.json
    signature.sig
  SteamLibrary\
```

## `manifest.json`

Ejemplo:

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

Campos:

- `schemaVersion`: version del formato. Actualmente `1`.
- `cartridgeId`: UUID estable del cartucho.
- `displayName`: nombre visible del juego.
- `platform`: por ahora siempre `STEAM`.
- `appId`: Steam AppID numerico.
- `libraryPath`: debe ser exactamente `SteamLibrary`.
- `createdAt`: fecha ISO-8601.

## Firma

`signature.sig` contiene HMAC-SHA256 del contenido exacto de `manifest.json`.

La firma se calcula sobre los bytes UTF-8 exactos del archivo. Cambiar valores,
espacios, orden o formato puede invalidarla. V1 no usa JSON canonico porque el
launcher controla la escritura y lectura del manifest que genera.

El secreto HMAC vive en la PC local:

```text
%USERPROFILE%\.cartridge-launcher\launcher.secret
```

El secreto no se copia al SSD.

Los cartuchos V1 son confiables solo en la PC que los creo. Copiar `.cartridge`
a otro SSD o a otra maquina no debe bastar para clonar un cartucho valido.

## Registro Local

El registro local se guarda en:

```text
%USERPROFILE%\.cartridge-launcher\registry.json
```

Se usa para verificar que el cartucho pertenece al disco registrado:

- `cartridgeId`
- `appId`
- `volumeSerialNumber`
- `capacityBytes`
- `displayName`

El registro describe la relacion local entre esta PC y el cartucho. Por eso
guarda datos del dispositivo, no archivos del juego.

## Campos Excluidos En V1

El manifest se mantiene minimo a proposito. No incluye:

- ruta de ejecutable.
- directorio de instalacion.
- version instalada.
- estado persistido.
- tamano del juego.
- detalles del editor.
- artwork formal dentro del cartucho.

La mayoria de esos datos pertenecen a Steam, al registro local o a futuras
versiones.

## Reglas De Seguridad Del Cartucho

- `libraryPath` debe ser exactamente `SteamLibrary`.
- `appId` debe ser numerico y estar entre `1` y `4294967295`.
- `.cartridge` esta reservado para metadata.
- Archivos ejecutables o interpretables dentro de `.cartridge` deben
  rechazarse: `.exe`, `.bat`, `.cmd`, `.ps1`, `.dll`, `.msi`.
- `SteamLibrary` puede contener archivos administrados por Steam, pero el
  launcher no los ejecuta ni los repara.
- Abrir o instalar requiere que el cartucho correspondiente este insertado y
  validado como activo.

## Crear Desde CLI

```powershell
py -m cartridge_launcher.app.main create --root G:\ --display-name "The Last of Us Part II Remastered" --app-id 2531310
```

## Actualizar Desde CLI

Cambiar nombre:

```powershell
py -m cartridge_launcher.app.main update --root G:\ --display-name "The Last of Us Part II Remastered" --app-id 2531310
```

Cambiar juego asociado:

```powershell
py -m cartridge_launcher.app.main update --root G:\ --display-name "Nuevo Juego" --app-id 123456
```

## Regla Importante

No edites manualmente `manifest.json`.

Si lo editas a mano, la firma deja de coincidir y el cartucho queda como
`INVALID_CARTRIDGE`. Usa `Actualizar cartucho` desde la UI o el comando
`update`.
