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

# Don't go fullscreen
import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1600, 1000)

from sivaji_unlocker.ui import LockWindow, CYAN, RED, GREEN

OUT = REPO / "demo" / "frames"
OUT.mkdir(parents=True, exist_ok=True)


def render(scenes):
    app = QApplication.instance() or QApplication(sys.argv)

    for name, setup in scenes:
        win = LockWindow()
        win.resize(1600, 1000)
        win.overlay.setGeometry(win.rect())
        win.show()
        app.processEvents()
        # Stop the auto-running mic timer so the radar stays still
        win.mic._timer.stop()
        win.overlay._timer.stop()
        win._clock_timer.stop()
        if hasattr(win, '_erase_timer'):
            win._erase_timer.stop()

        setup(win)
        app.processEvents()
        # Allow paint events to flush
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


def fake_wave():
    return (np.sin(np.linspace(0, 12 * np.pi, 200)) *
            np.random.uniform(0.3, 1.0, 200)).astype(np.float32)


def s_idle(w):
    w.mic.set_mode("idle")


def s_listening(w):
    w.mic.set_mode("listening")
    w.mic.set_waveform(fake_wave())
    w._set_status("◉ LISTENING ◉", CYAN)
    w._set_footer("RECORDING")


def s_processing(w):
    w.mic.set_mode("processing")
    w._set_status("ANALYZING VOICEPRINT...", CYAN)
    w._set_footer("ANALYZING")


def s_granted(w):
    w.mic.set_mode("ok")
    w._set_status("ACCESS GRANTED — MATCH 92.7%", GREEN)
    w._set_footer("UNLOCKED")


def s_denied(w):
    w.mic.set_mode("fail")
    w.fail_count = 1
    w._set_status("ACCESS DENIED — MIMICRY DETECTED. MGR-um naan-illa, SIVAJI-um naan-illa. (38.8%)", RED)
    w._set_footer("FAILED")
    w.footer.setText(w._footer_text("FAILED"))


def s_erasure(w):
    w.fail_count = 3
    w.mic.set_mode("fail")
    w._set_status("ERASING ALL DATA", RED)
    w._set_footer("DATA ERASURE")
    w.footer.setText(w._footer_text("DATA ERASURE"))
    w.erase_bar.setValue(67)
    w.erase_bar.show()


def s_locked_out(w):
    w.fail_count = 0
    w.mic.set_mode("fail")
    w._set_status("THREE FAILED ATTEMPTS — SYSTEM LOCKED FOR 60 SECONDS", RED)
    w._set_footer("LOCKED OUT")
    w.footer.setText(w._footer_text("LOCKED OUT"))
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
