from __future__ import annotations

import asyncio
import base64
import logging
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import numpy as np

from agent_core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    stt_model: str = "tiny.en"  # tiny.en, base.en, small.en, medium.en, large-v3
    stt_language: str = "en"
    tts_voice: str = "af_heart"  # Kokoro voices
    tts_speed: float = 1.0
    sample_rate: int = 16000
    channels: int = 1
    vad_threshold: float = 0.5
    silence_duration_ms: int = 800


class STTEngine:
    def __init__(self, config: VoiceConfig):
        self.config = config
        self._model = None
        self._init_model()

    def _init_model(self):
        try:
            # Try faster-whisper first (CTranslate2)
            from faster_whisper import WhisperModel
            model_path = self._get_model_path()
            self._model = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
            )
            self._backend = "faster-whisper"
            logger.info("Loaded faster-whisper model: %s", model_path)
        except ImportError:
            try:
                import whisper
                self._model = whisper.load_model(self.config.stt_model)
                self._backend = "whisper"
                logger.info("Loaded openai-whisper model: %s", self.config.stt_model)
            except ImportError:
                logger.warning("No STT backend available. Install faster-whisper or whisper.")
                self._model = None
                self._backend = None

    def _get_model_path(self) -> str:
        # Check for local model in .voice-data
        local_path = Path(settings.resolved_agent_data_dir).parent / "voice-data" / f"whisper-{self.config.stt_model}"
        if local_path.exists():
            return str(local_path)
        return self.config.stt_model  # Will download from HF

    def transcribe(self, audio_path: str) -> dict[str, Any]:
        if not self._model:
            return {"text": "", "error": "STT model not loaded"}

        try:
            if self._backend == "faster-whisper":
                segments, info = self._model.transcribe(
                    audio_path,
                    language=self.config.stt_language,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=self.config.silence_duration_ms),
                )
                text = " ".join(s.text for s in segments).strip()
                return {
                    "text": text,
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "duration": info.duration,
                }
            else:
                result = self._model.transcribe(audio_path, language=self.config.stt_language)
                return {
                    "text": result.get("text", "").strip(),
                    "language": result.get("language", self.config.stt_language),
                }
        except Exception as e:
            logger.error("STT transcription failed: %s", e)
            return {"text": "", "error": str(e)}

    async def transcribe_async(self, audio_path: str) -> dict[str, Any]:
        return await asyncio.get_event_loop().run_in_executor(None, self.transcribe, audio_path)


class TTSEngine:
    def __init__(self, config: VoiceConfig):
        self.config = config
        self._kokoro = None
        self._piper = None
        self._init_engines()

    def _init_engines(self):
        # Try Kokoro first
        try:
            from kokoro import KPipeline
            self._kokoro = KPipeline(lang_code='a')  # American English
            logger.info("Loaded Kokoro TTS")
        except ImportError:
            logger.debug("Kokoro not available")

        # Try Piper as fallback
        try:
            import piper
            self._piper = piper
            logger.info("Loaded Piper TTS")
        except ImportError:
            logger.debug("Piper not available")

    def synthesize(self, text: str, output_path: str) -> dict[str, Any]:
        if not text.strip():
            return {"success": False, "error": "Empty text"}

        # Try Kokoro first
        if self._kokoro:
            try:
                return self._synthesize_kokoro(text, output_path)
            except Exception as e:
                logger.warning("Kokoro synthesis failed, trying Piper: %s", e)

        # Fallback to Piper
        if self._piper:
            try:
                return self._synthesize_piper(text, output_path)
            except Exception as e:
                logger.error("Piper synthesis failed: %s", e)
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "No TTS engine available"}

    def _synthesize_kokoro(self, text: str, output_path: str) -> dict[str, Any]:
        import soundfile as sf

        # Split text into sentences for better prosody
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        if not sentences:
            sentences = [text]

        all_audio = []
        for sentence in sentences:
            generator = self._kokoro(sentence, voice=self.config.tts_voice, speed=self.config.tts_speed)
            for _, _, audio in generator:
                all_audio.append(audio)

        if all_audio:
            import numpy as np
            combined = np.concatenate(all_audio)
            sf.write(output_path, combined, self.config.sample_rate)
            return {"success": True, "engine": "kokoro", "duration": len(combined) / self.config.sample_rate}

        return {"success": False, "error": "No audio generated"}

    def _synthesize_piper(self, text: str, output_path: str) -> dict[str, Any]:
        # Piper voice model path
        voice_path = Path(settings.resolved_agent_data_dir).parent / "voice-data" / "piper-en-us-amy" / "en_US-amy-medium.onnx"
        if not voice_path.exists():
            voice_path = Path(settings.resolved_agent_data_dir).parent / "voice-data" / "piper-en-gb-southern-english-female" / "en_GB-southern_english_female-low.onnx"

        if not voice_path.exists():
            return {"success": False, "error": "Piper voice model not found"}

        cmd = [
            "piper",
            "--model", str(voice_path),
            "--output_file", output_path,
        ]

        result = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=30)
        if result.returncode == 0 and Path(output_path).exists():
            return {"success": True, "engine": "piper"}
        return {"success": False, "error": result.stderr.decode()}

    async def synthesize_async(self, text: str, output_path: str) -> dict[str, Any]:
        return await asyncio.get_event_loop().run_in_executor(None, self.synthesize, text, output_path)


