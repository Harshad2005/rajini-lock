"""Render demo frames of the Rajini-Lock UI.

Strategy: extract a frame from the background video (the actual film footage,
enhanced) and composite the PyQt6 overlay on top. This produces the exact same
visual the user sees on a real Mac, since QVideoWidget renders the same video
underneath the overlay.

Run from the repo root:
    xvfb-run -a -s "-screen 0 1600x1000x24" python scripts/render_demo.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Stub voiceprint loading
import sivaji_unlocker.audio as audio_mod
audio_mod.load_voiceprint = lambda: np.ones(256, dtype=np.float32)

# Don't go fullscreen, don't start the listener
import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1600, 1000)
ui_mod.LockWindow._start_listener = lambda self: None

# Render-only: replace the QVideoWidget+QMediaPlayer with a transparent stub.
# The actual movie frame is composited from FFmpeg-extracted images, since
# QtMultimedia's video surface doesn't render through QWidget.grab().
from PyQt6.QtWidgets import QWidget as _QW


class _StubVideo(_QW):
    def setSource(self, *a, **kw): pass
    def setVideoOutput(self, *a, **kw): pass
    def setAudioOutput(self, *a, **kw): pass
    def setLoops(self, *a, **kw): pass
    def play(self, *a, **kw): pass
    def setMuted(self, *a, **kw): pass


class _StubPlayer:
    class Loops:
        Infinite = -1
    def __init__(self, *a, **kw): pass
    def setSource(self, *a, **kw): pass
    def setVideoOutput(self, *a, **kw): pass
    def setAudioOutput(self, *a, **kw): pass
    def setLoops(self, *a, **kw): pass
    def play(self, *a, **kw): pass


class _StubAudio:
    def __init__(self, *a, **kw): pass
    def setMuted(self, *a, **kw): pass


ui_mod.QVideoWidget = _StubVideo
ui_mod.QMediaPlayer = _StubPlayer
ui_mod.QAudioOutput = _StubAudio

from sivaji_unlocker.ui import (
    LockWindow, TEXT_CYAN, TEXT_WHITE, RAIL_RED,
)
from sivaji_unlocker import config

OUT = REPO / "demo" / "frames"
OUT.mkdir(parents=True, exist_ok=True)
BG_VIDEO = REPO / "assets" / "lock_background.mp4"


def extract_bg_frame(t: float, w: int, h: int) -> Image.Image:
    """Extract a frame from the background video at time t."""
    out_path = REPO / "demo" / f"_bg_{int(t*1000)}.png"
    cmd = [
        "ffmpeg", "-y", "-ss", str(t), "-i", str(BG_VIDEO),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
               f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        "-frames:v", "1", "-q:v", "2", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    img = Image.open(out_path).convert("RGBA")
    out_path.unlink()
    return img


def render(scenes):
    app = QApplication.instance() or QApplication(sys.argv)
    W, H = 1600, 1000

    for name, bg_t, setup in scenes:
        win = LockWindow()
        win.resize(W, H)
        win.show()
        app.processEvents()
        # Freeze internal animation timers
        for tname in ("_timer", "_clock_timer"):
            t = getattr(win, tname, None)
            if t is not None: t.stop()
        if hasattr(win, "status_bar_widget"):
            win.status_bar_widget._timer.stop()

        setup(win)
        for _ in range(8):
            app.processEvents()

        # Capture overlay (transparent where it's transparent)
        # Save to PNG via Qt's own writer, then load with PIL.
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        overlay_pix: QPixmap = win.overlay.grab()
        overlay_qimg = overlay_pix.toImage()
        ba_obj = QByteArray()
        buf = QBuffer(ba_obj)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        overlay_qimg.save(buf, "PNG")
        buf.close()
        overlay_img = Image.open(io.BytesIO(bytes(ba_obj))).convert("RGBA")
        if overlay_img.size != (W, H):
            overlay_img = overlay_img.resize((W, H), Image.Resampling.LANCZOS)

        # Background frame from the actual enhanced film
        bg_img = extract_bg_frame(bg_t, W, H)

        # Composite: video underneath, overlay on top
        combined = Image.alpha_composite(bg_img, overlay_img)
        path = OUT / f"{name}.png"
        combined.convert("RGB").save(path)
        print(f"  → {path.relative_to(REPO)}  ({W}x{H})")

        win.close()
        win._allow_close = True
        win.deleteLater()
        app.processEvents()


def s_idle(w):
    w.status_bar_widget.set_text(config.IDLE_TEXT, TEXT_CYAN)


def s_listening(w):
    w.status_bar_widget.set_text(config.LISTENING_TEXT, TEXT_CYAN)


def s_processing(w):
    w.status_bar_widget.set_text(config.PROCESSING_TEXT, TEXT_CYAN)


def s_granted(w):
    w.status_bar_widget.set_text(config.SUCCESS_TEXT, TEXT_WHITE)


def s_denied(w):
    w.fail_count = 1
    w.status_bar_widget.set_text(
        "voice not recognised. nice try, buddy.",
        ui_mod.QColor("#FFE0E0"),
    )


def s_erasure(w):
    w.fail_count = 3
    w.status_bar_widget.set_text(config.ERASURE_TEXT, ui_mod.QColor("#FFE0E0"))
    w.erase_bar.setValue(67)
    w.erase_bar.show()


def s_locked_out(w):
    w.status_bar_widget.set_text(config.LOCKOUT_LINE, ui_mod.QColor("#FFE0E0"))
    w.erase_bar.setValue(100)
    w.erase_bar.show()


# Background timestamps chosen so each state shows the mascot in a varied pose
SCENES = [
    ("01_idle",       0.5, s_idle),
    ("02_listening",  1.0, s_listening),
    ("03_processing", 1.5, s_processing),
    ("04_granted",    2.0, s_granted),
    ("05_denied",     2.5, s_denied),
    ("06_erasure",    3.0, s_erasure),
    ("07_locked",     3.5, s_locked_out),
]

if __name__ == "__main__":
    render(SCENES)
    print(f"\nAll frames written to {OUT}")
