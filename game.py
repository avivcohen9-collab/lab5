"""Movement rules for the lab's chess variant.

Check, checkmate and stalemate follow standard chess. There is no castling and no
en passant.
"""

FILES = "abcdefgh"
BACK_ROW = "RNBQKBNR"


def new_position():
    board = {}
    for file, piece in zip(FILES, BACK_ROW):
        board[file + "1"] = "w" + piece
        board[file + "2"] = "wP"
        board[file + "7"] = "bP"
        board[file + "8"] = "b" + piece
    return [board, "w"]


def copy_position(position):
    """Copy the board and side to move."""
    return [position[0].copy(), position[1]]


def coordinates(square):
    if not isinstance(square, str) or len(square) != 2:
        raise ValueError("Expected a square such as e2")
    if square[0] not in FILES or square[1] not in "12345678":
        raise ValueError("Square is outside the board")
    return FILES.index(square[0]), int(square[1]) - 1


def other(side):
    return "b" if side == "w" else "w"


def in_check(board, side):
    king = next(
        (square for square, piece in board.items() if piece == side + "K"), None
    )
    return king is not None and any(
        king in reachable(board, square)
        for square, piece in board.items()
        if piece[0] != side
    )


def status(position):
    """Return "check", "checkmate", "stalemate", or None for the side to move."""
    board, turn = position[:2]
    check = in_check(board, turn)
    if any(
        legal_moves(position, square)
        for square, piece in board.items()
        if piece[0] == turn
    ):
        return "check" if check else None
    return "checkmate" if check else "stalemate"


def winner(position):
    if status(position) == "checkmate":
        return "White" if position[1] == "b" else "Black"
    return None


def legal_moves(position, source):
    """Moves for the side to move that do not leave its own king in check."""
    coordinates(source)
    board, turn = position[:2]
    piece = board.get(source)
    if not piece or piece[0] != turn:
        return []
    targets = []
    for target in reachable(board, source):
        trial = board.copy()
        trial[target] = trial.pop(source)
        if not in_check(trial, turn):
            targets.append(target)
    return targets


def reachable(board, source):
    """Squares the piece on source attacks or can move to, ignoring check."""
    piece = board[source]
    turn = piece[0]
    x, y = coordinates(source)
    targets = []
    for tx in range(8):
        for ty in range(8):
            target = FILES[tx] + str(ty + 1)
            occupant = board.get(target)
            if target == source or (occupant and occupant[0] == turn):
                continue
            dx, dy = tx - x, ty - y
            kind = piece[1]
            allowed = False
            if kind == "P":
                direction = 1 if turn == "w" else -1
                home = 1 if turn == "w" else 6
                allowed = (
                    (dx == 0 and dy == direction and not occupant)
                    or (
                        dx == 0
                        and dy == 2 * direction
                        and y == home
                        and not occupant
                        and FILES[x] + str(y + direction + 1) not in board
                    )
                    or (abs(dx) == 1 and dy == direction and bool(occupant))
                )
            elif kind == "N":
                allowed = (abs(dx), abs(dy)) in ((1, 2), (2, 1))
            elif kind == "K":
                allowed = max(abs(dx), abs(dy)) == 1
            else:
                diagonal = abs(dx) == abs(dy)
                straight = dx == 0 or dy == 0
                allowed = (
                    (kind == "B" and diagonal)
                    or (kind == "R" and straight)
                    or (kind == "Q" and (diagonal or straight))
                )
                if allowed:
                    sx = (dx > 0) - (dx < 0)
                    sy = (dy > 0) - (dy < 0)
                    for step in range(1, max(abs(dx), abs(dy))):
                        intermediate = FILES[x + step * sx] + str(y + step * sy + 1)
                        if intermediate in board:
                            allowed = False
                            break
            if allowed:
                targets.append(target)
    return targets


PROMOTION_PIECES = ("Q", "R", "B", "N")


def promotes(position, source, target):
    piece = position[0].get(source)
    return bool(piece) and piece[1] == "P" and target[1] in "18"


def move(position, source, target, promotion=None):
    """Apply a move in place. Return a short move label.

    A pawn reaching the last rank needs promotion: "Q", "R", "B" or "N".
    """
    coordinates(target)
    if target not in legal_moves(position, source):
        raise ValueError("That move is not allowed")
    promoting = promotes(position, source, target)
    if promoting and promotion not in PROMOTION_PIECES:
        raise ValueError("Choose a queen, rook, bishop or knight to promote to")
    if not promoting and promotion is not None:
        raise ValueError("Only a pawn reaching the last rank promotes")
    board = position[0]
    piece = board.pop(source)
    captured = board.get(target)
    board[target] = piece
    if promoting:
        board[target] = piece[0] + promotion
    position[1] = other(position[1])
    suffix = {"check": "+", "checkmate": "#"}.get(status(position), "")
    chosen = "=" + promotion if promoting else ""
    return source + ("x" if captured else "-") + target + chosen + suffix
