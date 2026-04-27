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

# On-screen text — straight from the film
TITLE_TEXT = "VOICE RECOGNITION SYSTEM"
SUBTITLE_TEXT = "SIVAJI FOUNDATION  ◆  AUTHORIZED ACCESS ONLY"
BRAND_TEXT = "BOSS"
PROMPT_TEXT = "PLEASE SPEAK THE PASSWORD"
LISTENING_TEXT = "◉ LISTENING ◉"
PROCESSING_TEXT = "ANALYZING VOICEPRINT..."
SUCCESS_TEXT = "ACCESS GRANTED"
DENIED_TEXT = "ACCESS DENIED"
ERASURE_TEXT = "ERASING ALL DATA"

# Mock lines after a failed attempt — Vivek-style sass + film references
MOCK_LINES = [
    "VOICE NOT RECOGNIZED. NICE TRY, BUDDY.",
    "MIMICRY DETECTED. MGR-um naan-illa, SIVAJI-um naan-illa.",
    "NEGATIVE MATCH. THE BOSS DOES NOT APPROVE.",
    "AUTHENTICATION FAILED. THIS IS NOT SIVAJI.",
    "WRONG VOICE. SIVAJI-kku apparam yevan da?",
]

LOCKOUT_LINE = (
    "THREE FAILED ATTEMPTS — SYSTEM LOCKED FOR 60 SECONDS"
)
