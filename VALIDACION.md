# Validacion de la migracion Python

Fecha: 2026-09-08. Estado: implementacion y migracion local verificadas;
aceptacion en otro equipo y reinicios fisicos pendiente.

## Comprobado

- 84 pruebas automatizadas: arranque, instancia unica, accesos directos, rutas
  con espacios, preferencias de inicio y recuperacion ante errores de preparacion.
- Instalacion real con Python 3.14.3: wheel, dependencias fijadas, pip check,
  Tkinter, backend de bandeja e integracion Windows.
- Prueba de escritorio: bandeja sin biblioteca inicial, segunda apertura sin
  duplicados, una biblioteca visible, cierre de biblioteca manteniendo bandeja y salida.
- Actualizacion desde el ZIP extraido en una ruta con espacios; inicio desactivado
  conservado y preferencia original restaurada al finalizar la prueba.
- Diagnostico correcto despues de borrar la carpeta extraida. Entorno anterior
  conservado y hashes de registro/secreto de usuario sin cambios.
- EXE antiguo y certificados locales retirados. Clave privada ausente verificada.
  La limpieza elevada termino con codigo 0 y conserva informes por elemento.

Evidencia local generada: `dist/windows-smoke.json`,
`dist/distribution-validation.json` y el informe `legacy-cleanup-report.json`
dentro de la carpeta instalada. Los informes generados no se versionan.

## Pendiente de aceptacion manual

- Reiniciar y apagar/encender Windows: tras iniciar sesion debe quedar una sola
  instancia en la bandeja, sin consola ni biblioteca abierta.
- Cerrar/iniciar sesion con inicio automatico activado y desactivado; comprobar
  una instancia o ninguna, respectivamente.
- Descargar el ZIP y repetir preparacion y uso en otro Windows con cuenta
  estandar, protecciones activadas y sin certificados de desarrollo.
- Probar SSD reales ya conectados al iniciar, insercion/extraccion y apertura de
  un juego mediante Steam. La prueba automatizada de escritorio usa accion Steam
  `none` y no inicia juegos ni prepara/repara cartuchos.

Para repetir la prueba de escritorio, cerrar primero 3SD y ejecutar con el
`python.exe` del entorno instalado:

```powershell
python -I scripts/smoke_windows.py --report resultado-escritorio.json
```

Usar el Python instalado en 3SD, no un interprete sin el paquete instalado.
La prueba abre y cierra una biblioteca y termina el tray que ella misma creo.
El criterio de exito es `success: true` en el informe.
