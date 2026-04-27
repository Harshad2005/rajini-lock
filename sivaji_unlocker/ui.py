"""Sivaji-style fullscreen voice-recognition UI — recreated to match the
2007 film's laptop scene shot-by-shot:

  • Pure-black background with electric-blue/cyan accent
  • Big bold "BOSS" branding + "VOICE RECOGNITION SYSTEM" title
  • Radar-pulse microphone animation (concentric expanding rings)
  • Live oscilloscope waveform during recording
  • Corner-bracket targeting-reticle frame
  • Subtle CRT scanline overlay
  • ACCESS GRANTED (green flash) / ACCESS DENIED (red flash) sequences
  • DATA ERASURE animation with progress bar after 3 failed attempts
"""
from __future__ import annotations

import logging
import math
import sys
import time
from dataclasses import dataclass

import numpy as np
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRectF, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QPointF,
)
from PyQt6.QtGui import (
    QColor, QFont, QGuiApplication, QKeyEvent, QPainter, QPen, QBrush,
    QPainterPath, QRadialGradient, QLinearGradient, QFontMetrics,
)
from PyQt6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget,
    QHBoxLayout, QGraphicsDropShadowEffect, QProgressBar,
)

from . import audio, config

log = logging.getLogger(__name__)

# Film-accurate palette
BG          = QColor("#000000")
PANEL       = QColor("#050810")
CYAN        = QColor("#00E5FF")     # primary electric blue
CYAN_DIM    = QColor("#0090A8")
AMBER       = QColor("#FFC000")     # secondary label color
GREEN       = QColor("#00FF66")     # access granted
RED         = QColor("#FF2030")     # access denied
WHITE       = QColor("#FFFFFF")


# ────────────────────────────────────────────────────────────── Worker thread

class VerifyWorker(QThread):
    """Records audio + runs speaker verification off the UI thread."""
    finished_ok   = pyqtSignal(float)
    finished_fail = pyqtSignal(float)
    error         = pyqtSignal(str)
    waveform      = pyqtSignal(object)  # np.ndarray of recorded samples

    def __init__(self, voiceprint: np.ndarray):
        super().__init__()
        self.voiceprint = voiceprint

    def run(self):
        try:
            samples = audio.record_audio()
            self.waveform.emit(samples)
            matched, sim = audio.verify(samples, self.voiceprint)
            (self.finished_ok if matched else self.finished_fail).emit(sim)
        except Exception as exc:  # noqa: BLE001
            log.exception("verify worker failed")
            self.error.emit(str(exc))


# ────────────────────────────────────────────────────── Radar-pulse mic widget

