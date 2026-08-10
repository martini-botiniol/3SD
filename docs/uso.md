# Uso

## Abrir La App

Desde codigo fuente:

```powershell
py -m cartridge_launcher.app.main ui
```

Desde el `.exe`:

```powershell
.\dist\3SD.exe
```

Al abrir el `.exe` sin argumentos, la app inicia el tray y abre la biblioteca.

## Modo Tray

```powershell
py -m cartridge_launcher.app.main tray --open-window --steam-action auto
```

Acciones del tray:

- `Open Library`: abre la ventana principal.
- `Scan Existing Cartridge`: escanea discos ya conectados.
- `Exit`: cierra ventana, tray y proceso.

La ventana puede cerrarse sin cerrar el tray. Para salir por completo, usa
`Exit` desde el tray.

## Biblioteca

La pantalla principal muestra portadas de Steam para los cartuchos registrados.

La tarjeta muestra:

- portada
- nombre del juego
- estado simple: `Insertado` o `No insertado`

La tarjeta no muestra AppID, serial, capacidad ni `cartridgeId` por defecto.
Esos datos quedan bajo `Detalles`.

La biblioteca representa cartuchos conocidos en esta PC. El flujo principal del
producto es fisico: conectar el SSD, validarlo y usar el cartucho activo. Las
acciones sobre `Juego seleccionado` solo se habilitan cuando ese mismo cartucho
esta insertado y validado.

## Crear Cartucho Desde UI

1. Conecta el SSD.
2. Abre `Opciones`.
3. En `Nuevo cartucho`, elige el disco.
4. Escribe el nombre del juego.
5. Usa `Buscar por nombre` para llenar nombre/AppID desde Steam.
6. Si la busqueda falla, escribe el AppID manualmente.
7. Presiona `Crear cartucho`.

La app crea:

```text
.cartridge\manifest.json
.cartridge\signature.sig
SteamLibrary\
```

## Actualizar Cartucho Desde UI

Usa `Actualizar cartucho` cuando:

- quieres corregir el nombre mostrado.
- quieres asociar otro juego al mismo SSD.
- quieres cambiar el AppID sin recrear el cartucho fisico.

Pasos:

1. Conecta el cartucho.
2. Selecciona el disco.
3. Escribe o busca el nuevo nombre/AppID.
4. Presiona `Actualizar cartucho`.

La actualizacion conserva el `cartridgeId`, reescribe el manifest, regenera la
firma y actualiza el registro local.

## Acciones Steam

Desde `Cartucho activo` o desde un `Juego seleccionado` que este insertado:

- `Abrir`: envia `steam://run/{appId}`.
- `Instalar`: envia `steam://install/{appId}`.
- `Abrir o instalar automaticamente`: abre si Steam detecta el juego instalado,
  o solicita instalacion si no lo encuentra.

En modo automatico, la app espera brevemente a que Steam reconozca la biblioteca
del SSD antes de decidir que el juego no esta instalado. Esto evita pedir
instalacion cuando el disco acaba de conectarse y Steam todavia no vio el
`appmanifest`.

La UI muestra:

- `Enviando orden a Steam`
- `Steam recibio la orden`
- mensaje humano si Steam no esta disponible

3SD no abre ejecutables desde el SSD. Siempre entrega un AppID a
Steam y deja que Steam resuelva licencia, instalacion, actualizacion, integridad
y ejecucion.

Si seleccionas un juego de la biblioteca pero su SSD no esta conectado, la app
pedira conectar ese SSD antes de abrir o instalar.

## Inicio Con Windows

En la seccion `Windows` puedes activar o desactivar:

```text
Iniciar con Windows
```

CLI equivalente:

```powershell
py -m cartridge_launcher.app.main startup status
py -m cartridge_launcher.app.main startup enable
py -m cartridge_launcher.app.main startup disable
```
