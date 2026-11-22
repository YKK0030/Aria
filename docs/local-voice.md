# Local Aria voice

Voice runs on the host, not in Docker. Microphone audio is processed locally;
Aria receives only the recognized transcript through its existing authenticated
`/chat` API. No audio is saved or sent to Attic. Voice mode listens continuously
while its process is running; there is no wake word. It is English-only and
supports interrupting spoken playback by speaking over Aria. It does not cancel
an agent request while the model is still generating a reply. Headphones reduce
false interruptions caused by Aria's voice leaking from speakers into the mic.
The microphone and speaker share one full-duplex 16 kHz audio stream; Piper output
is resampled to that device rate to avoid competing ALSA streams.

## Setup

Start Aria with the web/API channel and ensure `.env` has `ADMIN_API_KEY`:

```sh
python3 tools/aria start --channels web --voice
python3 -m venv .venv-voice
.venv-voice/bin/python -m pip install -r tools/voice-requirements.txt
```

Download and extract the official model archives from the Aria repository root:

```sh
mkdir -p .voice-data
curl -fL https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-tiny.en.tar.bz2 -o .voice-data/whisper-tiny.en.tar.bz2
tar -xjf .voice-data/whisper-tiny.en.tar.bz2 -C .voice-data
mkdir -p .voice-data/piper-en-us-amy
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx' -o .voice-data/piper-en-us-amy/en_US-amy-medium.onnx
curl -fL 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json' -o .voice-data/piper-en-us-amy/en_US-amy-medium.onnx.json
```

Additional downloaded Piper voices are available for audition:

| Voice | Locale | Piper quality |
|---|---|---|
| `amy` | US English | medium; current default |
| `hfc_female` | US English | medium |
| `kristin` | US English | medium |
| `kathleen` | US English | low |
| `southern_english_female` | UK English | low |

Choose a voice for one run with `ARIA_PIPER_VOICE`; Amy remains the default:

```sh
ARIA_PIPER_VOICE=hfc_female PYTHON=.venv-voice/bin/python python3 tools/aria start --channels web --voice
ARIA_PIPER_VOICE=kristin PYTHON=.venv-voice/bin/python python3 tools/aria start --channels web --voice
ARIA_PIPER_VOICE=kathleen PYTHON=.venv-voice/bin/python python3 tools/aria start --channels web --voice
ARIA_PIPER_VOICE=southern_english_female PYTHON=.venv-voice/bin/python python3 tools/aria start --channels web --voice
```

Review each model's license before use; model weights have licenses separate
from the runtime. The voice client uses quantized Whisper tiny.en for input and
Piper Amy medium for female speech output.

Run:

```sh
PYTHON=.venv-voice/bin/python python3 tools/aria start --channels web --voice
```

Aria greets you after loading the voice models, then sends each detected utterance
without keyboard confirmation. Say “cancel” or “never mind” to discard an utterance;
say “exit voice” or press Ctrl+C to stop. During spoken replies the mic stays active;
start speaking to stop playback and have Aria process your follow-up.
Piper Amy medium is the default female voice. Each turn prints separate capture,
agent, and speech timings. If it fails to detect quiet speech or reacts to
background noise, adjust the RMS threshold in `tools/aria_voice.py` for your mic.
Say “test the pending tool in isolation” (or “test tool NAME”) to run its sandbox
tests. Say “approve NAME” to run tests when needed and request an independent
review. If both pass, Aria asks you to say “confirm approve NAME” before install.
This local voice flow uses the admin API key but does not authenticate the speaker;
anyone able to use the microphone can approve a reviewed tool. Use voice mode only
in a trusted, private environment. The authenticated CLI remains available.

Official references: [sherpa-onnx Python API](https://k2-fsa.github.io/sherpa/onnx/python/),
[Whisper tiny.en model](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/whisper/tiny.en.html),
[Piper voice models](https://github.com/rhasspy/piper/blob/master/VOICES.md).

## Next voice stages

1. Calibrate the speech threshold and measure end-of-utterance/first-audio latency
   on the target microphone and CPU.
2. Add cancellation of agent requests while the model is still generating; spoken
   playback interruption is implemented, but still needs testing on the target mic.
3. Only then prototype opt-in speaker recognition with local-only enrollment;
   never treat a voice match as authorization or store voiceprints in Attic.
