from __future__ import annotations

import queue
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "pbrain-rapfi-windows-avxvnni.exe"
WORKDIR = ROOT / "engine"

SEQ_5 = [
    ("d8", 1), ("a1", 2), ("e8", 1), ("a3", 2), ("f8", 1),
    ("a5", 2), ("g8", 1), ("a7", 2), ("h8", 1), ("a9", 2),
]

ALG = "abcdefghijklmno"

def to_num(text: str) -> tuple[int, int]:
    return (ALG.index(text[0]) + 1, int(text[1:]))

def to_alg(col: int, row: int) -> str:
    return f"{ALG[col - 1]}{row}"

class Engine:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [str(ENGINE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1, cwd=str(WORKDIR),
        )
        self.lines: queue.Queue = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))

    def send(self, cmd: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def drain(self, seconds: float) -> list[str]:
        out = []
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                out.append(self.lines.get(timeout=0.05))
            except queue.Empty:
                pass
        return [ln for ln in out if not ln.startswith("MESSAGE Large")
                and not ln.startswith("MESSAGE Load")
                and not ln.startswith("MESSAGE Evaluator")]

    def suggest(self, seq, rule: int, ms: int = 1500) -> str:
        self.send("START 15")
        self.drain(0.4)
        self.send(f"INFO RULE {rule}")
        self.drain(0.3)
        self.send(f"INFO TIMEOUT_TURN {ms}")
        self.send("INFO THREAD_NUM 4")
        self.send("INFO MAX_MEMORY 268435456")
        self.send("BOARD")
        for mv, color in seq:
            col, row = to_num(mv)
            self.send(f"{col},{row},{color}")
        self.send("DONE")
        out = self.drain(ms / 1000.0 + 2.0)
        for ln in out:
            s = ln.strip()
            if "," in s and s.replace(",", "").isdigit() and len(s.split(",")) == 2:
                col, row = (int(v) for v in s.split(","))
                return to_alg(col, row)
        return f"<无着法> {out[-3:]}"

print("局面：黑 d8 e8 f8 g8 h8（已有 5 连），两端 c8 / i8 可走成 6")
print("黑棋走 c8 或 i8 = 6 连")
print("  freestyle：应立刻走成 6（赢）")
print("  连珠模式  ：成 6 是长连禁手，必须避开")
print()

for rule, label in ((0, "规则0 freestyle"), (1, "规则1 standard"), (4, "规则4 连珠")):
    eng = Engine()
    try:
        move = eng.suggest(SEQ_5, rule, ms=1500)
        makes_six = move in ("c8", "i8")
        print(f"{label:14s} 建议 = {move:5s}  "
              f"{'→ 走成 6 连（赢）' if makes_six else '→ 避开了长连'}")
    finally:
        eng.send("END")
        eng.drain(0.3)
        try:
            eng.proc.wait(timeout=3)
        except Exception:
            eng.proc.kill()
    print()

print("判定：两种模式建议不同 → set_rule 生效且禁手被遵守")
