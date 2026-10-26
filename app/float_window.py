from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import config
import theme
from board_view import BoardView
from engine_worker import AnalysisResult, EngineWorker
from session import (
    BLACK,
    BOARD_SIZE,
    RULE_FREESTYLE,
    RULE_IDS,
    RULE_LABELS,
    RULE_RENJU,
    WHITE,
    Session,
    color_name,
)

CARD_RADIUS = 12
HEADER_HEIGHT = 38
HEADER_HEIGHT_COMPACT = 26
AUTO_ACCEPT_DELAY_MS = 260

class CardHeader(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self._drag: QPoint | None = None
        self.setFixedHeight(HEADER_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(7)

        self.title = QLabel("GomokuFloat")
        self.title.setObjectName("Title")
        self.status = QLabel("")
        self.status.setObjectName("Status")
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.eval = QLabel("—")
        self.eval.setObjectName("Eval")
        self.eval.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.eval.setFixedWidth(58)

        self.btn_rule = self._tool("禁", "切换规则：连珠（有禁手） / 无禁手", checkable=True)
        self.btn_auto = self._tool("A", "自动采纳：引擎给出建议后自动落子", checkable=True)
        self.btn_pin = self._tool("⇧", "置顶", checkable=True)
        self.btn_pin.setChecked(True)
        self.btn_settings = self._tool("⚙", "设置")
        self.btn_compact = self._tool("⊟", "紧凑模式")
        self.btn_close = self._tool("✕", "退出")

        row.addWidget(self.title)
        row.addWidget(self.status, 1)
        row.addWidget(self.eval)
        row.addWidget(self.btn_rule)
        row.addWidget(self.btn_auto)
        row.addWidget(self.btn_pin)
        row.addWidget(self.btn_settings)
        row.addWidget(self.btn_compact)
        row.addWidget(self.btn_close)

    def _tool(self, text: str, tip: str, checkable: bool = False) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(24, 24)
        return btn

    def set_status(self, text: str, warn: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color:#f87171;" if warn else "")

    def set_eval(self, text: str) -> None:
        self.eval.setText(text)

    def set_compact(self, compact: bool) -> None:
        for widget in (self.title, self.eval, self.btn_rule, self.btn_auto,
                       self.btn_pin, self.btn_settings):
            widget.setVisible(not compact)
        self.setFixedHeight(HEADER_HEIGHT_COMPACT if compact else HEADER_HEIGHT)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._window.toggle_compact()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = CARD_RADIUS
        path = QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
        path.lineTo(rect.right() - radius, rect.top())
        path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        painter.fillPath(path, theme.HEADER_BG)

class CardFooter(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setFixedHeight(36)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 10, 6)
        row.setSpacing(6)

        self.btn_icon = QToolButton(self)
        self.btn_icon.setText("◐")
        self.btn_icon.setToolTip("透明度：拖动滑块 / Ctrl+滚轮 / ↑↓\n点此复位")
        self.btn_icon.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_icon.setFixedSize(20, 22)
        self.btn_icon.setStyleSheet(
            "QToolButton{color:#8b95a9;border:none;background:transparent;font-size:12px;}"
            "QToolButton:hover{color:#dfe6f2;}"
        )

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(int(config.MIN_OPACITY * 100), int(config.MAX_OPACITY * 100))
        self.slider.setSingleStep(1)
        self.slider.setPageStep(5)
        self.slider.setTracking(True)
        self.slider.setValue(int(round(window.cfg["opacity"] * 100)))
        self.slider.setFixedWidth(86)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.pct = QLabel(f"{self.slider.value()}%")
        self.pct.setObjectName("Pct")
        self.pct.setFixedWidth(32)
        self.pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.btn_accept = QPushButton("落子")
        self.btn_accept.setObjectName("Primary")
        self.btn_accept.setToolTip("在引擎建议位置落子（空格）")
        self.btn_accept.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_accept.setFixedHeight(24)
        self.btn_accept.setMinimumWidth(52)

        self.btn_undo = self._tool("↩", "撤销（Ctrl+Z，长按连续撤销）")
        self.btn_redo = self._tool("↪", "重做（Ctrl+Y）")
        self.btn_flip = self._tool("⇅", "翻转视角（F）")
        self.btn_new = self._tool("⟳", "新开一局（N）")

        row.addWidget(self.btn_icon)
        row.addWidget(self.slider)
        row.addWidget(self.pct)
        row.addStretch(1)
        row.addWidget(self.btn_accept)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)
        row.addWidget(self.btn_flip)
        row.addWidget(self.btn_new)

    def _tool(self, text: str, tip: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(26, 24)
        return btn

    def set_opacity_text(self, value: int) -> None:
        self.pct.setText(f"{value}%")

class HistoryStrip(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window)
        self._window = window
        self.setFixedHeight(24)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._items: list[str] = []
        self._ply = 0
        self._chips: list[tuple[QRectF, int]] = []
        self._hover: int | None = None
        self._qfont = QFont(theme.UI_FONT)
        self._qfont.setPixelSize(11)
        self._offset = 0.0

    def set_data(self, items: list[str], ply: int) -> None:
        grew = len(items) > len(self._items)
        self._items = list(items)
        self._ply = ply
        if grew:
            self._offset = 1e9
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._qfont)
        metrics = QFontMetricsF(self._qfont)

        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawLine(0, 0, self.width(), 0)

        widths = [metrics.horizontalAdvance(t) + 12 for t in self._items]
        total = sum(widths) + 12
        max_offset = max(0.0, total - self.width())
        self._offset = max(0.0, min(self._offset, max_offset))

        x = 10 - self._offset
        self._chips = []
        for index, text in enumerate(self._items):
            rect = QRectF(x, 3, widths[index], self.height() - 7)
            self._chips.append((rect, index))
            is_current = index == self._ply - 1
            if is_current:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(74, 222, 128, 46))
                painter.drawRoundedRect(rect, 4, 4)
            elif self._hover == index:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 255, 255, 16))
                painter.drawRoundedRect(rect, 4, 4)
            if index < self._ply:
                color = QColor(226, 232, 242) if is_current else QColor(176, 184, 200)
            else:
                color = QColor(104, 112, 128)
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            x += widths[index]

        if not self._items:
            painter.setPen(QColor(96, 104, 120))
            painter.drawText(
                QRectF(10, 0, self.width() - 20, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                "尚无着法",
            )

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        for rect, index in self._chips:
            if rect.contains(pos):
                self._window.jump_to(index + 1)
                return

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        hover = None
        for rect, index in self._chips:
            if rect.contains(pos):
                hover = index
                break
        if hover != self._hover:
            self._hover = hover
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    def wheelEvent(self, event) -> None:
        self._offset -= event.angleDelta().y() * 0.4
        self.update()

class SideOverlay(QWidget):
    def __init__(self, window: "FloatWindow") -> None:
        super().__init__(window.board)
        self._window = window
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 30, 30, 30)
        outer.addStretch(1)

        title = QLabel("选择你执的一方")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#eef2f8; font-size:14px; font-weight:600;")
        hint = QLabel("黑先。之后只需复刻对手落子\n空格在建议位置落子")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color:#9aa4b8; font-size:11px;")

        btn_black = QPushButton("执黑 · 先手")
        btn_black.setObjectName("Primary")
        btn_black.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_black.setMinimumHeight(34)
        btn_black.clicked.connect(lambda: self._window.choose_side(BLACK))

        btn_white = QPushButton("执白 · 后手")
        btn_white.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_white.setMinimumHeight(34)
        btn_white.clicked.connect(lambda: self._window.choose_side(WHITE))

        outer.addWidget(title)
        outer.addSpacing(6)
        outer.addWidget(hint)
        outer.addSpacing(18)
        outer.addWidget(btn_black)
        outer.addSpacing(8)
        outer.addWidget(btn_white)
        outer.addStretch(1)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(9, 10, 14, 216))
        painter.drawRect(self.rect())

