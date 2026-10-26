from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from PyQt6.QtWidgets import QApplication

from session import (
    BLACK,
    BOARD_SIZE,
    RULE_FREESTYLE,
    RULE_RENJU,
    WHITE,
    Session,
    pos_to_text,
    text_to_pos,
)

OK = 0
BAD = 0

DOUBLE_THREE = [(5, 7), (0, 0), (6, 7), (0, 2), (7, 5), (0, 4), (7, 6), (0, 6)]
FIVE_BLACK = [(3, 7), (0, 0), (4, 7), (0, 2), (5, 7), (0, 4), (6, 7), (0, 6), (7, 7)]

def check(label: str, good: bool, detail: str = "") -> None:
    global OK, BAD
    if good:
        OK += 1
    else:
        BAD += 1
    print(f"  [{'PASS' if good else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")

def build(seq, rule=RULE_RENJU):
    s = Session()
    s.rule_mode = rule
    s.reset(BLACK)
    for col, row in seq:
        s.push(col, row)
    return s

def main() -> int:
    app = QApplication(sys.argv)

    print("=" * 60)
    print("规则层校验")
    print("=" * 60)

    print("\n-- 1. 坐标与棋盘 --")
    check("棋盘 15 路", BOARD_SIZE == 15)
    check("h8 <-> (7,7)", text_to_pos("h8") == (7, 7) and pos_to_text(7, 7) == "h8")
    check("a1 <-> (0,0)", text_to_pos("a1") == (0, 0) and pos_to_text(0, 0) == "a1")
    check("o15 <-> (14,14)",
          text_to_pos("o15") == (14, 14) and pos_to_text(14, 14) == "o15")

    print("\n-- 2. 落子与轮次 --")
    s = Session()
    check("黑先", s.turn == BLACK)
    check("落子成功", s.push(7, 7))
    check("轮到白方", s.turn == WHITE)
    check("重复落子被拒", not s.push(7, 7))
    check("越界被拒", not s.push(15, 0))
    check("历史记录正确", s.move_texts() == ["h8"], str(s.move_texts()))

    print("\n-- 3. 双三禁手（连珠）--")
    s = build(DOUBLE_THREE)
    check("轮到黑方", s.turn == BLACK, s.turn_name)
    check("h8 被判为禁手", s.is_forbidden(7, 7))
    check("拦截开启时无法落子", not s.push(7, 7))
    check("禁手点未落子", s.is_empty(7, 7))
    check("force 可强制落子", s.push(7, 7, force=True))

    print("\n-- 4. 白棋无禁手 --")
    s = Session()
    s.reset(BLACK)

    for col, row in [(0, 0), (5, 7), (0, 2), (6, 7), (0, 4), (7, 5), (0, 6), (7, 6),
                     (0, 8)]:
        s.push(col, row)
    check("轮到白方", s.turn == WHITE, s.turn_name)
    check("白棋同形状不算禁手", not s.is_forbidden(7, 7))

    print("\n-- 5. 五连胜负（连珠）--")
    s = build(FIVE_BLACK)
    check("黑棋五连获胜", s.winner == BLACK, str(s.winner))
    check("对局结束", s.is_game_over())
    check("胜负文案", "胜" in s.win_text(), s.win_text())
    check("结束后无法落子", not s.push(10, 10))

    print("\n-- 6. 长连规则差异 --")

    GAP_SEQ = [(3, 7), (0, 0), (4, 7), (0, 2), (6, 7), (0, 4),
               (7, 7), (0, 6), (8, 7), (0, 8)]

    s = Session()
    s.rule_mode = RULE_FREESTYLE
    s.reset(BLACK)
    for col, row in GAP_SEQ:
        s.push(col, row)
    check("无禁手：轮到黑方", s.turn == BLACK, s.turn_name)
    check("无禁手：填隙前未获胜", s.winner is None, str(s.winner))
    ok = s.push(5, 7)
    check("无禁手：长连可落子", ok)
    check("无禁手：长连算赢", s.winner == BLACK, str(s.winner))

    s2 = Session()
    s2.rule_mode = RULE_RENJU
    s2.reset(BLACK)
    for col, row in GAP_SEQ:
        s2.push(col, row)
    check("连珠：轮到黑方", s2.turn == BLACK, s2.turn_name)
    check("连珠：填隙是长连禁手", s2.is_forbidden(5, 7))
    check("连珠：长连被拦", not s2.push(5, 7))
    check("连珠：未判赢", s2.winner is None, str(s2.winner))

    print("\n-- 7. 规则切换 --")
    s = build(DOUBLE_THREE)
    check("切换前有历史", s.ply == 8)
    check("切到无禁手", s.set_rule_mode(RULE_FREESTYLE))
    check("切换后历史清空", s.ply == 0, str(s.ply))
    check("切换后棋盘为空", s.is_empty(5, 7))
    check("无禁手下 h8 非禁手", not s.is_forbidden(7, 7))
    check("切回连珠", s.set_rule_mode(RULE_RENJU))
    check("重复切换返回 False", not s.set_rule_mode(RULE_RENJU))

    print("\n-- 8. 撤销 / 重做 / 回退 --")
    s = Session()
    for col, row in [(7, 7), (8, 8), (6, 6)]:
        s.push(col, row)
    check("三步历史", s.ply == 3)
    check("撤销", s.undo() and s.ply == 2)
    check("撤销后轮次正确", s.turn == BLACK, s.turn_name)
    check("重做", s.redo() and s.ply == 3)
    check("回退到第 1 手", s.jump_to(1) and s.ply == 1)
    check("回退后轮次正确", s.turn == WHITE, s.turn_name)
    check("回退后棋盘只剩一子", s.at(7, 7) == BLACK and s.is_empty(8, 8))

    print("\n-- 9. 撤销后胜负状态复位 --")
    s = build(FIVE_BLACK)
    check("先获胜", s.winner == BLACK)
    s.undo()
    check("撤销后 winner 清空", s.winner is None, str(s.winner))
    check("撤销后可继续落子", s.is_empty(7, 7))

    print("\n-- 10. 禁手列表 --")
    s = build(DOUBLE_THREE)
    pts = s.forbidden_points()
    check("能列出禁手点", (7, 7) in pts, str(pts[:5]))
    s.set_rule_mode(RULE_FREESTYLE)
    check("无禁手模式下列表为空", s.forbidden_points() == [])

    print(f"\n{'=' * 60}")
    print(f"规则校验: {OK} PASS / {BAD} FAIL")
    print("=" * 60)
    return 0 if BAD == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
