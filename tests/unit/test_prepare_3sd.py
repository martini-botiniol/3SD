import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location('prepare_3sd', Path(__file__).resolve().parents[2] / 'scripts' / 'prepare_3sd.py')
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


def test_failed_dependency_install_leaves_active_environment_untouched(tmp_path):
    root = tmp_path / 'installation'
    root.mkdir()
    manifest = root / 'installation.json'
    manifest.write_text('{"runtime": "old"}')
    launcher = root / 'Abrir-3SD.bat'
    launcher.write_text('old launcher')
    source = tmp_path / 'zip'
    (source / 'wheelhouse').mkdir(parents=True)
    (source / 'wheelhouse' / '3sd-0.1.0-py3-none-any.whl').touch()
    with patch('tkinter.Tcl'), patch.object(prepare.venv.EnvBuilder, 'create'), patch.object(prepare, 'run', side_effect=RuntimeError('download failed')):
        with pytest.raises(RuntimeError, match='download failed'):
            prepare.prepare(root, source)
    assert json.loads(manifest.read_text()) == {'runtime': 'old'}
    assert launcher.read_text() == 'old launcher'
    failed, = (root / 'runtimes').glob('*/failed.json')
    assert 'download failed' in failed.read_text()


def test_checks_finish_before_publication(tmp_path):
    source = tmp_path / 'zip'
    (source / 'wheelhouse').mkdir(parents=True)
    (source / 'wheelhouse' / '3sd-0.1.0-py3-none-any.whl').touch()
    with patch('tkinter.Tcl'), patch.object(prepare.venv.EnvBuilder, 'create'), patch.object(prepare, 'run') as run:
        prepare.prepare(tmp_path / 'install with spaces', source)
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[-2][-1] == 'cartridge_launcher.app.diagnostics'
    assert 'cartridge_launcher.infrastructure.deployment' in commands[-1]
    assert all('-e' not in command for command in commands)
