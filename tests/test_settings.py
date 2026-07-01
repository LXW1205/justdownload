"""Tests for justdownload.core.settings — persistence + cookies detection."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from justdownload.core import settings


class SettingsPathTests(unittest.TestCase):
    def test_linux_path(self):
        with mock.patch("justdownload.core.settings.sys.platform", "linux"):
            self.assertEqual(
                settings.settings_path(),
                Path.home() / ".config" / "justdownload" / "settings.json",
            )

    def test_macos_path(self):
        with mock.patch("justdownload.core.settings.sys.platform", "darwin"):
            self.assertEqual(
                settings.settings_path(),
                Path.home() / ".config" / "justdownload" / "settings.json",
            )

    def test_windows_path(self):
        with mock.patch("justdownload.core.settings.sys.platform", "win32"), \
             mock.patch.dict(os.environ, {"APPDATA": r"C:\Users\test\AppData\Roaming"}):
            self.assertEqual(
                settings.settings_path(),
                Path(r"C:\Users\test\AppData\Roaming") / "justdownload" / "settings.json",
            )


class LoadSaveTests(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        import shutil
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def test_load_returns_defaults_when_no_file(self):
        with mock.patch.object(settings, "settings_path",
                               return_value=self._tmp / "settings.json"):
            loaded = settings.load()
        self.assertIn("download_dir", loaded)
        self.assertIn("cookies_path", loaded)
        self.assertTrue(loaded["download_dir"].endswith("justdownload"))

    def test_save_then_load_round_trip(self):
        cfg = self._tmp / "settings.json"
        with mock.patch.object(settings, "settings_path", return_value=cfg):
            original = settings.load()
            original["download_dir"] = "/custom/path"
            settings.save(original)
            loaded = settings.load()
        self.assertEqual(loaded["download_dir"], "/custom/path")

    def test_load_ignores_unknown_keys(self):
        cfg = self._tmp / "settings.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(json.dumps({"download_dir": "/x", "unknown_key": "ignored"}))
        with mock.patch.object(settings, "settings_path", return_value=cfg):
            loaded = settings.load()
        self.assertEqual(loaded["download_dir"], "/x")
        self.assertNotIn("unknown_key", loaded)

    def test_load_returns_defaults_on_corrupt_file(self):
        cfg = self._tmp / "settings.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("not json {{{")
        with mock.patch.object(settings, "settings_path", return_value=cfg):
            loaded = settings.load()
        self.assertEqual(loaded, settings.DEFAULT_SETTINGS)

    def test_save_creates_parent_directory(self):
        deep = self._tmp / "a" / "b" / "c" / "settings.json"
        with mock.patch.object(settings, "settings_path", return_value=deep):
            settings.save({"download_dir": "/x", "cookies_path": ""})
        self.assertTrue(deep.is_file())


class CookiesDetectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._old_cwd = os.getcwd()
        self._old_home = os.environ.get("HOME")
        os.chdir(self._tmp)
        # Point HOME at a clean dir so ~/justdownload/cookies.txt and ~/cookies.txt don't resolve.
        self._fake_home = Path(tempfile.mkdtemp())
        os.environ["HOME"] = str(self._fake_home)

    def tearDown(self):
        os.chdir(self._old_home)
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        import shutil
        shutil.rmtree(self._tmp, True)
        shutil.rmtree(self._fake_home, True)

    def _write(self, path: Path, content: str = "# cookies\n") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_xdg_config_takes_priority(self):
        xdg_cfg = self._tmp / "cfg"
        xdg_data = self._tmp / "data"
        os.environ["XDG_CONFIG_HOME"] = str(xdg_cfg)
        os.environ["XDG_DATA_HOME"] = str(xdg_data)
        cfg_cookie = self._write(xdg_cfg / "justdownload" / "cookies.txt")
        self._write(xdg_data / "justdownload" / "cookies.txt")
        self._write(self._tmp / "cookies.txt")  # CWD fallback
        self.assertEqual(settings.detect_cookies(), str(cfg_cookie))

    def test_xdg_data_when_no_config(self):
        xdg_cfg = self._tmp / "empty_cfg"
        xdg_data = self._tmp / "data"
        os.environ["XDG_CONFIG_HOME"] = str(xdg_cfg)
        os.environ["XDG_DATA_HOME"] = str(xdg_data)
        data_cookie = self._write(xdg_data / "justdownload" / "cookies.txt")
        self.assertEqual(settings.detect_cookies(), str(data_cookie))

    def test_empty_file_is_skipped(self):
        (self._tmp / "cookies.txt").write_text("")
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("XDG_DATA_HOME", None)
        self.assertIsNone(settings.detect_cookies())

    def test_cwd_fallback(self):
        cwd_cookie = self._write(self._tmp / "cookies.txt")
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("XDG_DATA_HOME", None)
        self.assertEqual(settings.detect_cookies(), str(cwd_cookie))

    def test_no_cookies_returns_none(self):
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("XDG_DATA_HOME", None)
        self.assertIsNone(settings.detect_cookies())

    def test_home_justdownload_subdir(self):
        home_cookie = self._write(self._fake_home / "justdownload" / "cookies.txt")
        os.environ.pop("XDG_CONFIG_HOME", None)
        os.environ.pop("XDG_DATA_HOME", None)
        self.assertEqual(settings.detect_cookies(), str(home_cookie))


if __name__ == "__main__":
    unittest.main()
