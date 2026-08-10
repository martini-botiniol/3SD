from __future__ import annotations

helpTitle = "Ayuda de 3SD"
helpText = """3SD convierte un SSD extraible en un cartucho fisico para Steam.

Flujo recomendado

1. Conecta el SSD que quieres usar como cartucho.
2. Abre Opciones.
3. En "Seleccionar SSD y juego", elige el disco.
4. Escribe el nombre del juego o buscalo por nombre.
5. Confirma que el Steam AppID sea el correcto.
6. Abre "Crear cartucho" para preparar un SSD nuevo, o "Actualizar cartucho" para reemplazar el juego de un cartucho existente.
7. Cuando el SSD SLOT muestre "Listo", usa Jugar o Instalar.

SSD SLOT

- Sin cartucho: no hay un SSD preparado conectado.
- Validando: la app esta revisando la estructura, el manifiesto y la firma.
- Listo: el cartucho es valido y puede enviar una orden a Steam.
- Cartucho invalido: falta metadata, el manifiesto no es valido o la firma no coincide.
- SSD no coincide: el cartucho pertenece a otro dispositivo registrado.

Opciones

Las secciones empiezan cerradas para mantener el panel ordenado. Abre solo la
seccion que necesites:

- Seleccionar SSD y juego: disco, detalles del disco, busqueda en Steam y AppID.
- Crear cartucho: prepara un SSD nuevo con el juego elegido.
- Actualizar cartucho: conserva el cartucho y cambia el juego asociado.
- Cartucho activo: acciones para el SSD conectado en ese momento.
- Juego seleccionado: acciones para una portada elegida de la biblioteca.
- Windows: activa o desactiva el inicio con Windows.
- Actividad: ultimos eventos detectados por la app.

Biblioteca

La biblioteca muestra los cartuchos registrados en esta PC. Si seleccionas una
portada, puedes ver detalles. Abrir o instalar requiere que ese mismo SSD este
insertado y validado.

Steam

Jugar abre Steam directamente con steam.exe cuando esta disponible.
Instalar abre Steam con steam://install/{appId}.
Abrir o instalar automaticamente intenta abrir si Steam reporta el juego
instalado; si no, manda la orden de instalacion.

Tray e inicio con Windows

El modo tray mantiene 3SD residente para detectar inserciones de
SSD. Si activas "Iniciar con Windows", la app arranca en tray al iniciar sesion.
Al abrir el acceso del escritorio o menu inicio, se muestra la biblioteca y el
tray queda activo.

Seguridad

La app nunca ejecuta binarios desde el SSD. El SSD contiene un manifest.json
firmado y una carpeta SteamLibrary. La firma se valida antes de habilitar
acciones. Si modificas manualmente manifest.json, el cartucho dejara de ser
valido hasta volver a crearlo o actualizarlo desde la app.

Smart App Control

Si Windows bloquea 3SD.exe por Control inteligente de aplicaciones,
reinstala con Preparar-3SD.bat para regenerar y confiar la firma
local. Si puedes, ejecuta el instalador como administrador para que tambien
confie el certificado en el almacen de maquina local. Si el bloqueo persiste,
Windows esta aplicando reputacion de app local sin excepcion por app.

Icono

Cuando tengas el icono final, guardalo como assets\\3SD.ico y
reconstruye el exe. La app lo usara en la ventana, popups, tray y accesos.
"""
