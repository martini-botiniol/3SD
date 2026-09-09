from pathlib import Path
from cartridge_launcher.services.cartridge_writer import CartridgeWriter


class CartridgeConversionService(CartridgeWriter):
    def convert(self, root: Path):
        return self.write(root, "convert")
