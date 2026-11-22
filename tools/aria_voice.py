#!/usr/bin/env python3
"""Host-side voice client; audio never enters agent-core or Attic."""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICE_DATA = ROOT / ".voice-data"
ASR = VOICE_DATA / "sherpa-onnx-whisper-tiny.en"
PIPER_VOICES = {
    "amy": VOICE_DATA / "piper-en-us-amy" / "en_US-amy-medium.onnx",
    "hfc_female": VOICE_DATA / "piper-en-us-hfc_female" / "en_US-hfc_female-medium.onnx",
    "kristin": VOICE_DATA / "piper-en-us-kristin" / "en_US-kristin-medium.onnx",
    "kathleen": VOICE_DATA / "piper-en-us-kathleen" / "en_US-kathleen-low.onnx",
    "southern_english_female": (
        VOICE_DATA / "piper-en-gb-southern-english-female" / "en_GB-southern_english_female-low.onnx"
    ),
}
RATE = 16000
SILENCE_SECONDS = 1.0
# shortcut: fixed RMS gate depends on mic gain; tune or replace with VAD if it misses speech.
VOICE_THRESHOLD = 0.012


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    text = re.sub(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?m)^\s*\|?\s*:?-{3,}.*$", "", text)
    text = text.replace("|", ". ")
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|#{1,6}\s*)", "", text)
    text = re.sub(r"[*_~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_non_speech_transcript(text: str) -> bool:
    text = text.strip()
    if not text or re.fullmatch(r"\s*[\[(].*[\])]\s*", text):
        return True
    normalized = re.sub(r"[^a-z]", "", text.lower())
    return normalized in {
        "blankaudio", "wind", "windblowing", "soundeffects", "writingonboard",
        "muffledspeaking", "inaudible", "silence", "backgroundnoise",
    }


def voice_tool_intent(text: str) -> tuple[str, str | None] | None:
    lowered = text.lower()
    spoken_name = r"([a-z][a-z0-9_]*(?:\s+[a-z][a-z0-9_]*)?)"
    confirmation = re.search(
        rf"\b(?:confirm|yes)\s+(?:approve|install)\s+(?:the\s+)?(?:tool\s+)?(?:called\s+|named\s+)?{spoken_name}",
        lowered,
    )
    if confirmation:
        return "confirm_approve", re.sub(r"\s+", "_", confirmation.group(1).strip())
    if re.search(r"\bapprove\b", lowered) and (
        re.search(r"\b(?:tool|draft|it|that|without\s+testing)\b", lowered)
        or re.search(r"\bapprove\s+[a-z][a-z0-9_]*\b", lowered)
    ):
        match = re.search(
            rf"\bapprove\s+(?:the\s+)?(?:tool\s+)?(?:called\s+|named\s+)?{spoken_name}", lowered
        )
        name = re.sub(r"\s+", "_", match.group(1).strip()) if match else None
        if name in {"it", "that", "without", "tool", "draft", "that_tool", "without_testing"}:
            name = None
        return "approve", name
    if re.search(r"\b(?:test|tests|run)\b", lowered) and re.search(
        r"\b(?:tool|tools|draft|drafts|it|them|isolated|sandbox|case|cases|all)\b", lowered
    ):
        if re.search(r"\b(?:them|all|tools|drafts|tests|cases)\b", lowered):
            return "test_all", None
        match = re.search(r"\b(?:test|run)\s+(?:the\s+)?(?:tool\s+)?([a-z][a-z0-9_]*)", lowered)
        name = match.group(1) if match and match.group(1) not in {
            "it", "in", "the", "draft", "tool", "test", "tests", "case", "cases", "them", "all"
        } else None
        return "test", name
    return None


def voice_api(method: str, path: str, key: str, payload: dict | None = None) -> dict:
    api = (env_value("ARIA_API_URL") or "http://127.0.0.1:8001").rstrip("/")
    request = urllib.request.Request(
        api + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"x-admin-api-key": key, "content-type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def prepare_voice_approval(name: str | None, key: str) -> tuple[str, dict | None]:
    proposals = voice_api("GET", "/admin/tool-proposals", key)["proposals"]
    candidates = [p for p in proposals if p["status"] in {"pending", "tested", "reviewed"}]
    if name:
        candidates = [p for p in candidates if p["name"] == name]
    if not candidates:
        return (f"No eligible tool draft{f' named {name}' if name else ''} found.", None)
    if len(candidates) != 1:
        return ("Several tool drafts match. Say approve followed by the exact tool name.", None)

    proposal = voice_api("GET", f"/admin/tool-proposals/{candidates[0]['id']}", key)["proposal"]
    proposal_id = proposal["id"]
    if proposal["status"] == "pending":
        test_result = run_voice_tool_test(proposal["name"])
        if "Isolated tests passed" not in test_result:
            return (test_result, None)
        proposal = voice_api("GET", f"/admin/tool-proposals/{proposal_id}", key)["proposal"]
    if proposal["status"] == "tested":
        proposal = voice_api(
            "POST",
            f"/admin/tool-proposals/{proposal_id}/review",
            key,
            {"sha256": proposal["sha256"], "test_count": len(proposal["tests"])},
        )["proposal"]
    if proposal["status"] != "reviewed":
        review = proposal.get("review", {})
        detail = review.get("summary", "Independent review did not approve this draft.")
        return (f"Reviewer did not approve {proposal['name']}: {detail}", None)
    return (
        f"Tests and independent review passed for {proposal['name']}. This mic does not verify who is speaking. "
        f"Say ‘confirm approve {proposal['name']}’ to install it, or say cancel.",
        {"id": proposal_id, "name": proposal["name"], "sha256": proposal["sha256"]},
    )


def confirm_voice_approval(pending: dict, key: str) -> str:
    proposal = voice_api("GET", f"/admin/tool-proposals/{pending['id']}", key)["proposal"]
    if proposal["sha256"] != pending["sha256"] or proposal["status"] != "reviewed":
        return "Tool draft changed or is no longer reviewed. Nothing was installed."
    installed = voice_api("POST", f"/admin/tool-proposals/{pending['id']}/approve", key)["tool"]
    return f"Approved and installed {installed['name']}. Aria can use it on her next request."


def run_voice_tool_test(name: str | None, all_pending: bool = False) -> str:
    command = [sys.executable, str(ROOT / "tools" / "aria"), "tools"]
    try:
        listed = subprocess.run(
            [*command, "list"], cwd=ROOT, capture_output=True, text=True, timeout=15, check=True
        )
        proposals = []
        for line in listed.stdout.splitlines():
            fields = line.split()
            if len(fields) == 3 and fields[2] == "pending":
                proposals.append((fields[0], fields[1]))
        matches = [proposal for proposal in proposals if all_pending or name is None or proposal[1] == name]
        if not matches:
            return f"No pending tool draft{f' named {name}' if name else ''} to test."
        if len(matches) > 1 and not all_pending:
            return "There are several pending tool drafts. Say: test tool, then its name."
        outcomes = []
        for proposal_id, tool_name in matches:
            tested = subprocess.run(
                [*command, "test", proposal_id], cwd=ROOT, capture_output=True, text=True, timeout=240
            )
            outcomes.append((tool_name, tested.returncode == 0))
        passed = [tool_name for tool_name, success in outcomes if success]
        failed = [tool_name for tool_name, success in outcomes if not success]
        result = f"Isolated tests passed for {', '.join(passed)}." if passed else "No isolated tests passed."
        if failed:
            result += f" Tests failed for {', '.join(failed)}."
        result += " Drafts remain inactive pending review and owner approval."
        return result
    except (OSError, subprocess.SubprocessError):
        return "I could not run the isolated tool test. Nothing was installed."


def _audio_callback(chunks: queue.Queue, indata, _frames, _time, _status) -> None:
    try:
        chunks.put_nowait(indata[:, 0].copy())
    except queue.Full:
        pass


def _is_playback_echo(audio, reference, np) -> bool:
    if not reference:
        return False
    audio = audio[::8].astype(np.float32)
    audio -= audio.mean()
    audio_norm = float(np.linalg.norm(audio))
    if audio_norm < 1e-6:
        return False
    output = np.concatenate(tuple(reference))[::8]
    for start in range(0, len(output) - len(audio) + 1, 8):
        candidate = output[start : start + len(audio)]
        candidate = candidate - candidate.mean()
        norm = float(np.linalg.norm(candidate))
        if norm > 1e-6 and abs(float(np.dot(audio, candidate)) / (audio_norm * norm)) >= 0.65:
            return True
    return False


def is_recent_playback_echo(transcript: str, spoken: str, spoken_at: float, now: float) -> bool:
    if now - spoken_at > 4.0:
        return False
    heard = re.sub(r"[^a-z0-9]", "", transcript.lower())
    expected = re.sub(r"[^a-z0-9]", "", spoken.lower())
    return len(heard) >= 3 and SequenceMatcher(None, heard, expected).ratio() >= 0.5


def duplex_audio_callback(
    chunks: queue.Queue,
    playback_chunks: queue.Queue,
    capture_enabled: threading.Event,
    playback_state: dict,
    source_done: threading.Event,
    playback_done: threading.Event,
    interrupted: threading.Event,
    np,
    indata,
    outdata,
    frames,
    _time,
    _status,
) -> None:
    if capture_enabled.is_set():
        mic = indata[:, 0]
        output_rms = playback_state.get("output_rms", 0.0)
        mic_rms = float(np.sqrt(np.mean(mic * mic)))
        echo = _is_playback_echo(mic, playback_state.get("reference", ()), np)
        if output_rms > VOICE_THRESHOLD and mic_rms < output_rms * 0.2:
            echo = True
        if not echo:
            _audio_callback(chunks, indata, frames, _time, _status)
    outdata.fill(0)
    if interrupted.is_set():
        playback_state["samples"] = None
        playback_state["output_rms"] = 0.0
        playback_done.set()
        return

    offset = 0
    while offset < frames:
        samples = playback_state["samples"]
        if samples is None:
            try:
                samples = playback_chunks.get_nowait()
            except queue.Empty:
                break
            playback_state["samples"] = samples
            playback_state["offset"] = 0
        count = min(frames - offset, len(samples) - playback_state["offset"])
        outdata[offset : offset + count, 0] = samples[playback_state["offset"] : playback_state["offset"] + count]
        offset += count
        playback_state["offset"] += count
        if playback_state["offset"] == len(samples):
            playback_state["samples"] = None

    if source_done.is_set() and playback_state["samples"] is None and playback_chunks.empty():
        playback_done.set()
    playback_state["output_rms"] = float(np.sqrt(np.mean(outdata[:, 0] * outdata[:, 0])))
    playback_state.setdefault("reference", deque(maxlen=12)).append(outdata[:, 0].copy())


def clear_queue(chunks: queue.Queue) -> None:
    while True:
        try:
            chunks.get_nowait()
        except queue.Empty:
            return


def listen_for_utterance(chunks: queue.Queue, np, seed: list | None = None) -> object:
    """Collect speech until one second of silence; discard ambient audio before speech."""
    pre_roll = deque(maxlen=5)
    utterance = list(seed or [])
    active = bool(seed)
    quiet_samples = 0
    while True:
        chunk = chunks.get()
        level = float(np.sqrt(np.mean(chunk * chunk)))
        if level >= VOICE_THRESHOLD:
            if not active:
                utterance.extend(pre_roll)
                pre_roll.clear()
            active = True
            quiet_samples = 0
            utterance.append(chunk)
        elif active:
            utterance.append(chunk)
            quiet_samples += len(chunk)
            if quiet_samples >= RATE * SILENCE_SECONDS:
                return np.concatenate(utterance)
        else:
            pre_roll.append(chunk)


def _resample_speech(samples, source_rate: int, np):
    samples = samples.astype(np.float32) / 32768.0
    if source_rate == RATE:
        return samples
    target_size = round(len(samples) * RATE / source_rate)
    positions = np.arange(target_size, dtype=np.float32) * source_rate / RATE
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.float32)


def play_response(
    tts,
    text: str,
    config,
    chunks: queue.Queue,
    playback_chunks: queue.Queue,
    source_done: threading.Event,
    playback_done: threading.Event,
    interrupted: threading.Event,
    np,
) -> tuple[list | None, float | None]:
    """Queue speech on the shared duplex device and monitor user speech for barge-in."""
    errors = []
    first_audio = []
    source_done.clear()
    playback_done.clear()
    interrupted.clear()

    def playback() -> None:
        try:
            for chunk in tts.synthesize(text, config):
                if interrupted.is_set():
                    break
                samples = _resample_speech(
                    np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16), tts.config.sample_rate, np
                )
                if not first_audio:
                    first_audio.append(time.perf_counter())
                for start in range(0, len(samples), RATE):
                    while not interrupted.is_set():
                        try:
                            playback_chunks.put(samples[start : start + RATE], timeout=0.05)
                            break
                        except queue.Full:
                            continue
                    if interrupted.is_set():
                        break
        except Exception as error:
            if not interrupted.is_set():
                errors.append(error)
        finally:
            source_done.set()

    recent = deque(maxlen=5)
    worker = threading.Thread(target=playback, daemon=True)
    worker.start()
    seed = None
    while not playback_done.wait(0.05):
        try:
            audio = chunks.get(timeout=0.05)
        except queue.Empty:
            continue
        if float(np.sqrt(np.mean(audio * audio))) >= VOICE_THRESHOLD:
            seed = [*recent, audio]
            interrupted.set()
            clear_queue(playback_chunks)
            playback_done.wait(1.0)
            break
        recent.append(audio)
    worker.join(timeout=0.2 if interrupted.is_set() else None)
    if errors:
        raise errors[0]
    return seed, first_audio[0] if first_audio else None


