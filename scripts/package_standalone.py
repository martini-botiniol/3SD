"""Build a self-contained Windows ZIP without installing or starting 3SD."""
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import os
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    # Fail before packaging if Tk cannot be read (including sandbox restrictions).
    import tkinter
    tkinter.Tcl().eval("info library")
    (root / "build").mkdir(exist_ok=True)
    # Separate temp ownership for sandboxed and normal Windows executions.
    with tempfile.TemporaryDirectory(prefix="build-tests-", dir=root / "build") as testRoot:
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:cacheprovider",
                        "--basetemp", str(Path(testRoot) / "cases")], cwd=root, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "3SD", "--paths", str(root / "src"), "--hidden-import", "win32timezone",
        "--hidden-import", "win32com.shell.shell", "--hidden-import", "win32com.shell.shellcon",
        "--exclude-module", "numpy", "--exclude-module", "pytest", "--distpath", str(root / "dist"),
        "--workpath", str(root / "build" / "standalone"), "--specpath", str(root / "build"),
        str(root / "scripts" / "standalone_entry.py")], cwd=root, check=True)
    package = root / "dist" / "3SD"
    subprocess.run([str(package / "3SD.exe"), "self-check"], check=True, timeout=30,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for name in ("README.md", "MANUAL.md", "requirements-build.txt"):
        shutil.copy2(root / name, package / name)
    shutil.copytree(root / "docs", package / "docs", dirs_exist_ok=True)
    (package / "Instalar-3SD.bat").write_text('@echo off\r\n"%~dp03SD.exe" install\r\n', encoding="utf-8")
    # Record exact build environment for diagnosis/reproduction.
    # Include inherited distributions too: --local would omit shared runtime dependencies.
    frozen = subprocess.check_output([sys.executable, "-m", "pip", "list", "--format=freeze"], text=True)
    (package / "build-environment.txt").write_text(frozen, encoding="utf-8")
    output = root / "dist" / f"3SD-{version}-windows-x64.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in package.rglob("*"):
            if path.is_file():
                archive.write(path, Path("3SD") / path.relative_to(package))
    print(output)


if __name__ == "__main__":
    main()
