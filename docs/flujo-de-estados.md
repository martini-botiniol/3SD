# Flujo De Estados

## Insercion

```text
Disco insertado
  -> es unidad de red
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
        -> no reemplazar sesion activa valida
```

## Remocion

```text
Disco removido
  -> no es el activo
     -> ignorado
  -> es el activo
     -> NOT_INSERTED
     -> limpiar activeCartridgeId
     -> limpiar proteccion de accion Steam
```

## Acciones Steam

```text
READY
  -> open
     -> validar AppID
     -> solicitar a Steam apertura por AppID
  -> install
     -> validar AppID
     -> solicitar a Steam instalacion por AppID
  -> auto
     -> esperar a que Steam/manifest reconozca la biblioteca del SSD
     -> si instalado: open
     -> si no instalado despues de la espera: install
```

La accion se bloquea si ya se pidio para el mismo juego en la sesion actual,
para evitar loops o clicks repetidos. Al remover el SSD activo, esa proteccion
se limpia: si se conecta de nuevo, el juego vuelve a abrirse. Mientras un
cartucho esta activo, otro SSD/cartucho no puede reemplazarlo ni lanzar otro
juego al mismo tiempo.

Steam conserva la autoridad despues de recibir el AppID: licencia, instalacion,
actualizacion, integridad y ejecutable final no pertenecen al launcher.

Las acciones `Abrir` e `Instalar`, incluso desde la biblioteca, requieren que el
SSD correspondiente sea el cartucho activo.

## Estados Operativos

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

Algunos estados ya existen en dominio aunque V1 todavia no observe todas las
transiciones de forma completa, por ejemplo `GAME_RUNNING`.

## Popups

Los popups no se apilan:

- `VALIDATING`: persistente hasta el siguiente estado.
- `READY`: reemplaza el popup anterior y se cierra solo.
- `Iniciando/Instalando`: reemplaza el popup anterior y se cierra solo.
- `REMOVED` o error: reemplaza el popup anterior y se cierra solo.

En modo tray, el boton `Abrir biblioteca` del popup llama al mismo flujo que el
menu `Open Library`.
