from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from PyQt6.QtCore import QThread, pyqtSignal

try:
    from pygomo import EngineClient
    from pygomo.protocol.models import BoardPosition, Move
except ImportError:
    EngineClient = None
    BoardPosition = None
    Move = None

BLACK = 1
WHITE = 2

@dataclass
class AnalysisResult:
    version: int = 0
    col: int = -1
    row: int = -1
    depth: int = 0
    winrate: float = 0.0
    nodes: int = 0
    pv: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    interrupted: bool = False

    @property
    def valid(self) -> bool:
        return self.col >= 0 and self.row >= 0

class EngineWorker(QThread):
    ready = pyqtSignal(str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(dict)
    analysisDone = pyqtSignal(object)

    def __init__(
        self,
        engine_path: str,
        rule_id: int = 4,
        movetime_ms: int = 800,
        threads: int = 4,
        hash_mb: int = 256,
        low_priority: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.engine_path = engine_path
        self.workdir = os.path.dirname(os.path.abspath(engine_path)) or None
        self.rule_id = rule_id
        self.movetime_ms = movetime_ms
        self.threads = threads
        self.hash_mb = hash_mb
        self.low_priority = low_priority

        self._client = None
        self._running = True
        self._lock = None
        self._task: dict | None = None
        self._wake = None
        self._engine_name = ""

    def submit(self, version: int, moves: list[tuple[int, int, int]], movetime_ms: int) -> None:

        import threading

        if self._lock is None:
            self._lock = threading.Lock()
        with self._lock:
            self._task = {"version": version, "moves": moves, "ms": int(movetime_ms)}
        if self._wake is not None:
            self._wake.set()

    def cancel(self) -> None:
        import threading

        if self._lock is None:
            self._lock = threading.Lock()
        with self._lock:
            self._task = None
        if self._wake is not None:
            self._wake.set()

    def set_rule(self, rule_id: int) -> None:
        self.rule_id = rule_id
        if self._client is not None:
            try:
                self._client.send_raw(f"INFO RULE {rule_id}")
            except Exception:
                pass

    def shutdown(self) -> None:
        self._running = False
        self.cancel()

    def run(self) -> None:
        import threading

        if EngineClient is None:
            self.failed.emit("未安装 pygomo-lib，请先运行 install.bat")
            return
        if not os.path.isfile(self.engine_path):
            self.failed.emit("未找到 Rapfi 引擎，请把 pbrain-rapfi-*.exe 放到 engine\\ 目录")
            return

        self._wake = threading.Event()
        try:
            self._client = EngineClient(
                self.engine_path, working_directory=self.workdir
            )
            self._client.connect()
            self._configure()
            self.ready.emit(self._engine_name or "Rapfi")
            self._loop()
        except Exception as exc:
            self.failed.emit(f"引擎异常：{type(exc).__name__}: {exc}")
        finally:
            self._teardown()

    def _configure(self) -> None:
        assert self._client is not None
        about = ""
        try:
            about = self._client.about() or ""
        except Exception:
            pass
        if 'name="' in about:
            self._engine_name = about.split('name="', 1)[1].split('"', 1)[0]

        self._client.send_raw("START 15")
        time.sleep(0.12)
        self._client.send_raw(f"INFO RULE {self.rule_id}")
        self._client.send_raw(f"INFO TIMEOUT_TURN {self.movetime_ms}")
        self._client.send_raw(f"INFO THREAD_NUM {self.threads}")
        self._client.send_raw(f"INFO MAX_MEMORY {self.hash_mb * 1024 * 1024}")
        self._client.send_raw("INFO SHOW_DETAIL 2")
        time.sleep(0.12)
        self._lower_priority()

    def _lower_priority(self) -> None:
        if not self.low_priority or os.name != "nt" or self._client is None:
            return
        pid = getattr(self._client, "process_id", None)
        if not pid:
            return
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0200 | 0x0400, False, int(pid))
            if handle:
                kernel32.SetPriorityClass(handle, 0x00004000)
                kernel32.CloseHandle(handle)
        except Exception:
            pass

    def _loop(self) -> None:
        while self._running:
            task = None
            if self._lock is not None:
                with self._lock:
                    task = self._task
                    self._task = None
            if task is None:
                if self._wake is not None:
                    self._wake.wait(0.05)
                    self._wake.clear()
                continue
            self._analyse(task)

    def _analyse(self, task: dict) -> None:
        assert self._client is not None
        started = time.monotonic()
        version = int(task["version"])
        moves = task["moves"]
        ms = int(task["ms"])

        try:
            self._client.send_raw(f"INFO TIMEOUT_TURN {ms}")
            position = BoardPosition(
                moves=[(Move((col, row)), color) for col, row, color in moves]
            )
            result = self._client.board(position)
        except Exception as exc:
            self.analysisDone.emit(
                AnalysisResult(
                    version=version, interrupted=True,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            )
            self.failed.emit(f"分析失败：{type(exc).__name__}: {exc}")
            return

        elapsed = int((time.monotonic() - started) * 1000)
        if result is None or result.move is None:
            self.analysisDone.emit(
                AnalysisResult(version=version, elapsed_ms=elapsed)
            )
            return

        info = result.search_info
        winrate = 0.0
        depth = 0
        nodes = 0
        pv: list[str] = []
        if info is not None:
            depth = int(info.depth or 0)
            nodes = int(info.nodes or 0)
            if info.eval is not None:
                try:
                    winrate = float(info.eval.winrate_percent())
                except Exception:
                    winrate = 0.0
            if info.pv:
                pv = [str(m) for m in info.pv]

        self.analysisDone.emit(
            AnalysisResult(
                version=version,
                col=int(result.move.col),
                row=int(result.move.row),
                depth=depth,
                winrate=winrate,
                nodes=nodes,
                pv=pv,
                elapsed_ms=elapsed,
            )
        )

    def _teardown(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            client.send_raw("END")
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass
