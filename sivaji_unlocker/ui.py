"""Sivaji-style fullscreen voice-recognition UI — recreated to match the
9:37–9:47 sequence from the 2007 film:

  • Dark crimson background with glowing red curved 'arena' tracks
  • Bright electric-blue baseline ribbon running across the mid-screen
  • White scrolling oscilloscope waveform when speaking
  • Centered red status bar with segmented dark blocks on each side,
    showing lowercase 'processing' → 'voice recognised' / 'voice not recognised'
  • Stylized 'buddy' mascot silhouette on the left, holding a red mic prop
  • No mouse cursor, no buttons — always-listening VAD
  • 3-fail data-erasure animation, then 60s lockout
"""
from __future__ import annotations

import logging
import math
import random
import sys
import time
from collections import deque

import numpy as np
from pathlib import Path

from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF, QUrl,
)
from PyQt6.QtGui import (
    QColor, QFont, QGuiApplication, QKeyEvent, QPainter, QPen, QBrush,
    QPainterPath, QRadialGradient, QLinearGradient,
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget,
    QHBoxLayout, QGraphicsDropShadowEffect, QProgressBar, QStackedLayout,
)

from . import audio, config

log = logging.getLogger(__name__)

# Film-accurate palette (sampled directly from the 9:37–9:47 frames)
BG_DEEP     = QColor("#1A0006")     # near-black crimson at the edges
BG_RED      = QColor("#3A0008")     # main scene background
RAIL_RED    = QColor("#CC1010")     # bright glowing rail/track lines
RAIL_BLUE   = QColor("#1A1AE0")     # electric-blue accent line
BAR_RED     = QColor("#C81A1A")     # status bar fill
BAR_DARK    = QColor("#6A0808")     # segmented "off" blocks on the bar
BAR_BORDER  = QColor("#FF4040")     # bar top highlight
TEXT_CYAN   = QColor("#5BB0C0")     # 'processing' text — muted teal
TEXT_WHITE  = QColor("#F0F0F0")     # 'voice recognised' text
WAVE_WHITE  = QColor("#E8E8E8")     # waveform line
WAVE_BLUE   = QColor("#3030D0")     # baseline behind waveform
GREEN_OK    = QColor("#3FE07A")     # subtle granted accent
BLACK       = QColor("#000000")


# ────────────────────────────────────────────────────────────── Worker thread

class ListenWorker(QThread):
    """Continuously listens to the mic and fires verification when speech
    is detected. Always-on, no button required — like the film."""
    speech_detected = pyqtSignal()                 # voice activity detected
    ambient_level   = pyqtSignal(float, bool)      # rms, is_voiced
    waveform        = pyqtSignal(object)           # captured np.ndarray
    finished_ok     = pyqtSignal(float)
    finished_fail   = pyqtSignal(float)
    error           = pyqtSignal(str)

    def __init__(self, voiceprint: np.ndarray):
        super().__init__()
        self.voiceprint = voiceprint
        self._stop = False
        self._paused = False

    def pause(self, paused: bool = True):
        self._paused = paused

    def stop(self):
        self._stop = True

    def run(self):
        try:
            while not self._stop:
                if self._paused:
                    self.msleep(100)
                    continue
                samples = audio.listen_until_speech(
                    on_level=lambda rms, v: self.ambient_level.emit(rms, v),
                    max_wait_s=10.0,
                )
                if samples is None:
                    continue
                if self._paused or self._stop:
                    continue
                self.speech_detected.emit()
                self.waveform.emit(samples)
                matched, sim = audio.verify(samples, self.voiceprint)
                (self.finished_ok if matched else self.finished_fail).emit(sim)
                self._paused = True
        except Exception as exc:  # noqa: BLE001
            log.exception("listen worker failed")
            self.error.emit(str(exc))


# ─────────────────────────────────────────────── Animated arena background

