"""Render an animated GIF showing the listening → granted → fail → erasure
sequence by capturing many frames of the live UI."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import sivaji_unlocker.audio as audio_mod
audio_mod.load_voiceprint = lambda: np.ones(256, dtype=np.float32)

import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1280, 800)

from sivaji_unlocker.ui import LockWindow, CYAN, RED, GREEN

OUT = REPO / "demo" / "anim"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = LockWindow()
    win.resize(1280, 800)
    win.overlay.setGeometry(win.rect())
    win.show()
    for _ in range(10):
        app.processEvents()

    frames = []

    def grab(name):
        pix: QPixmap = win.grab()
        path = OUT / f"frame_{len(frames):03d}.png"
        pix.save(str(path))
        frames.append(path)

    # Phase 1: idle pulses (8 frames over ~1s)
    for _ in range(12):
        for _ in range(3):
            app.processEvents()
        # advance the radar phase manually
        win.mic._phase += 0.06
        win.mic.update()
        win.overlay._scan_phase = (win.overlay._scan_phase + 6) % 200
        win.overlay.update()
        for _ in range(3):
            app.processEvents()
        grab("idle")

    # Phase 2: listening with waveform
    win.mic.set_mode("listening")
    win._set_status("◉ LISTENING ◉", CYAN)
    win._set_footer("RECORDING")
    for i in range(12):
        wave = (np.sin(np.linspace(0, 12 * np.pi, 200) + i * 0.6) *
                np.random.uniform(0.4, 1.0, 200)).astype(np.float32)
        win.mic.set_waveform(wave)
        win.mic._phase += 0.06
        win.mic.update()
        win.overlay._scan_phase = (win.overlay._scan_phase + 6) % 200
        win.overlay.update()
        for _ in range(4):
            app.processEvents()
        grab("listen")

    # Phase 3: processing
    win.mic.set_mode("processing")
    win._set_status("ANALYZING VOICEPRINT...", CYAN)
    win._set_footer("ANALYZING")
    for _ in range(8):
        win.mic._phase += 0.08
        win.mic.update()
        for _ in range(3):
            app.processEvents()
        grab("proc")

    # Phase 4: granted hold
    win.mic.set_mode("ok")
    win._set_status("ACCESS GRANTED — MATCH 92.7%", GREEN)
    win._set_footer("UNLOCKED")
    for _ in range(10):
        win.mic._phase += 0.05
        win.mic.update()
        for _ in range(3):
            app.processEvents()
        grab("grant")

    print(f"Captured {len(frames)} frames in {OUT}")


if __name__ == "__main__":
    main()
