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
- Distribucion de pruebas con Python y entorno virtual por usuario.
- Inicio con Windows configurable desde la UI.

## Inicio Rapido

Instalar dependencias:

```powershell
py -m pip install -e ".[dev]"
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

## Distribucion Python para pruebas

En Windows, instala Python 3.11 o superior con **Tcl/Tk, pip y venv**.
La preparacion inicial necesita internet. No se instala Python automaticamente.

1. Extrae el ZIP completo en una carpeta.
2. Ejecuta `Preparar-3SD.bat` (sin administrador).
3. Usa el acceso directo de 3SD o `Abrir-3SD.bat`.

La aplicacion se instala en `%LOCALAPPDATA%\Programs\3SD`, con su propio
entorno virtual. Puedes eliminar la carpeta extraida cuando termine.
Python debe permanecer instalado; no uses un interprete temporal o del repositorio.
Si no se encuentra Python, define `THREE_SD_PYTHON` con la ruta a `python.exe`.

3SD vuelve a la bandeja al iniciar sesion despues de reiniciar o apagar/encender
Windows. `Iniciar con Windows` se activa en instalaciones nuevas; las actualizaciones
conservan tu preferencia. Cerrar la biblioteca no cierra la bandeja; `Exit` si.

Repite `Preparar-3SD.bat` para actualizar o reparar. Si ya estaba abierto, sal
desde la bandeja y vuelve a abrirlo. Una preparacion fallida conserva la version anterior.

Para revisar errores, usa `Diagnosticar-3SD.bat`; agrega `--run` para abrir con
consola. El registro esta en `%USERPROFILE%\.3sd\launcher.log`.

Crear el ZIP desde el entorno de desarrollo:

```powershell
python -m pip install -e ".[dev]"
python scripts/package_3sd.py
```

El ZIP se genera en `dist`. Contiene una wheel de 3SD, scripts y documentacion;
las dependencias de ejecucion tienen versiones fijadas. MSIX queda para otra etapa.

## Documentacion

La documentacion completa del proyecto esta en [MANUAL.md](MANUAL.md).