class RadarMicWidget(QWidget):
    """Microphone icon with concentric radar pulses — the iconic
    'voice listening' animation from the film."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self._phase = 0.0
        self._mode = "idle"          # idle | listening | processing | ok | fail
        self._wave: np.ndarray | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30fps

    def set_mode(self, mode: str):
        self._mode = mode
        self.update()

    def set_waveform(self, samples: np.ndarray):
        self._wave = samples
        self.update()

    def _tick(self):
        self._phase += 0.04
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 10

        accent = {
            "idle": CYAN_DIM,
            "listening": CYAN,
            "processing": CYAN,
            "ok": GREEN,
            "fail": RED,
        }[self._mode]

        # ─── concentric radar pulses
        rings = 4
        for i in range(rings):
            t = (self._phase + i / rings) % 1.0
            r = radius * t
            alpha = int(220 * (1 - t))
            pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), alpha), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # ─── inner solid disc
        grad = QRadialGradient(cx, cy, radius * 0.45)
        grad.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 80))
        grad.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), radius * 0.45, radius * 0.45)

        # ─── microphone glyph in the center (drawn with paths, no font deps)
        mic_w = radius * 0.20
        mic_h = radius * 0.32
        pen = QPen(accent, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 60)))
        # capsule body
        body_rect = QRectF(cx - mic_w / 2, cy - mic_h / 2 - mic_h * 0.1,
                           mic_w, mic_h)
        p.drawRoundedRect(body_rect, mic_w / 2, mic_w / 2)
        # arc cradle
        cradle_r = mic_w * 1.1
        cradle_rect = QRectF(cx - cradle_r, cy - cradle_r * 0.4,
                             cradle_r * 2, cradle_r * 1.6)
        p.drawArc(cradle_rect, 200 * 16, 140 * 16)
        # stand
        p.drawLine(QPointF(cx, cy + cradle_r * 0.85),
                   QPointF(cx, cy + cradle_r * 1.25))
        p.drawLine(QPointF(cx - mic_w * 0.6, cy + cradle_r * 1.25),
                   QPointF(cx + mic_w * 0.6, cy + cradle_r * 1.25))

        # ─── live oscilloscope band beneath the mic when listening
        if self._mode == "listening" and self._wave is not None:
            band_top = cy + radius * 0.55
            band_h = 30
            samples = self._wave
            n = 120
            if len(samples) > n:
                idx = np.linspace(0, len(samples) - 1, n).astype(int)
                samples = samples[idx]
            pen = QPen(accent, 2)
            p.setPen(pen)
            path = QPainterPath()
            for i, v in enumerate(samples):
                x = cx - radius * 0.6 + i * (radius * 1.2 / n)
                y = band_top + v * band_h
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            p.drawPath(path)


# ──────────────────────────────────────────────── Corner-bracket frame overlay

class FrameOverlay(QWidget):
    """Targeting-reticle corner brackets + faint scanlines, drawn over
    everything else."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._scan_phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._scan_phase = (self._scan_phase + 1) % 200
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin = 40
        bracket = 60

        # corner brackets
        pen = QPen(CYAN, 3)
        p.setPen(pen)
        # top-left
        p.drawLine(margin, margin, margin + bracket, margin)
        p.drawLine(margin, margin, margin, margin + bracket)
        # top-right
        p.drawLine(w - margin, margin, w - margin - bracket, margin)
        p.drawLine(w - margin, margin, w - margin, margin + bracket)
        # bottom-left
        p.drawLine(margin, h - margin, margin + bracket, h - margin)
        p.drawLine(margin, h - margin, margin, h - margin - bracket)
        # bottom-right
        p.drawLine(w - margin, h - margin, w - margin - bracket, h - margin)
        p.drawLine(w - margin, h - margin, w - margin, h - margin - bracket)

        # scanlines — every 3 px, very low alpha
        scan_pen = QPen(QColor(0, 229, 255, 12), 1)
        p.setPen(scan_pen)
        for y in range(0, h, 3):
            p.drawLine(0, y, w, y)

        # moving bright scan band
        band_pen = QPen(QColor(0, 229, 255, 40), 2)
        p.setPen(band_pen)
        sy = self._scan_phase * h // 200
        p.drawLine(0, sy, w, sy)


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
        self.worker: VerifyWorker | None = None

        self._build_ui()
        self._make_fullscreen()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(500)

    # ─────────────────────────────────────────────────────────────────── UI

    def _build_ui(self):
        self.setStyleSheet(f"background: {BG.name()};")
        central = QWidget()
        central.setStyleSheet(f"background: {BG.name()};")
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(120, 80, 120, 80)
        outer.setSpacing(14)

        # ── Top status bar
        top = QHBoxLayout()
        self.sys_label = QLabel("◈ BOSS BIOSEC v3.14 ◈ THINKPAD X41 ◈ INDIA")
        self.sys_label.setStyleSheet(self._mono(CYAN_DIM, 14, 4))
        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet(self._mono(CYAN_DIM, 14, 2))
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(self.sys_label)
        top.addStretch()
        top.addWidget(self.clock_label)
        outer.addLayout(top)

        outer.addStretch(1)

        # ── BOSS brand
        self.brand = QLabel(config.BRAND_TEXT)
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_font = QFont("Helvetica", 180, QFont.Weight.Black)
        self.brand.setFont(brand_font)
        self.brand.setStyleSheet(
            f"color: {CYAN.name()}; letter-spacing: 40px;"
        )
        glow = QGraphicsDropShadowEffect()
        glow.setColor(CYAN); glow.setBlurRadius(80); glow.setOffset(0, 0)
        self.brand.setGraphicsEffect(glow)
        outer.addWidget(self.brand)

        # ── Title + subtitle
        self.title = QLabel(config.TITLE_TEXT)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(self._mono(WHITE, 22, 10, bold=True))
        outer.addWidget(self.title)

        self.subtitle = QLabel(config.SUBTITLE_TEXT)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setStyleSheet(self._mono(AMBER, 13, 6))
        outer.addWidget(self.subtitle)

        outer.addSpacing(20)

        # ── Radar mic
        mic_row = QHBoxLayout()
        mic_row.addStretch()
        self.mic = RadarMicWidget()
        mic_row.addWidget(self.mic)
        mic_row.addStretch()
        outer.addLayout(mic_row)

        # ── Status line (PROMPT / LISTENING / PROCESSING / GRANTED / DENIED)
        self.status = QLabel(config.PROMPT_TEXT)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(self._mono(CYAN, 24, 8, bold=True))
        outer.addWidget(self.status)

        # ── Erasure progress bar (hidden until needed)
        self.erase_bar = QProgressBar()
        self.erase_bar.setRange(0, 100)
        self.erase_bar.setValue(0)
        self.erase_bar.setTextVisible(True)
        self.erase_bar.setFormat("%p%  —  ERASING")
        self.erase_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {PANEL.name()};
                border: 2px solid {RED.name()};
                color: {WHITE.name()};
                font-family: 'Menlo','Courier New',monospace;
                font-size: 14px; font-weight: bold;
                text-align: center; height: 28px;
                letter-spacing: 4px;
            }}
            QProgressBar::chunk {{ background: {RED.name()}; }}
        """)
        self.erase_bar.hide()
        outer.addWidget(self.erase_bar)

        # ── Speak button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.speak_btn = QPushButton("◉  PRESS TO SPEAK  ◉")
        self.speak_btn.setFixedSize(440, 70)
        self.speak_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speak_btn.setStyleSheet(f"""
            QPushButton {{
                background: {PANEL.name()};
                color: {CYAN.name()};
                border: 2px solid {CYAN.name()};
                font-family: 'Menlo','Courier New',monospace;
                font-size: 20px; font-weight: bold;
                letter-spacing: 6px;
            }}
            QPushButton:hover {{
                background: {CYAN.name()}; color: {BG.name()};
            }}
            QPushButton:disabled {{
                color: {CYAN_DIM.name()}; border-color: {CYAN_DIM.name()};
            }}
        """)
        self.speak_btn.clicked.connect(self._start_unlock)
        btn_row.addWidget(self.speak_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        outer.addStretch(2)

        # ── Footer status readout
        self.footer = QLabel(self._footer_text("READY"))
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet(self._mono(CYAN_DIM, 13, 4))
        outer.addWidget(self.footer)

        # ── Frame overlay (corner brackets + scanlines)
        self.overlay = FrameOverlay(self)
        self.overlay.lower()
        self.overlay.raise_()

    def _mono(self, color: QColor, size: int, spacing: int, bold: bool = False):
        weight = "bold" if bold else "normal"
        return (f"color: {color.name()}; font-family: 'Menlo','Courier New',monospace;"
                f"font-size: {size}px; letter-spacing: {spacing}px; font-weight: {weight};")

    def _make_fullscreen(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        screen = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "overlay"):
            self.overlay.setGeometry(self.rect())

    # ──────────────────────────────────────────────────────────── Behavior

    def _footer_text(self, status: str) -> str:
        return (f"AUTH: VOICEPRINT-256  ◆  ATTEMPTS: {self.fail_count}/{config.MAX_ATTEMPTS}"
                f"  ◆  STATUS: {status}")

    def _tick_clock(self):
        from datetime import datetime
        self.clock_label.setText(datetime.now().strftime("%a %d %b %Y  %H:%M:%S"))

    def _set_status(self, text: str, color: QColor):
        self.status.setText(text)
        self.status.setStyleSheet(self._mono(color, 24, 8, bold=True))

    def _set_footer(self, status: str):
        self.footer.setText(self._footer_text(status))

    def _start_unlock(self):
        if time.time() < self.locked_until:
            remaining = int(self.locked_until - time.time())
            self._set_status(f"LOCKED OUT — WAIT {remaining}s", RED)
            return

        self.speak_btn.setEnabled(False)
        self.mic.set_mode("listening")
        self._set_status(config.LISTENING_TEXT, CYAN)
        self._set_footer("RECORDING")

        self.worker = VerifyWorker(self.voiceprint)
        self.worker.waveform.connect(self.mic.set_waveform)
        self.worker.waveform.connect(lambda _s: (
            self.mic.set_mode("processing"),
            self._set_status(config.PROCESSING_TEXT, CYAN),
            self._set_footer("ANALYZING"),
        ))
        self.worker.finished_ok.connect(self._on_success)
        self.worker.finished_fail.connect(self._on_fail)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_success(self, sim: float):
        self.mic.set_mode("ok")
        self._set_status(f"{config.SUCCESS_TEXT} — MATCH {sim*100:.1f}%", GREEN)
        self._set_footer("UNLOCKED")
        log.info("Unlocked. similarity=%.3f", sim)
        QTimer.singleShot(1800, QApplication.quit)

    def _on_fail(self, sim: float):
        import random
        self.mic.set_mode("fail")
        self.fail_count += 1

        line = random.choice(config.MOCK_LINES)
        self._set_status(f"{config.DENIED_TEXT} — {line} ({sim*100:.1f}%)", RED)
        self._set_footer("FAILED")

        if self.fail_count >= config.MAX_ATTEMPTS:
            self._trigger_erasure()
            return

        # Re-arm after a beat
        QTimer.singleShot(1500, lambda: (
            self.mic.set_mode("idle"),
            self._set_status(config.PROMPT_TEXT, CYAN),
            self._set_footer("READY"),
            self.speak_btn.setEnabled(True),
        ))

    def _trigger_erasure(self):
        """The film's iconic 3-strike data wipe (visual only — no real
        deletion happens). After the animation, we lock out for 60s."""
        self._set_status(config.ERASURE_TEXT, RED)
        self._set_footer("DATA ERASURE")
        self.erase_bar.setValue(0)
        self.erase_bar.show()
        self.speak_btn.setEnabled(False)

        self._erase_pct = 0
        self._erase_timer = QTimer(self)
        self._erase_timer.timeout.connect(self._erase_step)
        self._erase_timer.start(60)

    def _erase_step(self):
        self._erase_pct += 2
        self.erase_bar.setValue(self._erase_pct)
        if self._erase_pct >= 100:
            self._erase_timer.stop()
            self._set_status(config.LOCKOUT_LINE, RED)
            self.locked_until = time.time() + config.LOCKOUT_SECONDS
            QTimer.singleShot(config.LOCKOUT_SECONDS * 1000, self._reset_after_lockout)

    def _reset_after_lockout(self):
        self.fail_count = 0
        self.erase_bar.hide()
        self.mic.set_mode("idle")
        self._set_status(config.PROMPT_TEXT, CYAN)
        self._set_footer("READY")
        self.speak_btn.setEnabled(True)

    def _on_error(self, msg: str):
        self.mic.set_mode("fail")
        self._set_status(f"ERROR: {msg.upper()}", RED)
        self.speak_btn.setEnabled(True)

    # ────────────────────────────────────────────────── Hard-block escapes

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._start_unlock()
        # swallow everything else (no Cmd-Q, ESC, etc.)

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
    app.aboutToQuit.connect(lambda: setattr(win, "_allow_close", True))
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_lock_app())
