"""Render demo frames of the Rajini-Lock UI without a real microphone.

Each frame is rendered in a clean state — no animations across frames —
so the script is fast and deterministic.

Run from the repo root:
    xvfb-run -a -s "-screen 0 1600x1000x24" python scripts/render_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Stub voiceprint loading
import sivaji_unlocker.audio as audio_mod
audio_mod.load_voiceprint = lambda: np.ones(256, dtype=np.float32)

# Don't go fullscreen, and don't actually start the listener thread
import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1600, 1000)
ui_mod.LockWindow._start_listener = lambda self: None

from sivaji_unlocker.ui import (
    LockWindow, TEXT_CYAN, TEXT_WHITE, RAIL_RED,
)
from sivaji_unlocker import config

OUT = REPO / "demo" / "frames"
OUT.mkdir(parents=True, exist_ok=True)


def render(scenes):
    app = QApplication.instance() or QApplication(sys.argv)

    for name, setup in scenes:
        win = LockWindow()
        win.resize(1600, 1000)
        win.bg.setGeometry(win.rect())
        win.show()
        app.processEvents()
        # Freeze internal animation timers for deterministic frames
        win.bg._timer.stop()
        win.mascot._timer.stop()
        win.waveform._timer.stop()
        win.status_bar_widget._timer.stop()
        win._clock_timer.stop()
        if hasattr(win, '_erase_timer'):
            win._erase_timer.stop()

        setup(win)
        app.processEvents()
        for _ in range(8):
            app.processEvents()

        pix: QPixmap = win.grab()
        path = OUT / f"{name}.png"
        pix.save(str(path))
        print(f"  → {path.relative_to(REPO)}  ({pix.width()}x{pix.height()})")
        win.close()
        win._allow_close = True
        win.deleteLater()
        app.processEvents()


def fake_wave(amp=1.0, n=220):
    rng = np.random.default_rng(7)
    return np.abs(np.sin(np.linspace(0, 14 * np.pi, n)) *
                  rng.uniform(0.4, 1.0, n) * amp).astype(np.float32)


def s_idle(w):
    w.mascot.set_mode("idle")
    w.status_bar_widget.set_text(config.IDLE_TEXT, TEXT_CYAN)
    # Set a flat waveform
    w.waveform._buffer.clear()
    for v in [0.04] * 220:
        w.waveform._buffer.append(v)
    w.waveform._intensity = 0.0


def s_listening(w):
    w.mascot.set_mode("listening")
    w.status_bar_widget.set_text(config.LISTENING_TEXT, TEXT_CYAN)
    wave = fake_wave(0.6)
    w.waveform._buffer.clear()
    for v in wave:
        w.waveform._buffer.append(float(v))
    w.waveform._intensity = 0.7


def s_processing(w):
    w.mascot.set_mode("listening")
    w.status_bar_widget.set_text(config.PROCESSING_TEXT, TEXT_CYAN)
    wave = fake_wave(1.0)
    w.waveform._buffer.clear()
    for v in wave:
        w.waveform._buffer.append(float(v))
    w.waveform._intensity = 1.0


def s_granted(w):
    w.mascot.set_mode("ok")
    w.status_bar_widget.set_text(config.SUCCESS_TEXT, TEXT_WHITE)
    wave = fake_wave(0.3)
    w.waveform._buffer.clear()
    for v in wave:
        w.waveform._buffer.append(float(v))
    w.waveform._intensity = 0.4


def s_denied(w):
    w.mascot.set_mode("fail")
    w.fail_count = 1
    w.status_bar_widget.set_text(
        "voice not recognised. nice try, buddy.",
        ui_mod.QColor("#FFE0E0"),
    )
    wave = fake_wave(0.7)
    w.waveform._buffer.clear()
    for v in wave:
        w.waveform._buffer.append(float(v))
    w.waveform._intensity = 0.6


def s_erasure(w):
    w.fail_count = 3
    w.mascot.set_mode("fail")
    w.status_bar_widget.set_text(config.ERASURE_TEXT,
                                 ui_mod.QColor("#FFE0E0"))
    w.erase_bar.setValue(67)
    w.erase_bar.show()
    wave = fake_wave(0.2)
    w.waveform._buffer.clear()
    for v in wave:
        w.waveform._buffer.append(float(v))
    w.waveform._intensity = 0.2


def s_locked_out(w):
    w.fail_count = 0
    w.mascot.set_mode("fail")
    w.status_bar_widget.set_text(config.LOCKOUT_LINE,
                                 ui_mod.QColor("#FFE0E0"))
    w.erase_bar.setValue(100)
    w.erase_bar.show()


SCENES = [
    ("01_idle",       s_idle),
    ("02_listening",  s_listening),
    ("03_processing", s_processing),
    ("04_granted",    s_granted),
    ("05_denied",     s_denied),
    ("06_erasure",    s_erasure),
    ("07_locked",     s_locked_out),
]

if __name__ == "__main__":
    render(SCENES)
    print(f"\nAll frames written to {OUT}")
