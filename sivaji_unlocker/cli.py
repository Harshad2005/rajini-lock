"""Tiny CLI helpers for emergency disable/enable of the lock screen."""
from __future__ import annotations

from . import config


def disable() -> int:
    config.KILL_SWITCH.touch()
    print(f"[✓] Kill-switch enabled at {config.KILL_SWITCH}")
    print("    Rajini-Lock will not run on next login until you re-enable.")
    return 0


def enable() -> int:
    if config.KILL_SWITCH.exists():
        config.KILL_SWITCH.unlink()
        print(f"[✓] Kill-switch removed. Rajini-Lock is active again.")
    else:
        print("[i] Kill-switch was not set. Already active.")
    return 0
