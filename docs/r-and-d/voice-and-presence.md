# R&D: Aria voice and presence

**Status:** research/design only. No microphone or camera access is enabled.

## Goal

Explore a portable Aria that responds quickly to either typed or spoken input,
speaks with a pleasant selectable voice, handles interruptions naturally,
optionally observes a camera feed, recognizes people who explicitly enrolled,
and asks before saving a new person's details. Voice matching may help Aria
decide whether to treat speech as the owner's ordinary request, but it is not
strong authentication. It must not unlock doors, grant access, or approve
code changes, purchases, or other consequential actions by itself.

## Main recommendation

Build this as optional sensor adapters around the existing agent, not as new
permissions inside the agent itself:

```text
Microphone ──> local VAD/streaming ASR ──> turn ───────┐
Keyboard ────────────────────────────────> same turn ├─> interaction manager ─> Aria task
Speaker check (optional) ────────────────> owner? ───┘        │
                                                             ├─ interrupt/cancel state
Aria response ──> local TTS (phrase-sized chunks) ─> speaker <──┘
Camera ──> local face detector/matcher ──> minimal event ──> consent flow
```

Raw audio/video should stay in the sensor process and be discarded after
inference. The agent receives text or a minimal event such as
`unrecognized_face_detected`; it should not receive continuous media. Keep
sensor processes, credentials, and biometric records outside Attic and outside
the agent's self-editable code paths.

## What each feature means

- **Voice interface:** speech-to-text (ASR), text-to-speech (TTS), and optionally
  a wake word. This lets a user speak to Aria; it does not identify the speaker.
- **Speaker recognition:** compares voice characteristics to an enrolled
  speaker. This is biometric processing, is optional, and is not needed for
  voice chat. Use it as a convenience filter, not sole proof of identity.
- **Face detection:** detects that a face is in a frame. It does not tell Aria
  who the person is.
- **Face recognition:** compares a detected face with enrolled identities.
  “No match” means “not recognized,” not proof the person is new.

Keep these capabilities separate in code, permissions, storage, and UI. Prefer
push-to-talk first; a wake word is a later, explicit opt-in. Typed and spoken
input should enter the same normalized turn path. Do not record or retain
ambient audio by default.

## Natural, interruptible conversation

“Fast” must be measured on the actual computer and target device; the model
alone does not determine responsiveness. Stream partial ASR results, stream
model output into phrase-sized TTS chunks, and play the first complete phrase
while later speech is still being generated. Keep audio capture and playback responsive
while a task runs. Benchmark time-to-first-partial transcript, end-of-utterance
to first audible response, and interruption-to-silence at p50/p95 on each
supported device. Set numeric targets only after a baseline on the user's
hardware.

Treat speech during playback as a **barge-in**, not as a second microphone
session:

1. Voice activity starts while TTS is playing → fade/stop playback immediately.
2. Partial transcription arrives → Aria briefly yields instead of talking over
   the user.
3. At end of the interruption, classify it as stop/cancel, correction, side
   question, or additional instruction; clarify when intent is ambiguous.
4. Cancel model generation cooperatively when possible. For an already-started
   tool/action, report its state and stop only at safe checkpoints; do not claim
   rollback or blindly retry a non-idempotent action.
5. Preserve the original task context if the user says “wait” or asks a side
   question, then resume only when appropriate. Keep typing available to correct
   transcripts or take over at any point.

Naturalness checks should include interruption timing, conversational pauses,
no talking over the user, recovery from ASR mistakes, and a voice-selection
listening test for clarity, warmth, pronunciation, and intelligibility in the
languages/accent the user actually uses. Prefer licensed existing voices for
the first version; voice cloning is a separate consent and licensing decision.

## Candidate components

