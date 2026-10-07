"""Tests for justdownload.core.updater — version parsing + PyPI check + pip update."""

import json
import sys
import unittest
from unittest import mock

from justdownload.core import updater


class YtdlpArgvTests(unittest.TestCase):
    """The resolver is the one place that decides which yt-dlp we run."""

    def test_prefers_module_when_importable(self):
        with mock.patch("justdownload.core.updater.importlib.util.find_spec",
                        return_value=mock.Mock()), \
             mock.patch("justdownload.core.updater.shutil.which") as mock_which:
            self.assertEqual(updater.ytdlp_argv(), [sys.executable, "-m", "yt_dlp"])
        # Importable means PATH is never consulted — no second install can sneak in.
        mock_which.assert_not_called()

    def test_falls_back_to_path_when_not_importable(self):
        with mock.patch("justdownload.core.updater.importlib.util.find_spec",
                        return_value=None), \
             mock.patch("justdownload.core.updater.shutil.which",
                        return_value="/usr/bin/yt-dlp") as mock_which:
            self.assertEqual(updater.ytdlp_argv(), ["/usr/bin/yt-dlp"])
        mock_which.assert_called_once_with("yt-dlp")

    def test_empty_when_neither_available(self):
        with mock.patch("justdownload.core.updater.importlib.util.find_spec",
                        return_value=None), \
             mock.patch("justdownload.core.updater.shutil.which", return_value=None):
            self.assertEqual(updater.ytdlp_argv(), [])


class GetYtDlpVersionTests(unittest.TestCase):
    @mock.patch("justdownload.core.updater.subprocess.run")
    @mock.patch("justdownload.core.updater.ytdlp_argv", return_value=["/venv/bin/python", "-m", "yt_dlp"])
    def test_runs_the_resolved_ytdlp(self, _argv, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="2026.6.9\n")
        self.assertEqual(updater.get_yt_dlp_version(), "2026.6.9")
        self.assertEqual(mock_run.call_args[0][0], ["/venv/bin/python", "-m", "yt_dlp", "--version"])

    @mock.patch("justdownload.core.updater.subprocess.run")
    @mock.patch("justdownload.core.updater.ytdlp_argv", return_value=[])
    def test_missing_ytdlp_returns_none_without_spawning(self, _argv, mock_run):
        self.assertIsNone(updater.get_yt_dlp_version())
        mock_run.assert_not_called()

    @mock.patch("justdownload.core.updater.subprocess.run",
                side_effect=OSError("boom"))
    @mock.patch("justdownload.core.updater.ytdlp_argv", return_value=["yt-dlp"])
    def test_spawn_failure_returns_none(self, _argv, _run):
        self.assertIsNone(updater.get_yt_dlp_version())


class ParseVersionTests(unittest.TestCase):
    def test_basic_dotted(self):
        self.assertEqual(updater._parse_version("2024.10.7"), (2024, 10, 7))

    def test_two_part(self):
        self.assertEqual(updater._parse_version("6.1"), (6, 1))

    def test_post_release(self):
        # "2024.10.7.post1" → first 3 segments
        self.assertEqual(updater._parse_version("2024.10.7.post1"), (2024, 10, 7))

    def test_empty_string(self):
        self.assertIsNone(updater._parse_version(""))

    def test_garbage(self):
        self.assertIsNone(updater._parse_version("abc"))

    def test_starts_with_garbage(self):
        self.assertIsNone(updater._parse_version("v1.2.3"))


class IsOutdatedTests(unittest.TestCase):
    def test_older_returns_true(self):
        self.assertTrue(updater.is_outdated("2024.10.7", "2024.12.13"))

    def test_newer_returns_false(self):
        self.assertFalse(updater.is_outdated("2024.12.13", "2024.10.7"))

    def test_equal_returns_false(self):
        self.assertFalse(updater.is_outdated("2024.12.13", "2024.12.13"))

    def test_different_widths(self):
        self.assertTrue(updater.is_outdated("1.0", "1.0.1"))
        self.assertFalse(updater.is_outdated("1.0.1", "1.0"))

    def test_garbage_returns_false(self):
        # Defensive: don't crash, just say "not outdated"
        self.assertFalse(updater.is_outdated("garbage", "2024.10.7"))
        self.assertFalse(updater.is_outdated("2024.10.7", "garbage"))


class CheckYtDlpUpdateTests(unittest.TestCase):
    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value="2024.10.7")
    @mock.patch("justdownload.core.updater.urllib.request.urlopen")
    def test_outdated(self, mock_urlopen, _version):
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"info": {"version": "2026.6.9"}}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        info = updater.check_yt_dlp_update()
        self.assertTrue(info.outdated)
        self.assertEqual(info.installed, "2024.10.7")
        self.assertEqual(info.latest, "2026.6.9")

    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value="2026.6.9")
    @mock.patch("justdownload.core.updater.urllib.request.urlopen")
    def test_up_to_date(self, mock_urlopen, _version):
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"info": {"version": "2026.6.9"}}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        info = updater.check_yt_dlp_update()
        self.assertFalse(info.outdated)
        self.assertEqual(info.installed, "2026.6.9")
        self.assertEqual(info.latest, "2026.6.9")

    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value="2024.10.7")
    @mock.patch("justdownload.core.updater.urllib.request.urlopen",
                side_effect=ConnectionError("nope"))
    def test_network_failure_silent(self, _urlopen, _version):
        # Network down → latest is None, outdated is False, no exception.
        info = updater.check_yt_dlp_update()
        self.assertIsNone(info.latest)
        self.assertFalse(info.outdated)

    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value="2024.10.7")
    @mock.patch("justdownload.core.updater.urllib.request.urlopen")
    def test_malformed_response_silent(self, mock_urlopen, _version):
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = b"not json"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = mock.Mock(return_value=False)
        mock_urlopen.return_value = mock_resp
        info = updater.check_yt_dlp_update()
        self.assertIsNone(info.latest)
        self.assertFalse(info.outdated)


class UpdateYtDlpTests(unittest.TestCase):
    @mock.patch("justdownload.core.updater.subprocess.Popen")
    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value="2026.6.9")
    def test_success_emits_done(self, _version, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        q = _FakeQueue()
        updater.update_yt_dlp(q)
        events = q.events
        kinds = [e[0] for e in events]
        # First event is the banner, last is the "updated" status.
        self.assertEqual(kinds[0], "status")
        self.assertTrue(any("2026.6.9" in (e[1] if len(e) > 1 else "") for e in events))

    @mock.patch("justdownload.core.updater.subprocess.Popen",
                side_effect=FileNotFoundError("no pip"))
    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value=None)
    def test_missing_pip_emits_error(self, _version, _popen):
        q = _FakeQueue()
        updater.update_yt_dlp(q)
        kinds = [e[0] for e in q.events]
        self.assertIn("error", kinds)

    @mock.patch("justdownload.core.updater.subprocess.Popen")
    @mock.patch("justdownload.core.updater.get_yt_dlp_version", return_value=None)
    def test_pip_failure_emits_error(self, _version, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc
        q = _FakeQueue()
        updater.update_yt_dlp(q)
        kinds = [e[0] for e in q.events]
        self.assertIn("error", kinds)


class _FakeQueue:
    """Minimal queue.Queue stand-in for tests — just records put() calls."""
    def __init__(self):
        self.events: list[tuple] = []

    def put(self, item):
        self.events.append(item)


if __name__ == "__main__":
    unittest.main()