class AudioProcessor:
    @staticmethod
    def save_wav(audio_data: bytes, sample_rate: int = 16000, channels: int = 1) -> str:
        """Save raw audio bytes to WAV file."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            with wave.open(f.name, 'wb') as wav:
                wav.setnchannels(channels)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)
                wav.writeframes(audio_data)
            return f.name

    @staticmethod
    def convert_to_wav(input_path: str, output_path: str, sample_rate: int = 16000) -> bool:
        """Convert any audio to WAV using ffmpeg."""
        try:
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", str(sample_rate),
                "-ac", "1",
                "-c:a", "pcm_s16le",
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_duration(audio_path: str) -> float:
        try:
            with wave.open(audio_path, 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / float(rate)
        except Exception:
            return 0.0


class VoiceInterface:
    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig()
        self.stt = STTEngine(self.config)
        self.tts = TTSEngine(self.config)
        self.audio = AudioProcessor()

    def transcribe_audio(self, audio_data: bytes | str, is_base64: bool = True) -> dict[str, Any]:
        """Transcribe audio from bytes or file path."""
        if isinstance(audio_data, str) and Path(audio_data).exists():
            audio_path = audio_data
        else:
            # Save base64 or raw bytes to temp file
            if is_base64 and isinstance(audio_data, str):
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = audio_data if isinstance(audio_data, bytes) else audio_data.encode()
            audio_path = self.audio.save_wav(audio_bytes, self.config.sample_rate, self.config.channels)

        try:
            result = self.stt.transcribe(audio_path)
            return result
        finally:
            # Cleanup temp file if we created it
            if not isinstance(audio_data, str) or not Path(audio_data).exists():
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass

    async def transcribe_audio_async(self, audio_data: bytes | str, is_base64: bool = True) -> dict[str, Any]:
        if isinstance(audio_data, str) and Path(audio_data).exists():
            return await self.stt.transcribe_async(audio_data)
        else:
            if is_base64 and isinstance(audio_data, str):
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = audio_data if isinstance(audio_data, bytes) else audio_data.encode()
            audio_path = self.audio.save_wav(audio_bytes, self.config.sample_rate, self.config.channels)
            try:
                return await self.stt.transcribe_async(audio_path)
            finally:
                try:
                    Path(audio_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def synthesize_speech(self, text: str, output_path: str | None = None) -> dict[str, Any]:
        """Synthesize speech to file or return base64."""
        if output_path is None:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name

        result = self.tts.synthesize(text, output_path)
        if result.get("success") and output_path:
            # Read back as base64 for API response
            try:
                with open(output_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                result["audio_base64"] = audio_b64
                result["audio_path"] = output_path
            except Exception:
                pass
        return result

    async def synthesize_speech_async(self, text: str, output_path: str | None = None) -> dict[str, Any]:
        if output_path is None:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_path = f.name
        result = await self.tts.synthesize_async(text, output_path)
        if result.get("success"):
            try:
                with open(output_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                result["audio_base64"] = audio_b64
                result["audio_path"] = output_path
            except Exception:
                pass
        return result

    def is_available(self) -> dict[str, bool]:
        return {
            "stt": self.stt._model is not None,
            "tts": self.tts._kokoro is not None or self.tts._piper is not None,
            "stt_backend": self.stt._backend,
            "tts_engines": {
                "kokoro": self.tts._kokoro is not None,
                "piper": self.tts._piper is not None,
            }
        }


# Global instance
voice_interface = VoiceInterface()