class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GomokuFloat 设置")
        self.setStyleSheet(theme.QSS)
        self.setMinimumWidth(430)

        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 12)
        form.setSpacing(10)

        self.rule = QComboBox()
        self.rule.addItem("连珠（有禁手）", RULE_RENJU)
        self.rule.addItem("无禁手（长连算赢）", RULE_FREESTYLE)
        index = self.rule.findData(cfg.get("rule_mode") or RULE_RENJU)
        self.rule.setCurrentIndex(index if index >= 0 else 0)
        self.rule.setToolTip("切换规则会清空当前棋局")

        self.block = QCheckBox("禁手拦截（关闭后只提示、不阻止落子）")
        self.block.setChecked(bool(cfg.get("block_forbidden", True)))

        self.strength = QComboBox()
        for key, (label, ms, threads, hash_mb) in config.STRENGTH_PRESETS.items():
            self.strength.addItem(f"{label}（{ms / 1000:.1f}s · {threads} 线程）", key)
        self.strength.addItem("自定义", config.CUSTOM_STRENGTH)
        index = self.strength.findData(str(cfg.get("strength") or "balanced"))
        self.strength.setCurrentIndex(index if index >= 0 else 1)

        self.movetime = QSpinBox()
        self.movetime.setRange(50, 30000)
        self.movetime.setSingleStep(50)
        self.movetime.setSuffix(" ms")
        self.movetime.setValue(int(cfg["movetime_ms"]))

        self.threads = QSpinBox()
        self.threads.setRange(1, 32)
        self.threads.setValue(int(cfg["threads"]))

        self.hash = QSpinBox()
        self.hash.setRange(16, 4096)
        self.hash.setSingleStep(16)
        self.hash.setSuffix(" MB")
        self.hash.setValue(int(cfg["hash_mb"]))

        self.coords = QCheckBox("在棋盘上显示坐标")
        self.coords.setChecked(bool(cfg.get("show_coords", False)))

        self.auto_accept = QCheckBox("自动采纳：引擎出建议后自动落子")
        self.auto_accept.setChecked(bool(cfg.get("auto_accept", False)))

        self.low_priority = QCheckBox("引擎低优先级（玩游戏时不抢 CPU）")
        self.low_priority.setChecked(bool(cfg.get("low_priority", True)))

        engine_row = QWidget()
        engine_layout = QHBoxLayout(engine_row)
        engine_layout.setContentsMargins(0, 0, 0, 0)
        engine_layout.setSpacing(6)
        self.engine_path = QLineEdit(str(cfg.get("engine_path") or ""))
        self.engine_path.setPlaceholderText("留空则自动使用 engine\\pbrain-rapfi-*.exe")
        browse = QPushButton("浏览…")
        browse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse.clicked.connect(self._browse)
        engine_layout.addWidget(self.engine_path, 1)
        engine_layout.addWidget(browse)

        form.addRow("规则", self.rule)
        form.addRow("", self.block)
        form.addRow("引擎强度", self.strength)
        form.addRow("单步思考", self.movetime)
        form.addRow("引擎线程", self.threads)
        form.addRow("Hash 大小", self.hash)
        form.addRow("引擎路径", engine_row)
        form.addRow("", self.coords)
        form.addRow("", self.auto_accept)
        form.addRow("", self.low_priority)

        for spin in (self.movetime, self.threads, self.hash):
            spin.valueChanged.connect(self._mark_custom)
        self.strength.currentIndexChanged.connect(self._on_strength_changed)
        self._apply_strength_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_strength_changed(self) -> None:
        key = self.strength.currentData()
        if key in config.STRENGTH_PRESETS:
            _, ms, threads, hash_mb = config.STRENGTH_PRESETS[key]
            for widget, value in ((self.movetime, ms), (self.threads, threads),
                                  (self.hash, hash_mb)):
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
        self._apply_strength_enabled()

    def _mark_custom(self) -> None:
        if self.strength.currentData() != config.CUSTOM_STRENGTH:
            self.strength.blockSignals(True)
            self.strength.setCurrentIndex(self.strength.count() - 1)
            self.strength.blockSignals(False)
            self._apply_strength_enabled()

    def _apply_strength_enabled(self) -> None:
        custom = self.strength.currentData() == config.CUSTOM_STRENGTH
        for widget in (self.movetime, self.threads, self.hash):
            widget.setEnabled(custom)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Rapfi 可执行文件", "", "可执行文件 (*.exe);;所有文件 (*)"
        )
        if path:
            self.engine_path.setText(path)

    def values(self) -> dict:
        return {
            "rule_mode": self.rule.currentData(),
            "block_forbidden": self.block.isChecked(),
            "strength": self.strength.currentData(),
            "movetime_ms": self.movetime.value(),
            "threads": self.threads.value(),
            "hash_mb": self.hash.value(),
            "show_coords": self.coords.isChecked(),
            "auto_accept": self.auto_accept.isChecked(),
            "low_priority": self.low_priority.isChecked(),
            "engine_path": self.engine_path.text().strip(),
        }

