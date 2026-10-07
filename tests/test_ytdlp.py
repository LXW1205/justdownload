"""Tests for justdownload.core.ytdlp — pure helpers + subprocess mocks."""

import json
import queue
import unittest
from unittest import mock

from justdownload.core import ytdlp


class StemForTests(unittest.TestCase):
    def test_same_url_and_format_same_stem(self):
        a = ytdlp._stem_for("https://example.com/v=1", "22")
        b = ytdlp._stem_for("https://example.com/v=1", "22")
        self.assertEqual(a, b)

    def test_different_format_different_stem(self):
        a = ytdlp._stem_for("https://example.com/v=1", "22")
        b = ytdlp._stem_for("https://example.com/v=1", "137")
        self.assertNotEqual(a, b)

    def test_different_url_different_stem(self):
        a = ytdlp._stem_for("https://example.com/v=1", None)
        b = ytdlp._stem_for("https://example.com/v=2", None)
        self.assertNotEqual(a, b)

    def test_none_format_treated_as_best(self):
        a = ytdlp._stem_for("https://example.com/v=1", None)
        b = ytdlp._stem_for("https://example.com/v=1", "best")
        self.assertEqual(a, b)

    def test_stem_is_12_chars(self):
        self.assertEqual(len(ytdlp._stem_for("https://example.com", "22")), 12)


class FormatDurationTests(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(ytdlp._format_duration(45), "0:45")

    def test_minutes(self):
        self.assertEqual(ytdlp._format_duration(125), "2:05")

    def test_hours(self):
        self.assertEqual(ytdlp._format_duration(3725), "1:02:05")

    def test_zero(self):
        self.assertEqual(ytdlp._format_duration(0), "--:--")

    def test_none(self):
        self.assertEqual(ytdlp._format_duration(None), "--:--")

    def test_invalid(self):
        self.assertEqual(ytdlp._format_duration("not a number"), "--:--")

    def test_negative(self):
        self.assertEqual(ytdlp._format_duration(-1), "--:--")


class FormatUploadDateTests(unittest.TestCase):
    def test_standard(self):
        self.assertEqual(ytdlp._format_upload_date("20240915"), "2024-09-15")

    def test_empty(self):
        self.assertEqual(ytdlp._format_upload_date(""), "")

    def test_none(self):
        self.assertEqual(ytdlp._format_upload_date(None), "")

    def test_wrong_length(self):
        self.assertEqual(ytdlp._format_upload_date("2024"), "2024")


class BuildLabelTests(unittest.TestCase):
    def test_video_and_audio(self):
        f = {"vcodec": "h264", "acodec": "aac", "ext": "mp4",
             "resolution": "1920x1080", "height": 1080, "format_note": "1080p", "fps": 30}
        kind, label = ytdlp._build_label(f)
        self.assertEqual(kind, "Video+Audio")
        self.assertIn("[mp4]", label)
        self.assertIn("Video+Audio", label)
        self.assertIn("1080p", label)
        self.assertIn("30fps", label)

    def test_video_only(self):
        f = {"vcodec": "h264", "acodec": "none", "ext": "mp4",
             "resolution": "1920x1080", "height": 1080, "format_note": ""}
        kind, _ = ytdlp._build_label(f)
        self.assertEqual(kind, "Video Only")

    def test_audio_only(self):
        f = {"vcodec": "none", "acodec": "aac", "ext": "m4a", "format_note": ""}
        kind, _ = ytdlp._build_label(f)
        self.assertEqual(kind, "Audio Only")

    def test_missing_fields_no_crash(self):
        f = {}
        kind, label = ytdlp._build_label(f)
        self.assertEqual(kind, "Audio Only")
        self.assertIn("?", label)


class FetchInfoTests(unittest.TestCase):
    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_parses_first_json_line(self, _argv, mock_run):
        json_line = json.dumps({"id": "abc", "title": "Hello", "formats": []})
        mock_run.return_value = mock.Mock(returncode=0, stdout=json_line + "\n", stderr="")
        info = ytdlp.fetch_info("https://example.com/v=1", None)
        self.assertEqual(info["id"], "abc")
        self.assertEqual(info["title"], "Hello")
        self.assertEqual(info["formats"], [])

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_skips_non_json_output(self, _argv, mock_run):
        # yt-dlp sometimes prints progress to stdout before the JSON.
        json_line = json.dumps({"id": "abc", "title": "Hello", "formats": []})
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="[info] Looking up...\n" + json_line + "\n",
            stderr="",
        )
        info = ytdlp.fetch_info("https://example.com/v=1", None)
        self.assertEqual(info["id"], "abc")

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_non_zero_exit_raises(self, _argv, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=1, stdout="", stderr="ERROR: video unavailable"
        )
        with self.assertRaises(RuntimeError) as cm:
            ytdlp.fetch_info("https://example.com/v=1", None)
        self.assertIn("video unavailable", str(cm.exception))

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_filters_video_plus_audio_only(self, _argv, mock_run):
        # Format with both codecs = none should be excluded.
        json_line = json.dumps({
            "id": "1", "title": "T",
            "formats": [
                {"format_id": "a", "vcodec": "h264", "acodec": "aac", "ext": "mp4"},
                {"format_id": "b", "vcodec": "none", "acodec": "none", "ext": "unknown"},
                {"format_id": "c", "vcodec": "none", "acodec": "aac", "ext": "m4a"},
            ],
        })
        mock_run.return_value = mock.Mock(returncode=0, stdout=json_line, stderr="")
        info = ytdlp.fetch_info("https://example.com/v=1", None)
        ids = [f["format_id"] for f in info["formats"]]
        self.assertIn("a", ids)
        self.assertIn("c", ids)
        self.assertNotIn("b", ids)

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_passes_cookies_path(self, _argv, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0, stdout=json.dumps({"id": "1", "title": "T", "formats": []}), stderr=""
        )
        ytdlp.fetch_info("https://example.com/v=1", "/path/to/cookies.txt")
        args = mock_run.call_args[0][0]
        self.assertIn("--cookies", args)
        self.assertIn("/path/to/cookies.txt", args)

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["/venv/bin/python", "-m", "yt_dlp"])
    def test_uses_resolved_ytdlp(self, _argv, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0, stdout=json.dumps({"id": "1", "title": "T", "formats": []}), stderr=""
        )
        ytdlp.fetch_info("https://example.com/v=1", None)
        self.assertEqual(
            mock_run.call_args[0][0][:4],
            ["/venv/bin/python", "-m", "yt_dlp", "--dump-json"],
        )

    @mock.patch("justdownload.core.ytdlp.subprocess.run")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=[])
    def test_missing_ytdlp_raises_without_spawning(self, _argv, mock_run):
        with self.assertRaises(RuntimeError) as cm:
            ytdlp.fetch_info("https://example.com/v=1", None)
        self.assertIn("yt-dlp not found", str(cm.exception))
        mock_run.assert_not_called()


