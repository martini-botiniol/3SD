# 3SD

Prototipo Windows + Steam para usar SSDs extraibles como cartuchos fisicos.

3SD valida un manifiesto firmado dentro del SSD, registra cartuchos en la PC
local y abre o instala juegos mediante URLs oficiales de Steam. Nunca ejecuta
binarios desde el SSD.

## Estado Actual

- UI principal con biblioteca de portadas.
- Tray app residente.
- Creacion y actualizacion de cartuchos.
- Deteccion de discos por polling.
- Validacion de `.cartridge/manifest.json` con firma HMAC-SHA256.
- Acciones Steam: abrir, instalar y modo automatico.
- Firma local de desarrollo para builds `.exe`.
- Inicio con Windows configurable desde la UI.

## Inicio Rapido

Instalar dependencias:

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

Crear cartucho desde CLI:

```powershell
3sd create --root G:\ --display-name "The Last of Us Part II Remastered" --app-id 2531310
```

Reparar cartucho desde CLI:

```powershell
3sd repair --root G:\ --display-name "Nombre correcto" --app-id 123456
```

Ejecutar pruebas:

```powershell
py -m pytest
```

## Instalador Local

Preparar, firmar, empaquetar e instalar en esta PC:

```powershell
.\Preparar-3SD.bat
```

El flujo local instala en:

```text
%LOCALAPPDATA%\Programs\3SD
```

## Documentacion

La documentacion completa del proyecto esta en [MANUAL.md](MANUAL.md).