class FloatWindow(QWidget):
    def __init__(self, cfg: dict) -> None:
        super().__init__(None)
        self.cfg = cfg
        self.setWindowTitle("GomokuFloat")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(theme.QSS)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.session = Session(self)
        self.session.rule_mode = str(cfg.get("rule_mode") or RULE_RENJU)
        self.session.block_forbidden = bool(cfg.get("block_forbidden", True))
        self.session.reset(BLACK)

        self._engine: EngineWorker | None = None
        self._engine_ok = False
        self._engine_error: str | None = None
        self._suggestion: AnalysisResult | None = None
        self._side_chosen = False
        self._thinking = False
        self._status_override: str | None = None
        self._status_warn = False
        self._compact = False
        self._normal_height = 620

        self.header = CardHeader(self)
        self.board = BoardView(self.session, self)
        self.board.show_coords = bool(cfg.get("show_coords", False))
        self.footer = CardFooter(self)
        self.history = HistoryStrip(self)
        self.overlay = SideOverlay(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.board, 1)
        layout.addWidget(self.history)
        layout.addWidget(self.footer)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._start_analysis)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status_override)
        self._repeat_timer = QTimer(self)
        self._repeat_timer.setInterval(110)
        self._repeat_timer.timeout.connect(self.undo)

        self._wire()
        self._restore_geometry()
        self.setWindowOpacity(float(cfg["opacity"]))
        self.board.installEventFilter(self)
        self.overlay.setGeometry(self.board.rect())
        self.overlay.raise_()

        self.header.btn_rule.setChecked(self.session.rule_mode == RULE_RENJU)
        self.header.btn_auto.setChecked(bool(cfg.get("auto_accept", False)))

        self._start_engine()
        self._refresh_ui()

    def _wire(self) -> None:
        self.session.positionChanged.connect(self._on_position_changed)
        self.session.historyChanged.connect(self._on_history_changed)

        self.board.moveRequested.connect(self._play_move)
        self.board.illegalRequest.connect(lambda t: self._flash_status(t, warn=True))
        self.board.hoverChanged.connect(self._on_hover)

        self.header.btn_rule.toggled.connect(self._on_rule_toggled)
        self.header.btn_auto.toggled.connect(self._set_auto_accept)
        self.header.btn_pin.toggled.connect(self._set_always_on_top)
        self.header.btn_settings.clicked.connect(self.open_settings)
        self.header.btn_compact.clicked.connect(self.toggle_compact)
        self.header.btn_close.clicked.connect(self.close)

        self.footer.slider.valueChanged.connect(self._on_opacity)
        self.footer.btn_icon.clicked.connect(self.reset_opacity)
        self.footer.btn_accept.clicked.connect(self.accept_suggestion)
        self.footer.btn_undo.pressed.connect(self._begin_repeat_undo)
        self.footer.btn_undo.released.connect(self._repeat_timer.stop)
        self.footer.btn_redo.clicked.connect(self.redo)
        self.footer.btn_flip.clicked.connect(self.flip)
        self.footer.btn_new.clicked.connect(self.new_game)

    def eventFilter(self, obj, event):
        if obj is self.board and event.type() == QEvent.Type.Resize:
            self.overlay.setGeometry(self.board.rect())
        elif obj is self.board and event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta:
                    self._adjust_opacity(2 if delta > 0 else -2)
                    return True
        return super().eventFilter(obj, event)

    def _start_engine(self) -> None:
        explicit = self.cfg.get("engine_path") or None
        path = config.find_engine(explicit)
        if path is None:
            self._engine_ok = False
            self._engine_error = "未找到 Rapfi，请把 pbrain-rapfi-*.exe 放到 engine\\ 目录"
            self._status_override = None
            self._status_timer.stop()
            self.header.set_status(self._engine_error, warn=True)
            return
        self._engine_error = None
        self.cfg["engine_path"] = str(path)
        self._engine = EngineWorker(
            str(path),
            rule_id=RULE_IDS[self.session.rule_mode],
            movetime_ms=int(self.cfg["movetime_ms"]),
            threads=int(self.cfg["threads"]),
            hash_mb=int(self.cfg["hash_mb"]),
            low_priority=bool(self.cfg.get("low_priority", True)),
        )
        self._engine.ready.connect(self._on_engine_ready)
        self._engine.failed.connect(self._on_engine_failed)
        self._engine.progress.connect(self._on_engine_progress)
        self._engine.analysisDone.connect(self._on_analysis_done)
        self._engine.start()

    def _stop_engine(self) -> None:
        if self._engine is not None:
            self._engine.shutdown()
            self._engine.wait(5000)
            self._engine = None
        self._engine_ok = False

    def _on_engine_ready(self, name: str) -> None:
        self._engine_ok = True
        self._engine_error = None
        self._flash_status(f"{name} 就绪")
        if self._side_chosen:
            self._schedule_analysis()

    def _on_engine_failed(self, message: str) -> None:
        self._engine_ok = False
        self._engine_error = message
        self.header.set_status(message, warn=True)

    def _on_engine_progress(self, data: dict) -> None:
        if data.get("version") != self.session.version:
            return
        depth = data.get("depth") or 0
        winrate = data.get("winrate")
        if winrate is not None:
            self.header.set_eval(f"{winrate:.0f}%")
        if self._thinking and self._status_override is None:
            self._set_status_quiet(f"分析中 · 深度 {depth}")

    def _on_analysis_done(self, result: AnalysisResult) -> None:
        if result.version != self.session.version:
            return
        self._thinking = False

        if not self.session.is_my_turn or self.session.is_game_over():
            self._refresh_ui()
            return
        if not result.valid:
            self._refresh_ui()
            return
        if not self.session.is_empty(result.col, result.row):
            self._refresh_ui()
            return

        self._suggestion = result
        self.board.set_suggestion((result.col, result.row), stale=False)
        self.header.set_eval(f"{result.winrate:.0f}%")
        self._refresh_ui()

        if self.cfg.get("auto_accept"):
            version = result.version
            col, row = result.col, result.row
            QTimer.singleShot(
                AUTO_ACCEPT_DELAY_MS,
                lambda: self._auto_accept(version, col, row),
            )

    def _auto_accept(self, version: int, col: int, row: int) -> None:
        if not self.cfg.get("auto_accept"):
            return
        if version != self.session.version:
            return
        if not self.session.is_empty(col, row):
            return
        if self._play_move(col, row):
            self._flash_status("自动落子")

    def _schedule_analysis(self) -> None:
        self._debounce.stop()
        if not self._side_chosen:
            return
        if self.session.is_game_over():
            self._refresh_ui()
            return
        if not self.session.is_my_turn:
            return
        self._debounce.start(int(self.cfg["debounce_ms"]))

    def _start_analysis(self) -> None:
        if not self._side_chosen or self._engine is None or not self._engine_ok:
            return
        if self.session.is_game_over() or not self.session.is_my_turn:
            return
        self._thinking = True
        moves = [
            (move.col, move.row, BLACK if index % 2 == 0 else WHITE)
            for index, move in enumerate(self.session.history)
        ]
        self._engine.submit(
            self.session.version, moves, int(self.cfg["movetime_ms"])
        )
        self._set_status_quiet("分析中…")

    def _play_move(self, col: int, row: int) -> bool:
        if not self.session.push(col, row):
            if self.session.is_forbidden(col, row):
                self._flash_status("禁手，不能落子", warn=True)
            else:
                self._flash_status("这里不能落子", warn=True)
            return False
        return True

    def accept_suggestion(self) -> None:
        move = self._suggestion_move()
        if move is None:
            self._flash_status("暂无可用建议", warn=True)
            return
        col, row = move
        if self._play_move(col, row):
            self._flash_status("已按建议落子")

    def _suggestion_move(self) -> tuple[int, int] | None:
        board_move = self.board.suggestion
        if board_move is not None and self.session.is_empty(*board_move):
            return board_move
        result = self._suggestion
        if result is not None and result.version == self.session.version and result.valid:
            if self.session.is_empty(result.col, result.row):
                return (result.col, result.row)
        return None

    def undo(self) -> None:
        if not self.session.undo():
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept("已撤销")
        else:
            self._flash_status("已撤销")

    def redo(self) -> None:
        if not self.session.redo():
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept("已重做")
        else:
            self._flash_status("已重做")

    def jump_to(self, ply: int) -> None:
        if not self.session.jump_to(ply):
            return
        if self.cfg.get("auto_accept"):
            self._pause_auto_accept(f"回到第 {ply} 手")
        else:
            self._flash_status(f"回到第 {ply} 手")

    def flip(self) -> None:
        self.session.toggle_flip()
        self.board.update()

    def new_game(self) -> None:
        self._side_chosen = False
        self._suggestion = None
        self._clear_flash_now()
        self.board.set_suggestion(None)
        self.session.reset(self.session.my_color)
        self.overlay.show()
        self.overlay.raise_()
        self._refresh_ui()

    def choose_side(self, color: int) -> None:
        self.overlay.hide()
        self._side_chosen = True
        self._clear_flash_now()
        self.session.reset(color)
        self.session.flipped = color == WHITE
        self._refresh_ui()
        self._schedule_analysis()

    def _on_position_changed(self, version: int) -> None:
        prev = self.board.suggestion
        self._suggestion = None
        self._thinking = False
        if self._engine is not None:
            self._engine.cancel()
        if prev is None:
            self.board.set_suggestion(None)
        else:
            still_ok = self.session.is_empty(*prev)
            self.board.set_suggestion(
                prev, stale=not (still_ok and self.session.is_my_turn)
            )
        self._schedule_analysis()
        self._refresh_ui()

    def _on_history_changed(self) -> None:
        self.board.update()
        self.history.set_data(self.session.move_texts(), self.session.ply)
        self._refresh_ui()

    def _on_hover(self, col: int, row: int, forbidden: bool) -> None:
        if col < 0:
            return
        if forbidden and self.session.block_forbidden:
            self._set_status_quiet("禁手点")
        elif self._status_override is None:
            self._refresh_ui()

    def _refresh_ui(self) -> None:
        self.footer.btn_undo.setEnabled(self.session.ply > 0)
        self.footer.btn_redo.setEnabled(self.session.can_redo)
        self.footer.btn_accept.setEnabled(self._suggestion_move() is not None)

        if self.session.is_game_over():
            text = self.session.win_text() or "对局结束"
            self._set_status_quiet(text)
            return

        if not self._side_chosen:
            if self._engine_error:
                self.header.set_status(self._engine_error, warn=True)
            else:
                self.header.set_status("请选择先后手")
            self.header.set_eval("—")
            return

        if self._engine_error:
            self.header.set_status(self._engine_error, warn=True)
            self.header.set_eval("—")
            return

        if self._status_override:
            self.header.set_status(self._status_override, self._status_warn)
            return

        if self.session.is_my_turn:
            if self._thinking:
                self._set_status_quiet("轮你走 · 分析中…")
            elif self._suggestion is not None and self._suggestion.valid:
                from session import pos_to_text
                text = pos_to_text(self._suggestion.col, self._suggestion.row)
                self._set_status_quiet(
                    f"轮你走 · 建议 {text} · 深度 {self._suggestion.depth}"
                )
            else:
                self._set_status_quiet("轮你走")
        else:
            self._set_status_quiet("轮对手走 · 复刻对手落子")

    def _set_status_quiet(self, text: str) -> None:
        self.header.set_status(text)

    def _flash_status(self, text: str, warn: bool = False, ms: int = 1800) -> None:
        self._status_override = text
        self._status_warn = warn
        self.header.set_status(text, warn)
        self._status_timer.start(ms)

    def _clear_flash_now(self) -> None:
        self._status_timer.stop()
        self._status_override = None
        self._status_warn = False

    def _clear_status_override(self) -> None:
        self._status_override = None
        self._status_warn = False
        self._refresh_ui()

    def _on_rule_toggled(self, checked: bool) -> None:
        mode = RULE_RENJU if checked else RULE_FREESTYLE
        self.set_rule_mode(mode)

    def set_rule_mode(self, mode: str) -> None:
        if mode == self.session.rule_mode:
            return
        self._clear_flash_now()
        self._suggestion = None
        self.board.set_suggestion(None)
        self.session.set_rule_mode(mode)
        self.cfg["rule_mode"] = mode
        config.save_config(self.cfg)
        if self._engine is not None:
            self._engine.set_rule(RULE_IDS[mode])
        self.header.btn_rule.blockSignals(True)
        self.header.btn_rule.setChecked(mode == RULE_RENJU)
        self.header.btn_rule.blockSignals(False)
        self._side_chosen = False
        self.overlay.show()
        self.overlay.raise_()
        self._flash_status(f"已切换到{RULE_LABELS[mode]}，棋局已重置")

    def _on_opacity(self, value: int) -> None:
        opacity = max(config.MIN_OPACITY, min(config.MAX_OPACITY, value / 100.0))
        self.cfg["opacity"] = round(opacity, 3)
        self.setWindowOpacity(opacity)
        self.footer.set_opacity_text(value)

    def _adjust_opacity(self, delta: int) -> None:
        value = self.footer.slider.value() + delta
        low = int(round(config.MIN_OPACITY * 100))
        high = int(round(config.MAX_OPACITY * 100))
        self.footer.slider.setValue(max(low, min(high, value)))

    def reset_opacity(self) -> None:
        self.footer.slider.setValue(int(round(config.DEFAULT_OPACITY * 100)))
        self._flash_status(f"透明度复位为 {int(round(config.DEFAULT_OPACITY * 100))}%")

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self._adjust_opacity(2 if delta > 0 else -2)
                event.accept()
                return
        super().wheelEvent(event)

    def _set_always_on_top(self, on: bool) -> None:
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _set_auto_accept(self, on: bool) -> None:
        self.cfg["auto_accept"] = bool(on)
        config.save_config(self.cfg)
        if not on:
            self._flash_status("自动采纳已关闭")
            return
        self._flash_status("自动采纳已开启")
        move = self._suggestion_move()
        if move is not None:
            version = self.session.version
            col, row = move
            QTimer.singleShot(
                AUTO_ACCEPT_DELAY_MS,
                lambda: self._auto_accept(version, col, row),
            )

    def _pause_auto_accept(self, reason: str) -> None:
        if not self.cfg.get("auto_accept"):
            return
        self.header.btn_auto.blockSignals(True)
        self.header.btn_auto.setChecked(False)
        self.header.btn_auto.blockSignals(False)
        self.cfg["auto_accept"] = False
        config.save_config(self.cfg)
        self._flash_status(f"{reason} · 自动采纳已暂停")

    def toggle_compact(self) -> None:
        self._compact = not self._compact
        if self._compact:
            self._normal_height = self.height()
            self.footer.setVisible(False)
            self.history.setVisible(False)
            self.header.set_compact(True)
            height = self.width() + HEADER_HEIGHT_COMPACT + 6
            self.resize(self.width(), height)
        else:
            self.footer.setVisible(True)
            self.history.setVisible(True)
            self.header.set_compact(False)
            self.resize(self.width(), max(self._normal_height, self.height()))
        self.header.btn_compact.setToolTip(
            "退出紧凑模式" if self._compact else "紧凑模式"
        )

    def set_strength(self, name: str) -> None:
        if name not in config.STRENGTH_PRESETS:
            return
        old = (self.cfg.get("threads"), self.cfg.get("hash_mb"))
        config.apply_preset(self.cfg, name)
        config.save_config(self.cfg)
        label = config.STRENGTH_PRESETS[name][0]
        if self._engine is not None:
            self._engine.movetime_ms = int(self.cfg["movetime_ms"])
            self._engine.threads = int(self.cfg["threads"])
            self._engine.hash_mb = int(self.cfg["hash_mb"])
        if (self.cfg["threads"], self.cfg["hash_mb"]) != old:
            self._stop_engine()
            self._start_engine()
        else:
            self._schedule_analysis()
        self._flash_status(
            f"强度：{label}（{int(self.cfg['movetime_ms']) / 1000:.1f}s · "
            f"{self.cfg['threads']} 线程）"
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.cfg, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        old_rule = self.session.rule_mode
        old_engine = (
            self.cfg.get("engine_path"),
            self.cfg.get("threads"),
            self.cfg.get("hash_mb"),
            self.cfg.get("low_priority"),
        )
        self.cfg.update(values)
        self.session.block_forbidden = bool(values["block_forbidden"])
        self.board.show_coords = bool(values["show_coords"])
        self.board.update()
        self.header.btn_auto.blockSignals(True)
        self.header.btn_auto.setChecked(bool(values["auto_accept"]))
        self.header.btn_auto.blockSignals(False)

        if values["rule_mode"] != old_rule:
            self.session.rule_mode = old_rule
            self.set_rule_mode(values["rule_mode"])

        new_engine = (
            self.cfg.get("engine_path"),
            self.cfg.get("threads"),
            self.cfg.get("hash_mb"),
            self.cfg.get("low_priority"),
        )
        if new_engine != old_engine:
            self._stop_engine()
            self._start_engine()
        else:
            if self._engine is not None:
                self._engine.movetime_ms = int(self.cfg["movetime_ms"])
            self._schedule_analysis()
        config.save_config(self.cfg)
        self._flash_status("设置已保存")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if key == Qt.Key.Key_Space:
            self.accept_suggestion()
        elif ctrl and key == Qt.Key.Key_Z:
            self.undo()
        elif ctrl and key == Qt.Key.Key_Y:
            self.redo()
        elif ctrl and int(Qt.Key.Key_1) <= key <= int(Qt.Key.Key_4):
            names = list(config.STRENGTH_PRESETS)
            self.set_strength(names[key - int(Qt.Key.Key_1)])
        elif key == Qt.Key.Key_F:
            self.flip()
        elif key == Qt.Key.Key_N:
            self.new_game()
        elif key == Qt.Key.Key_Up:
            self._adjust_opacity(2)
        elif key == Qt.Key.Key_Down:
            self._adjust_opacity(-2)
        else:
            super().keyPressEvent(event)

    def _begin_repeat_undo(self) -> None:
        self.undo()
        self._repeat_timer.start()

    def _restore_geometry(self) -> None:
        geo = self.cfg.get("geometry")
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        if isinstance(geo, list) and len(geo) == 4:
            x, y, w, h = (int(v) for v in geo)
            w = max(config.WINDOW_MIN_WIDTH, w)
            h = max(config.WINDOW_MIN_HEIGHT, h)
            if area is not None:
                x = max(area.left(), min(x, area.right() - 80))
                y = max(area.top(), min(y, area.bottom() - 60))
            self.setGeometry(x, y, w, h)
        else:
            x, y, w, h = config.DEFAULT_GEOMETRY
            if area is not None:
                x = min(x, area.right() - w - 20)
                y = min(y, area.bottom() - h - 20)
            self.setGeometry(x, y, w, h)
        self._normal_height = self.height()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, CARD_RADIUS, CARD_RADIUS)
        painter.fillPath(path, theme.CARD_BG)
        painter.setPen(QPen(theme.CARD_BORDER, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.overlay.setGeometry(self.board.rect())
        self.overlay.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def closeEvent(self, event) -> None:
        geo = self.geometry()
        self.cfg["geometry"] = [geo.x(), geo.y(), geo.width(), geo.height()]
        config.save_config(self.cfg)
        self._debounce.stop()
        self._stop_engine()
        super().closeEvent(event)
