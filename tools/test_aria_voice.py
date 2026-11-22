import os
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aria_voice


class EnvValueTests(unittest.TestCase):
    def test_environment_overrides_env_file(self):
        with patch.dict(os.environ, {"VOICE_TEST_KEY": "from-process"}):
            self.assertEqual(aria_voice.env_value("VOICE_TEST_KEY"), "from-process")

    def test_reads_env_file_without_exporting_values(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text("VOICE_TEST_KEY='from-file'\n", encoding="utf-8")
            with patch.object(aria_voice, "ROOT", Path(directory)), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(aria_voice.env_value("VOICE_TEST_KEY"), "from-file")

    def test_speech_text_removes_markdown_formatting(self):
        self.assertEqual(
            aria_voice.clean_for_speech("The sum is **91**.\n\n- [details](https://example.com)"),
            "The sum is 91. details",
        )

    def test_speech_text_does_not_read_code_blocks(self):
        self.assertEqual(aria_voice.clean_for_speech("Answer: 4. `print(2 + 2)`"), "Answer: 4. print(2 + 2)")

    def test_speech_text_omits_urls_and_proposal_ids(self):
        text = "Tool draft 23bea21d-460b-45b4-bd10-4fa2b31988ce. More: https://example.com"
        spoken = aria_voice.clean_for_speech(text)
        self.assertNotIn("23bea21d", spoken)
        self.assertNotIn("https://", spoken)

    def test_non_speech_asr_labels_are_discarded(self):
        for transcript in ("", "[BLANK_AUDIO]", "(wind blowing)", "[ Sound Effects ]", "[ Writing on Board ]"):
            with self.subTest(transcript=transcript):
                self.assertTrue(aria_voice.is_non_speech_transcript(transcript))
        self.assertFalse(aria_voice.is_non_speech_transcript("Can you help me?"))

    def test_voice_tool_intent_recognizes_safe_test_and_approval_requests(self):
        self.assertEqual(
            aria_voice.voice_tool_intent("test it in the isolated environment"),
            ("test", None),
        )
        self.assertEqual(
            aria_voice.voice_tool_intent("test tool subtract_numbers in isolation"),
            ("test", "subtract_numbers"),
        )
        self.assertEqual(aria_voice.voice_tool_intent("run the test case"), ("test", None))
        self.assertEqual(aria_voice.voice_tool_intent("test them"), ("test_all", None))
        self.assertEqual(aria_voice.voice_tool_intent("run them"), ("test_all", None))
        self.assertEqual(aria_voice.voice_tool_intent("approve that tool without testing"), ("approve", None))
        self.assertEqual(aria_voice.voice_tool_intent("approve without testing"), ("approve", None))
        self.assertEqual(aria_voice.voice_tool_intent("approve subtract_numbers"), ("approve", "subtract_numbers"))
        self.assertEqual(aria_voice.voice_tool_intent("approve add numbers"), ("approve", "add_numbers"))
        self.assertEqual(
            aria_voice.voice_tool_intent("approve the tool called subtract numbers"),
            ("approve", "subtract_numbers"),
        )
        self.assertEqual(
            aria_voice.voice_tool_intent("confirm approve subtract_numbers"),
            ("confirm_approve", "subtract_numbers"),
        )
        self.assertEqual(
            aria_voice.voice_tool_intent("confirm approve add numbers"),
            ("confirm_approve", "add_numbers"),
        )

    def test_voice_approval_runs_tests_and_review_before_requesting_confirmation(self):
        pending = {"id": "draft-id", "name": "subtract_numbers", "status": "pending"}
        tested = {**pending, "status": "tested", "sha256": "digest", "tests": [{}]}
        reviewed = {**tested, "status": "reviewed"}
        with (
            patch.object(aria_voice, "voice_api", side_effect=[
                {"proposals": [pending]}, {"proposal": pending}, {"proposal": tested}, {"proposal": reviewed}
            ]) as api,
            patch.object(aria_voice, "run_voice_tool_test", return_value="Isolated tests passed for subtract_numbers."),
        ):
            message, confirmation = aria_voice.prepare_voice_approval("subtract_numbers", "secret")
        self.assertEqual(confirmation["name"], "subtract_numbers")
        self.assertIn("confirm approve subtract_numbers", message)
        self.assertEqual(api.call_args_list[-1].args[:3], (
            "POST", "/admin/tool-proposals/draft-id/review", "secret"
        ))

    def test_recent_playback_echo_is_ignored_but_genuine_followup_is_not(self):
        self.assertTrue(
            aria_voice.is_recent_playback_echo(
                "Good bye", "Goodbye! Have a great day.", 10.0, 11.0
            )
        )
        self.assertFalse(
            aria_voice.is_recent_playback_echo(
                "What time is it", "Goodbye! Have a great day.", 10.0, 11.0
            )
        )
        self.assertFalse(
            aria_voice.is_recent_playback_echo(
                "Good bye", "Goodbye! Have a great day.", 10.0, 15.0
            )
        )

    def test_silence_detection_returns_one_utterance(self):
        import numpy as np

        chunks = queue.Queue()
        for _ in range(5):
            chunks.put(np.zeros(1024, dtype=np.float32))
        chunks.put(np.full(1024, 0.03, dtype=np.float32))
        for _ in range(16):
            chunks.put(np.zeros(1024, dtype=np.float32))
        audio = aria_voice.listen_for_utterance(chunks, np)
        self.assertGreater(float(np.max(audio)), aria_voice.VOICE_THRESHOLD)

    def test_duplex_callback_outputs_audio_and_captures_microphone(self):
        import numpy as np

        chunks = queue.Queue()
        playback = queue.Queue()
        spoken = np.array([0.0, 0.2, -0.1, 0.3, -0.2, 0.1, -0.3, 0.25], dtype=np.float32)
        playback.put(spoken)
        import threading

        capture_enabled = threading.Event()
        capture_enabled.set()
        source_done = threading.Event()
        source_done.set()
        playback_done = threading.Event()
        interrupted = threading.Event()
        state = {"samples": None, "offset": 0, "reference": aria_voice.deque(maxlen=12)}
        microphone = np.full((8, 1), 0.03, dtype=np.float32)
        output = np.empty((8, 1), dtype=np.float32)

        aria_voice.duplex_audio_callback(
            chunks, playback, capture_enabled, state, source_done, playback_done,
            interrupted, np, microphone, output, 8, None, None,
        )

        np.testing.assert_array_equal(output[:, 0], spoken)
        np.testing.assert_array_equal(chunks.get_nowait(), microphone[:, 0])
        self.assertTrue(playback_done.is_set())

    def test_duplex_callback_ignores_matching_speaker_echo(self):
        import numpy as np
        import threading

        chunks = queue.Queue()
        playback = queue.Queue()
        spoken = np.sin(np.arange(1024, dtype=np.float32) * 0.037)
        playback.put(spoken)
        capture_enabled = threading.Event()
        capture_enabled.set()
        source_done = threading.Event()
        playback_done = threading.Event()
        interrupted = threading.Event()
        state = {"samples": None, "offset": 0, "reference": aria_voice.deque(maxlen=12)}
        output = np.empty((1024, 1), dtype=np.float32)

        aria_voice.duplex_audio_callback(
            chunks, playback, capture_enabled, state, source_done, playback_done,
            interrupted, np, np.zeros((1024, 1), dtype=np.float32), output,
            1024, None, None,
        )
        aria_voice.clear_queue(chunks)
        echo = output[:, 0] * 0.12
        aria_voice.duplex_audio_callback(
            chunks, playback, capture_enabled, state, source_done, playback_done,
            interrupted, np, echo[:, None], np.empty((1024, 1), dtype=np.float32),
            1024, None, None,
        )

        self.assertTrue(chunks.empty())

    def test_resamples_piper_audio_to_duplex_rate(self):
        import numpy as np

        audio = np.array([0, 32767, 0, -32768], dtype=np.int16)
        resampled = aria_voice._resample_speech(audio, 22050, np)
        self.assertEqual(len(resampled), round(len(audio) * aria_voice.RATE / 22050))
        self.assertAlmostEqual(float(resampled[0]), 0.0)

    def test_duplex_callback_silences_playback_after_interruption(self):
        import numpy as np
        import threading

        chunks = queue.Queue()
        playback = queue.Queue()
        playback.put(np.ones(8, dtype=np.float32))
        capture_enabled = threading.Event()
        source_done = threading.Event()
        playback_done = threading.Event()
        interrupted = threading.Event()
        interrupted.set()
        output = np.empty((8, 1), dtype=np.float32)

        aria_voice.duplex_audio_callback(
            chunks, playback, capture_enabled, {"samples": None, "offset": 0},
            source_done, playback_done, interrupted, np,
            np.zeros((8, 1), dtype=np.float32), output, 8, None, None,
        )

        np.testing.assert_array_equal(output, np.zeros((8, 1), dtype=np.float32))
        self.assertTrue(playback_done.is_set())

    def test_clear_queue_discards_stale_microphone_audio(self):
        chunks = queue.Queue()
        chunks.put("stale")
        aria_voice.clear_queue(chunks)
        self.assertTrue(chunks.empty())


if __name__ == "__main__":
    unittest.main()