class ArenaBackground(QWidget):
    """The dark-crimson 'arena' with glowing red curved rails and a
    bright blue baseline — straight out of the 9:37 frame."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        self._phase += 0.012
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Vertical radial gradient: brighter red toward center, deeper at edges
        grad = QRadialGradient(w / 2, h * 0.55, max(w, h) * 0.7)
        grad.setColorAt(0.0, QColor("#5A0010"))
        grad.setColorAt(0.5, BG_RED)
        grad.setColorAt(1.0, BG_DEEP)
        p.fillRect(self.rect(), QBrush(grad))

        # Glowing red curved rails — 4 layered ellipses suggesting an arena
        # The animation is subtle: the rails pulse in brightness.
        pulse = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(self._phase * 2))
        cx, cy = w / 2, h * 0.62
        for i, scale in enumerate([1.4, 1.15, 0.95, 0.78]):
            rw = w * 0.85 * scale
            rh = h * 0.55 * scale
            alpha = int(220 * pulse * (1 - i * 0.18))
            # Outer glow
            for k in range(4):
                pen = QPen(QColor(RAIL_RED.red(), RAIL_RED.green(), RAIL_RED.blue(),
                                  max(0, alpha // (k + 2))), 8 - k * 1.5)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - rw / 2, cy - rh / 2, rw, rh))

        # Electric-blue baseline ribbon across the mid-screen
        blue_y = h * 0.55
        ribbon_grad = QLinearGradient(0, blue_y - 8, 0, blue_y + 8)
        ribbon_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        ribbon_grad.setColorAt(0.5, QColor(60, 80, 240, 220))
        ribbon_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(0, blue_y - 8, w, 16), QBrush(ribbon_grad))
        # Bright blue line on top of ribbon
        p.setPen(QPen(QColor(120, 160, 255, 240), 2))
        p.drawLine(0, int(blue_y), w, int(blue_y))

        # Dark vignette
        vg = QRadialGradient(w / 2, h / 2, max(w, h) * 0.7)
        vg.setColorAt(0.55, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 200))
        p.fillRect(self.rect(), QBrush(vg))


# ─────────────────────────────────────────────────── Buddy mascot character

class BuddyMascot(QWidget):
    """Stylized silhouette of the 'buddy' character holding a red microphone.
    Drawn purely with paths — no external assets needed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase = 0.0
        self._mode = "idle"   # idle | listening | ok | fail
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def _tick(self):
        self._phase += 0.06
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        bob = math.sin(self._phase * 1.4) * 4

        body_color = QColor("#E0856B")     # warm peach skin tone
        body_dark = QColor("#8C3F2F")
        eye_color = QColor("#1A1A1A")
        ear_color = QColor("#C66A52")

        # Body / chest (rounded oval)
        body_rect = QRectF(cx - w * 0.32, cy + bob - h * 0.05,
                           w * 0.64, h * 0.55)
        body_grad = QLinearGradient(0, body_rect.top(), 0, body_rect.bottom())
        body_grad.setColorAt(0.0, QColor("#22A0A0"))   # teal shirt
        body_grad.setColorAt(1.0, QColor("#0A6060"))
        p.setBrush(QBrush(body_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(body_rect)

        # Head — large, pear-shaped
        head_rect = QRectF(cx - w * 0.28, cy + bob - h * 0.45,
                           w * 0.56, h * 0.55)
        head_grad = QRadialGradient(cx - w * 0.05, cy + bob - h * 0.25, w * 0.3)
        head_grad.setColorAt(0.0, body_color)
        head_grad.setColorAt(1.0, body_dark)
        p.setBrush(QBrush(head_grad))
        p.drawEllipse(head_rect)

        # Snout (smaller oval lower on the face, pointing slightly left)
        snout_rect = QRectF(cx - w * 0.33, cy + bob - h * 0.18,
                            w * 0.32, h * 0.20)
        p.setBrush(QBrush(body_color.lighter(110)))
        p.drawEllipse(snout_rect)

        # Ears (two pointy)
        ear_path = QPainterPath()
        ear_path.moveTo(cx - w * 0.18, cy + bob - h * 0.40)
        ear_path.lineTo(cx - w * 0.05, cy + bob - h * 0.62)
        ear_path.lineTo(cx + w * 0.06, cy + bob - h * 0.42)
        ear_path.closeSubpath()
        p.setBrush(QBrush(ear_color))
        p.drawPath(ear_path)
        ear_path2 = QPainterPath()
        ear_path2.moveTo(cx + w * 0.16, cy + bob - h * 0.36)
        ear_path2.lineTo(cx + w * 0.24, cy + bob - h * 0.58)
        ear_path2.lineTo(cx + w * 0.28, cy + bob - h * 0.34)
        ear_path2.closeSubpath()
        p.drawPath(ear_path2)

        # Eyes — large circular with reflective highlight
        for ex in (-w * 0.10, w * 0.10):
            ey = cy + bob - h * 0.27
            er = w * 0.07
            # white eye
            p.setBrush(QBrush(QColor(240, 240, 240)))
            p.drawEllipse(QPointF(cx + ex, ey), er, er)
            # iris/pupil
            p.setBrush(QBrush(eye_color))
            p.drawEllipse(QPointF(cx + ex + er * 0.2, ey + er * 0.1),
                          er * 0.55, er * 0.55)
            # highlight
            p.setBrush(QBrush(QColor(255, 255, 255, 220)))
            p.drawEllipse(QPointF(cx + ex - er * 0.1, ey - er * 0.25),
                          er * 0.18, er * 0.18)

        # Smile (slight curve)
        smile_pen = QPen(QColor(60, 20, 10), 4)
        smile_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(smile_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        smile_rect = QRectF(cx - w * 0.13, cy + bob - h * 0.10,
                            w * 0.16, h * 0.08)
        p.drawArc(smile_rect, 200 * 16, 140 * 16)

        # Red microphone prop — held to the right, near mouth
        mic_x, mic_y = cx + w * 0.20, cy + bob - h * 0.10
        # Mic ball
        ball_grad = QRadialGradient(mic_x - w * 0.02, mic_y - h * 0.02, w * 0.10)
        ball_grad.setColorAt(0.0, QColor("#FF6060"))
        ball_grad.setColorAt(1.0, QColor("#A00808"))
        p.setBrush(QBrush(ball_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(mic_x, mic_y), w * 0.10, h * 0.08)
        # Mic grille lines
        grille_pen = QPen(QColor(60, 0, 0, 180), 1.2)
        p.setPen(grille_pen)
        for i in range(-3, 4):
            p.drawLine(QPointF(mic_x - w * 0.08, mic_y + i * h * 0.014),
                       QPointF(mic_x + w * 0.08, mic_y + i * h * 0.014))
        # Mic handle (going down-right)
        p.setBrush(QBrush(QColor("#3A1010")))
        p.setPen(Qt.PenStyle.NoPen)
        handle_path = QPainterPath()
        handle_path.moveTo(mic_x + w * 0.04, mic_y + h * 0.06)
        handle_path.lineTo(mic_x + w * 0.20, mic_y + h * 0.30)
        handle_path.lineTo(mic_x + w * 0.14, mic_y + h * 0.34)
        handle_path.lineTo(mic_x - w * 0.02, mic_y + h * 0.10)
        handle_path.closeSubpath()
        p.drawPath(handle_path)

        # Mode-based aura around the mic
        if self._mode == "listening":
            aura = QColor(255, 80, 80, 180)
        elif self._mode == "ok":
            aura = QColor(80, 255, 120, 180)
        elif self._mode == "fail":
            aura = QColor(255, 40, 40, 220)
        else:
            aura = QColor(255, 80, 80, 80)
        for r_idx, scale in enumerate([1.4, 1.7, 2.0]):
            a = int(aura.alpha() * (1 - r_idx * 0.3))
            p.setPen(QPen(QColor(aura.red(), aura.green(), aura.blue(), a), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(mic_x, mic_y),
                          w * 0.11 * scale, h * 0.09 * scale)


# ───────────────────────────────────────────── Animated waveform display

class WaveformDisplay(QWidget):
    """White scrolling oscilloscope waveform on a transparent background.
    Draws a horizontal blue baseline behind a white jagged wave."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._phase = 0.0
        self._intensity = 0.0   # 0 = idle, 1 = full speech
        self._target_intensity = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self._buffer = deque([0.0] * 220, maxlen=220)

    def set_intensity(self, value: float):
        self._target_intensity = max(0.0, min(1.0, value))

    def push_sample(self, rms: float):
        """Push a live RMS value to scroll across the waveform."""
        self._buffer.append(min(1.0, rms * 6.0))

    def _tick(self):
        self._phase += 0.18
        # Smooth toward target
        self._intensity += (self._target_intensity - self._intensity) * 0.12
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2

        # Blue baseline (always visible)
        p.setPen(QPen(QColor(80, 100, 240, 200), 3))
        p.drawLine(0, int(cy), w, int(cy))
        # Faint blue glow above/below
        glow = QLinearGradient(0, cy - 6, 0, cy + 6)
        glow.setColorAt(0.0, QColor(60, 80, 220, 0))
        glow.setColorAt(0.5, QColor(60, 80, 220, 90))
        glow.setColorAt(1.0, QColor(60, 80, 220, 0))
        p.fillRect(QRectF(0, cy - 6, w, 12), QBrush(glow))

        # White jagged waveform — overlay
        n = len(self._buffer)
        amp = h * 0.42
        # Use buffer values plus some sine variation for a lively look
        path = QPainterPath()
        path.moveTo(0, cy)
        for i, v in enumerate(self._buffer):
            x = i * w / max(n - 1, 1)
            # Combine live buffer + a faster oscillation
            wobble = math.sin(self._phase * 3 + i * 0.7) * 0.25
            base = v if self._intensity > 0.05 else 0.04
            y = cy - (base * (1 + wobble) * amp * (0.5 + 0.5 * self._intensity))
            # Alternate sign for jagged scope feel
            if i % 2 == 0:
                y = 2 * cy - y
            path.lineTo(x, y)

        # Subtle shadow first
        p.setPen(QPen(QColor(255, 255, 255, 60), 4))
        p.drawPath(path)
        # Bright white stroke
        p.setPen(QPen(WAVE_WHITE, 2))
        p.drawPath(path)


# ──────────────────────────────────────────────── Status bar (the red bar)

class StatusBar(QWidget):
    """The signature red status bar with segmented dark blocks on each side
    and centered text. Exactly like the film's bottom bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = config.IDLE_TEXT
        self._text_color = TEXT_CYAN
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)
        self.setMinimumHeight(80)

    def set_text(self, text: str, color: QColor):
        self._text = text
        self._text_color = color
        self.update()

    def _tick(self):
        self._phase += 1
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Outer bar with slight 3D bevel
        bar_rect = QRectF(8, 8, w - 16, h - 16)
        bar_grad = QLinearGradient(0, bar_rect.top(), 0, bar_rect.bottom())
        bar_grad.setColorAt(0.0, BAR_BORDER)
        bar_grad.setColorAt(0.15, BAR_RED)
        bar_grad.setColorAt(1.0, QColor("#7A0808"))
        p.setBrush(QBrush(bar_grad))
        p.setPen(QPen(QColor("#FF5050"), 1.5))
        p.drawRoundedRect(bar_rect, 4, 4)

        # Vertical leading pipe on far left
        p.setPen(QPen(QColor(255, 200, 200, 220), 2))
        p.drawLine(QPointF(bar_rect.left() + 8, bar_rect.top() + 6),
                   QPointF(bar_rect.left() + 8, bar_rect.bottom() - 6))

        # Segmented dark blocks on left and right of the text
        block_count = 10
        block_h = bar_rect.height() - 18
        block_w = (bar_rect.width() / 3.5 - 12) / block_count - 3
        block_w = max(block_w, 10)
        # Animation: a "loader" effect where one block is brighter
        active_idx = int(self._phase / 2) % block_count

        # Left segments
        left_x0 = bar_rect.left() + 22
        for i in range(block_count):
            x = left_x0 + i * (block_w + 3)
            y = bar_rect.top() + 9
            is_active = i == active_idx
            color = QColor("#FF8080") if is_active else BAR_DARK
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(x, y, block_w, block_h))

        # Right segments (mirror)
        right_x0 = bar_rect.right() - 22 - block_count * (block_w + 3) + 3
        for i in range(block_count):
            x = right_x0 + i * (block_w + 3)
            y = bar_rect.top() + 9
            is_active = (block_count - 1 - i) == active_idx
            color = QColor("#FF8080") if is_active else BAR_DARK
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(x, y, block_w, block_h))

        # Center text
        font = QFont("Verdana", int(h * 0.34))
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 105)
        p.setFont(font)
        p.setPen(QPen(self._text_color))
        p.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, self._text)


