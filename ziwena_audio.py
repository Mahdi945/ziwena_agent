"""
Ziwena — Audio module (Phase 5: voice in, voice out)

Speech-to-text: microphone (via sounddevice, not pyaudio) -> Google's free
recognition API (via SpeechRecognition).
Text-to-speech: offline, via pyttsx3 (no API key, works without internet).

Requires: pip install sounddevice numpy SpeechRecognition pyttsx3
(sounddevice has prebuilt wheels for far more Python versions/platforms
than pyaudio, so it installs cleanly on Windows without extra tools.)
"""

import io
import wave

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

_tts_engine = None

SAMPLE_RATE = 16000  # Hz — what Google's recognizer expects


def listen(timeout: int = 8, phrase_time_limit: int = 20):
    """
    Record from the default microphone (via sounddevice) and return
    recognized text, or None if nothing usable was captured.
    """
    if sd is None:
        print("[Audio: sounddevice not installed — voice input disabled. "
              "Run: pip install sounddevice numpy]")
        return None
    if sr is None:
        print("[Audio: SpeechRecognition not installed — voice input disabled. "
              "Run: pip install SpeechRecognition]")
        return None

    duration = phrase_time_limit
    print(f"[Listening... speak now (up to {duration}s)]")
    try:
        recording = sd.rec(
            int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
    except Exception as e:
        print(f"[Audio: no microphone available ({e})]")
        return None

    # Package the raw samples as an in-memory WAV file so speech_recognition
    # can read it the same way it would read a file from disk.
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 -> 2 bytes/sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(recording.tobytes())
    wav_buffer.seek(0)

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_buffer) as source:
        audio = recognizer.record(source)

    try:
        # Free tier of Google's web speech API — no key needed, rate-limited.
        text = recognizer.recognize_google(audio)
        print(f"[Heard]: {text}")
        return text
    except sr.UnknownValueError:
        print("[Audio: couldn't understand that]")
        return None
    except sr.RequestError as e:
        print(f"[Audio: speech recognition service error: {e}]")
        return None


def _get_engine():
    global _tts_engine
    if _tts_engine is None and pyttsx3 is not None:
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 175)
    return _tts_engine


def speak(text: str):
    """Speak `text` out loud, offline, blocking until done."""
    if pyttsx3 is None:
        print("[Audio: pyttsx3 not installed — voice output disabled. "
              "Run: pip install pyttsx3]")
        return
    if not text or not text.strip():
        return
    engine = _get_engine()
    if engine is None:
        return
    engine.say(text)
    engine.runAndWait()