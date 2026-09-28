"""
Tests for settings management module.
Consolidated tests with high assertion density.
"""

import json
from unittest.mock import patch

import pytest

from opencode_status_bar.utils import settings
from opencode_status_bar.utils.settings import Settings, get_settings, save_settings


class TestSettingsDataclass:
    """Tests for Settings dataclass initialization"""

    @pytest.mark.parametrize(
        "init_kwargs,expected_values",
        [
            # Default values when no args
            (
                {},
                {
                    "usage_refresh_interval": 60,
                    "permission_threshold_seconds": 5,
                    "ask_user_timeout": 1800,
                },
            ),
            # Custom usage_refresh_interval preserves other defaults
            (
                {"usage_refresh_interval": 120},
                {
                    "usage_refresh_interval": 120,
                    "permission_threshold_seconds": 5,
                    "ask_user_timeout": 1800,
                },
            ),
            # Custom permission_threshold_seconds preserves other defaults
            (
                {"permission_threshold_seconds": 10},
                {
                    "usage_refresh_interval": 60,
                    "permission_threshold_seconds": 10,
                    "ask_user_timeout": 1800,
                },
            ),
            # Custom ask_user_timeout preserves other defaults
            (
                {"ask_user_timeout": 3600},
                {
                    "usage_refresh_interval": 60,
                    "permission_threshold_seconds": 5,
                    "ask_user_timeout": 3600,
                },
            ),
            # All custom values
            (
                {
                    "usage_refresh_interval": 90,
                    "permission_threshold_seconds": 15,
                    "ask_user_timeout": 7200,
                },
                {
                    "usage_refresh_interval": 90,
                    "permission_threshold_seconds": 15,
                    "ask_user_timeout": 7200,
                },
            ),
        ],
    )
    def test_initialization_with_defaults_and_custom_values(
        self, init_kwargs, expected_values
    ):
        """Settings should initialize with correct defaults and accept custom values"""
        s = Settings(**init_kwargs)

        assert s.usage_refresh_interval == expected_values["usage_refresh_interval"]
        assert (
            s.permission_threshold_seconds
            == expected_values["permission_threshold_seconds"]
        )
        assert s.ask_user_timeout == expected_values["ask_user_timeout"]
        # Verify only expected fields exist
        assert set(vars(s).keys()) == {
            "usage_refresh_interval",
            "permission_threshold_seconds",
            "ask_user_timeout",
        }


class TestSettingsPersistence:
    """Tests for Settings.save() and Settings.load() file operations"""

    def test_save_creates_directory_and_writes_then_overwrites(self, tmp_path):
        """save() should create config directory, write JSON, and overwrite on subsequent saves"""
        config_dir = tmp_path / "config"
        config_file = config_dir / "settings.json"

        with (
            patch.object(settings, "CONFIG_DIR", str(config_dir)),
            patch.object(settings, "CONFIG_FILE", str(config_file)),
        ):
            # First save: creates directory and file
            s1 = Settings(
                usage_refresh_interval=90,
                permission_threshold_seconds=15,
                ask_user_timeout=7200,
            )
            s1.save()

            assert config_dir.is_dir()
            assert config_file.is_file()
            with open(config_file) as f:
                data1 = json.load(f)
            assert data1 == {
                "usage_refresh_interval": 90,
                "permission_threshold_seconds": 15,
                "ask_user_timeout": 7200,
            }

            # Second save: overwrites with new values
            s2 = Settings(
                usage_refresh_interval=120,
                permission_threshold_seconds=20,
                ask_user_timeout=900,
            )
            s2.save()

            with open(config_file) as f:
                data2 = json.load(f)
            assert data2 == {
                "usage_refresh_interval": 120,
                "permission_threshold_seconds": 20,
                "ask_user_timeout": 900,
            }
            # Old values completely replaced
            assert data2["usage_refresh_interval"] == 120
            assert data2["permission_threshold_seconds"] == 20

    def test_load_reads_existing_file_and_filters_obsolete_fields(self, tmp_path):
        """load() should read valid fields, ignore obsolete fields, and apply defaults for missing"""
        config_file = tmp_path / "settings.json"

        # File with some valid fields, some obsolete, some missing
        config_file.write_text(
            json.dumps(
                {
                    "usage_refresh_interval": 45,
                    "permission_threshold_seconds": 10,
                    # ask_user_timeout is missing - should get default
                    "obsolete_field": "should be ignored",
                    "another_old_setting": 999,
                }
            )
        )

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            s = Settings.load()

            # Valid fields loaded correctly
            assert s.usage_refresh_interval == 45
            assert s.permission_threshold_seconds == 10
            # Missing field gets default
            assert s.ask_user_timeout == 1800
            # Only valid fields present in object
            assert list(vars(s).keys()) == [
                "usage_refresh_interval",
                "permission_threshold_seconds",
                "ask_user_timeout",
            ]
            assert len(vars(s)) == 3

    @pytest.mark.parametrize(
        "scenario",
        ["file_missing", "invalid_json", "permission_error"],
    )
    def test_load_returns_defaults_on_any_error(self, tmp_path, scenario):
        """load() should return default settings on file missing, invalid JSON, or read error"""
        if scenario == "file_missing":
            config_file = tmp_path / "nonexistent" / "settings.json"
        else:
            config_file = tmp_path / "settings.json"
            if scenario == "invalid_json":
                config_file.write_text("not valid json {{{")
            else:
                config_file.write_text('{"usage_refresh_interval": 45}')

        with patch.object(settings, "CONFIG_FILE", str(config_file)):
            if scenario == "permission_error":
                with patch(
                    "builtins.open", side_effect=PermissionError("Access denied")
                ):
                    s = Settings.load()
            else:
                s = Settings.load()

            # All error scenarios return exact defaults
            assert s.usage_refresh_interval == 60
            assert s.permission_threshold_seconds == 5
            assert s.ask_user_timeout == 1800


class TestSettingsGlobalAccess:
    """Tests for get_settings() and save_settings() singleton pattern"""

    def setup_method(self):
        settings._settings = None

    def teardown_method(self):
        settings._settings = None

    def test_get_settings_lazy_loads_caches_and_save_persists(self, tmp_path):
        """get_settings() lazy loads, caches instance; save_settings() persists modifications"""
        config_dir = tmp_path / "config"
        config_file = config_dir / "settings.json"

        # Create initial config file
        config_dir.mkdir(parents=True)
        config_file.write_text(
            '{"usage_refresh_interval": 75, "permission_threshold_seconds": 8}'
        )

        with (
            patch.object(settings, "CONFIG_DIR", str(config_dir)),
            patch.object(settings, "CONFIG_FILE", str(config_file)),
        ):
            # First call: lazy loads from file
            s1 = get_settings()
            assert s1.usage_refresh_interval == 75
            assert s1.permission_threshold_seconds == 8
            assert s1.ask_user_timeout == 1800  # default for missing field

            # Second call: returns cached instance (identity check)
            s2 = get_settings()
            assert s1 is s2

            # Modify and save
            s1.usage_refresh_interval = 200
            s1.permission_threshold_seconds = 25
            s1.ask_user_timeout = 900
            save_settings()

            # Verify file contains all modifications
            with open(config_file) as f:
                data = json.load(f)
            assert data == {
                "usage_refresh_interval": 200,
                "permission_threshold_seconds": 25,
                "ask_user_timeout": 900,
            }

    def test_save_settings_noop_when_never_loaded(self):
        """save_settings() should safely do nothing if get_settings() was never called"""
        with patch.object(Settings, "save") as mock_save:
            save_settings()
            assert mock_save.call_count == 0