| Capability | Candidate for a proof of concept | Important constraint |
|---|---|---|
| Local ASR/TTS/VAD | [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/) | Supports offline ASR/TTS and multiple operating systems; audit the license of each chosen model and voice, not only the runtime. |
| ASR comparison | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | MIT-licensed implementation; benchmark latency, memory, and language accuracy on the target device. |
| Wake word | [openWakeWord](https://github.com/dscripka/openWakeWord) | Code is Apache-2.0, but included pretrained models are CC BY-NC-SA 4.0; its documented support is currently English-focused. Do not bundle a model for redistribution until its model license and language fit are confirmed. |
| Face detection only | [MediaPipe Face Detector](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceDetector) | Has live-stream detection; detection is not identity. Confirm the selected task model's license and target-platform support. |
| Face identity | No model selected | InsightFace says its code is MIT but public pretrained models are non-commercial research only. Do not ship those weights without a suitable license. Evaluate a properly licensed model only after the detection-only prototype. |
| TTS voice | sherpa-onnx/Piper-compatible voice as a candidate | Piper code and each voice/model have separate licensing; review the exact [voice model card](https://github.com/rhasspy/piper-voices) before bundling. |
| Owner voice check | sherpa-onnx speaker embedding/verification APIs | Research candidate only. Validate false accepts/rejects and spoof resistance; speaker match is not secure authentication. Exact model license must be checked. |

Recommendation: prototype speech with sherpa-onnx behind a small Aria ASR/TTS
interface, compare Whisper.cpp for transcription quality, and postpone choosing
a wake-word or face-identity model until model licensing, target hardware, and
language requirements are settled. The speech runtime may be permissively
licensed while its downloaded weights are not.

For the requested interruption behavior, the key design choice is a streaming
interaction manager with cancellable task state—not a single blocking
“record, wait, reply” call. Keep streaming ASR and chunked TTS behind
replaceable interfaces so Aria can change inference engines without changing
memory or agent policy. Benchmark phrase-boundary artifacts and prosody; a
system can stream audio quickly and still sound choppy.

## Memory and consent boundary

Attic remains for ordinary durable facts, preferences, and decisions. It is not
a biometric vault.

- Never store raw face images, video, voice recordings, face embeddings, or
  speaker embeddings in Attic nodes or Aria's long-term SQLite graph.
- If the person has explicitly agreed to be remembered, an Attic node may hold
  ordinary details such as their chosen name and relationship, plus an opaque
  reference ID. The biometric template and consent/retention record belong in a
  separate, local, access-controlled and encrypted biometric store.
- Unknown/unmatched media is processed transiently and discarded. Do not create
  an identity or a memory from an unrecognized face alone.
- Before enrollment, show a clear explanation and get the person's consent as
  well as the owner's approval. Offer immediate deletion/revocation. Do not
  enroll guests, children, or bystanders by default.
- “Add a voice” must enter a short, visible enrollment mode only in an
  owner-authorized session. Bootstrap the first owner profile through an
  existing authenticated CLI/web session; voice cannot authenticate itself
  before enrollment. Later, the enrolled owner may say “add a voice” to start a
  short capture window. Capture the new person's prompted sample only with
  their consent, explain what is stored, then require owner confirmation before
  saving. Unknown voices never enroll themselves. Re-enrollment, export, and
  deletion should be owner controlled.
- Voice matching can be fooled by recordings or generated speech. Use it only
  as a best-effort filter for ordinary conversational requests; it cannot
  guarantee that only the owner is speaking. Allow a safe “stop/pause” from any
  speaker, and require a separate authenticated confirmation for sensitive
  actions. Do not treat a matching voice as authorization to use tools or alter
  Aria's code. NIST's digital-authenticator guidance rejects voice biometric
  comparison as an authentication method.
- Use an explicit camera/microphone enable switch, visible active indicator,
  per-device permission, and a clear pause/disable path. No hidden camera feeds
  or remote access by default.
- Never use voice/face matching as proof of identity for sensitive actions.
  Ask for normal account authentication or human confirmation instead.

Face matching can produce false matches and misses; performance depends on
image quality and can vary across demographic groups. An alert should say
“Aria could not match this face,” never assert “a stranger is here.” Measure
false-match and false-nonmatch rates on representative, consented test data and
choose conservative thresholds before any notification feature.

## Suggested R&D stages and exit checks

1. **Responsive voice conversation:** implement push-to-talk and streaming ASR →
   existing Aria request path → phrase-chunked TTS; keyboard uses the same turn path.
   Demonstrate barge-in, safe task cancellation, transcript correction, and
   pleasant voice selection. Measure latency and verify no audio retention or
   upload.
2. **Owner voice convenience check:** enroll only in explicit owner-started
   mode; unknown/uncertain speakers cannot trigger tools. Test false accepts,
   false rejects, replay/generated-voice attempts, noise, and language/accent
   variation. Keep a non-biometric owner control and step-up confirmation.
3. **Hands-free option:** evaluate local VAD/wake word only after push-to-talk
   works. Test false activations per hour, missed activations, multilingual
   behavior, resource use, and model redistribution terms. Keep push-to-talk as
   fallback.
4. **Camera detection, no identity:** process an explicitly selected local
   camera feed; report a face-present event without saving frames or asserting
   identity. Verify hardware disable, no network media egress, and event
   debouncing so one person does not cause repeated alerts.
5. **Opt-in identity proof of concept:** only after a model with acceptable
   licensing is selected. Enroll a consenting test user; distinguish match,
   no-match, and uncertain. Evaluate false matches/misses under lighting,
   pose, distance, and demographic variation. No automatic enrollment.
6. **Consent and memory UX:** show the person/owner what will be stored, ask
   before enrollment and before adding ordinary facts to Attic, support revoke
   and delete, and test that biometric material never enters Attic or logs.
7. **Portable packaging:** keep OS-specific camera/microphone capture behind
   adapters and inference behind replaceable ASR/TTS/vision interfaces. Test
   each target OS/device separately; “runs anywhere” requires a per-device
   support matrix, not one universal container.

Do not begin stages 3–5 until the privacy/storage boundary and exact model
licenses are reviewed. Voice interaction can be researched independently of
biometric identification.

## Sources checked (2026-10-21)

- sherpa-onnx documents offline processing and cross-platform builds:
  [project docs](https://k2-fsa.github.io/sherpa/onnx/),
  [feature/API overview](https://k2-fsa.github.io/sherpa/onnx/c-api/html/index.html),
  [speaker identification](https://k2-fsa.github.io/sherpa/onnx/speaker-identification/),
  [pretrained model catalog](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/index.html).
- Whisper.cpp repository and license:
  [official repository](https://github.com/ggml-org/whisper.cpp).
- openWakeWord code/model license distinction and language notes:
  [official repository](https://github.com/dscripka/openWakeWord).
- MediaPipe live-stream face detector API:
  [official API reference](https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceDetector).
- InsightFace code and pretrained model license distinction:
  [model zoo/license guide](https://github.com/deepinsight/insightface/blob/master/python-package/docs/model_zoo.md).
- Piper engine and voice/model licensing:
  [engine license](https://github.com/rhasspy/piper/blob/master/LICENSE.md),
  [voice catalog](https://github.com/rhasspy/piper-voices).
- NIST summarizes false-match/miss demographic differentials and image-quality
  sensitivity: [Face Recognition Technology Evaluation](https://pages.nist.gov/frvt/html/frvt_demographics.html).
- NIST's digital identity guidance on biometrics and voice comparison:
  [SP 800-63B authenticator requirements](https://pages.nist.gov/800-63-4/sp800-63b/authenticators/).
- India’s official statute, if India is a deployment jurisdiction:
  [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/writereaddata/files/Digital%20Personal%20Data%20Protection%20Act%202023.pdf).

This is engineering R&D, not legal advice. Before any real deployment, review
the applicable privacy/biometric rules for each location and the licenses for
the exact software, model weights, and voice.
