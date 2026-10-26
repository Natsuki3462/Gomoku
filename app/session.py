from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from pygomo.board import BitBoard, RenjuBitBoard
from pygomo.protocol.models import Move

BOARD_SIZE = 15
BLACK = 1
WHITE = 2

RULE_FREESTYLE = "freestyle"
RULE_RENJU = "renju"
RULE_LABELS = {
    RULE_FREESTYLE: "无禁手",
    RULE_RENJU: "连珠（有禁手）",
}
RULE_IDS = {RULE_FREESTYLE: 0, RULE_RENJU: 4}

ALG = "abcdefghijklmno"

Pos = tuple[int, int]

def make_move(col: int, row: int) -> Move:
    return Move((col, row))

def pos_to_text(col: int, row: int) -> str:
    return f"{ALG[col]}{row + 1}"

def text_to_pos(text: str) -> Pos:
    return (ALG.index(text[0]), int(text[1:]) - 1)

def color_name(color: int) -> str:
    return "黑方" if color == BLACK else "白方"

class Session(QObject):
    positionChanged = pyqtSignal(int)
    historyChanged = pyqtSignal()
    ruleChanged = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.rule_mode = RULE_RENJU
        self.my_color = BLACK
        self.flipped = False
        self.version = 0
        self.block_forbidden = True
        self._board = self._new_board()
        self._stack: list[Move] = []
        self._snaps: list = []
        self._redo: list[Move] = []
        self._winner: int | None = None

    def _new_board(self):
        if self.rule_mode == RULE_RENJU:
            return RenjuBitBoard(BOARD_SIZE)
        return BitBoard(BOARD_SIZE)

    @property
    def board(self):
        return self._board

    @property
    def size(self) -> int:
        return BOARD_SIZE

    @property
    def ply(self) -> int:
        return len(self._stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def turn(self) -> int:
        return self._board.current_player

    @property
    def is_my_turn(self) -> bool:
        return self.turn == self.my_color and self._winner is None

    @property
    def turn_name(self) -> str:
        return color_name(self.turn)

    @property
    def my_name(self) -> str:
        return color_name(self.my_color)

    @property
    def last_move(self) -> Move | None:
        return self._board.last_move

    @property
    def winner(self) -> int | None:
        return self._winner

    @property
    def history(self) -> list[Move]:
        return list(self._stack)

    def at(self, col: int, row: int) -> int:
        return self._board.get(make_move(col, row))

    def is_empty(self, col: int, row: int) -> bool:
        try:
            return self._board.is_empty(make_move(col, row))
        except Exception:
            return False

    def is_on_board(self, col: int, row: int) -> bool:
        return 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE

    def is_game_over(self) -> bool:
        return self._winner is not None or self._board.is_full()

    def is_forbidden(self, col: int, row: int) -> bool:

        if self.rule_mode != RULE_RENJU or self.turn != BLACK:
            return False
        if not self.is_on_board(col, row) or not self.is_empty(col, row):
            return False
        try:
            return bool(self._board.is_forbidden(make_move(col, row)))
        except Exception:
            return False

    def forbidden_points(self) -> list[Pos]:
        if self.rule_mode != RULE_RENJU or self.turn != BLACK:
            return []
        try:
            return [(m.col, m.row) for m in self._board.get_forbidden_moves()]
        except Exception:
            return []

    def push(self, col: int, row: int, force: bool = False) -> bool:
        if self._winner is not None:
            return False
        if not self.is_on_board(col, row) or not self.is_empty(col, row):
            return False
        if self.block_forbidden and not force and self.is_forbidden(col, row):
            return False

        move = make_move(col, row)
        self._snaps.append(self._board.copy())
        if not self._place(move, force):
            self._snaps.pop()
            return False
        self._stack.append(move)
        self._redo.clear()
        self._update_winner(move)
        self._bump()
        return True

    def _place(self, move: Move, force: bool = False) -> bool:

        if force and self.rule_mode == RULE_RENJU:
            return bool(BitBoard.place(self._board, move))
        return bool(self._board.place(move))

    def _update_winner(self, move: Move) -> None:
        try:
            info = self._board.check_win(move)
        except Exception:
            info = None
        if info is not None:
            self._winner = getattr(info, "winner", None)
        else:
            self._winner = None

    def undo(self) -> bool:
        if not self._stack or not self._snaps:
            return False
        move = self._stack.pop()
        self._board = self._snaps.pop()
        self._redo.append(move)
        self._winner = None
        self._bump()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        move = self._redo.pop()
        self._snaps.append(self._board.copy())
        if not self._place(move):
            self._snaps.pop()
            return False
        self._stack.append(move)
        self._update_winner(move)
        self._bump()
        return True

    def jump_to(self, ply: int) -> bool:
        target = max(0, min(ply, self.ply + len(self._redo)))
        if target == self.ply:
            return False
        if target < self.ply:
            while self.ply > target:
                move = self._stack.pop()
                self._board = self._snaps.pop()
                self._redo.append(move)
        else:
            pending = list(reversed(self._redo))
            self._redo = []
            need = target - self.ply
            for index, move in enumerate(pending):
                if index >= need:
                    self._redo.append(move)
                    continue
                self._snaps.append(self._board.copy())
                if not self._place(move):
                    self._snaps.pop()
                    continue
                self._stack.append(move)
            self._redo = list(reversed(self._redo))
        self._winner = None
        if self._stack:
            self._update_winner(self._stack[-1])
        self._bump()
        return True

    def reset(self, my_color: int | None = None) -> None:
        if my_color is not None:
            self.my_color = my_color
        self._board = self._new_board()
        self._stack.clear()
        self._snaps.clear()
        self._redo.clear()
        self._winner = None
        self._bump()

    def set_rule_mode(self, mode: str) -> bool:

        if mode not in (RULE_FREESTYLE, RULE_RENJU) or mode == self.rule_mode:
            return False
        self.rule_mode = mode
        self._board = self._new_board()
        self._stack.clear()
        self._snaps.clear()
        self._redo.clear()
        self._winner = None
        self.ruleChanged.emit(mode)
        self._bump()
        return True

    def toggle_flip(self) -> None:
        self.flipped = not self.flipped
        self.historyChanged.emit()

    def move_texts(self) -> list[str]:
        return [pos_to_text(m.col, m.row) for m in self._stack]

    def win_text(self) -> str:
        if self._winner is None:
            if self._board.is_full():
                return "棋盘已满 · 和棋"
            return ""
        side = color_name(self._winner)
        mine = "（你赢了）" if self._winner == self.my_color else "（你输了）"
        return f"{side}胜{mine}"

    def _bump(self) -> None:
        self.version += 1
        self.historyChanged.emit()
        self.positionChanged.emit(self.version)
