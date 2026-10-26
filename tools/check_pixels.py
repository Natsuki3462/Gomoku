from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from PyQt6.QtWidgets import QApplication

import config
from float_window import FloatWindow
from session import BLACK, RULE_FREESTYLE, RULE_RENJU

OK = 0
BAD = 0
BG = (226, 190, 138)

def check(label: str, good: bool, detail: str = "") -> None:
    global OK, BAD
    if good:
        OK += 1
    else:
        BAD += 1
    print(f"  [{'PASS' if good else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")

def near(a, b, tol=30) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a[:3], b[:3]))

class Probe:
    def __init__(self, image) -> None:
        self.img = image

    def colors(self, x0, y0, x1, y1, step: int = 1):
        out = []
        for y in range(int(y0), int(y1), step):
            for x in range(int(x0), int(x1), step):
                if 0 <= x < self.img.width() and 0 <= y < self.img.height():
                    out.append(self.img.pixelColor(x, y).getRgb()[:3])
        return out

    def count(self, x0, y0, x1, y1, predicate, step: int = 1) -> int:
        return sum(1 for c in self.colors(x0, y0, x1, y1, step) if predicate(c))

    def modal(self, x0, y0, x1, y1, step: int = 1):
        colors = self.colors(x0, y0, x1, y1, step)
        if not colors:
            return (0, 0, 0), 0.0
        color, hits = Counter(colors).most_common(1)[0]
        return color, hits / len(colors)

def main() -> int:
    app = QApplication(sys.argv)
    cfg = config.load_config()
    cfg["geometry"] = [40, 40, 470, 560]
    cfg["movetime_ms"] = 400
    cfg["debounce_ms"] = 120
    cfg["auto_accept"] = False
    cfg["strength"] = "custom"
    cfg["rule_mode"] = RULE_RENJU
    cfg["block_forbidden"] = True

    window = FloatWindow(cfg)
    window.resize(470, 560)
    window.show()

    def pump(seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    pump(1.0)
    window.choose_side(BLACK)
    pump(0.5)

    board = window.board
    rect = board.board_rect()
    cell = board.cell()
    r = board.stone_radius()
    print(f"\n棋盘 {board.width()}x{board.height()}  网格 {rect.width():.0f}x"
          f"{rect.height():.0f}  格距 {cell:.1f}  棋子半径 {r:.1f}")

    probe = Probe(board.grab().toImage())

    print("\n-- 1. 棋盘底色 --")
    color, ratio = probe.modal(rect.x() + cell * 0.3, rect.y() + cell * 0.3,
                               rect.right() - cell * 0.3, rect.bottom() - cell * 0.3, 3)
    check("木质底色占主导", near(color, BG, 20) and ratio > 0.55,
          f"主色 {color} 占比 {ratio:.0%}")

    print("\n-- 2. 网格线 --")
    top_line = probe.count(rect.x() + cell * 0.5, rect.y() - 2,
                           rect.right() - cell * 0.5, rect.y() + 3,
                           lambda c: not near(c, BG, 26))
    check("顶部横线", top_line >= 80, f"{top_line}")
    left_line = probe.count(rect.x() - 2, rect.y() + cell * 0.5,
                            rect.x() + 3, rect.bottom() - cell * 0.5,
                            lambda c: not near(c, BG, 26))
    check("左侧竖线", left_line >= 80, f"{left_line}")

    print("\n-- 3. 星位 --")
    star = board.point_xy(3, 3)
    star_hits = probe.count(star.x() - cell * 0.14, star.y() - cell * 0.14,
                            star.x() + cell * 0.14, star.y() + cell * 0.14,
                            lambda c: near(c, (72, 48, 26), 40))
    check("天元有星位点", star_hits >= 4, f"{star_hits}")

    print("\n-- 4. 棋子 --")
    window.session.push(7, 7)
    pump(0.3)
    probe2 = Probe(board.grab().toImage())
    center = board.point_xy(7, 7)
    dark = probe2.count(center.x() - r * 0.55, center.y() - r * 0.55,
                        center.x() + r * 0.55, center.y() + r * 0.55,
                        lambda c: max(c) < 90)
    check("黑子为深色实心", dark >= 60, f"{dark}")

    window.session.push(6, 7)
    pump(0.3)
    probe3 = Probe(board.grab().toImage())
    wcenter = board.point_xy(6, 7)
    light = probe3.count(wcenter.x() - r * 0.55, wcenter.y() - r * 0.55,
                         wcenter.x() + r * 0.55, wcenter.y() + r * 0.55,
                         lambda c: min(c) > 200)
    check("白子为浅色实心", light >= 60, f"{light}")

    print("\n-- 5. 最后一手标记 --")
    last = window.session.last_move
    lcenter = board.point_xy(last.col, last.row)
    ring = probe3.count(lcenter.x() - r * 0.45, lcenter.y() - r * 0.45,
                        lcenter.x() + r * 0.45, lcenter.y() + r * 0.45,
                        lambda c: c[0] > 170 and c[0] > c[1] + 60 and c[0] > c[2] + 60)
    check("最后一手有红圈", ring >= 6, f"{ring}")

    print("\n-- 6. 建议环（独立棋盘，避免引擎结果覆盖）--")
    from board_view import BoardView
    from session import Session

    solo_session = Session()
    solo = BoardView(solo_session)
    solo.resize(460, 460)
    solo.show()
    pump(0.3)
    sr = solo.stone_radius()
    solo.set_suggestion((9, 9), stale=False)
    pump(0.3)
    probe4 = Probe(solo.grab().toImage())
    scenter = solo.point_xy(9, 9)
    green = probe4.count(scenter.x() - sr * 1.3, scenter.y() - sr * 1.3,
                         scenter.x() + sr * 1.3, scenter.y() + sr * 1.3,
                         lambda c: c[1] > c[0] + 25 and c[1] > c[2] + 25)
    check("建议点是绿色环", green >= 30, f"{green}")

    solo.set_suggestion((9, 9), stale=True)
    pump(0.3)
    probe5 = Probe(solo.grab().toImage())
    gray = probe5.count(scenter.x() - sr * 1.3, scenter.y() - sr * 1.3,
                        scenter.x() + sr * 1.3, scenter.y() + sr * 1.3,
                        lambda c: abs(c[0] - c[1]) < 26 and abs(c[1] - c[2]) < 26
                        and max(c) > 90)
    check("陈旧建议变灰", gray >= 20, f"{gray}")
    solo.close()

    print("\n-- 7. 禁手叉号 --")
    window.new_game()
    pump(0.3)
    window.choose_side(BLACK)
    pump(0.3)
    for col, row in [(5, 7), (0, 0), (6, 7), (0, 2), (7, 5), (0, 4), (7, 6), (0, 6)]:
        window.session.push(col, row)
    board._hover = (7, 7)
    pump(0.3)
    probe6 = Probe(board.grab().toImage())
    fcenter = board.point_xy(7, 7)
    red = probe6.count(fcenter.x() - r * 0.7, fcenter.y() - r * 0.7,
                       fcenter.x() + r * 0.7, fcenter.y() + r * 0.7,
                       lambda c: c[0] > 180 and c[0] > c[1] + 70 and c[0] > c[2] + 70)
    check("禁手点显示红叉", red >= 20, f"{red}")
    board._hover = None

    window.close()
    pump(0.3)

    print(f"\n{'=' * 46}")
    print(f"像素校验: {OK} PASS / {BAD} FAIL")
    print("=" * 46)
    return 0 if BAD == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
