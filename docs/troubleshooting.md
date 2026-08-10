# Troubleshooting

## `No module named PIL`

Instala dependencias:

```powershell
py -m pip install -e ".[build]"
```

## `No module named tkinter`

Tkinter viene con la instalacion oficial de Python para Windows, pero puede
faltar si se uso una distribucion incompleta.

Solucion recomendada:

1. Instala Python desde python.org.
2. En el instalador activa `tcl/tk and IDLE`.
3. Reinstala dependencias:

```powershell
py -m pip install -e ".[build]"
```

Prueba:

```powershell
py -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('tk ok')"
```

## Smart App Control Bloquea El `.exe`

Usa el instalador principal:

```powershell
.\Preparar-3SD.bat
```

Ese flujo cierra instancias antiguas de `3SD.exe` y `CartridgeLauncher.exe`,
crea el `.exe`, lo firma con certificado local, confia el certificado en el
usuario actual, instala los accesos y quita la marca de internet.

Si puedes correrlo como administrador, el instalador tambien intenta confiar el
certificado en el almacen de maquina local. Eso puede ayudar con validaciones de
Windows mas estrictas.

Si Smart App Control lo bloquea aun despues de eso, el bloqueo viene de la
politica de Windows para apps locales sin reputacion publica. El instalador no
puede crear una excepcion por app para Smart App Control.

## El Tray No Cierra

Prueba cerrar cualquier proceso viejo:

```powershell
taskkill /F /IM CartridgeLauncher.exe /T
taskkill /F /IM 3SD.exe /T
```

Luego reconstruye:

```powershell
.\scripts\build\build_exe.ps1 -UseLocalCertificate
```

## La Portada Dice `Juego sin nombre`

Eso significa que el registro local no tiene `displayName` para ese cartucho.

Soluciones:

- conecta el cartucho y espera que valide como `READY`.
- usa `Actualizar cartucho` en la UI.
- o usa CLI:

```powershell
py -m cartridge_launcher.app.main update --root G:\ --display-name "Nombre correcto" --app-id 2531310
```

## La Portada No Carga

Las portadas vienen de Steam CDN. Si no hay internet o Steam no tiene imagen para
ese AppID, la UI usa fallback visual.

## Steam No Abre El Juego

Revisa:

- Steam esta instalado.
- Steam esta abierto o disponible.
- El AppID es correcto.
- La accion no fue bloqueada por repeticion.

La app usa:

```text
steam://run/{appId}
steam://install/{appId}
```

No ejecuta archivos desde el SSD.

## `INVALID_SIGNATURE`

El manifest fue modificado o ya no coincide con `signature.sig`.

Solucion:

- usa `Actualizar cartucho`.
- o recrea el cartucho desde la UI.

No edites `manifest.json` a mano.

## `DEVICE_MISMATCH`

El cartucho no coincide con el disco registrado en esta PC.

Puede pasar si:

- se copio `.cartridge` a otro SSD.
- cambio el registro local.
- se cambio AppID manualmente sin regenerar firma/registro.

Usa `Actualizar cartucho` desde la misma PC y el mismo SSD.
