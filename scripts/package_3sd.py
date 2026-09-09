"""Build a wheel and ZIP. Run with the development Python environment."""
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="3sd-package-") as folder:
        wheels = Path(folder)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-build-isolation",
                        "--no-deps", "--wheel-dir", str(wheels), str(root)], check=True)
        wheel, = wheels.glob("3sd-*.whl")
        output = dist / f"{wheel.name.split('-')[0]}-{wheel.name.split('-')[1]}-python.zip"
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.write(wheel, f"wheelhouse/{wheel.name}")
            for name in ("Preparar-3SD.bat", "Abrir-3SD.bat", "Diagnosticar-3SD.bat", "README.md", "MANUAL.md",
                         "scripts/prepare_3sd.py", "scripts/cleanup_legacy.ps1", "scripts/smoke_windows.py",
                         "docs/ACCEPTANCE.md", "requirements-build.txt"):
                archive.write(root / name, name)
        print(output)


if __name__ == "__main__":
    main()
