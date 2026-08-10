# Ideas Principales Del Proyecto

Este documento resume las decisiones rectoras del diseno original del proyecto.
Sirve como puente entre la idea de producto y la implementacion actual.

## Idea Central

3SD recupera una interaccion fisica: insertar un SSD extraible y
hacer que ese objeto represente un videojuego concreto.

El modelo fundamental es:

```text
Cartucho (SSD) -> Launcher -> Steam -> Juego
```

No existe un camino directo desde el SSD hacia la ejecucion. El launcher no es
una tienda, no administra licencias y no reemplaza la instalacion de Steam. Su
trabajo es validar una identidad fisica autenticada y entregar a Steam un AppID
confiable.

## Experiencia Esperada

La experiencia ideal debe sentirse cercana a una consola:

1. El usuario conecta un cartucho.
2. El launcher detecta el SSD.
3. Si el cartucho es valido, el sistema solicita a Steam abrir o instalar el
   juego asociado.
4. Si el cartucho no es autentico, esta incompleto o no coincide con el
   dispositivo registrado, se rechaza antes de contactar a Steam.

La UI debe evitar que el usuario piense en rutas, ejecutables o carpetas
internas. El AppID es el identificador tecnico central, pero la experiencia debe
presentarse principalmente con nombre, portada y estado del juego.

## Principios De Diseno

### Steam Conserva La Autoridad

Steam sigue siendo responsable de:

- propiedad y licencias.
- descarga e instalacion.
- actualizaciones.
- verificacion de integridad.
- seleccion de ejecutable, parametros, servicios auxiliares y DRM.

3SD solo solicita acciones por AppID despues de validar el
cartucho.

### El Launcher Nunca Ejecuta Desde El SSD

El launcher no busca `.exe`, no ejecuta scripts, no carga DLLs y no arma rutas de
ejecucion hacia el SSD. Incluso si Steam instala archivos del juego dentro de
`SteamLibrary`, la apertura siempre se solicita a Steam por AppID.

El SSD puede contener archivos administrados por Steam. Lo prohibido es que
3SD los trate como codigo confiable o los ejecute directamente.

### Validar Antes De Confiar

La presencia de una unidad no implica que haya un cartucho. La presencia de
`.cartridge` tampoco basta. Antes de solicitar cualquier accion Steam, el
launcher debe validar estructura, manifest, firma, reglas de dominio y
asociacion fisica.

Las unidades ordinarias se ignoran. Una unidad que intenta presentarse como
cartucho, pero esta incompleta o fue modificada, produce un error visible.

### Simplicidad Deliberada

V1 favorece componentes pequenos y transparentes:

- Windows como unico sistema operativo.
- Steam como unica plataforma.
- JSON local en lugar de SQLite.
- HMAC-SHA256 local en lugar de PKI.
- cartuchos confiables solo en el equipo que los creo.
- manifest minimo.

La arquitectura debe permitir evolucionar despues sin romper la regla principal:
el launcher valida una identidad fisica y Steam administra el juego.

## Alcance V1

V1 debe demostrar que el sistema puede:

- detectar insercion y remocion de SSDs.
- distinguir unidades ordinarias de cartuchos.
- autenticar `manifest.json` con HMAC-SHA256.
- detectar modificaciones del manifest.
- validar AppID y `libraryPath` antes de usarlos.
- asociar el cartucho con el dispositivo registrado.
- solicitar apertura o instalacion a Steam.
- permitir que Steam administre `SteamLibrary`.
- notificar estados y errores en lenguaje comprensible.

Quedan fuera de V1: nube, cuentas propias, portabilidad segura entre equipos,
firma asimetrica, SQLite, plataformas distintas de Steam, artwork formal dentro
del cartucho e integridad propia de archivos del juego.

## Decisiones Registradas

| Referencia | Decision |
| --- | --- |
| PD-42 | Usar autenticacion local HMAC-SHA256. |
| PD-43 | Los cartuchos V1 son confiables solo en el equipo creador. |
| PD-44 | Mantener `manifest.json` minimo. |
| PD-45 | Usar JSON en lugar de SQLite inicialmente. |
| RS-15 | El launcher nunca ejecuta archivos desde el SSD. |
| RS-16 | Ignorar unidades desconocidas salvo que presenten estructura de cartucho. |