# ───────────────────────────────────────────────────────── Main lock window

class LockWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.voiceprint = audio.load_voiceprint()
        if self.voiceprint is None:
            raise RuntimeError(
                "No voiceprint enrolled. Run: rajini-enroll first."
            )

        self.fail_count = 0
        self.locked_until = 0.0
        self.worker: ListenWorker | None = None

        self._build_ui()
        self._make_fullscreen()
        self._hide_cursor()
        self._start_listener()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(500)

    # ─────────────────────────────────────────────────────────────────── UI

    def _build_ui(self):
        self.setStyleSheet(f"background: {BG_DEEP.name()};")
        central = QWidget()
        central.setStyleSheet(f"background: {BG_DEEP.name()};")
        self.setCentralWidget(central)

        # ── Layer 1: video background (fills the whole window)
        self.video_widget = QVideoWidget(central)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.media_player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.audio_out.setMuted(True)  # video is silent — we don't want audio
        self.media_player.setAudioOutput(self.audio_out)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.setLoops(QMediaPlayer.Loops.Infinite)

        # Look for the bundled video in two places:
        #   1. Inside the package (sivaji_unlocker/assets/) — always works when pip-installed
        #   2. Repo-relative ../assets/ — works when running from source
        pkg_dir = Path(__file__).resolve().parent
        candidates = [
            pkg_dir / "assets" / "lock_background.mp4",
            pkg_dir.parent / "assets" / "lock_background.mp4",
        ]
        bg_path = next((p for p in candidates if p.exists()), candidates[0])
        if not bg_path.exists():
            # Fallback to old hand-drawn arena if the asset is missing
            log.warning("lock_background.mp4 not found at %s — using arena fallback", bg_path)
            self.video_widget.hide()
            self.bg = ArenaBackground(central)
        else:
            self.media_player.setSource(QUrl.fromLocalFile(str(bg_path)))
            self.media_player.play()
            self.bg = None

        # ── Layer 2: foreground UI overlay (transparent panel)
        self.overlay = QWidget(central)
        self.overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.overlay.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self.overlay)
        # Top/sides padded; bottom flush so our status bar lines up with the
        # film's bar position and fully covers it.
        outer.setContentsMargins(60, 40, 60, 0)
        outer.setSpacing(0)

        # Top corner labels: BOSS brand + clock
        top_row = QHBoxLayout()
        self.brand = QLabel(config.BRAND_TEXT)
        brand_font = QFont("Helvetica", 28, QFont.Weight.Black)
        self.brand.setFont(brand_font)
        self.brand.setStyleSheet(
            "color: rgba(255, 240, 240, 230); letter-spacing: 8px;"
            "background: transparent;"
        )
        glow = QGraphicsDropShadowEffect()
        glow.setColor(QColor(0, 0, 0, 220))
        glow.setBlurRadius(20); glow.setOffset(2, 2)
        self.brand.setGraphicsEffect(glow)

        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet(
            "color: rgba(255,230,230,230); font-family: 'Verdana','sans-serif';"
            "font-size: 14px; letter-spacing: 2px; background: transparent;"
        )
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight |
                                      Qt.AlignmentFlag.AlignVCenter)
        clock_glow = QGraphicsDropShadowEffect()
        clock_glow.setColor(QColor(0, 0, 0, 220))
        clock_glow.setBlurRadius(8); clock_glow.setOffset(1, 1)
        self.clock_label.setGraphicsEffect(clock_glow)

        top_row.addWidget(self.brand)
        top_row.addStretch()
        top_row.addWidget(self.clock_label)
        outer.addLayout(top_row)

        # Spacer — let the video show through the middle
        outer.addStretch(1)

        # Passphrase hint (small line above status bar) — drawn on a translucent strip
        self.hint = QLabel(f"\u201c{config.PASSPHRASE_HINT}\u201d")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(
            "color: rgba(255, 240, 220, 240); font-family: 'Verdana','sans-serif';"
            "font-size: 20px; font-style: italic; letter-spacing: 3px;"
            "background: rgba(0, 0, 0, 130); padding: 8px 24px;"
        )
        hint_glow = QGraphicsDropShadowEffect()
        hint_glow.setColor(QColor(0, 0, 0, 240))
        hint_glow.setBlurRadius(16); hint_glow.setOffset(2, 2)
        self.hint.setGraphicsEffect(hint_glow)
        outer.addWidget(self.hint)
        outer.addSpacing(12)

        # Status bar (the iconic red bar) — sits at the very bottom and fully
        # covers whatever bar is in the source video. Sized large to ensure
        # full coverage even if the screen is tall.
        self.status_bar_widget = StatusBar()
        self.status_bar_widget.setFixedHeight(110)
        outer.addWidget(self.status_bar_widget)

        # Erasure progress bar (hidden until needed)
        self.erase_bar = QProgressBar()
        self.erase_bar.setRange(0, 100)
        self.erase_bar.setValue(0)
        self.erase_bar.setTextVisible(True)
        self.erase_bar.setFormat("erasing data %p%")
        self.erase_bar.setStyleSheet(f"""
            QProgressBar {{
                background: #1A0006;
                border: 2px solid {RAIL_RED.name()};
                color: #FFFFFF;
                font-family: 'Verdana','sans-serif';
                font-size: 14px; font-weight: bold;
                text-align: center; height: 24px;
                letter-spacing: 4px;
            }}
            QProgressBar::chunk {{ background: {RAIL_RED.name()}; }}
        """)
        self.erase_bar.hide()
        outer.addWidget(self.erase_bar)

        # No mascot or waveform widgets — the video is doing both visually.
        self.mascot = None
        self.waveform = None

    def _make_fullscreen(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        screen = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.showFullScreen()

    def _hide_cursor(self):
        QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

    def _start_listener(self):
        self.worker = ListenWorker(self.voiceprint)
        self.worker.ambient_level.connect(self._on_ambient)
        self.worker.speech_detected.connect(self._on_speech_detected)
        self.worker.waveform.connect(self._on_waveform_arrived)
        self.worker.finished_ok.connect(self._on_success)
        self.worker.finished_fail.connect(self._on_fail)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "video_widget") and self.video_widget is not None:
            self.video_widget.setGeometry(self.rect())
            self.video_widget.lower()
        if hasattr(self, "bg") and self.bg is not None:
            self.bg.setGeometry(self.rect())
            self.bg.lower()
        if hasattr(self, "overlay"):
            self.overlay.setGeometry(self.rect())
            self.overlay.raise_()

    # ──────────────────────────────────────────────────────────── Behavior

    def _tick_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%a %d %b  %H:%M:%S"))

    # ── Safe helpers: mascot/waveform may be None when video bg is active
    def _set_mascot(self, mode: str):
        if self.mascot is not None:
            self.mascot.set_mode(mode)

    def _wf_push(self, rms: float):
        if self.waveform is not None:
            self.waveform.push_sample(rms)

    def _wf_intensity(self, value: float):
        if self.waveform is not None:
            self.waveform.set_intensity(value)

    def _on_ambient(self, rms: float, voiced: bool):
        if time.time() < self.locked_until:
            return
        self._wf_push(rms)
        if voiced and self.status_bar_widget._text == config.IDLE_TEXT:
            self.status_bar_widget.set_text(config.LISTENING_TEXT, TEXT_CYAN)
            self._wf_intensity(0.6)

    def _on_speech_detected(self):
        if time.time() < self.locked_until:
            return
        self._set_mascot("listening")
        self.status_bar_widget.set_text(config.PROCESSING_TEXT, TEXT_CYAN)
        self._wf_intensity(1.0)

    def _on_waveform_arrived(self, samples):
        if self.waveform is None or samples is None or len(samples) == 0:
            return
        n = 220
        idx = np.linspace(0, len(samples) - 1, n).astype(int)
        sub = np.abs(samples[idx])
        for v in sub:
            self.waveform.push_sample(float(v))

    def _on_success(self, sim: float):
        self._set_mascot("ok")
        self.status_bar_widget.set_text(config.SUCCESS_TEXT, TEXT_WHITE)
        self._wf_intensity(0.4)
        log.info("Unlocked. similarity=%.3f", sim)
        if self.worker:
            self.worker.stop()
        QTimer.singleShot(1800, QApplication.quit)

    def _on_fail(self, sim: float):
        self._set_mascot("fail")
        self.fail_count += 1
        line = random.choice(config.MOCK_LINES)
        self.status_bar_widget.set_text(line, QColor("#FFE0E0"))

        if self.fail_count >= config.MAX_ATTEMPTS:
            self._trigger_erasure()
            return

        def _rearm():
            self._set_mascot("idle")
            self.status_bar_widget.set_text(config.IDLE_TEXT, TEXT_CYAN)
            self._wf_intensity(0.0)
            if self.worker:
                self.worker.pause(False)
        QTimer.singleShot(2200, _rearm)

    def _trigger_erasure(self):
        self.status_bar_widget.set_text(config.ERASURE_TEXT, QColor("#FFE0E0"))
        self.erase_bar.setValue(0)
        self.erase_bar.show()
        self._erase_pct = 0
        self._erase_timer = QTimer(self)
        self._erase_timer.timeout.connect(self._erase_step)
        self._erase_timer.start(60)

    def _erase_step(self):
        self._erase_pct += 2
        self.erase_bar.setValue(self._erase_pct)
        if self._erase_pct >= 100:
            self._erase_timer.stop()
            self.status_bar_widget.set_text(config.LOCKOUT_LINE,
                                            QColor("#FFE0E0"))
            self.locked_until = time.time() + config.LOCKOUT_SECONDS
            QTimer.singleShot(config.LOCKOUT_SECONDS * 1000,
                              self._reset_after_lockout)

    def _reset_after_lockout(self):
        self.fail_count = 0
        self.erase_bar.hide()
        self._set_mascot("idle")
        self.status_bar_widget.set_text(config.IDLE_TEXT, TEXT_CYAN)
        if self.worker:
            self.worker.pause(False)

    def _on_error(self, msg: str):
        self._set_mascot("fail")
        self.status_bar_widget.set_text(f"error: {msg.lower()}",
                                        QColor("#FFE0E0"))

    # ────────────────────────────────────────────────── Hard-block escapes

    def keyPressEvent(self, event: QKeyEvent):
        # Voice-only — keyboard does nothing.
        pass

    def closeEvent(self, event):
        if not getattr(self, "_allow_close", False):
            event.ignore()
        else:
            event.accept()


# ──────────────────────────────────────────────────────────── Entry-points

def run_lock_app():
    if config.KILL_SWITCH.exists():
        log.warning("Kill-switch found at %s — exiting.", config.KILL_SWITCH)
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(config.LOG_FILE),
                  logging.StreamHandler(sys.stderr)],
    )

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)

    try:
        win = LockWindow()
    except RuntimeError as exc:
        log.error("Cannot launch lock UI: %s", exc)
        print(f"\n[!] {exc}\n", file=sys.stderr)
        return 2

    win._allow_close = False

    def _on_quit():
        setattr(win, "_allow_close", True)
        QApplication.restoreOverrideCursor()
        if win.worker:
            win.worker.stop()

    app.aboutToQuit.connect(_on_quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_lock_app())
