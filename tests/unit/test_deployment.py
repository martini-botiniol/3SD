import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cartridge_launcher.infrastructure import deployment


@pytest.mark.parametrize('previous,legacy,exists,wanted', [
    (False, False, False, True), (False, True, True, True),
    (False, True, False, False), (True, False, False, False), (True, False, True, True),
])
def test_startup_preference(previous, legacy, exists, wanted):
    assert deployment.startupWanted(previous, legacy, exists) is wanted


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / 'installation with spaces'
    runtime = root / 'runtimes' / 'candidate'
    (runtime / 'Scripts').mkdir(parents=True)
    (runtime / 'Scripts' / 'pythonw.exe').touch()
    paths = tuple(tmp_path / folder / '3SD.lnk' for folder in ('desktop', 'menu', 'startup'))
    return root, runtime, paths


def fake_shortcut(path, command, workingDirectory):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'command': command, 'cwd': str(workingDirectory)}))


def test_first_install_and_update_preserve_disabled_startup(installation, tmp_path):
    root, runtime, paths = installation
    with patch.object(deployment, 'shortcutPaths', return_value=paths), patch.object(deployment, 'createShortcut', side_effect=fake_shortcut):
        deployment.publish(root, runtime, tmp_path)
        assert paths[2].exists()
        assert '--open-window' not in json.loads(paths[2].read_text())['command']
        paths[2].unlink()
        second = root / 'runtimes' / 'second'
        (second / 'Scripts').mkdir(parents=True)
        (second / 'Scripts' / 'pythonw.exe').touch()
        deployment.publish(root, second, tmp_path)
    state = json.loads((root / 'installation.json').read_text())
    assert state['runtime'] == str(second)
    assert state['previousRuntime'] == str(runtime)
    assert runtime.exists()
    assert not paths[2].exists()
    assert str(second / 'Scripts' / 'pythonw.exe') == json.loads(paths[0].read_text())['command'][0]


def test_failed_publication_restores_old_shortcuts_and_manifest(installation, tmp_path):
    root, runtime, paths = installation
    old = {'runtime': 'previous environment'}
    (root / 'installation.json').write_text(json.dumps(old))
    for path in paths:
        path.parent.mkdir(parents=True)
        path.write_bytes(b'old shortcut')
    calls = 0
    def fail_second(path, command, workingDirectory):
        nonlocal calls
        calls += 1
        fake_shortcut(path, command, workingDirectory)
        if calls == 2:
            raise RuntimeError('shortcut failure')
    with patch.object(deployment, 'shortcutPaths', return_value=paths), patch.object(deployment, 'createShortcut', side_effect=fail_second):
        with pytest.raises(RuntimeError, match='shortcut failure'):
            deployment.publish(root, runtime, tmp_path)
    assert json.loads((root / 'installation.json').read_text()) == old
    assert all(path.read_bytes() == b'old shortcut' for path in paths)
    assert not (root / 'Abrir-3SD.bat').exists()


def test_runtime_outside_installation_rejected(installation, tmp_path):
    root, runtime, paths = installation
    with pytest.raises(ValueError):
        deployment.publish(root, tmp_path, tmp_path)
