# 3SD

Prototipo Windows + Steam para usar SSDs extraibles como cartuchos fisicos.

La app valida un manifiesto firmado dentro del SSD, registra cartuchos en la PC
local y abre o instala juegos mediante URLs oficiales de Steam. 3SD nunca
ejecuta binarios desde el SSD.

## Estado Actual

- UI principal con biblioteca de portadas.
- Tray app residente.
- Creacion y actualizacion de cartuchos.
- Deteccion de discos por polling.
- Validacion de `.cartridge/manifest.json` con firma HMAC-SHA256.
- Acciones Steam: abrir, instalar y modo automatico.
- Firma local de desarrollo para builds `.exe`.
- Inicio con Windows configurable desde la UI.

## Formas De Uso

3SD se puede probar de dos maneras distintas:

- desde el codigo fuente, para desarrollo o pruebas tecnicas.
- desde un instalador/paquete publicado, para uso normal en otra PC.

Actualmente el repositorio contiene el codigo fuente, documentacion, scripts de
instalacion local y pruebas. No incluye `build/` ni `dist/`, porque son salidas
generadas y estan excluidas del repositorio.

## Usar Desde Codigo

Este flujo sirve si quieres clonar el proyecto, instalar dependencias y ejecutar
la app directamente con Python.

Clonar el repositorio:

```powershell
git clone https://github.com/martini-botiniol/3SD.git
cd 3SD
```

Instalar dependencias locales:

```powershell
py -m pip install -e ".[build]"
```

Abrir la ventana principal:

```powershell
py -m cartridge_launcher.app.main ui
```

Iniciar en modo tray:

```powershell
py -m cartridge_launcher.app.main tray --open-window --steam-action auto
```

Crear cartucho desde CLI:

```powershell
py -m cartridge_launcher.app.main create --root G:\ --display-name "The Last of Us Part II Remastered" --app-id 2531310
```

Actualizar cartucho desde CLI:

```powershell
py -m cartridge_launcher.app.main update --root G:\ --display-name "Nuevo nombre" --app-id 123456
```

Ejecutar pruebas:

```powershell
py -m pytest
```

## Usar Con Instalador

Este seria el flujo esperado para un usuario final, sin abrir el codigo ni usar
comandos de Python:

1. Descargar el instalador o paquete publicado desde la seccion de releases del
   repositorio.
2. Ejecutar el instalador de 3SD.
3. Aceptar los permisos de Windows si el instalador necesita registrar accesos,
   accesos directos o confianza local del certificado.
4. Abrir 3SD desde el menu inicio o el acceso directo del escritorio.
5. Conectar un SSD preparado como cartucho y usar la app normalmente.

En ese escenario, el usuario solo necesita el instalador. No deberia clonar el
repositorio, instalar Python ni ejecutar scripts manuales.

> Nota: todavia no hay un instalador final publicado como release. El flujo
> actual para generar uno es local/de desarrollo.

## Preparar Instalador Local

Generar `.exe` firmado con certificado local de desarrollo:

```powershell
.\scripts\build\build_exe.ps1 -UseLocalCertificate
```

El ejecutable queda en:

```text
dist\3SD.exe
```

Preparar, firmar, empaquetar e instalar en esta PC:

```powershell
.\Preparar-3SD.bat
```

Ese flujo instala en:

```text
%LOCALAPPDATA%\Programs\3SD
```

Para que `Preparar-3SD.bat` funcione, deben existir los scripts de build bajo
`scripts\build\`. Si estas probando desde un clon limpio y esos scripts no
estan presentes, usa primero el flujo "Usar Desde Codigo" o agrega los scripts
de build antes de preparar el instalador.

## Documentacion

- [Ideas principales del proyecto](docs/ideas-principales.md)
- [Arquitectura](docs/arquitectura.md)
- [Uso de la app](docs/uso.md)
- [Cartuchos](docs/cartuchos.md)
- [Flujo de estados](docs/flujo-de-estados.md)
- [Build, firma local e instalacion](docs/build-y-firma.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Pendientes V1](docs/pendientes-v1.md)

## Icono

Cuando tengas el icono final, ponlo en:

```text
assets\3SD.ico
```

El build lo embebe en el `.exe` y la app lo usa en ventana, popups y tray.

## Smart App Control

El instalador por defecto genera y usa `3SD.exe`.

Para reducir bloqueos en una PC propia, el flujo local:

- firma el `.exe` con certificado local.
- confia ese certificado en el usuario actual.
- si el instalador corre como administrador, tambien intenta confiarlo en el
  almacen de maquina local.
- quita la marca de internet de los archivos instalados.

Smart App Control puede bloquear ejecutables locales sin reputacion publica por
politica de Windows. No hay una excepcion por app que el instalador pueda forzar,
pero el instalador deja preparado el exe para uso local con firma y certificado
confiado en esta PC.
