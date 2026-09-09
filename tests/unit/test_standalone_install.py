import json
from pathlib import Path
from unittest.mock import patch

import pytest
from cartridge_launcher.infrastructure import standalone_install as installer


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / "extracted"
    (source / "_internal").mkdir(parents=True)
    (source / "3SD.exe").write_bytes(b"exe")
    paths = tuple(tmp_path / name / "3SD.lnk" for name in ("desktop", "menu", "startup"))
    return tmp_path / "installed", source, paths


def shortcut(path, command, cwd):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(command))


def test_standalone_update_preserves_disabled_startup_and_previous_package(setup):
    root, source, paths = setup
    with patch.object(installer, "shortcutPaths", return_value=paths), patch.object(installer, "createShortcut", side_effect=shortcut), patch.object(installer.subprocess, "run") as check:
        installer.install(root, source)
        first = json.loads((root / "standalone.json").read_text())["package"]
        paths[2].unlink()
        installer.install(root, source)
    state = json.loads((root / "standalone.json").read_text())
    assert state["previousPackage"] == first
    assert Path(first).is_dir()
    assert not paths[2].exists()
    assert check.call_count == 2
    assert json.loads(paths[0].read_text())[0] == str(Path(state["package"]) / "3SD.exe")


def test_standalone_failed_self_check_never_activates(setup):
    root, source, paths = setup
    with patch.object(installer.subprocess, "run", side_effect=RuntimeError("bad runtime")), pytest.raises(RuntimeError):
        installer.install(root, source)
    assert not (root / "standalone.json").exists()
    assert all(not path.exists() for path in paths)


def test_standalone_publication_failure_restores_shortcuts(setup):
    root, source, paths = setup
    with patch.object(installer, "shortcutPaths", return_value=paths), patch.object(installer, "createShortcut", side_effect=shortcut), patch.object(installer.subprocess, "run"):
        installer.install(root, source)
        old = {path: path.read_bytes() for path in (*paths, root / "standalone.json")}
        count = 0
        def fail(path, command, cwd):
            nonlocal count
            shortcut(path, command, cwd)
            count += 1
            if count == 2:
                raise RuntimeError("publication failure")
        with patch.object(installer, "createShortcut", side_effect=fail), pytest.raises(RuntimeError):
            installer.install(root, source)
    assert all(path.read_bytes() == data for path, data in old.items())


def test_standalone_rejects_source_inside_destination(setup):
    root, source, paths = setup
    with pytest.raises(ValueError):
        installer.install(source, source)
