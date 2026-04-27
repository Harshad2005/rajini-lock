"""Microphone recording + speaker-verification logic.

Uses Resemblyzer for speaker embeddings (cosine similarity in a 256-dim
voice-print space). This is the same idea used in production speaker-ID
systems — it's the "any words in your voice" mode you picked.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List

import numpy as np

# Lazy imports — these pull in heavy native deps (PortAudio, torch). We
# don't want them at module-import time so the UI can run in demo/test
# environments without microphone hardware.
_sd = None
_VoiceEncoder = None
_preprocess_wav = None


def _lazy_audio():
    global _sd
    if _sd is None:
        import sounddevice as sd
        _sd = sd
    return _sd


def _lazy_resemblyzer():
    global _VoiceEncoder, _preprocess_wav
    if _VoiceEncoder is None:
        from resemblyzer import VoiceEncoder, preprocess_wav
        _VoiceEncoder = VoiceEncoder
        _preprocess_wav = preprocess_wav
    return _VoiceEncoder, _preprocess_wav


from . import config

log = logging.getLogger(__name__)

# Lazy-load the encoder — it takes ~1 second on first import.
_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        log.info("Loading speaker-encoder model...")
        VoiceEncoder, _ = _lazy_resemblyzer()
        _encoder = VoiceEncoder(verbose=False)
    return _encoder


def record_audio(seconds: float = config.RECORD_SECONDS) -> np.ndarray:
    """Record `seconds` of mono audio at 16 kHz from the default mic."""
    log.info("Recording %.1fs of audio...", seconds)
    sd = _lazy_audio()
    audio = sd.rec(
        int(seconds * config.SAMPLE_RATE),
        samplerate=config.SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio.flatten()


def listen_until_speech(
    silence_threshold: float = 0.015,
    min_silence_ms: int = 300,
    max_wait_s: float = 30.0,
    capture_s: float = 4.0,
    on_level=None,
):
    """Continuously sample the mic in small chunks. As soon as RMS exceeds
    `silence_threshold` we treat that as speech onset and capture the next
    `capture_s` seconds. Returns the captured audio, or None if `max_wait_s`
    elapsed without speech.

    `on_level(rms, is_voiced)` is called for each chunk so the UI can
    visualize ambient sound and show 'detecting' state.
    """
    sd = _lazy_audio()
    chunk_ms = 50
    chunk_n = int(config.SAMPLE_RATE * chunk_ms / 1000)
    elapsed = 0.0

    with sd.InputStream(
        samplerate=config.SAMPLE_RATE, channels=1, dtype="float32",
        blocksize=chunk_n,
    ) as stream:
        while elapsed < max_wait_s:
            buf, _ = stream.read(chunk_n)
            chunk = buf.flatten()
            rms = float(np.sqrt(np.mean(chunk ** 2) + 1e-12))
            voiced = rms > silence_threshold
            if on_level is not None:
                on_level(rms, voiced)
            if voiced:
                # Capture the next capture_s of audio (including this chunk).
                tail_n = int(capture_s * config.SAMPLE_RATE) - chunk_n
                tail_buf, _ = stream.read(tail_n)
                full = np.concatenate([chunk, tail_buf.flatten()])
                return full
            elapsed += chunk_ms / 1000.0
    return None


def embed(audio: np.ndarray) -> np.ndarray:
    """Convert raw audio into a 256-dim speaker embedding."""
    _, preprocess_wav = _lazy_resemblyzer()
    wav = preprocess_wav(audio, source_sr=config.SAMPLE_RATE)
    return _get_encoder().embed_utterance(wav)


def enroll(samples: List[np.ndarray]) -> np.ndarray:
    """Average the embeddings of multiple enrollment recordings to build
    a robust voiceprint. More samples = better generalization."""
    embeddings = np.stack([embed(s) for s in samples])
    voiceprint = embeddings.mean(axis=0)
    # L2-normalize so cosine similarity == dot product
    voiceprint = voiceprint / np.linalg.norm(voiceprint)
    return voiceprint


def verify(audio: np.ndarray, voiceprint: np.ndarray) -> tuple[bool, float]:
    """Return (matched, similarity) for an unlock attempt."""
    candidate = embed(audio)
    candidate = candidate / np.linalg.norm(candidate)
    voiceprint = voiceprint / np.linalg.norm(voiceprint)
    similarity = float(np.dot(candidate, voiceprint))
    matched = similarity >= config.SIMILARITY_THRESHOLD
    log.info("Verify: similarity=%.3f matched=%s", similarity, matched)
    return matched, similarity


def save_voiceprint(voiceprint: np.ndarray) -> None:
    np.save(config.EMBEDDING_FILE, voiceprint)
    log.info("Saved voiceprint to %s", config.EMBEDDING_FILE)


def load_voiceprint() -> np.ndarray | None:
    if not config.EMBEDDING_FILE.exists():
        return None
    return np.load(config.EMBEDDING_FILE)
