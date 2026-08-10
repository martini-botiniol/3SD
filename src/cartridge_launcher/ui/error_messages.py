from __future__ import annotations

from dataclasses import dataclass

from cartridge_launcher.domain.errors import ErrorCode


@dataclass(frozen=True)
class FriendlyError:
    title: str
    message: str
    action: str


ERROR_MESSAGES = {
    ErrorCode.INVALID_STRUCTURE: FriendlyError("Cartucho incompleto", "No se encontro la estructura esperada.", "Revisa que el SSD haya sido preparado desde la app."),
    ErrorCode.INVALID_MANIFEST: FriendlyError("Manifiesto invalido", "El archivo manifest.json no se puede leer.", "Vuelve a crear el cartucho."),
    ErrorCode.INVALID_SIGNATURE: FriendlyError("Cartucho modificado", "El cartucho fue modificado o no coincide con su firma.", "Vuelve a preparar este SSD desde la app."),
    ErrorCode.UNSUPPORTED_SCHEMA: FriendlyError("Cartucho no compatible", "La version del cartucho no es compatible.", "Actualiza 3SD o recrea el cartucho."),
    ErrorCode.INVALID_APP_ID: FriendlyError("Steam AppID invalido", "El identificador de Steam no es valido.", "Busca el juego de nuevo o ingresa un AppID numerico."),
    ErrorCode.INVALID_LIBRARY_PATH: FriendlyError("Biblioteca invalida", "La ruta de biblioteca no es segura.", "Recrea el cartucho desde la app."),
    ErrorCode.DEVICE_MISMATCH: FriendlyError("SSD no coincide", "Este cartucho pertenece a otro dispositivo.", "Usa el SSD original o vuelve a prepararlo."),
    ErrorCode.STEAM_NOT_FOUND: FriendlyError("Steam requerido", "No se encontro Steam.", "Instala o abre Steam y vuelve a intentar."),
    ErrorCode.GAME_NOT_INSTALLED: FriendlyError("Juego no instalado", "Steam no reporta el juego instalado.", "Usa Instalar o deja que la app lo prepare."),
    ErrorCode.DEVICE_REMOVED: FriendlyError("SSD removido", "El disco seleccionado ya no esta disponible.", "Conecta de nuevo el SSD."),
    ErrorCode.CARTRIDGE_ALREADY_EXISTS: FriendlyError("Cartucho ya creado", "Este SSD ya tiene un cartucho asociado.", "Usa Actualizar cartucho para cambiar el juego, o elimina el registro duplicado desde la biblioteca."),
}


def friendlyErrorFromCode(code: ErrorCode) -> FriendlyError:
    return ERROR_MESSAGES[code]
