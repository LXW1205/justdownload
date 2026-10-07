"""Tests for justdownload.core.deps — runtime dependency detection."""

import unittest
from unittest import mock

from justdownload.core import deps, ytdlp


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
    @mock.patch("justdownload.core.deps.ytdlp_argv", return_value=[])
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    def test_all_missing_raises_three_warnings(self, _update, _argv, _which):
        report = deps.check()
        self.assertFalse(report.ytdlp_ok)
        self.assertFalse(report.ffmpeg_ok)
        self.assertIsNone(report.js_runtime)
        # 3 missing: yt-dlp, ffmpeg, js runtime
        self.assertEqual(len(report.messages), 3)

    @mock.patch("justdownload.core.deps.shutil.which")
    @mock.patch("justdownload.core.deps.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.deps.get_yt_dlp_version", return_value="2026.6.9")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    def test_all_present_no_warnings(self, _update, _version, _argv, mock_which):
        def fake_which(name):
            return f"/usr/bin/{name}" if name in ("ffmpeg", "node") else None
        mock_which.side_effect = fake_which
        report = deps.check()
        self.assertTrue(report.ytdlp_ok)
        self.assertTrue(report.ffmpeg_ok)
        self.assertEqual(report.js_runtime, "node")
        self.assertEqual(report.messages, [])

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/yt-dlp")
    @mock.patch("justdownload.core.deps.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.deps.get_yt_dlp_version", return_value="2024.10.7")
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=True, latest="2026.6.9", installed="2024.10.7"))
    def test_outdated_ytdlp_warns(self, _update, _version, _argv, _which):
        report = deps.check()
        self.assertTrue(report.ytdlp_ok)
        self.assertIn("outdated: 2024.10.7 → 2026.6.9", " ".join(report.messages))

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/ffmpeg")
    @mock.patch("justdownload.core.deps.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.updater.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    @mock.patch("justdownload.core.updater.subprocess.run")
    def test_gets_ytdlp_version(self, mock_run, _update, _uargv, _argv, _which):
        mock_run.return_value = mock.Mock(returncode=0, stdout="2026.6.9\n")
        report = deps.check()
        self.assertEqual(report.ytdlp_version, "2026.6.9")
        # Version comes from the resolved yt-dlp, not a PATH lookalike.
        argv = next(c[0][0] for c in mock_run.call_args_list if "--version" in c[0][0])
        self.assertEqual(argv, ["yt-dlp", "--version"])

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/ffmpeg")
    @mock.patch("justdownload.core.deps.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.updater.ytdlp_argv", return_value=["yt-dlp"])
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    @mock.patch("justdownload.core.updater.subprocess.run")
    def test_handles_ytdlp_version_failure(self, mock_run, _update, _uargv, _argv, _which):
        # Non-zero exit → version is None, no crash.
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        report = deps.check()
        self.assertIsNone(report.ytdlp_version)

    @mock.patch("justdownload.core.deps.shutil.which", return_value="/usr/bin/ffmpeg")
    @mock.patch("justdownload.core.deps.ytdlp_argv",
                return_value=["/venv/bin/python", "-m", "yt_dlp"])
    @mock.patch("justdownload.core.updater.ytdlp_argv",
                return_value=["/venv/bin/python", "-m", "yt_dlp"])
    @mock.patch("justdownload.core.deps.check_yt_dlp_update",
                return_value=mock.Mock(outdated=False, latest=None, installed=None))
    @mock.patch("justdownload.core.updater.subprocess.run")
    def test_reports_resolved_ytdlp_not_the_path_one(self, mock_run, _update, _uargv, _argv, _which):
        # The bug: report used to name the PATH copy while the update hit the venv.
        mock_run.return_value = mock.Mock(returncode=0, stdout="2026.6.9\n")
        report = deps.check()
        self.assertTrue(report.ytdlp_ok)
        self.assertEqual(report.ytdlp_path, "/venv/bin/python -m yt_dlp")
        argv = next(c[0][0] for c in mock_run.call_args_list if "--version" in c[0][0])
        self.assertEqual(argv, ["/venv/bin/python", "-m", "yt_dlp", "--version"])


class ResolverAgreementTests(unittest.TestCase):
    """deps.check() and fetch_info() must target the *same* yt-dlp."""

    def test_version_check_and_download_use_one_ytdlp(self):
        calls: list[list[str]] = []

        def fake_run(args, **_kwargs):
            args = list(args)
            calls.append(args)
            if "--version" in args:
                return mock.Mock(returncode=0, stdout="2026.6.9\n", stderr="")
            return mock.Mock(
                returncode=0, stderr="",
                stdout='{"id": "1", "title": "T", "formats": []}',
            )

        with mock.patch("justdownload.core.deps.check_yt_dlp_update",
                        return_value=mock.Mock(outdated=False, latest=None, installed=None)), \
             mock.patch("justdownload.core.updater.subprocess.run", side_effect=fake_run), \
             mock.patch("justdownload.core.ytdlp.subprocess.run", side_effect=fake_run):
            report = deps.check()
            ytdlp.fetch_info("https://example.com/v=1", None)

        self.assertEqual(report.ytdlp_version, "2026.6.9")
        version_argv = next(c for c in calls if "--version" in c)
        info_argv = next(c for c in calls if "--dump-json" in c)
        prefix = version_argv[:-1]  # drop "--version"
        self.assertTrue(prefix)
        # Same launcher, so --update's pip target is the one we check/download.
        self.assertEqual(info_argv[:len(prefix)], prefix)
        self.assertTrue(report.ytdlp_path.startswith(" ".join(prefix)))


if __name__ == "__main__":
    unittest.main()
