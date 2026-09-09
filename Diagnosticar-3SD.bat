@echo off
setlocal
if not exist "%LOCALAPPDATA%\Programs\3SD\Diagnosticar-3SD.bat" (
  echo Ejecuta Preparar-3SD.bat primero.
  pause
  exit /b 1
)
call "%LOCALAPPDATA%\Programs\3SD\Diagnosticar-3SD.bat" %*
