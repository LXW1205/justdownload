"""Tests for justdownload.core.deps — runtime dependency detection."""

import unittest
from unittest import mock

from justdownload.core import deps


class JsRuntimeTests(unittest.TestCase):
    def test_finds_node(self):
        with mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/node"):
            self.assertEqual(deps.get_js_runtime(), "node")

    def test_falls_back_to_deno(self):
        def fake_which(name):
            return "/usr/bin/deno" if name == "deno" else None
        with mock.patch("justdownload.core.deps.shutil.which", side_effect=fake_which):
            self.assertEqual(deps.get_js_runtime(), "deno")

    def test_returns_none_when_nothing_available(self):
        with mock.patch("justdownload.core.deps.shutil.which", return_value=None):
            self.assertIsNone(deps.get_js_runtime())

    def test_preference_order(self):
        # node > deno > bun > qjs
        order = []
        def fake_which(name):
            order.append(name)
            return f"/usr/bin/{name}" if name == "bun" else None
        with mock.patch("justdownload.core.deps.shutil.which", side_effect=fake_which):
            self.assertEqual(deps.get_js_runtime(), "bun")
        # Confirms we probed node and deno first, then settled on bun.
        self.assertIn("node", order)
        self.assertIn("deno", order)
        self.assertIn("bun", order)


class CheckTests(unittest.TestCase):
    @mock.patch("justdownload.core.deps.shutil.which", return_value=None)
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    def test_all_missing_raises_three_warnings(self, _update, _which):
        report = deps.check()
        self.assertFalse(report.ytdlp_ok)
        self.assertFalse(report.ffmpeg_ok)
        self.assertIsNone(report.js_runtime)
        # 3 missing: yt-dlp, ffmpeg, js runtime
        self.assertEqual(len(report.messages), 3)

    @mock.patch("justdownload.core.deps.shutil.which")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    def test_all_present_no_warnings(self, _update, mock_which):
        def fake_which(name):
            return f"/usr/bin/{name}" if name in ("yt-dlp", "ffmpeg", "node") else None
        mock_which.side_effect = fake_which
        report = deps.check()
        self.assertTrue(report.ytdlp_ok)
        self.assertTrue(report.ffmpeg_ok)
        self.assertEqual(report.js_runtime, "node")
        self.assertEqual(report.messages, [])

    @mock.patch("justdownload.core.deps.shutil.which")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=True, latest="2026.6.9", installed="2024.10.7"))
    def test_outdated_ytdlp_warns(self, _update, mock_which):
        mock_which.return_value = "/usr/bin/yt-dlp"
        report = deps.check()
        self.assertTrue(report.ytdlp_ok)
        self.assertIn("outdated: 2024.10.7 → 2026.6.9", " ".join(report.messages))

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/yt-dlp")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    @mock.patch("justdownload.core.deps.subprocess.run")
    def test_gets_ytdlp_version(self, mock_run, _update, _which):
        mock_run.return_value = mock.Mock(returncode=0, stdout="2026.6.9\n")
        report = deps.check()
        self.assertEqual(report.ytdlp_version, "2026.6.9")

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/yt-dlp")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    @mock.patch("justdownload.core.deps.subprocess.run")
    def test_handles_ytdlp_version_failure(self, mock_run, _update, _which):
        # Non-zero exit → version is None, no crash.
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        report = deps.check()
        self.assertIsNone(report.ytdlp_version)


if __name__ == "__main__":
    unittest.main()