class StartDownloadTests(unittest.TestCase):
    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_returns_handle(self, _argv, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        handle = ytdlp.start_download("https://example.com/v=1", "22", "/tmp", None, q)
        self.assertIsNotNone(handle)
        self.assertEqual(handle.stem, ytdlp._stem_for("https://example.com/v=1", "22"))

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen", side_effect=FileNotFoundError)
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_missing_ytdlp_returns_none(self, _argv, _popen):
        q: queue.Queue = queue.Queue()
        handle = ytdlp.start_download("https://example.com/v=1", "22", "/tmp", None, q)
        self.assertIsNone(handle)
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        self.assertTrue(any(e[0] == "error" for e in events))

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=[])
    def test_unresolvable_ytdlp_returns_none(self, _argv, mock_popen):
        # No importable yt_dlp and none on PATH — resolver hands back [].
        q: queue.Queue = queue.Queue()
        handle = ytdlp.start_download("https://example.com/v=1", "22", "/tmp", None, q)
        self.assertIsNone(handle)
        mock_popen.assert_not_called()
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        self.assertIn(("done", False, None), events)
        self.assertTrue(any(e[0] == "error" and "not found" in e[1] for e in events))

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_format_passthrough_when_not_best(self, _argv, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        ytdlp.start_download("https://example.com/v=1", "137", "/tmp", None, q)
        args = mock_popen.call_args[0][0]
        self.assertIn("--format", args)
        self.assertIn("137", args)

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_no_format_arg_when_best(self, _argv, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        ytdlp.start_download("https://example.com/v=1", "best", "/tmp", None, q)
        args = mock_popen.call_args[0][0]
        self.assertNotIn("--format", args)

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_passes_cookies(self, _argv, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        ytdlp.start_download("https://example.com/v=1", "22", "/tmp", "/c.txt", q)
        args = mock_popen.call_args[0][0]
        self.assertIn("--cookies", args)
        self.assertIn("/c.txt", args)

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["yt-dlp"])
    def test_banner_hides_the_resolver_prefix(self, _argv, mock_popen):
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        ytdlp.start_download("https://example.com/v=1", "22", "/tmp", None, q)
        banner = q.get_nowait()
        self.assertEqual(banner[0], "status")
        self.assertTrue(banner[1].startswith("$ yt-dlp --no-playlist "), banner[1])
        self.assertNotIn("-m", banner[1])

    @mock.patch("justdownload.core.ytdlp.subprocess.Popen")
    @mock.patch("justdownload.core.ytdlp.ytdlp_argv", return_value=["/venv/bin/python", "-m", "yt_dlp"])
    def test_banner_hides_the_interpreter_prefix(self, _argv, mock_popen):
        # "[python, -m, yt_dlp, ...]" must still read as "$ yt-dlp <flags>".
        mock_proc = mock.MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.stderr = iter([])
        mock_popen.return_value = mock_proc
        q: queue.Queue = queue.Queue()
        ytdlp.start_download("https://example.com/v=1", "22", "/tmp", None, q)
        banner = q.get_nowait()
        self.assertTrue(banner[1].startswith("$ yt-dlp --no-playlist "), banner[1])
        self.assertNotIn("/venv/bin/python", banner[1])
        self.assertNotIn(" -m ", banner[1])
        # ...while the spawned argv keeps the real prefix.
        self.assertEqual(
            mock_popen.call_args[0][0][:3],
            ["/venv/bin/python", "-m", "yt_dlp"],
        )


class DownloadCancelTests(unittest.TestCase):
    def test_cancel_terminates_proc(self):
        mock_proc = mock.MagicMock()
        handle = ytdlp.Download(proc=mock_proc, stem="abc", download_dir="/tmp")
        handle.cancel()
        mock_proc.terminate.assert_called_once()

    def test_cancel_handles_process_lookup_error(self):
        mock_proc = mock.MagicMock()
        mock_proc.terminate.side_effect = ProcessLookupError
        handle = ytdlp.Download(proc=mock_proc, stem="abc", download_dir="/tmp")
        # Should not raise.
        handle.cancel()


if __name__ == "__main__":
    unittest.main()
