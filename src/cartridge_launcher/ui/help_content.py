from __future__ import annotations

helpTitle = "Ayuda de 3SD"
helpText = """3SD convierte un SSD extraible en un cartucho fisico para Steam.

Flujo recomendado

1. Conecta el SSD que quieres usar como cartucho.
2. Abre el menu con el boton de tres lineas.
3. Abre "Opciones de cartucho" y elige Crear o Actualizar cartucho.
4. En la ventana, selecciona primero el SSD y después el juego: busca por nombre o escribe nombre y AppID.
5. Confirma la operación. Cada formulario comienza sin disco ni juego seleccionados.
6. En modo automático, conecta el cartucho y 3SD solicita abrir o instalar en Steam.
7. Para corregir metadata, abre Reparar cartucho > Reparar y confirma dentro del formulario.
8. Para un cartucho antiguo, abre Reparar cartucho > Preparar para usar en cualquier PC. Conserva el juego y un respaldo.

Solo se permite un formulario a la vez. Cancelar, Escape y X cierran el formulario;
durante una escritura debes esperar a que termine. Los errores aparecen dentro
de la misma ventana y permiten corregir y reintentar. No desconectes el SSD al guardar.

SSD SLOT

- Sin cartucho: no hay un SSD preparado conectado.
- Validando: la app esta revisando la estructura, el manifiesto y la firma.
- Listo: el cartucho es valido y puede enviar una orden a Steam.
- Cartucho invalido: falta metadata, el manifiesto no es valido o la firma no coincide.
- Cartucho antiguo: puede requerir conversion explicita para compartirlo.

Menu lateral

Las secciones empiezan cerradas para mantener el panel ordenado. Abre solo la
seccion que necesites:

- Opciones de cartucho: Crear cartucho, Actualizar cartucho y Reparar cartucho.
- Dentro de Reparar cartucho: Reparar y Preparar para usar en cualquier PC.
- Windows: activa o desactiva el inicio con Windows.
- Actividad: ultimos eventos detectados por la app.

Biblioteca

La biblioteca muestra los cartuchos registrados en esta PC. Si seleccionas una
portada, puedes ver detalles. Abrir o instalar requiere que ese mismo SSD este
insertado y validado.

Steam

La primera vez en cada PC, añade SteamLibrary del SSD en Steam > Parametros > Almacenamiento si se solicita.
Antes de retirar el SSD, termina juegos y descargas.

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
V2 con autorizacion cifrada y una carpeta SteamLibrary. Se valida antes de habilitar
acciones. Si modificas manualmente manifest.json, el cartucho dejara de ser
valido hasta repararlo, volver a crearlo o actualizarlo desde la app.
"""
