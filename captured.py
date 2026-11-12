"""Captured pieces for the captured-pieces sidebar."""

from collections.abc import Iterable

from game import new_position


def captured_pieces(moves: Iterable[tuple[str, str, str | None]]) -> list[str]:
    """Pieces captured by the given already-legal moves, played from the start.

    A move captures whatever stands on its target square (this variant has no en
    passant). Counting captures move by move, rather than comparing piece counts with
    the starting position, keeps a promoted pawn from looking captured.
    """
    board: dict[str, str] = new_position()[0]
    captured: list[str] = []
    for source, target, promotion in moves:
        piece = board.pop(source)
        if target in board:
            captured.append(board[target])
        board[target] = piece[0] + promotion if promotion else piece
    return sorted(captured)
