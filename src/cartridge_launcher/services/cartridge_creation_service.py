from pathlib import Path
from cartridge_launcher.services.cartridge_writer import CartridgeWriter


class CartridgeCreationService(CartridgeWriter):
    def create(self, root: Path, displayName: str, appId: str):
        return self.write(root, 'create', displayName, appId)
