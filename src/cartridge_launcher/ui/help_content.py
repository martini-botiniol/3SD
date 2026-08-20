from __future__ import annotations

helpTitle = "Ayuda de 3SD"
helpText = """3SD convierte un SSD extraible en un cartucho fisico para Steam.

Flujo recomendado

1. Conecta el SSD que quieres usar como cartucho.
2. Abre el menu con el boton de tres lineas.
3. En "Seleccionar SSD y juego", elige el disco.
4. Escribe el nombre del juego o buscalo por nombre.
5. Confirma que el Steam AppID sea el correcto.
6. Abre "Crear cartucho" para preparar un SSD nuevo, "Actualizar cartucho" para reemplazar el juego de un cartucho existente, o "Reparar cartucho" si el SSD aparece como invalido.
7. Cuando el SSD SLOT muestre "Listo", usa Jugar o Instalar.

SSD SLOT

- Sin cartucho: no hay un SSD preparado conectado.
- Validando: la app esta revisando la estructura, el manifiesto y la firma.
- Listo: el cartucho es valido y puede enviar una orden a Steam.
- Cartucho invalido: falta metadata, el manifiesto no es valido o la firma no coincide.
- SSD no coincide: el cartucho pertenece a otro dispositivo registrado.

Menu lateral

Las secciones empiezan cerradas para mantener el panel ordenado. Abre solo la
seccion que necesites:

- Seleccionar SSD y juego: disco, detalles del disco, busqueda en Steam y AppID.
- Crear cartucho: prepara un SSD nuevo con el juego elegido.
- Actualizar cartucho: conserva el cartucho y cambia el juego asociado.
- Reparar cartucho: reconstruye metadata, firma y registro local para un SSD invalido.
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
valido hasta repararlo, volver a crearlo o actualizarlo desde la app.
"""
