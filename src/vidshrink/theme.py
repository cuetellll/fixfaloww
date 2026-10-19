"""Visual language: Dark Black-Purple Gaming Glassmorphism, Neon Glow & 60fps Clock."""
from __future__ import annotations

import math

from PySide6.QtCore import QElapsedTimer, QEasingCurve, QObject, QPropertyAnimation, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from . import i18n

# =========================================================================== PALETTE
# Dark Black-Purple Gaming Theme (Obsidian & Ultraviolet)
BG = QColor(4, 2, 10)                  # Ultra deep pitch black
DARK_SURFACE = QColor(9, 5, 20, 220)   # Obsidian purple glass background
GLASS_OVERLAY = QColor(255, 255, 255, 12)  # Specular glass reflection
PURPLE = QColor(168, 85, 247)          # Electric Neon Purple (Main brand)
VIOLET = QColor(139, 92, 246)          # Cyber Ultraviolet
CYAN = QColor(34, 211, 238)            # High-tech Laser Cyan
MAGENTA = QColor(236, 72, 153)         # Hyper Neon Pink / Magenta
BLUE = QColor(99, 102, 241)            # Deep Indigo Blue
GREEN = QColor(52, 211, 153)           # Matrix Green (Success / Savings)
AMBER = QColor(251, 191, 36)           # Neon Amber (Optimal / Warnings)
RED = QColor(244, 63, 94)              # Laser Crimson (Danger / Errors)
TEXT = QColor(248, 250, 252)           # Crisp HUD Text (High contrast)
MUTED = QColor(180, 160, 225, 210)     # Luminous purple-tinted muted text


def rgba(c: QColor, a: float) -> QColor:
    q = QColor(c)
    q.setAlphaF(max(0.0, min(1.0, a)))
    return q


def mix(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


# =========================================================================== FONTS
FAMILIES = [
    "Segoe UI Variable Display", "Segoe UI", "Vazirmatn", "Tahoma",
    "Inter", "Noto Sans", "DejaVu Sans", "Arial"
]


def font(px: float, bold: bool = False, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(int(px))
    f.setBold(bold)
    if spacing and i18n.LANG == "en":
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


# =========================================================================== ANIMATION CLOCK
class Clock(QObject):
    tick = Signal()

    def __init__(self):
        super().__init__()
        self._el = QElapsedTimer()
        self._el.start()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self.tick.emit)

    def start(self):
        self._timer.start()

    @property
    def t(self) -> float:
        return self._el.elapsed() / 1000.0


_clock: Clock | None = None


def clock() -> Clock:
    global _clock
    if _clock is None:
        _clock = Clock()
        _clock.start()
    return _clock


def animate(obj, prop: str, end, ms: int = 300, curve=QEasingCurve.OutCubic):
    store = obj.__dict__.setdefault("_anims", {})
    a = store.get(prop)
    if a is None:
        a = QPropertyAnimation(obj, prop.encode(), obj)
        store[prop] = a
    a.stop()
    a.setDuration(ms)
    a.setEasingCurve(curve)
    a.setStartValue(obj.property(prop))
    a.setEndValue(end)
    a.start()


# =========================================================================== GLOW & GLASS RENDERERS
def draw_glow(p: QPainter, rect: QRectF, radius: float, color: QColor, strength: float = 1.0, spread: int = 12):
    """High-intensity multi-pass gaming neon bloom."""
    if strength <= 0.01:
        return
    p.save()
    p.setBrush(Qt.NoBrush)
    step = 2 if spread >= 6 else 1
    for i in range(spread, 0, -step):
        f = 1.0 - i / (spread + 1.0)
        # Deep cubic falloff for authentic laser/neon bloom
        alpha = strength * 0.12 * step * (f ** 2.2)
        pen = QPen(rgba(color, alpha), i * 2.2)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawRoundedRect(rect, radius + i * 0.6, radius + i * 0.6)
    p.restore()


def draw_glass(p: QPainter, rect: QRectF, radius: float, border_color: QColor = PURPLE, glow_strength: float = 0.5):
    """Frosted Obsidian Glass with dual-layer neon rim and specular reflex."""
    if glow_strength > 0.05:
        draw_glow(p, rect, radius, border_color, glow_strength, 10)

    # 1) Deep obsidian purple glass body
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0, QColor(20, 12, 38, 205))
    bg.setColorAt(0.5, QColor(10, 6, 22, 235))
    bg.setColorAt(1, QColor(5, 3, 14, 245))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(rect, radius, radius)

    # 2) Specular top glass sheen
    sheen = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + rect.height() * 0.45)
    sheen.setColorAt(0, QColor(255, 255, 255, 22))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(sheen)
    p.drawRoundedRect(rect, radius, radius)

    # 3) Luminous neon perimeter wire
    edge = QLinearGradient(rect.topLeft(), rect.bottomRight())
    edge.setColorAt(0, rgba(border_color, 0.75))
    edge.setColorAt(0.45, rgba(VIOLET, 0.45))
    edge.setColorAt(1, rgba(CYAN, 0.60))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(edge), 1.4))
    p.drawRoundedRect(rect, radius, radius)


