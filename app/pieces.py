from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient

import theme

BLACK = 1
WHITE = 2

def draw_stone(
    painter: QPainter,
    center: QPointF,
    radius: float,
    color: int,
    alpha: float = 1.0,
    with_shadow: bool = True,
) -> None:
    if radius <= 1.0:
        return

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if with_shadow:
        shadow = QColor(60, 40, 20, int(60 * alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(
            QRectF(center.x() - radius * 0.98,
                   center.y() - radius * 0.86,
                   radius * 2, radius * 2)
        )

    outer = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)

    if color == BLACK:
        grad = QRadialGradient(
            QPointF(center.x() - radius * 0.30, center.y() - radius * 0.34),
            radius * 1.55,
        )
        base = QColor(theme.BLACK_STONE)
        base.setAlphaF(alpha)
        top = QColor(96, 98, 108)
        top.setAlphaF(alpha)
        grad.setColorAt(0.0, top)
        grad.setColorAt(0.45, base)
        grad.setColorAt(1.0, QColor(20, 20, 24, int(255 * alpha)))
        painter.setBrush(grad)
        edge = QColor(theme.BLACK_STONE_EDGE)
        edge.setAlphaF(alpha)
        painter.setPen(QPen(edge, max(0.8, radius * 0.05)))
    else:
        grad = QRadialGradient(
            QPointF(center.x() - radius * 0.32, center.y() - radius * 0.36),
            radius * 1.55,
        )
        grad.setColorAt(0.0, QColor(255, 255, 253, int(255 * alpha)))
        grad.setColorAt(0.55, QColor(246, 243, 236, int(255 * alpha)))
        grad.setColorAt(1.0, QColor(214, 208, 196, int(255 * alpha)))
        painter.setBrush(grad)
        edge = QColor(theme.WHITE_STONE_EDGE)
        edge.setAlphaF(alpha)
        painter.setPen(QPen(edge, max(0.8, radius * 0.05)))

    painter.drawEllipse(outer)

    if color == BLACK:
        shine = QColor(200, 205, 220, int(46 * alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shine)
        painter.drawEllipse(
            QRectF(center.x() - radius * 0.44,
                   center.y() - radius * 0.52,
                   radius * 0.52, radius * 0.40)
        )

    painter.restore()

def draw_last_marker(
    painter: QPainter,
    center: QPointF,
    radius: float,
    color: int,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(theme.LAST_MOVE, max(1.4, radius * 0.14)))
    r = radius * 0.34
    painter.drawEllipse(QRectF(center.x() - r, center.y() - r, r * 2, r * 2))
    painter.restore()

def draw_suggest_ring(
    painter: QPainter,
    center: QPointF,
    radius: float,
    stale: bool = False,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    base = theme.SUGGEST_STALE if stale else theme.SUGGEST
    color = QColor(base)
    color.setAlpha(150 if stale else 235)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(color, max(1.8, radius * 0.16)))
    r = radius * 1.10
    painter.drawEllipse(QRectF(center.x() - r, center.y() - r, r * 2, r * 2))

    dot = QColor(color)
    dot.setAlpha(70 if stale else 120)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(dot)
    painter.drawEllipse(center, radius * 0.30, radius * 0.30)
    painter.restore()

def draw_forbidden_cross(
    painter: QPainter,
    center: QPointF,
    radius: float,
) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(theme.FORBIDDEN, max(2.0, radius * 0.22)))
    r = radius * 0.62
    painter.drawLine(
        QPointF(center.x() - r, center.y() - r),
        QPointF(center.x() + r, center.y() + r),
    )
    painter.drawLine(
        QPointF(center.x() + r, center.y() - r),
        QPointF(center.x() - r, center.y() + r),
    )
    painter.restore()
