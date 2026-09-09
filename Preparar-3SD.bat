@echo off
setlocal
if defined THREE_SD_PYTHON (
  "%THREE_SD_PYTHON%" "%~dp0scripts\prepare_3sd.py" %*
) else (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 "%~dp0scripts\prepare_3sd.py" %*
  ) else (
    python "%~dp0scripts\prepare_3sd.py" %*
  )
)
if errorlevel 1 (
  echo No se pudo preparar 3SD. Revisa el error anterior.
  echo Se requiere Python 3.11 o superior con Tcl/Tk y pip.
  echo Puedes definir THREE_SD_PYTHON con la ruta a python.exe.
  pause
  exit /b 1
)
echo 3SD listo. Usa el acceso directo del escritorio o Abrir-3SD.bat.