def draw_bar(p: QPainter, r: QRectF, frac: float, t: float, c1: QColor = PURPLE, c2: QColor = CYAN, glow: float = 1.0):
    """Gaming laser energy bar with dual-speed travelling pulse and intense core."""
    h = r.height()
    rad = h / 2
    # Recessed dark slot
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(14, 9, 28, 220))
    p.drawRoundedRect(r, rad, rad)
    # Ambient slot glow
    p.setPen(QPen(QColor(255, 255, 255, 25), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r, rad, rad)

    if frac <= 0.002:
        return

    fr = QRectF(r.left(), r.top(), max(h, r.width() * frac), h)
    draw_glow(p, fr, rad, mix(c1, c2, 0.5), 1.2 * glow, 8)

    # Core laser gradient
    g = QLinearGradient(fr.left(), 0, fr.right(), 0)
    g.setColorAt(0, c1)
    g.setColorAt(0.7, mix(c1, c2, 0.6))
    g.setColorAt(1, c2)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(fr, rad, rad)

    # Travelling laser flare
    p.save()
    path = QPainterPath()
    path.addRoundedRect(fr, rad, rad)
    p.setClipPath(path)

    # High-speed shimmer
    x = fr.left() + ((t * 1.1) % 1.6 - 0.3) * fr.width()
    sg = QLinearGradient(x - 36, 0, x + 36, 0)
    sg.setColorAt(0, QColor(255, 255, 255, 0))
    sg.setColorAt(0.5, QColor(255, 255, 255, 190))
    sg.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(fr, sg)

    # Hot core center line
    core_pen = QPen(QColor(255, 255, 255, 140), max(1.0, h * 0.28), Qt.SolidLine, Qt.RoundCap)
    p.setPen(core_pen)
    p.drawLine(fr.left() + rad, fr.center().y(), fr.right() - rad, fr.center().y())
    p.restore()


def draw_logo(p: QPainter, r: QRectF, t: float = 0.0):
    """VidShrink Cyber Mark: Dual converging laser chevrons with neon bloom."""
    rr = r.height() * 0.28
    # Outer gaming badge
    draw_glow(p, r, rr, PURPLE, 0.8 + 0.3 * math.sin(t * 2.5), 8)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, PURPLE)
    g.setColorAt(0.5, VIOLET)
    g.setColorAt(1, CYAN)
    p.setPen(QPen(rgba(CYAN, 0.6), 1.2))
    p.setBrush(g)
    p.drawRoundedRect(r, rr, rr)

    cx, cy = r.center().x(), r.center().y()
    s = r.height() * 0.20
    gap = r.height() * (0.07 + 0.04 * math.sin(t * 3.4))
    pen = QPen(QColor(255, 255, 255), r.height() * 0.10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    left = QPainterPath()
    left.moveTo(cx - gap - s, cy - s)
    left.lineTo(cx - gap, cy)
    left.lineTo(cx - gap - s, cy + s)

    right = QPainterPath()
    right.moveTo(cx + gap + s, cy - s)
    right.lineTo(cx + gap, cy)
    right.lineTo(cx + gap + s, cy + s)

    p.drawPath(left)
    p.drawPath(right)
