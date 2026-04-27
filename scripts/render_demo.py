"""Render demo frames of the Rajini-Lock UI.

Strategy: extract a frame from the per-state pose video and composite the
PyQt6 HUD overlay on top. The composite mirrors what the real Mac app draws,
since on a Mac the VideoBackground paints the same frame underneath the same
HUD overlay.

Run from the repo root:
    xvfb-run -a -s "-screen 0 1600x1000x24" python scripts/render_demo.py
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QWidget as _QW

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# ── Stub things that need a real audio/video backend ────────────────────────
import sivaji_unlocker.audio as audio_mod
audio_mod.load_voiceprint = lambda: np.ones(256, dtype=np.float32)

import sivaji_unlocker.ui as ui_mod
ui_mod.LockWindow._make_fullscreen = lambda self: self.resize(1600, 1000)
ui_mod.LockWindow._start_listener = lambda self: None


class _StubMediaPlayer:
    class Loops:
        Infinite = -1

    def __init__(self, *a, **kw): pass
    def setSource(self, *a, **kw): pass
    def setVideoOutput(self, *a, **kw): pass
    def setAudioOutput(self, *a, **kw): pass
    def setVideoSink(self, *a, **kw): pass
    def setLoops(self, *a, **kw): pass
    def play(self, *a, **kw): pass
    def stop(self, *a, **kw): pass


class _StubAudioOutput:
    def __init__(self, *a, **kw): pass
    def setMuted(self, *a, **kw): pass
    def setVolume(self, *a, **kw): pass


class _StubVideoSink:
    class _Sig:
        def connect(self, *a, **kw): pass
    def __init__(self, *a, **kw):
        self.videoFrameChanged = self._Sig()


class _StubSoundEffect:
    def __init__(self, *a, **kw): pass
    def setSource(self, *a, **kw): pass
    def setVolume(self, *a, **kw): pass
    def play(self, *a, **kw): pass
    def stop(self, *a, **kw): pass


ui_mod.QMediaPlayer = _StubMediaPlayer
ui_mod.QAudioOutput = _StubAudioOutput
ui_mod.QVideoSink = _StubVideoSink
ui_mod.QSoundEffect = _StubSoundEffect


from sivaji_unlocker.ui import (  # noqa: E402
    LockWindow, TEXT_CYAN, TEXT_WHITE,
)
from sivaji_unlocker import config  # noqa: E402

OUT = REPO / "demo" / "frames"
OUT.mkdir(parents=True, exist_ok=True)
POSE_DIR = REPO / "assets" / "poses"


def extract_pose_frame(pose: str, t: float, w: int, h: int) -> Image.Image:
    """Extract a frame from the pose video for ``state`` at time ``t``.

    Renders cover-fit (fill+crop) to match the runtime VideoBackground.
    """
    src = POSE_DIR / f"pose_{pose}.mp4"
    if not src.exists():
        # Fallback if a pose is missing
        src = POSE_DIR / "pose_idle.mp4"

    out_path = REPO / "demo" / f"_bg_{pose}_{int(t*1000)}.png"
    cmd = [
        "ffmpeg", "-y", "-ss", str(t), "-i", str(src),
        # Cover-fit: scale to cover then center-crop
        "-vf",
        (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}"
        ),
        "-frames:v", "1", "-q:v", "2", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    img = Image.open(out_path).convert("RGBA")
    out_path.unlink()
    return img


def add_scrims(img: Image.Image, red_wash: float = 0.0) -> Image.Image:
    """Layer the same vignette + top/bottom scrims that VideoBackground draws,
    so the demo frame matches what the running app actually shows."""
    w, h = img.size
    if red_wash > 0:
        wash = Image.new("RGBA", (w, h), (180, 0, 0, int(120 * red_wash)))
        img = Image.alpha_composite(img, wash)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pixels = overlay.load()
    # Top scrim (band 0..140, fades top→0)
    band_h = 140
    for y in range(band_h):
        a = int(170 * (1 - y / band_h))
        for x in range(w):
            pixels[x, y] = (0, 0, 0, a)
    # Bottom scrim (last 340px, 0→200)
    band_h = 340
    for y in range(h - band_h, h):
        a = int(200 * (y - (h - band_h)) / band_h)
        for x in range(w):
            pixels[x, y] = (0, 0, 0, a)
    return Image.alpha_composite(img, overlay)


def render(scenes):
    app = QApplication.instance() or QApplication(sys.argv)
    W, H = 1600, 1000

    for name, pose, bg_t, setup in scenes:
        win = LockWindow()
        win.resize(W, H)
        win.show()
        app.processEvents()
        # Freeze animation timers
        for tname in ("_timer", "_clock_timer"):
            t = getattr(win, tname, None)
            if t is not None:
                t.stop()
        if hasattr(win, "status_bar_widget"):
            win.status_bar_widget._timer.stop()

        setup(win)
        for _ in range(8):
            app.processEvents()

        # Background pose frame + scrims (red wash for erasing)
        bg_img = extract_pose_frame(pose, bg_t, W, H)
        bg_img = add_scrims(bg_img, red_wash=0.7 if pose == "erasing" else 0.0)

        # HUD overlay
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
    if hasattr(w, "waveform") and w.waveform is not None:
        w.waveform.set_intensity(0.6)
        for v in [0.2, 0.5, 0.8, 0.6, 0.4, 0.7, 0.9, 0.5] * 30:
            w.waveform.push_sample(v)


def s_processing(w):
    w.status_bar_widget.set_text(config.PROCESSING_TEXT, TEXT_CYAN)
    if hasattr(w, "waveform") and w.waveform is not None:
        w.waveform.set_intensity(1.0)
        for v in [0.3, 0.9, 1.0, 0.8, 0.6, 0.95, 0.7, 0.85] * 30:
            w.waveform.push_sample(v)


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


# Each scene specifies which pose video to sample and at what timestamp,
# matching the runtime state→pose mapping.
SCENES = [
    ("01_idle",       "idle",       0.4, s_idle),
    ("02_listening",  "listening",  0.4, s_listening),
    ("03_processing", "processing", 0.4, s_processing),
    ("04_granted",    "granted",    0.4, s_granted),
    ("05_denied",     "denied",     0.4, s_denied),
    ("06_erasure",    "erasing",    0.4, s_erasure),
    ("07_locked",     "denied",     0.6, s_locked_out),
]

if __name__ == "__main__":
    render(SCENES)
    print(f"\nAll frames written to {OUT}")
