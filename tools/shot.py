from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(exist_ok=True)

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import config
from float_window import FloatWindow
from session import BLACK, RULE_FREESTYLE, RULE_RENJU, WHITE, pos_to_text

SIZE = (470, 560)
OK = 0
BAD = 0

def check(label: str, good: bool, detail: str = "") -> None:
    global OK, BAD
    if good:
        OK += 1
    else:
        BAD += 1
    print(f"  [{'PASS' if good else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")

def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)

def wait_for(app: QApplication, predicate, timeout: float = 20.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
        if predicate():
            return True
    return False

def compose(window: FloatWindow, path: Path) -> None:
    pix = window.grab()
    canvas = QPixmap(pix.size())
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, canvas.width(), canvas.height())
    grad.setColorAt(0.0, QColor(38, 52, 78))
    grad.setColorAt(0.5, QColor(72, 92, 120))
    grad.setColorAt(1.0, QColor(146, 120, 96))
    painter.fillRect(canvas.rect(), grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(255, 255, 255, 26))
    painter.drawEllipse(QPoint(90, 120), 120, 120)
    painter.setOpacity(max(0.05, window.windowOpacity()))
    painter.drawPixmap(0, 0, pix)
    painter.end()
    canvas.save(str(path))
    print(f"        截图 {path.name}")

def center(window: FloatWindow, col: int, row: int) -> QPoint:
    return window.board.point_xy(col, row).toPoint()

def click(window: FloatWindow, col: int, row: int) -> None:
    QTest.mouseClick(
        window.board, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier, center(window, col, row),
    )