def env_value(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("\"'")
    return ""


def main() -> None:
    try:
        import numpy as np
        from piper import PiperVoice, SynthesisConfig
        import sounddevice as sd
    except ImportError as error:
        raise SystemExit("Voice dependencies missing. Install with: python3 -m pip install -r tools/voice-requirements.txt") from error

    key = env_value("ADMIN_API_KEY")
    if not key:
        raise SystemExit("Set ADMIN_API_KEY in Aria .env to use the authenticated local chat API.")
    voice_name = os.environ.get("ARIA_PIPER_VOICE", "amy").strip().lower()
    if voice_name not in PIPER_VOICES:
        raise SystemExit(f"Unknown ARIA_PIPER_VOICE {voice_name!r}. Choose: {', '.join(PIPER_VOICES)}")
    voice_model = PIPER_VOICES[voice_name]
    import sherpa_onnx

    required = [ASR / "tiny.en-encoder.int8.onnx", ASR / "tiny.en-decoder.int8.onnx", ASR / "tiny.en-tokens.txt",
                voice_model, voice_model.with_suffix(voice_model.suffix + ".json")]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Voice models are not installed. See docs/local-voice.md; missing: " + ", ".join(missing))

    recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(ASR / "tiny.en-encoder.int8.onnx"), decoder=str(ASR / "tiny.en-decoder.int8.onnx"),
        tokens=str(ASR / "tiny.en-tokens.txt"), num_threads=2,
        language="en", task="transcribe", provider="cpu",
    )
    tts = PiperVoice.load(voice_model)
    chunks: queue.Queue = queue.Queue(maxsize=64)
    playback_chunks: queue.Queue = queue.Queue(maxsize=16)
    capture_enabled = threading.Event()
    source_done = threading.Event()
    playback_done = threading.Event()
    interrupted = threading.Event()
    playback_state = {"samples": None, "offset": 0, "reference": deque(maxlen=12), "output_rms": 0.0}
    capture_enabled.set()
    last_spoken = ""
    last_spoken_at = 0.0

    def audio_callback(indata, outdata, frames, timing, status):
        duplex_audio_callback(
            chunks, playback_chunks, capture_enabled, playback_state, source_done,
            playback_done, interrupted, np, indata, outdata, frames, timing, status,
        )

    def speak(text: str) -> tuple[list | None, float | None]:
        nonlocal last_spoken, last_spoken_at
        clear_queue(chunks)
        playback_state["samples"] = None
        playback_state["offset"] = 0
        capture_enabled.set()
        result = play_response(
            tts, text, SynthesisConfig(speaker_id=0, length_scale=0.9), chunks,
            playback_chunks, source_done, playback_done, interrupted, np,
        )
        last_spoken = clean_for_speech(text)
        last_spoken_at = time.monotonic()
        if result[0] is None:
            capture_enabled.clear()
            clear_queue(chunks)
            capture_enabled.set()
        return result

    print("Voice mode active — Aria listens locally until you press Ctrl+C. Audio is not saved.")
    session = "local-voice"
    pending_audio = None
    pending_approval = None
    with sd.Stream(samplerate=RATE, channels=(1, 1), dtype="float32", blocksize=1024,
                   callback=audio_callback):
        pending_audio, _ = speak("Hi, I'm Aria. I'm here and listening. What can I help you with?")
        while True:
            samples = listen_for_utterance(chunks, np, pending_audio)
            pending_audio = None
            capture_enabled.clear()
            clear_queue(chunks)
            listen_seconds = len(samples) / RATE
            asr_started = time.perf_counter()
            stream = recognizer.create_stream()
            stream.accept_waveform(RATE, samples)
            recognizer.decode_stream(stream)
            asr_seconds = time.perf_counter() - asr_started
            transcript = stream.result.text.strip()
            if is_non_speech_transcript(transcript):
                print("[voice] Ignored blank or non-speech audio.")
                capture_enabled.set()
                continue
            if is_recent_playback_echo(transcript, last_spoken, last_spoken_at, time.monotonic()):
                print("[voice] Ignored speaker echo.")
                clear_queue(chunks)
                capture_enabled.set()
                continue
            print(f"You: {transcript}")
            if transcript.lower().strip(" .!?,") in {"exit voice", "stop listening", "quit voice"}:
                return
            if transcript.lower().strip(" .!?,") in {"cancel", "never mind", "nevermind"}:
                pending_approval = None
                capture_enabled.set()
                continue
            tool_intent = voice_tool_intent(transcript)
            if tool_intent and tool_intent[0] == "confirm_approve":
                if pending_approval and tool_intent[1] == pending_approval["name"]:
                    try:
                        answer = confirm_voice_approval(pending_approval, key)
                    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as error:
                        answer = f"Approval failed; nothing was installed. {error}"
                else:
                    answer = "No matching approval is waiting. Say approve and the tool name first."
                pending_approval = None
                print(f"Aria: {answer}")
                pending_audio, _ = speak(answer)
                continue
            if tool_intent and tool_intent[0] in {"test", "test_all"}:
                answer = run_voice_tool_test(tool_intent[1], all_pending=tool_intent[0] == "test_all")
                print(f"Aria: {answer}")
                spoken = clean_for_speech(answer)
                if spoken:
                    pending_audio, _ = speak(spoken)
                if pending_audio:
                    print("[voice] Speech interrupted — listening to your follow-up.")
                else:
                    capture_enabled.set()
                continue
            if tool_intent and tool_intent[0] == "approve":
                pending_approval = None
                try:
                    answer, pending_approval = prepare_voice_approval(tool_intent[1], key)
                except (urllib.error.URLError, urllib.error.HTTPError, OSError, subprocess.SubprocessError, KeyError, ValueError) as error:
                    answer = f"Approval review failed; nothing was installed. {error}"
                print(f"Aria: {answer}")
                pending_audio, _ = speak(answer)
                continue
            pending_approval = None
            api = (env_value("ARIA_API_URL") or "http://127.0.0.1:8001").rstrip("/") + "/chat"
            request = urllib.request.Request(
                api,
                data=json.dumps({"text": transcript, "session_id": session, "voice_mode": True}).encode(),
                headers={"x-admin-api-key": key, "content-type": "application/json"},
                method="POST",
            )
            try:
                api_started = time.perf_counter()
                with urllib.request.urlopen(request, timeout=180) as response:
                    answer = json.load(response).get("response_text", "No response returned.")
                api_seconds = time.perf_counter() - api_started
            except urllib.error.HTTPError as error:
                raise SystemExit(f"Aria API returned HTTP {error.code}: {error.read().decode(errors='replace')}") from error
            except urllib.error.URLError as error:
                raise SystemExit(f"Could not reach Aria at {api}: {error.reason}") from error
            display_answer = re.sub(
                r"(?:draft|proposal)\s*(?:ID\s*)?[:#]?\s*[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}",
                "tool draft",
                answer,
                flags=re.IGNORECASE,
            )
            display_answer = re.sub(
                r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", "", display_answer, flags=re.IGNORECASE
            )
            print(f"Aria: {display_answer}")
            spoken = clean_for_speech(answer)
            tts_seconds = 0.0
            first_audio_seconds = 0.0
            if spoken:
                tts_started = time.perf_counter()
                pending_audio, first_audio_at = speak(spoken)
                first_audio_seconds = first_audio_at - tts_started if first_audio_at else 0.0
                tts_seconds = time.perf_counter() - tts_started
            print(f"[timing] capture {listen_seconds:.1f}s | ASR {asr_seconds:.1f}s | agent {api_seconds:.1f}s | first audio {first_audio_seconds:.1f}s | playback {tts_seconds:.1f}s")
            if pending_audio:
                print("[voice] Speech interrupted — listening to your follow-up.")
            else:
                capture_enabled.set()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nVoice chat stopped.")
