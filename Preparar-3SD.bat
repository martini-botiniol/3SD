@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
for %%I in ("%PROJECT_ROOT%..\..\..") do set "REAL_USERPROFILE=%%~fI"
set "INSTALL_DIR=%REAL_USERPROFILE%\AppData\Local\Programs\3SD"

net session >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
  echo Solicitando permisos de administrador para confiar la firma local...
  powershell.exe -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

echo.
echo 3SD
echo ===
echo.
echo Este proceso va a cerrar instancias antiguas, crear el .exe, firmarlo, preparar el paquete local
echo e instalar o actualizar la aplicacion en esta PC.
echo Tambien desbloquea el ejecutable e instala la confianza local necesaria.
echo.

taskkill /F /IM 3SD.exe /T >nul 2>&1
taskkill /F /IM CartridgeLauncher.exe /T >nul 2>&1

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { " ^
  "  Set-Location '%PROJECT_ROOT%'; " ^
  "  & '.\scripts\build\build_exe.ps1' -UseLocalCertificate; " ^
  "  & '.\scripts\build\sign_local_dev.ps1'; " ^
  "  & '.\scripts\build\package_local_dev_release.ps1'; " ^
  "  & '.\scripts\install\install_cartridge_launcher.ps1' -SourceDirectory '.\dist\3SD-local-dev' -InstallDirectory '%INSTALL_DIR%' -Force; " ^
  "  & '.\scripts\install\repair_smart_screen.ps1' -InstallDirectory '%INSTALL_DIR%'; " ^
  "} catch { Write-Host $_.Exception.Message -ForegroundColor Red; exit 1 }"

set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" (
  echo 3SD quedo listo para usar.
  echo Abre la app desde el escritorio o el menu inicio.
) else (
  echo No se pudo preparar 3SD. Codigo: %RESULT%
  pause
)
exit /b %RESULT%
