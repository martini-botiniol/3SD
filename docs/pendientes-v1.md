# Pendientes V1

## Producto

- Definir icono final.
- Revisar textos finales de UI en una pasada completa.
- Hacer prueba de flujo completo con al menos dos SSD/cartuchos reales.
- Validar experiencia de cambio rapido de cartuchos.
- Revisar textos finales para explicar que `Juego seleccionado` requiere el SSD
  insertado.

## UI

- Pulir responsive en pantallas pequenas.
- Mejorar selector de busqueda Steam con portadas/resultados mas claros.
- Separar mejor detalle tecnico de detalle simple.
- Agregar indicador visual mas claro del cartucho activo.
- Pulir feedback cuando se inserta un segundo cartucho mientras otro esta activo.
- Revisar estados vacios: sin discos, sin internet, sin Steam, sin cartuchos.

## Tray

- Mantener tray siempre activo mientras la app este abierta.
- Mantener `Exit` cerrando completamente app y proceso.
- Confirmar comportamiento despues de varios ciclos abrir/cerrar ventana.

## Steam

- Validar con un juego instalado real.
- Validar con un juego no instalado real.
- Mejorar mensaje cuando Steam recibe la orden pero no inicia nada visible.
- Evaluar deteccion mas robusta de juego instalado.
- Observar transiciones `OPENING -> GAME_RUNNING -> READY` cuando sea posible.
- Validar manualmente que no se reporta exito si Steam lanza error o no acepta
  la accion.

## Cartuchos

- Flujo de actualizacion mas guiado:
  - cambiar solo nombre
  - cambiar juego completo
  - confirmar antes de sobrescribir AppID
- Reparacion guiada para cartuchos con registro local incompleto.
- Evaluar detectar si el dispositivo es estrictamente SSD en una version futura.
- Definir migracion futura a SQLite sin cambiar contratos de servicios.
- Evaluar exportar/importar registro local solo si se disena portabilidad segura
  entre PCs; V1 asume cartuchos confiables solo en el equipo creador.

## Build

- Mantener firma local para desarrollo.
- Revisar Smart App Control con el instalador del exe en una maquina limpia.
- Mejorar el build local si Windows sigue marcando el exe.

## Tests Manuales

- Crear cartucho desde UI.
- Actualizar nombre desde UI.
- Actualizar AppID desde UI.
- Remover y reinsertar el mismo SSD.
- Insertar segundo SSD/cartucho.
- Abrir juego instalado.
- Solicitar instalacion de juego no instalado.
- Cerrar ventana y confirmar tray activo.
- Usar `Exit` y confirmar que no queda proceso.
