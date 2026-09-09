from pathlib import Path
from cartridge_launcher.services.cartridge_writer import CartridgeWriter


class CartridgeUpdateService(CartridgeWriter):
    def update(self, root: Path, displayName: str, appId: str):
        return self.write(root, 'update', displayName, appId)
