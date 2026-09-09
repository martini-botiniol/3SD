"""Prepare an isolated, versioned Python installation. Never move a venv."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import venv


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def prepare(root: Path, source: Path) -> Path:
    if os.name != "nt" or sys.version_info < (3, 11):
        raise RuntimeError("Se requiere Windows y Python 3.11 o superior.")
    import tkinter
    tkinter.Tcl()
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # A lock also prevents two independent copies of the ZIP from publishing together.
    lock = root / "preparing.lock"
    with lock.open("a+b") as handle:
        import msvcrt
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Otra preparacion de 3SD esta en curso.") from exc
        candidate = root / "runtimes" / uuid.uuid4().hex
        candidate.mkdir(parents=True)
        try:
            print(f"Preparando entorno: {candidate}", flush=True)
            venv.EnvBuilder(with_pip=True).create(candidate)
            python = str(candidate / "Scripts" / "python.exe")
            wheels = sorted((source / "wheelhouse").glob("3sd-*.whl"))
            if not wheels:
                if not (source / "pyproject.toml").is_file():
                    raise RuntimeError("El ZIP no contiene la wheel de 3SD. Vuelve a extraerlo completo.")
                run([python, "-m", "pip", "install", "setuptools==80.9.0", "wheel==0.45.1"])
                wheelhouse = candidate / "wheelhouse"
                run([python, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
                     "--wheel-dir", str(wheelhouse), str(source)])
                wheels = sorted(wheelhouse.glob("3sd-*.whl"))
            if len(wheels) != 1:
                raise RuntimeError("Debe haber exactamente una wheel de 3SD.")
            run([python, "-m", "pip", "install", str(wheels[0])])
            run([python, "-m", "pip", "check"])
            # Check from outside the checkout so source imports cannot hide packaging errors.
            run([python, "-I", "-m", "cartridge_launcher.app.diagnostics"], cwd=root)
            run([python, "-I", "-m", "cartridge_launcher.infrastructure.deployment",
                 "--root", str(root), "--source", str(source)], cwd=root)
            print("Preparacion completada. Inicio automatico conservado/configurado.")
            return candidate
        except Exception as exc:
            (candidate / "failed.json").write_text(json.dumps({"error": str(exc)}, indent=2), encoding="utf-8")
            print("No se activo el entorno nuevo. La instalacion anterior se conserva.", file=sys.stderr)
            raise
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-directory", type=Path,
                        default=Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "3SD")
    args = parser.parse_args()
    try:
        prepare(args.install_directory, Path(__file__).resolve().parent.parent)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
