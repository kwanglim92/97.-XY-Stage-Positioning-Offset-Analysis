"""onefile 내장 스펙 및 Windows 레지스트리 사용자 설정 회귀 테스트."""

import json
from pathlib import Path

from core import settings


class _FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _FakeWinreg:
    HKEY_CURRENT_USER = object()
    REG_SZ = 1
    REG_DWORD = 4

    def __init__(self):
        self.values = {}

    def CreateKey(self, root, path):
        assert root is self.HKEY_CURRENT_USER
        assert path == r'Software\XYStageOffset'
        return _FakeKey()

    def OpenKey(self, root, path):
        assert root is self.HKEY_CURRENT_USER
        assert path == r'Software\XYStageOffset'
        if not self.values:
            raise FileNotFoundError(path)
        return _FakeKey()

    def SetValueEx(self, key, name, reserved, value_type, value):
        self.values[name] = (value, value_type)

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name]


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_build_script_creates_onefile_with_embedded_settings_and_cleanup():
    project_dir = Path(__file__).resolve().parents[1]
    build_script = (project_dir / 'build.bat').read_text(encoding='utf-8')

    assert '--onefile' in build_script
    assert 'src\\core\\settings.json;core' in build_script
    assert 'del /q "%PROJECT_DIR%dist\\settings.json"' in build_script


def test_frozen_resource_path_matches_packaged_core_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'IS_FROZEN', True)
    monkeypatch.setattr(settings.sys, '_MEIPASS', str(tmp_path), raising=False)

    resolved = settings._resolve_bundled_settings_file()

    assert resolved == str(tmp_path / 'core' / 'settings.json')


def test_source_mode_reads_embedded_settings_json(monkeypatch):
    monkeypatch.setattr(settings, 'IS_FROZEN', False)
    loaded = settings.load_settings()

    assert list(loaded['spec_deviation']) == [
        'Vision Pattern', 'In-Die Align', 'LLC Translation', 'Global Align'
    ]
    assert loaded['spec_deviation']['Vision Pattern'] == {
        'spec_range': 1.0, 'spec_stddev': 0.2
    }


def test_frozen_mode_uses_embedded_specs_and_registry_user_settings(tmp_path, monkeypatch):
    bundled = tmp_path / 'bundled-settings.json'
    legacy_external = tmp_path / 'settings.json'
    expected_specs = {
        'Vision Pattern': {'spec_range': 1.0, 'spec_stddev': 0.2},
        'Global Align': {'spec_range': 6.0, 'spec_stddev': 1.2},
    }
    _write_json(bundled, {
        'spec_deviation': expected_specs,
        'spec_limits': {'Vision Pattern': {'X': {'lsl': -5000, 'usl': 5000}}},
        'last_folder': '',
        'wafer_size': 300,
    })
    _write_json(legacy_external, {
        'spec_deviation': {},
        'last_folder': 'E:/must-not-be-read',
    })
    monkeypatch.setattr(settings, 'BUNDLED_SETTINGS_FILE', str(bundled))
    monkeypatch.setattr(settings, 'IS_FROZEN', True)
    monkeypatch.setattr(settings, '_read_registry_settings', lambda: {
        'last_folder': 'D:/measurement-data',
        'wafer_size': 200,
        'spec_deviation': {'Vision Pattern': {'spec_range': 99.0}},
    })

    loaded = settings.load_settings()

    assert loaded['spec_deviation'] == expected_specs
    assert loaded['spec_limits']['Vision Pattern']['X']['usl'] == 5000
    assert loaded['last_folder'] == 'D:/measurement-data'
    assert loaded['wafer_size'] == 200


def test_frozen_save_writes_only_allowed_registry_values(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(settings, 'IS_FROZEN', True)
    monkeypatch.setattr(settings, '_write_registry_settings', captured.update)

    settings.save_settings({
        'spec_limits': {'Vision Pattern': {}},
        'spec_deviation': {'Vision Pattern': {'spec_range': 1.0}},
        'standard_recipe_names': ['Vision Pattern'],
        'last_folder': 'D:/measurement-data',
        'window_geometry': '1600x900+0+0',
        'recent_folders': ['D:/measurement-data'],
        'wafer_size': 200,
        'outlier_method': 'iqr',
    })

    assert captured == {
        'last_folder': 'D:/measurement-data',
        'window_geometry': '1600x900+0+0',
        'recent_folders': ['D:/measurement-data'],
        'wafer_size': 200,
    }
    assert not (tmp_path / 'settings.json').exists()


def test_registry_roundtrip_serializes_list_and_integer(monkeypatch):
    fake_registry = _FakeWinreg()
    monkeypatch.setattr(settings, 'winreg', fake_registry)
    expected = {
        'last_folder': 'D:/measurement-data',
        'window_geometry': '1600x900+0+0',
        'recent_folders': ['D:/measurement-data', 'E:/archive'],
        'wafer_size': 200,
    }

    settings._write_registry_settings(expected)
    loaded = settings._read_registry_settings()

    assert loaded == expected
    assert fake_registry.values['recent_folders'][1] == fake_registry.REG_SZ
    assert fake_registry.values['wafer_size'][1] == fake_registry.REG_DWORD


def test_source_save_writes_json_file(tmp_path, monkeypatch):
    target = tmp_path / 'settings.json'
    expected = {
        'spec_deviation': {'Vision Pattern': {'spec_range': 1.0}},
        'wafer_size': 200,
    }
    monkeypatch.setattr(settings, 'IS_FROZEN', False)
    monkeypatch.setattr(settings, 'BUNDLED_SETTINGS_FILE', str(target))

    settings.save_settings(expected)

    assert json.loads(target.read_text(encoding='utf-8')) == expected
