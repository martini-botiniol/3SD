from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cartridge_launcher.infrastructure import startup_shortcut as startup


def test_python_startup_has_module_and_no_window_request():
    with patch.object(startup, 'windowPython', return_value=Path('C:/Ruta con espacios/pythonw.exe')):
        command = startup.startupCommand()
    assert command == ['C:\\Ruta con espacios\\pythonw.exe', '-I', '-m', 'cartridge_launcher.app.main', 'tray', '--steam-action', 'auto']
    assert '--open-window' not in command


def test_shortcut_uses_com_and_quotes_arguments(tmp_path):
    shortcut = MagicMock()
    with patch('win32com.client.Dispatch') as dispatch:
        dispatch.return_value.CreateShortcut.return_value = shortcut
        startup.createShortcut(tmp_path / 'test.lnk', ['C:/space here/pythonw.exe', '-m', 'module', 'argument with spaces'], tmp_path)
    assert shortcut.TargetPath == 'C:/space here/pythonw.exe'
    assert shortcut.Arguments == '-m module "argument with spaces"'
    shortcut.Save.assert_called_once()


def test_failed_shortcut_is_not_replaced_with_text(tmp_path):
    path = tmp_path / '3SD.lnk'
    with patch.object(startup, 'startupShortcutPath', return_value=path), patch('win32com.client.Dispatch', side_effect=RuntimeError('COM failed')):
        with pytest.raises(RuntimeError, match='COM failed'):
            startup.enableStartup()
    assert not path.exists()


def test_invalid_shortcut_is_not_enabled(tmp_path):
    path = tmp_path / '3SD.lnk'
    path.write_text('old broken shortcut')
    with patch.object(startup, 'startupShortcutPath', return_value=path), patch('win32com.client.Dispatch', side_effect=RuntimeError('COM failed')):
        assert not startup.isStartupEnabled()
