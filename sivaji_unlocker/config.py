"""Configuration paths and constants for the Sivaji unlocker."""
from __future__ import annotations

import os
from pathlib import Path

# Where the app stores enrollment data, logs, and the kill-switch flag.
APP_NAME = "RajiniLock"
APP_SUPPORT = Path(os.path.expanduser(f"~/Library/Application Support/{APP_NAME}"))
APP_SUPPORT.mkdir(parents=True, exist_ok=True)

EMBEDDING_FILE = APP_SUPPORT / "voiceprint.npy"
CONFIG_FILE = APP_SUPPORT / "config.json"
LOG_FILE = APP_SUPPORT / "unlocker.log"

# Kill-switch: if this file exists, the unlocker exits immediately on launch.
# Your safety net — `touch` it via SSH or Recovery Mode and the lock skips.
KILL_SWITCH = Path(os.path.expanduser("~/.rajini_disable"))

# Voice matching parameters
SAMPLE_RATE = 16000
RECORD_SECONDS = 4
ENROLL_SAMPLES = 5
SIMILARITY_THRESHOLD = 0.75

# Fail-handling
MAX_ATTEMPTS = 3
LOCKOUT_SECONDS = 60

# On-screen text — film-accurate (Sivaji 9:37–9:47 clip)
# The bar shows lowercase "processing" → "voice recognised" — exactly like the film.
PASSPHRASE_HINT = "Hi, I am Harshad, buddy"
IDLE_TEXT       = "say the phrase"
LISTENING_TEXT  = "listening"
PROCESSING_TEXT = "processing"
SUCCESS_TEXT    = "voice recognised"
DENIED_TEXT     = "voice not recognised"
ERASURE_TEXT    = "erasing data"

# Brand text (small, in corner)
BRAND_TEXT = "BOSS"

# Mock lines after a failed attempt — Vivek-style sass + film references
MOCK_LINES = [
    "voice not recognised. nice try, buddy.",
    "mimicry detected. mgr-um naan-illa, sivaji-um naan-illa.",
    "negative match. the boss does not approve.",
    "authentication failed. this is not sivaji.",
    "wrong voice. sivaji-kku apparam yevan da?",
]

LOCKOUT_LINE = "three failed attempts — locked for 60s"