def main() -> int:
    app = QApplication(sys.argv)
    cfg = config.load_config()
    cfg["geometry"] = [40, 40, *SIZE]
    cfg["opacity"] = 0.95
    cfg["movetime_ms"] = 500
    cfg["debounce_ms"] = 120
    cfg["strength"] = "custom"
    cfg["auto_accept"] = False
    cfg["rule_mode"] = RULE_RENJU
    cfg["block_forbidden"] = True

    window = FloatWindow(cfg)
    window.resize(*SIZE)
    window.show()
    pump(app, 1.0)

    compose(window, OUT / "01_choose_side.png")

    print("\n-- 几何映射 --")
    board = window.board
    check("点位往返一致", all(
        board.square_at(board.point_xy(c, r)) == (c, r)
        for c in range(15) for r in range(15)
    ))
    check("棋盘为 15 路", board.session.size == 15, str(board.session.size))

    print("\n-- 执黑流程 --")
    window.choose_side(BLACK)
    pump(app, 0.4)
    check("执黑时未翻转", not window.session.flipped)
    check("黑先", window.session.turn == BLACK)

    got = wait_for(app, lambda: window._suggestion is not None, 20.0)
    check("开局给出建议", got,
          f"{pos_to_text(window._suggestion.col, window._suggestion.row)} "
          f"depth {window._suggestion.depth}" if got else "超时")
    compose(window, OUT / "02_suggestion.png")

    click(window, 7, 7)
    pump(app, 0.35)
    check("点击空点落子", window.session.ply == 1, str(window.session.ply))
    check("记谱为 h8", window.session.move_texts()[:1] == ["h8"],
          str(window.session.move_texts()[:1]))
    check("落子后轮到白方", window.session.turn == WHITE)

    click(window, 7, 7)
    pump(app, 0.2)
    check("点已占用点被拒", window.session.ply == 1)

    kept = window.board.suggestion
    check("轮对手时箭头转灰",
          kept is None or window.board.suggestion_stale,
          f"sug={kept} stale={window.board.suggestion_stale}")
    compose(window, OUT / "03_stale.png")

    print("\n-- 撤销 / 重做 --")
    window.undo()
    pump(app, 0.25)
    check("撤销", window.session.ply == 0)
    check("撤销后轮到黑方", window.session.turn == BLACK)
    window.redo()
    pump(app, 0.25)
    check("重做", window.session.ply == 1)

    print("\n-- 执白 --")
    window.new_game()
    pump(app, 0.3)
    window.choose_side(WHITE)
    pump(app, 0.4)
    check("执白时翻转", window.session.flipped)
    check("执白开局轮黑方", window.session.turn == BLACK)
    click(window, 7, 7)
    pump(app, 0.3)
    check("执白时仍可复刻对手落子", window.session.ply == 1)
    compose(window, OUT / "04_white.png")

    print("\n-- 禁手拦截 --")
    window.new_game()
    pump(app, 0.3)
    window.choose_side(BLACK)
    pump(app, 0.3)
    for col, row in [(5, 7), (0, 0), (6, 7), (0, 2), (7, 5), (0, 4), (7, 6), (0, 6)]:
        window.session.push(col, row)
    pump(app, 0.25)
    check("h8 被判为禁手", window.session.is_forbidden(7, 7))
    before = window.session.ply
    click(window, 7, 7)
    pump(app, 0.3)
    check("禁手点点击被拦截", window.session.ply == before, str(window.session.ply))
    check("状态栏提示禁手", "禁手" in window.header.status.text(),
          window.header.status.text())
    compose(window, OUT / "05_forbidden.png")

    print("\n-- 规则切换 --")
    window.set_rule_mode(RULE_FREESTYLE)
    pump(app, 0.6)
    check("切到无禁手", window.session.rule_mode == RULE_FREESTYLE)
    check("切换后历史清空", window.session.ply == 0)
    for col, row in [(5, 7), (0, 0), (6, 7), (0, 2), (7, 5), (0, 4), (7, 6), (0, 6)]:
        window.session.push(col, row)
    pump(app, 0.2)
    check("无禁手模式下 h8 不是禁手", not window.session.is_forbidden(7, 7))
    window.set_rule_mode(RULE_RENJU)
    pump(app, 0.6)
    check("切回连珠", window.session.rule_mode == RULE_RENJU)

    print("\n-- 胜负判定 --")
    window.new_game()
    pump(app, 0.3)
    window.choose_side(BLACK)
    pump(app, 0.3)
    seq = [(3, 7), (0, 0), (4, 7), (0, 2), (5, 7), (0, 4), (6, 7), (0, 6), (7, 7)]
    for col, row in seq:
        window.session.push(col, row)
    pump(app, 0.3)
    check("黑棋五连获胜", window.session.winner == BLACK, str(window.session.winner))
    check("对局结束", window.session.is_game_over())
    check("状态显示胜负", "胜" in window.header.status.text(),
          window.header.status.text())
    compose(window, OUT / "06_win.png")

    print("\n-- 自动采纳 --")
    window.new_game()
    pump(app, 0.3)
    window.choose_side(BLACK)
    pump(app, 0.2)
    window.header.btn_auto.setChecked(True)
    auto = wait_for(app, lambda: window.session.ply >= 1, 20.0)
    check("自动采纳生效", auto, str(window.session.move_texts()[:1]))
    window.undo()
    pump(app, 0.6)
    check("撤销后自动暂停", not window.cfg["auto_accept"])

    print("\n-- 紧凑模式 --")
    window.toggle_compact()
    pump(app, 0.3)
    check("紧凑模式隐藏底栏", not window.footer.isVisible())
    compose(window, OUT / "07_compact.png")
    window.toggle_compact()
    pump(app, 0.2)

    print("\n-- 强度预设 --")
    window.set_strength("fast")
    pump(app, 1.0)
    check("切轻快档", window.cfg["movetime_ms"] == 300, f"{window.cfg['movetime_ms']}ms")
    window.set_strength("balanced")
    pump(app, 1.0)
    check("切均衡档", window.cfg["movetime_ms"] == 800, f"{window.cfg['movetime_ms']}ms")
    check("换档后引擎就绪", window._engine_ok)

    print("\n-- 引擎缺失 --")
    saved = config.find_engine
    saved_path = window.cfg.get("engine_path")
    window._stop_engine()
    window.cfg["engine_path"] = ""
    config.find_engine = lambda explicit=None: None
    window._start_engine()
    pump(app, 0.4)
    check("缺引擎时状态栏说明原因", "未找到" in window.header.status.text(),
          window.header.status.text())
    window.choose_side(BLACK)
    pump(app, 0.3)
    check("选先后手后提示仍在", "未找到" in window.header.status.text())
    config.find_engine = saved
    window.cfg["engine_path"] = saved_path or ""
    window._start_engine()
    pump(app, 2.0)
    check("恢复引擎后就绪", window._engine_ok and window._engine_error is None)

    window.close()
    pump(app, 0.5)

    print(f"\n{'=' * 50}")
    print(f"结果: {OK} PASS / {BAD} FAIL")
    print("=" * 50)
    return 0 if BAD == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
