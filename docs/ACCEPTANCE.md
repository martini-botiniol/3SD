# Matriz de aceptación 0.2

## Escenarios implementados

| Escenario | Resultado esperado |
|---|---|
| V2 creado en A y conectado en B | Validación y registro sin convertir, misma identidad. |
| Actualización en B, regreso a A | Autorización válida y datos actualizados. |
| V1 externo | Botón de conversión explícita; nunca convertir al conectar. |
| V2 alterado, sin autorización o con token copiado | Rechazo sin fallback a V1. |
| Versión o clave desconocida | Actualizar 3SD, sin reparación destructiva. |
| Juego completo en biblioteca registrada | Solicitud de apertura y confirmación observada. |
| Juego ausente o parcial | Solicitud de instalación/reanudación en Steam. |
| Steam ausente | Mensaje para instalarlo; ninguna apertura de juego. |
| Biblioteca sin registrar | Mostrar carpeta para añadir en Almacenamiento de Steam. |
| Segundo cartucho conectado | Espera; se evalúa al retirar el activo. |
| Desconexión o cambio de letra reutilizada | Cancelar resultados de sesión anterior y revalidar. |
| Registro corrupto | Aviso y respaldo, o error sin sobrescribir datos. |
| Red lenta o ausente | UI responde, portadas de respaldo, AppID manual disponible. |
| Actualización de instalación fallida | Conservar accesos y generación anterior. |

## Verificación automatizada

Ejecutar `python -m pytest`. Las suites de portabilidad modelan dos perfiles
independientes sobre directorios temporales. Las de Steam simulan el cliente y
archivos de bibliotecas. No se abren juegos ni se modifican discos reales.
El build autónomo ejecuta `self-check` antes de producir el ZIP.

## Verificación física pendiente

Estos puntos requieren dos PCs Windows y dos SSD con juegos reales; no se deben
marcar aprobados solo por pasar las pruebas automatizadas:

- Instalar el ZIP en una PC sin Python y comprobar biblioteca, bandeja e inicio automático.
- Añadir la biblioteca del SSD a Steam una vez y probar conectar/abrir/desconectar.
- Intercambiar A → B → A, actualizar en B y volver a A.
- Repetir con cuenta sin licencia, Steam cerrado, descarga parcial y sin internet.
- Probar juegos duplicados en otras bibliotecas y comprobar qué instalación abre Steam.
- Conectar dos SSD, retirar el activo y verificar promoción del segundo.
- Probar adaptadores distintos, cambios rápidos y desconexión durante una operación
  de metadata sobre un cartucho de prueba sin datos importantes.
- Repetir abrir/cerrar ventana, reiniciar Windows, actualizar y desinstalar.
- Revisar escalado 100/150/200 %, pantalla pequeña y navegación con teclado.

Registrar versión de Windows/Steam, adaptador, sistema de archivos, resultado y
log relevante por escenario. No publicar como validación física completa sin estos resultados.
