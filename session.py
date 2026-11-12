"""Application actions and information shown beside the board."""

import json
from pathlib import Path
from typing import Any

from computer import choose_move
from game import (
    legal_moves,
    move,
    new_position,
    status,
    winner,
)

# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"),
    ("h7", "h5"),
    ("a4", "a5"),
    ("h5", "h4"),
    ("a5", "a6"),
    ("h4", "h3"),
    ("a6", "b7"),
    ("h3", "g2"),
]

# Saved in the current directory; *.save.json is ignored by git.
SAVE_FILE = "game.save.json"

# One played move: (source, target, promotion). Promotion is None when there was none.
Move = tuple[str, str, str | None]


class Session:
    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.opponent = opponent
        # The game's history. Everything else can be rebuilt by replaying self.moves.
        self.moves: list[Move] = []
        self.redo: list[Move] = []

    def play(self, source, target):
        label = move(self.position, source, target)
        self.notation.append(label)
        self.moves.append((source, target, None))
        self.after_move()

    def rebuild(self) -> None:
        """Rebuild the position and notation by replaying the moves from the start."""
        self.position = new_position()
        self.notation = []
        for source, target, _promotion in self.moves:
            self.notation.append(move(self.position, source, target))
        self.after_move()

    def undo(self) -> None:
        """Take back the last move; against the computer, back to the player's turn."""
        while self.moves:
            removed = len(self.moves) - 1
            self.moves.pop()
            # White (the player) makes the even-numbered moves.
            if self.opponent != "computer" or removed % 2 == 0:
                break
        self.rebuild()

    def save(self) -> None:
        data = {"opponent": self.opponent, "moves": self.moves, "redo": self.redo}
        try:
            Path(SAVE_FILE).write_text(json.dumps(data))
        except OSError as error:
            raise ValueError(f"Could not save the game: {error.strerror}") from error

    def load(self) -> None:
        """Replace the game with the saved one. On any error, the game is unchanged."""
        try:
            text = Path(SAVE_FILE).read_text()
        except FileNotFoundError:
            raise ValueError("No saved game to load") from None
        except OSError as error:
            raise ValueError(
                f"Could not read the saved game: {error.strerror}"
            ) from error
        try:
            loaded = replay(json.loads(text))
        except (ValueError, TypeError) as error:
            raise ValueError(f"The saved game is invalid: {error}") from None
        self.__dict__.update(loaded.__dict__)

    def after_move(self):
        pass

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (
            self.opponent == "computer"
            and self.position[1] == "b"
            and status(self.position) not in ("checkmate", "stalemate")
        )

    def sidebar(self):
        return {}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "undo":
            self.undo()
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            self.save()
        elif command == "load":
            self.load()
        else:
            raise ValueError("Unknown action")
        return self.view()


def replay(data: Any) -> Session:
    """Build a new Session from saved data, checking its shape and every move."""
    if not isinstance(data, dict):
        raise TypeError("expected an object")
    if data.get("opponent") not in ("human", "computer"):
        raise ValueError("unknown opponent")
    moves = parse_moves(data.get("moves"))
    redo = parse_moves(data.get("redo"))
    session = Session(data["opponent"])
    for source, target, promotion in moves:
        if promotion is not None:
            raise ValueError("promotion is not supported")
        session.play(source, target)
    session.redo = redo
    return session


def parse_moves(value: Any) -> list[Move]:
    if not isinstance(value, list):
        raise TypeError("expected a list of moves")
    moves: list[Move] = []
    for item in value:
        if not (
            isinstance(item, list)
            and len(item) == 3
            and isinstance(item[0], str)
            and isinstance(item[1], str)
            and (item[2] is None or isinstance(item[2], str))
        ):
            raise ValueError(f"bad move {item!r}")
        moves.append((item[0], item[1], item[2]))
    return moves
