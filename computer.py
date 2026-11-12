"""A computer opponent that looks one move ahead."""

import random

from game import PROMOTION_PIECES, copy_position, legal_moves, move, promotes, status

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
CHECKMATE = 1000


def candidate_moves(position):
    board, turn = position[:2]
    for source, piece in sorted(board.items()):
        if piece[0] == turn:
            for target in legal_moves(position, source):
                if promotes(position, source, target):
                    for piece in PROMOTION_PIECES:
                        yield (source, target, piece)
                else:
                    yield (source, target)


def evaluate(position, side):
    """Score a position for side: material, unless the game is over."""
    result = status(position)
    if result == "checkmate":
        return CHECKMATE if position[1] != side else -CHECKMATE
    if result == "stalemate":
        return 0
    return sum(
        VALUES[piece[1]] * (1 if piece[0] == side else -1)
        for piece in position[0].values()
    )


def choose_move(position, rng=random):
    """Return the move with the best score after it, or None if there is no move."""
    side = position[1]
    best, best_score = [], None
    for candidate in candidate_moves(position):
        trial = copy_position(position)
        move(trial, *candidate)
        score = evaluate(trial, side)
        if best_score is None or score > best_score:
            best, best_score = [candidate], score
        elif score == best_score:
            best.append(candidate)
    return rng.choice(best) if best else None
