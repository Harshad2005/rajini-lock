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
