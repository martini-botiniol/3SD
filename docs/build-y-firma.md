# Build Y Firma Local

## Dependencias

Instala dependencias del proyecto y build:

```powershell
py -m pip install -e ".[build]"
```

Dependencias principales:

- `Pillow`
- `pystray`
- `pywin32` en Windows
- `pyinstaller` para build

## Build `.exe`

```powershell
.\scripts\build\build_exe.ps1
```

Salida:

```text
dist\3SD.exe
```

El script:

- cierra procesos `3SD` y `CartridgeLauncher` abiertos, salvo
  `-NoStopRunningApp`.
- limpia `build/` y `dist/`, salvo `-NoClean`.
- instala dependencias, salvo `-SkipInstall`.
- ejecuta PyInstaller.
- embebe `assets\3SD.ico` si existe; si no, usa `assets\CartridgeLauncher.ico`
  como fallback.

## Firma Local De Desarrollo

Para firmar con certificado local self-signed:

```powershell
.\scripts\build\build_exe.ps1 -UseLocalCertificate
```

Esto:

- crea o reutiliza un certificado `CN=3SD Local Dev`.
- lo instala en `CurrentUser\My`.
- lo confia en:
  - `CurrentUser\Root`
  - `CurrentUser\TrustedPublisher`
- al instalar, si el instalador corre como administrador, tambien intenta
  confiar el certificado en `LocalMachine\Root` y
  `LocalMachine\TrustedPublisher`.
- firma el `.exe` con `Set-AuthenticodeSignature`.

Windows puede mostrar una advertencia al confiar el certificado. Es esperada si
el certificado fue creado por ti para desarrollo local.

Verificar firma:

```powershell
Get-AuthenticodeSignature .\dist\3SD.exe
```

Resultado esperado:

```text
Status : Valid
```

## Firmar Un `.exe` Ya Generado

```powershell
.\scripts\build\sign_local_dev.ps1
```

El script tambien exporta el certificado publico a:

```text
dist\3SD-LocalDev.cer
```

## Paquete Local De Desarrollo

```powershell
.\scripts\build\package_local_dev_release.ps1
```

Genera:

```text
dist\3SD-local-dev\
```

Ese paquete incluye el `.exe`, certificado publico y scripts de instalacion.

## Instalacion Local

Flujo completo recomendado:

```powershell
.\Preparar-3SD.bat
```

Instala o actualiza en:

```text
%LOCALAPPDATA%\Programs\3SD
```

El instalador cierra instancias antiguas de `3SD.exe` y `CartridgeLauncher.exe`
antes de copiar archivos para permitir actualizaciones limpias.

## Limitacion De Smart App Control

La firma local ayuda en tu PC, pero no da reputacion publica.

Smart App Control puede bloquear ejecutables locales o de baja reputacion aunque
esten firmados con un certificado self-signed. El instalador local usa firma
self-signed, confianza local del certificado y desbloqueo de archivos. Si
Windows aun lo bloquea, el bloqueo viene de la politica de Smart App Control
para apps locales sin reputacion.
