"""Tests for justdownload.core.progress — yt-dlp line parser."""

import unittest

from justdownload.core.progress import parse_line


class ProgressLineTests(unittest.TestCase):
    def test_download_with_percent_and_eta(self):
        line = "[download]  47.2% of  12.3MiB at  1.2MiB/s ETA 00:07"
        self.assertEqual(parse_line(line), [("progress", 47.2, line)])

    def test_download_at_100_percent(self):
        line = "[download] 100% of  10.00MiB at  5.00MiB/s ETA 00:00"
        self.assertEqual(parse_line(line), [("progress", 100.0, line)])

    def test_download_at_zero_percent(self):
        line = "[download]   0.0% of  12.3MiB at  Unknown B/s ETA Unknown"
        self.assertEqual(parse_line(line), [("progress", 0.0, line)])

    def test_download_clamps_percent_above_100(self):
        # Defensive: if yt-dlp ever emits 105% (it shouldn't), clamp to 100.
        line = "[download]  105.0% of  12.3MiB at  1.2MiB/s ETA 00:00"
        result = parse_line(line)
        self.assertEqual(result[0][1], 100.0)

    def test_negative_percent_parses_as_positive(self):
        # The regex (\d{1,3}(?:\.\d+)?) skips the leading minus, so "-5.0%"
        # parses as 5.0. yt-dlp doesn't emit negatives, so this is a quirk of
        # the regex, not a real-world case. Document it as current behavior.
        line = "[download]  -5.0% of  12.3MiB at  1.2MiB/s ETA 00:00"
        result = parse_line(line)
        self.assertEqual(result[0][1], 5.0)

    def test_info_line_is_stdout(self):
        self.assertEqual(parse_line("[info] Testing format 18"), [("stdout", "[info] Testing format 18")])

    def test_destination_line_is_stdout(self):
        self.assertEqual(parse_line("Destination: foo.mp4"), [("stdout", "Destination: foo.mp4")])

    def test_extractaudio_phase_no_percent_event(self):
        # Merging/extract phases have no [download] tag → just stdout, no progress event.
        line = "[ExtractAudio] Destination: foo.m4a"
        self.assertEqual(parse_line(line), [("stdout", line)])

    def test_stderr_error_prefixed(self):
        self.assertEqual(parse_line("ERROR: something went wrong"), [("stderr", "ERROR: something went wrong")])

    def test_empty_line_no_events(self):
        self.assertEqual(parse_line(""), [])

    def test_whitespace_only_no_events(self):
        self.assertEqual(parse_line("   \n"), [])

    def test_percent_without_download_tag_stays_stdout(self):
        # A non-download line with a % sign should not emit a progress event.
        self.assertEqual(parse_line("Conversion: 50% complete"), [("stdout", "Conversion: 50% complete")])


if __name__ == "__main__":
    unittest.main()
