"""Tests for justdownload.cli — formatting helpers, error mapping, presets, main() arg parsing."""

import io
import queue
import unittest
from unittest import mock

import justdownload.cli as cli


class FormatSizeTests(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(cli._format_size(500), "500.0B")

    def test_kib(self):
        self.assertEqual(cli._format_size(2048), "2.0KiB")

    def test_mib(self):
        self.assertEqual(cli._format_size(5 * 1024 * 1024), "5.0MiB")

    def test_gib(self):
        self.assertEqual(cli._format_size(2 * 1024 ** 3), "2.0GiB")

    def test_none(self):
        self.assertEqual(cli._format_size(None), "?")

    def test_zero(self):
        self.assertEqual(cli._format_size(0), "?")

    def test_non_numeric(self):
        self.assertEqual(cli._format_size("abc"), "?")


class RenderBarTests(unittest.TestCase):
    def test_zero(self):
        bar = cli._render_bar(0)
        self.assertIn("  0%", bar)
        self.assertIn("░" * 30, bar)
        self.assertNotIn("█", bar)

    def test_full(self):
        bar = cli._render_bar(100)
        self.assertIn("100%", bar)
        self.assertIn("█" * 30, bar)
        self.assertNotIn("░", bar)

    def test_half(self):
        bar = cli._render_bar(50)
        self.assertIn("50%", bar)
        self.assertEqual(bar.count("█"), 15)
        self.assertEqual(bar.count("░"), 15)

    def test_snaps_to_10_percent(self):
        # 47 → 50, 73 → 70, 99 → 100, 14 → 10, 4 → 0
        self.assertIn("50%", cli._render_bar(47))
        self.assertIn("70%", cli._render_bar(73))
        self.assertIn("100%", cli._render_bar(99))
        self.assertIn("10%", cli._render_bar(14))
        self.assertIn("  0%", cli._render_bar(4))

    def test_bar_width_is_30(self):
        # Width is hardcoded — confirm the contract.
        self.assertEqual(len(cli._render_bar(50).split("]")[0].split("[")[1]), 30)


class ParseSpeedEtaTests(unittest.TestCase):
    def test_full_line(self):
        line = "[download]  47.2% of  12.3MiB at  1.2MiB/s ETA 00:07"
        speed, eta = cli._parse_speed_eta(line)
        self.assertEqual(speed, "1.2MiB/s")
        self.assertEqual(eta, "ETA 00:07")

    def test_no_eta(self):
        line = "[download] 100% of 10.0MiB at 5.0MiB/s"
        speed, eta = cli._parse_speed_eta(line)
        self.assertEqual(speed, "5.0MiB/s")
        self.assertEqual(eta, "")

    def test_no_speed_no_eta(self):
        speed, eta = cli._parse_speed_eta("[download] 50%")
        self.assertEqual(speed, "")
        self.assertEqual(eta, "")

    def test_empty(self):
        speed, eta = cli._parse_speed_eta("")
        self.assertEqual(speed, "")
        self.assertEqual(eta, "")


class FriendlyErrorTests(unittest.TestCase):
    def test_bot_check(self):
        self.assertIn("flagged", cli._friendly_error("Sign in to confirm you're not a bot"))

    def test_403(self):
        self.assertIn("Access denied", cli._friendly_error("HTTP Error 403: Forbidden"))

    def test_signature_extract(self):
        self.assertIn("JS runtime", cli._friendly_error("Unable to extract player response signature"))

    def test_no_formats(self):
        self.assertIn("Format unavailable", cli._friendly_error("No video formats found"))

    def test_video_unavailable(self):
        self.assertIn("private", cli._friendly_error("Video unavailable").lower())

    def test_age_restricted(self):
        self.assertIn("Age-restricted", cli._friendly_error("Sign in to view this video (age-restricted)"))

    def test_unsupported_url(self):
        self.assertIn("isn't supported", cli._friendly_error("Unsupported URL: https://example.com"))

    def test_unknown_error_passes_through(self):
        # No pattern matches → return None (caller shows the raw line)
        self.assertIsNone(cli._friendly_error("Some unrelated yt-dlp noise"))

    def test_case_insensitive(self):
        self.assertIsNotNone(cli._friendly_error("VIDEO UNAVAILABLE"))


class PresetsTests(unittest.TestCase):
    def test_presets_have_unique_selectors(self):
        selectors = [p[1] for p in cli.PRESETS]
        self.assertEqual(len(selectors), len(set(selectors)))

    def test_format_friendly_matches_preset(self):
        for i, (label, selector) in enumerate(cli.PRESETS):
            self.assertEqual(cli._format_friendly(selector), f"[{i}] {label}")

    def test_format_friendly_passes_through_raw(self):
        self.assertEqual(cli._format_friendly("bv*[height<=9999]+ba"), "bv*[height<=9999]+ba")

    def test_first_preset_is_best(self):
        # "Best" must be the default — non-interactive shells pick it.
        self.assertEqual(cli.PRESETS[0][1], "bv*+ba/b")

    def test_preset_count(self):
        # 5 presets: best, 1080p, 720p, audio, video
        self.assertEqual(len(cli.PRESETS), 5)


class MainArgParsingTests(unittest.TestCase):
    def test_url_only_dispatches_to_download(self):
        with mock.patch.object(cli, "_cmd_download", return_value=0) as mock_dl, \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            result = cli.main(["https://example.com/v=1"])
        self.assertEqual(result, 0)
        mock_dl.assert_called_once()
        args = mock_dl.call_args[0][0]
        self.assertEqual(args.url, "https://example.com/v=1")
        self.assertFalse(args.yes)

    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as cm, \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            cli.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_status_calls_status_command(self):
        with mock.patch.object(cli, "_cmd_status", return_value=0) as mock_status, \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            cli.main(["--status"])
        mock_status.assert_called_once()

    def test_update_calls_update_command(self):
        with mock.patch.object(cli, "_cmd_update", return_value=0) as mock_update, \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            cli.main(["--update", "-y"])
        mock_update.assert_called_once_with(yes=True)

    def test_no_args_shows_help_and_returns_1(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            result = cli.main([])
        self.assertEqual(result, 1)

    def test_format_flag_parsed(self):
        with mock.patch.object(cli, "_cmd_download", return_value=0) as mock_dl, \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            cli.main(["https://example.com/v=1", "-f", "22", "-o", "/tmp/x"])
        args = mock_dl.call_args[0][0]
        self.assertEqual(args.format, "22")
        self.assertEqual(args.output_dir, "/tmp/x")

    def test_update_yes_flag(self):
        with mock.patch.object(cli, "_cmd_update", return_value=0) as mock_update, \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            cli.main(["--update", "--yes"])
        mock_update.assert_called_once_with(yes=True)


class DrainEventsTests(unittest.TestCase):
    def _drain(self, q, handle):
        with mock.patch("justdownload.cli.signal.signal", return_value=None):
            return cli._drain_events(q, handle)

    def test_returns_success_on_done_ok(self):
        q: queue.Queue = queue.Queue()
        q.put(("done", True, "/path/to/file.mp4"))
        handle = mock.MagicMock()
        status, filename = self._drain(q, handle)
        self.assertEqual(status, "success")
        self.assertEqual(filename, "/path/to/file.mp4")

    def test_returns_error_on_done_false(self):
        q: queue.Queue = queue.Queue()
        q.put(("done", False, None))
        handle = mock.MagicMock()
        status, filename = self._drain(q, handle)
        self.assertEqual(status, "error")
        self.assertIsNone(filename)

    def test_progress_event_continues_until_done(self):
        q: queue.Queue = queue.Queue()
        q.put(("progress", 50.0, "[download] 50% of 1MiB at 1MiB/s ETA 00:01"))
        q.put(("progress", 100.0, "[download] 100% of 1MiB at 1MiB/s ETA 00:00"))
        q.put(("done", True, "/file.mp4"))
        handle = mock.MagicMock()
        with mock.patch("justdownload.cli.signal.signal", return_value=None), \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            status, filename = cli._drain_events(q, handle)
        self.assertEqual(status, "success")
        self.assertEqual(filename, "/file.mp4")

    def test_stdout_event_prints_to_stdout(self):
        q: queue.Queue = queue.Queue()
        q.put(("stdout", "[info] hello"))
        q.put(("done", True, "/file.mp4"))
        handle = mock.MagicMock()
        with mock.patch("justdownload.cli.signal.signal", return_value=None), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            cli._drain_events(q, handle)
        self.assertIn("[info] hello", mock_stdout.getvalue())

    def test_error_event_prints_to_stderr(self):
        q: queue.Queue = queue.Queue()
        q.put(("error", "Some failure"))
        q.put(("done", False, None))
        handle = mock.MagicMock()
        with mock.patch("justdownload.cli.signal.signal", return_value=None), \
             mock.patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            cli._drain_events(q, handle)
        self.assertIn("Some failure", mock_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
