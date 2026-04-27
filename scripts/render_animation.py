"""Render an animated GIF showing the idle → listening → processing → granted
sequence by capturing many frames of the live UI."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import sivaji_unlocker.audio as audio_mod
audio_mod.load_voiceprint = lambda: np.ones(256, dtype=np.float32)

import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1280, 800)
ui_mod.LockWindow._start_listener = lambda self: None

from sivaji_unlocker.ui import LockWindow, TEXT_CYAN, TEXT_WHITE
from sivaji_unlocker import config

OUT = REPO / "demo" / "anim"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = LockWindow()
    win.resize(1280, 800)
    win.bg.setGeometry(win.rect())
    win.show()
    for _ in range(10):
        app.processEvents()

    frames = []

    def grab():
        pix: QPixmap = win.grab()
        path = OUT / f"frame_{len(frames):03d}.png"
        pix.save(str(path))
        frames.append(path)

    def advance_anim_phase():
        # Manually tick all background animation timers since they're free-running
        win.bg._phase += 0.05
        win.mascot._phase += 0.10
        win.waveform._phase += 0.22
        win.status_bar_widget._phase += 1
        win.bg.update()
        win.mascot.update()
        win.waveform.update()
        win.status_bar_widget.update()

    rng = np.random.default_rng(0)

    def push_buffer(amp):
        # Push a few samples to make the wave breathe
        for _ in range(4):
            v = abs(math.sin(win.waveform._phase * 1.7) *
                    rng.uniform(0.3, 1.0)) * amp
            win.waveform.push_sample(v)

    # Phase 1: idle (8 frames)
    win.mascot.set_mode("idle")
    win.status_bar_widget.set_text(config.IDLE_TEXT, TEXT_CYAN)
    win.waveform.set_intensity(0.0)
    for _ in range(8):
        push_buffer(0.05)
        advance_anim_phase()
        for _ in range(3): app.processEvents()
        grab()

    # Phase 2: listening (12 frames)
    win.mascot.set_mode("listening")
    win.status_bar_widget.set_text(config.LISTENING_TEXT, TEXT_CYAN)
    win.waveform.set_intensity(0.7)
    for _ in range(12):
        push_buffer(0.7)
        advance_anim_phase()
        for _ in range(3): app.processEvents()
        grab()

    # Phase 3: processing (10 frames)
    win.status_bar_widget.set_text(config.PROCESSING_TEXT, TEXT_CYAN)
    win.waveform.set_intensity(1.0)
    for _ in range(10):
        push_buffer(0.9)
        advance_anim_phase()
        for _ in range(3): app.processEvents()
        grab()

    # Phase 4: voice recognised (12 frames)
    win.mascot.set_mode("ok")
    win.status_bar_widget.set_text(config.SUCCESS_TEXT, TEXT_WHITE)
    win.waveform.set_intensity(0.4)
    for _ in range(12):
        push_buffer(0.3)
        advance_anim_phase()
        for _ in range(3): app.processEvents()
        grab()

    print(f"Captured {len(frames)} frames in {OUT}")


if __name__ == "__main__":
    main()
