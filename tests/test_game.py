import pytest

from game import copy_position, legal_moves, move, new_position, status, winner
from session import Session


def test_starting_moves_and_blocked_pieces():
    position = new_position()
    assert len(position[0]) == 32
    assert set(legal_moves(position, "e2")) == {"e3", "e4"}
    assert set(legal_moves(position, "b1")) == {"a3", "c3"}
    for source in ("a1", "c1", "d1", "e1", "e7"):
        assert legal_moves(position, source) == []


def test_capture_turn_and_illegal_move_is_atomic():
    position = new_position()
    move(position, "e2", "e4")
    before = copy_position(position)
    with pytest.raises(ValueError):
        move(position, "e4", "e5")
    assert position == before
    move(position, "d7", "d5")
    assert move(position, "e4", "d5") == "e4xd5"
    assert position[0]["d5"] == "wP"
    assert "e4" not in position[0]
    assert len(position[0]) == 31
    assert position[1] == "b"


@pytest.mark.parametrize(
    "kind,target,blocker", [("R", "d7", "d5"), ("B", "g7", "e5"), ("Q", "g4", "e4")]
)
def test_sliding_paths_and_own_pieces(kind, target, blocker):
    position = [{"a1": "wK", "h8": "bK", "d4": "w" + kind, blocker: "bP"}, "w"]
    assert blocker in legal_moves(position, "d4")
    assert target not in legal_moves(position, "d4")
    position[0][blocker] = "wP"
    assert blocker not in legal_moves(position, "d4")


def test_black_pawn_and_blocked_double_step():
    position = new_position()
    position[1] = "b"
    assert set(legal_moves(position, "d7")) == {"d6", "d5"}
    position[0]["d6"] = "wN"
    assert legal_moves(position, "d7") == []


@pytest.mark.parametrize("square", [None, "", "a9", "z1", 3])
def test_bad_squares(square):
    with pytest.raises(ValueError):
        legal_moves(new_position(), square)


def test_king_cannot_move_into_check():
    position = [{"e1": "wK", "d8": "bR", "h8": "bK"}, "w"]
    assert set(legal_moves(position, "e1")) == {"e2", "f1", "f2"}


def test_pinned_piece_cannot_leave_the_line():
    position = [{"e1": "wK", "e2": "wB", "e8": "bR", "a8": "bK"}, "w"]
    assert legal_moves(position, "e2") == []


def test_check_must_be_answered():
    position = [{"e1": "wK", "a2": "wR", "e8": "bR", "a8": "bK"}, "w"]
    assert status(position) == "check"
    assert legal_moves(position, "a2") == ["e2"]


def test_checkmate_finishes_game():
    position = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    assert move(position, "a1", "a8") == "a1-a8#"
    assert status(position) == "checkmate"
    assert winner(position) == "White"
    assert legal_moves(position, "g8") == []


def test_check_is_marked_in_notation():
    position = [{"e1": "wK", "a1": "wR", "e8": "bK"}, "w"]
    assert move(position, "a1", "a8") == "a1-a8+"
    assert status(position) == "check"
    assert winner(position) is None


def test_stalemate_is_a_draw():
    position = [{"a8": "bK", "b6": "wQ", "c1": "wK"}, "b"]
    assert status(position) == "stalemate"
    assert winner(position) is None


def test_action_notation_and_reset():
    session = Session()
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    assert session.view()["moves"] == ["e2-e4"]
    assert session.view()["status"] is None
    session.dispatch({"action": "new"})
    assert session.view()["moves"] == []
    assert session.position == new_position()


def test_promotion_setup_uses_real_moves():
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    assert len(session.notation) == 8
    assert session.position[0]["b7"] == "wP"
    assert session.position[0]["g2"] == "bP"
    assert "a8" in legal_moves(session.position, "b7")
