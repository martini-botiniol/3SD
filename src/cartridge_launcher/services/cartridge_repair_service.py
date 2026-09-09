from pathlib import Path
from cartridge_launcher.services.cartridge_writer import CartridgeWriter


class CartridgeRepairService(CartridgeWriter):
    def repair(self, root: Path, displayName: str, appId: str):
        return self.write(root, 'repair', displayName, appId)
