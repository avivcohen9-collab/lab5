"""Application actions and information shown beside the board."""

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


class Session:
    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.opponent = opponent
        # The game history: everything else is rebuilt from it (see replay).
        self.moves: list[tuple[str, str, str | None]] = []
        self.redo: list[tuple[str, str, str | None]] = []

    def play(self, source, target):
        label = move(self.position, source, target)
        self.notation.append(label)
        self.moves.append((source, target, None))
        self.after_move()

    def replay(self) -> None:
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
        self.replay()

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
        else:
            raise ValueError("Unknown action")
        return self.view()
