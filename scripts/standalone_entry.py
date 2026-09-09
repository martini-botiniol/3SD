from cartridge_launcher.app.main import main

if __name__ == "__main__":
    import sys
    try:
        result = main()
        if len(sys.argv) > 1 and sys.argv[1] == "install":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "3SD instalado. Abre la biblioteca desde el acceso directo. Si ya estaba abierto, sal de la bandeja y vuelve a abrirlo.", "3SD", 0)
        raise SystemExit(result)
    except Exception as exc:
        if "self-check" not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "3SD: no se pudo completar", 16)
        raise SystemExit(1)
