@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "INSTALL_DIR=%LOCALAPPDATA%\Programs\3SD"

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
echo Este proceso va a cerrar instancias antiguas, crear el .exe, firmarlo,
echo preparar el paquete local e instalar o actualizar la aplicacion en esta PC.
echo Tambien desbloquea el ejecutable e instala la confianza local necesaria.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%scripts\prepare_3sd.ps1" -InstallDirectory "%INSTALL_DIR%"

set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" (
  echo 3SD quedo listo para usar.
  echo Abre la app desde el escritorio o el menu inicio.
) else (
  echo No se pudo preparar 3SD. Codigo: %RESULT%
  pause
)
exit /b %RESULT%
