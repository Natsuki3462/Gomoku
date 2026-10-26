from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtWidgets import QWidget

import pieces
import theme
from session import BOARD_SIZE, RULE_RENJU, Session

STAR_POINTS = [(3, 3), (3, 11), (11, 3), (11, 11), (7, 7)]

class BoardView(QWidget):
    moveRequested = pyqtSignal(int, int)
    hoverChanged = pyqtSignal(int, int, bool)
    illegalRequest = pyqtSignal(str)

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self._hover: tuple[int, int] | None = None
        self._suggestion: tuple[int, int] | None = None
        self._suggestion_stale = False
        self._flash: tuple[int, int] | None = None
        self._interactive = True
        self.show_coords = False
        self.show_forbidden = True

        self.setMinimumSize(320, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

    def set_suggestion(self, pos: tuple[int, int] | None, stale: bool = False) -> None:
        self._suggestion = pos
        self._suggestion_stale = stale
        self.update()

    @property
    def suggestion(self) -> tuple[int, int] | None:
        return self._suggestion

    @property
    def suggestion_stale(self) -> bool:
        return self._suggestion_stale

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = enabled

    def _clear_flash(self) -> None:
        self._flash = None
        self.update()

    def margin(self) -> float:
        side = min(self.width(), self.height())
        return max(16.0, side * 0.045)

    def board_rect(self) -> QRectF:
        pad = self.margin()
        avail_w = max(40.0, self.width() - 2 * pad)
        avail_h = max(40.0, self.height() - 2 * pad)
        cell = min(avail_w / (BOARD_SIZE - 1), avail_h / (BOARD_SIZE - 1))
        side = cell * (BOARD_SIZE - 1)
        return QRectF(
            (self.width() - side) / 2.0,
            (self.height() - side) / 2.0,
            side, side,
        )

    def cell(self) -> float:
        return self.board_rect().width() / (BOARD_SIZE - 1)

    def stone_radius(self) -> float:
        return self.cell() * 0.455

    def screen_index(self, col: int, row: int) -> tuple[int, int]:
        if self.session.flipped:
            return (BOARD_SIZE - 1 - col, row)
        return (col, BOARD_SIZE - 1 - row)

    def point_xy(self, col: int, row: int) -> QPointF:
        rect = self.board_rect()
        cell = self.cell()
        sx, sy = self.screen_index(col, row)
        return QPointF(rect.x() + sx * cell, rect.y() + sy * cell)

    def square_at(self, pos: QPointF) -> tuple[int, int] | None:
        rect = self.board_rect()
        cell = self.cell()
        sx = round((pos.x() - rect.x()) / cell)
        sy = round((pos.y() - rect.y()) / cell)
        if not (0 <= sx < BOARD_SIZE and 0 <= sy < BOARD_SIZE):
            return None
        center = QPointF(rect.x() + sx * cell, rect.y() + sy * cell)
        if (pos - center).manhattanLength() > cell * 0.72:
            return None
        if self.session.flipped:
            return (BOARD_SIZE - 1 - sx, sy)
        return (sx, BOARD_SIZE - 1 - sy)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        self._paint_board(painter)
        self._paint_last_move(painter)
        self._paint_stones(painter)
        self._paint_hover(painter)
        self._paint_suggestion(painter)
        self._paint_coords(painter)

    def _paint_board(self, painter: QPainter) -> None:
        rect = self.board_rect()
        cell = self.cell()
        pad = self.margin()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.BOARD_BG)
        painter.drawRoundedRect(
            rect.adjusted(-pad * 0.62, -pad * 0.62, pad * 0.62, pad * 0.62),
            6, 6,
        )

        line_w = max(1.0, cell * 0.028)
        painter.setPen(QPen(theme.BOARD_LINE, line_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for index in range(BOARD_SIZE):
            offset = index * cell
            painter.drawLine(
                QPointF(rect.x(), rect.y() + offset),
                QPointF(rect.right(), rect.y() + offset),
            )
            painter.drawLine(
                QPointF(rect.x() + offset, rect.y()),
                QPointF(rect.x() + offset, rect.bottom()),
            )

        painter.setPen(QPen(theme.BOARD_EDGE, max(1.6, cell * 0.062)))
        painter.drawRect(rect)

        dot = max(2.2, cell * 0.10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.STAR_POINT)
        for col, row in STAR_POINTS:
            center = self.point_xy(col, row)
            painter.drawEllipse(center, dot, dot)

    def _paint_last_move(self, painter: QPainter) -> None:
        last = self.session.last_move
        if last is None:
            return
        center = self.point_xy(last.col, last.row)
        radius = self.stone_radius()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.LAST_MOVE.red(), theme.LAST_MOVE.green(),
                                theme.LAST_MOVE.blue(), 42))
        r = radius * 1.30
        painter.drawEllipse(QRectF(center.x() - r, center.y() - r, r * 2, r * 2))

    def _paint_stones(self, painter: QPainter) -> None:
        radius = self.stone_radius()
        for col in range(BOARD_SIZE):
            for row in range(BOARD_SIZE):
                color = self.session.at(col, row)
                if not color:
                    continue
                pieces.draw_stone(
                    painter, self.point_xy(col, row), radius, color
                )

        last = self.session.last_move
        if last is not None:
            pieces.draw_last_marker(
                painter,
                self.point_xy(last.col, last.row),
                radius,
                self.session.at(last.col, last.row),
            )

    def _paint_hover(self, painter: QPainter) -> None:
        if not self._interactive or self._hover is None:
            return
        col, row = self._hover
        if not self.session.is_empty(col, row):
            return
        radius = self.stone_radius()
        center = self.point_xy(col, row)

        if self.show_forbidden and self.session.is_forbidden(col, row):
            pieces.draw_forbidden_cross(painter, center, radius)
            return

        pieces.draw_stone(
            painter, center, radius, self.session.turn,
            alpha=0.34, with_shadow=False,
        )

    def _paint_suggestion(self, painter: QPainter) -> None:
        if self._suggestion is None:
            return
        col, row = self._suggestion
        if not self.session.is_empty(col, row):
            return
        pieces.draw_suggest_ring(
            painter, self.point_xy(col, row), self.stone_radius(),
            stale=self._suggestion_stale,
        )

    def _paint_coords(self, painter: QPainter) -> None:
        if not self.show_coords:
            return
        rect = self.board_rect()
        cell = self.cell()
        margin = self.margin()
        font = QFont(theme.UI_FONT)
        font.setPixelSize(max(7, int(margin * 0.40)))
        painter.setFont(font)
        painter.setPen(theme.TEXT_FAINT)
        metrics = QFontMetricsF(font)

        for index in range(BOARD_SIZE):
            label = chr(ord("A") + index)
            px = rect.x() + index * cell
            painter.drawText(
                QPointF(px - metrics.horizontalAdvance(label) / 2.0,
                        rect.bottom() + margin * 0.66),
                label,
            )
            number = str(index + 1)
            py = rect.y() + index * cell
            painter.drawText(
                QPointF(rect.left() - margin * 0.66 - metrics.horizontalAdvance(number),
                        py + metrics.ascent() * 0.36),
                number,
            )

    def _reject(self, col: int, row: int, reason: str) -> None:
        self._flash = (col, row)
        self._flash_timer.start(420)
        self.illegalRequest.emit(reason)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self.square_at(event.position())
        if pos is None:
            return
        col, row = pos

        if not self.session.is_empty(col, row):
            self.illegalRequest.emit("这里已经有棋子了")
            return
        if not self._interactive:
            return
        if self.session.is_game_over():
            self.illegalRequest.emit("对局已结束")
            return

        if self.session.block_forbidden and self.session.is_forbidden(col, row):
            self._reject(col, row, "这里是禁手，不能落子")
            return

        self.moveRequested.emit(col, row)

    def mouseMoveEvent(self, event) -> None:
        pos = self.square_at(event.position())
        if pos == self._hover:
            return
        self._hover = pos
        if pos is None:
            self.hoverChanged.emit(-1, -1, False)
        else:
            self.hoverChanged.emit(
                pos[0], pos[1], self.session.is_forbidden(*pos)
            )
        self.update()

    def leaveEvent(self, event) -> None:
        if self._hover is not None:
            self._hover = None
            self.hoverChanged.emit(-1, -1, False)
            self.update()
