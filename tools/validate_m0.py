from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".venv" / "Lib" / "site-packages"))

from pygomo import EngineClient
from pygomo.board import RenjuBitBoard
from pygomo.protocol.models import BoardPosition, Move

ENGINE = ROOT / "engine" / "pbrain-rapfi-windows-avxvnni.exe"
WORKDIR = ROOT / "engine"

OK = 0
BAD = 0

def check(label: str, good: bool, detail: str = "") -> None:
    global OK, BAD
    if good:
        OK += 1
    else:
        BAD += 1
    print(f"  [{'PASS' if good else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")

def section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)

SEQ_5_IN_ROW = [
    ("d8", 1), ("a1", 2), ("e8", 1), ("a3", 2), ("f8", 1),
    ("a5", 2), ("g8", 1), ("a7", 2), ("h8", 1), ("a9", 2),
]

SEQ_DOUBLE_THREE = [
    ("f8", 1), ("a1", 2), ("g8", 1), ("a3", 2),
    ("h6", 1), ("a5", 2), ("h7", 1), ("a7", 2),
]

SEQ_WHITE_OVERLINE = [
    ("a1", 1), ("d8", 2), ("a3", 1), ("e8", 2), ("a5", 1), ("f8", 2),
    ("a7", 1), ("g8", 2), ("a9", 1), ("h8", 2), ("a11", 1),
]

def pos(seq) -> BoardPosition:
    return BoardPosition(moves=[(Move(mv), color) for mv, color in seq])

def make_engine(rule: int, ms: int = 1200, threads: int = 4, mem_mb: int = 256):
    engine = EngineClient(str(ENGINE), working_directory=str(WORKDIR))
    engine.connect()
    engine.send_raw("START 15")
    time.sleep(0.2)
    engine.send_raw(f"INFO RULE {rule}")
    engine.send_raw(f"INFO TIMEOUT_TURN {ms}")
    engine.send_raw(f"INFO THREAD_NUM {threads}")
    engine.send_raw(f"INFO MAX_MEMORY {mem_mb * 1024 * 1024}")
    engine.send_raw("INFO SHOW_DETAIL 2")
    time.sleep(0.2)
    return engine

def think(engine, sequence) -> str | None:
    result = engine.board(pos(sequence))
    if result is None or result.move is None:
        return None
    return str(result.move)

def main() -> int:
    section("M0-1 确认 pygomo set_rule 失效")
    engine = make_engine(4)
    res = engine.execute("INFO RULE 4")
    print(f"  execute('INFO RULE 4'): success={res.is_success} error={res.error}")
    check("记录：set_rule 走路由会失败", not res.is_success)
    engine.send_raw("END")
    engine.disconnect()

    section("M0-2 决定性验证：黑棋长连（已有 5 连，两端可成 6）")
    print("  期望：freestyle 走成 6（算赢）；renju 避开（长连禁手）")
    results = {}
    for rule, label in ((0, "freestyle"), (1, "standard"), (4, "renju")):
        eng = make_engine(rule)
        try:
            mv = think(eng, SEQ_5_IN_ROW)
        finally:
            eng.send_raw("END")
            eng.disconnect()
        results[rule] = mv
        makes_six = mv in ("c8", "i8")
        print(f"    rule {rule} {label:10s} -> {str(mv):5s}  "
              f"{'走成 6 连' if makes_six else '避开长连'}")
    check("freestyle 允许长连", results[0] in ("c8", "i8"), str(results[0]))
    check("renju 拒绝长连", results[4] not in ("c8", "i8"), str(results[4]))
    check("freestyle 与 renju 行为不同", results[0] != results[4])

    section("M0-3 白棋长连（连珠下应允许并获胜）")
    eng = make_engine(4)
    try:
        mv = think(eng, SEQ_WHITE_OVERLINE)
        print(f"  连珠规则，白棋已有 d8~h8 五连，轮白走 -> {mv}")
        check("白棋可走成 6 连", mv in ("i8", "c8"), str(mv))
    finally:
        eng.send_raw("END")
        eng.disconnect()

    section("M0-4 双三：本地判定 vs 引擎建议")
    local = RenjuBitBoard(15)
    for mv, _ in SEQ_DOUBLE_THREE:
        local.place(Move(mv))
    forbidden = local.is_forbidden(Move("h8"))
    print(f"  本地 RenjuBitBoard.is_forbidden(h8) = {forbidden}")
    check("本地判定 h8 为双三禁手", forbidden is True)

    for rule, label in ((0, "freestyle"), (4, "renju")):
        eng = make_engine(rule, ms=2000)
        try:
            mv = think(eng, SEQ_DOUBLE_THREE)
            print(f"    rule {rule} {label:10s} -> 建议 {mv}")
            if rule == 4:
                check("renju 下建议不是禁手点 h8", mv != "h8", str(mv))
        finally:
            eng.send_raw("END")
            eng.disconnect()

    section("M0-5 引擎是否拒绝喂进去的禁手着法")
    eng = make_engine(4, ms=600)
    try:
        eng.board(pos(SEQ_DOUBLE_THREE), start_thinking=False)
        try:
            r = eng.turn(Move("h8"), timeout=20)
            verdict = "接受" if r is not None else "拒绝(None)"
        except Exception as exc:
            verdict = f"抛异常 {type(exc).__name__}"
        print(f"  连珠规则下 turn(h8) -> {verdict}")
        print("  => TURN 是「对手落子」语义，引擎不做禁手校验，本地必须自己守门")
    finally:
        eng.send_raw("END")
        eng.disconnect()

    section("M0-6 API 疑点")
    eng = make_engine(4)
    try:
        check("能拿到引擎 pid", eng.process_id is not None, str(eng.process_id))
        r = eng.board(pos(SEQ_DOUBLE_THREE))
        check("board() 自动思考并返回建议",
              r is not None and r.move is not None,
              str(r.move) if r else "None")
        if r and r.search_info:
            info = r.search_info
            wr = info.eval.winrate_percent() if info.eval else 0
            print(f"    depth={info.depth} nodes={info.nodes} 胜率={wr:.0f}% "
                  f"pv={' '.join(str(m) for m in info.pv[:4])}")
            check("search_info 字段可用", info.depth > 0,
                  f"depth={info.depth} nodes={info.nodes}")
            if info.nodes == 0:
                print("    注：nodes 恒为 0 是 Rapfi 的 detail 输出特性，"
                      "不影响胜率与深度，UI 不依赖它")
    finally:
        eng.send_raw("END")
        eng.disconnect()

    section("M0-7 耗时曲线（定强度预设用）")
    print(f"  {'限时':>8} {'实测':>9} {'深度':>6} {'节点':>10} {'着法':>6}")
    for ms in (300, 800, 1500, 3000):
        eng = make_engine(4, ms=ms)
        try:
            t0 = time.monotonic()
            r = eng.board(pos(SEQ_DOUBLE_THREE))
            dt = (time.monotonic() - t0) * 1000
            if r and r.search_info:
                print(f"  {ms:>6}ms {dt:>7.0f}ms {r.search_info.depth:>6} "
                      f"{r.search_info.nodes:>10} {str(r.move):>6}")
            else:
                print(f"  {ms:>6}ms {dt:>7.0f}ms 无结果")
        finally:
            eng.send_raw("END")
            eng.disconnect()

    section("汇总")
    print(f"  PASS {OK} / FAIL {BAD}")
    return 0 if BAD == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
