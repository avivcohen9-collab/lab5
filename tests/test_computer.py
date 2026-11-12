import random

import pytest

from computer import choose_move, evaluate
from game import new_position
from session import Session


def test_takes_the_most_valuable_piece():
    position = [{"a1": "wK", "h8": "bK", "e5": "bR", "e2": "wQ", "b5": "wN"}, "b"]
    assert choose_move(position) == ("e5", "e2")


def test_prefers_checkmate_to_material():
    # b6xd4 wins a knight; Ra8-a1 is mate on the back rank.
    position = [
        {
            "g1": "wK",
            "f2": "wP",
            "g2": "wP",
            "h2": "wP",
            "d4": "wN",
            "g8": "bK",
            "a8": "bR",
            "b6": "bB",
        },
        "b",
    ]
    assert choose_move(position) == ("a8", "a1")


def test_scores_material_for_the_side():
    position = new_position()
    assert evaluate(position, "w") == 0
    del position[0]["d8"]
    assert evaluate(position, "w") == 9
    assert evaluate(position, "b") == -9


def test_no_move_when_the_game_is_over():
    position = [{"a8": "bK", "b6": "wQ", "c1": "wK"}, "b"]
    assert choose_move(position) is None


def test_ties_vary_with_the_random_source():
    moves = {choose_move(new_position(), random.Random(seed)) for seed in range(20)}
    assert len(moves) > 1


def test_new_game_against_the_computer():
    session = Session()
    view = session.dispatch({"action": "new", "opponent": "computer"})
    assert view["opponent"] == "computer"
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    with pytest.raises(ValueError):
        session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    view = session.dispatch({"action": "computer-move"})
    assert view["turn"] == "w"
    assert len(view["moves"]) == 2
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})


def test_two_player_game_has_no_computer():
    session = Session()
    assert session.view()["opponent"] == "human"
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "move", "source": "e7", "target": "e5"})


def test_new_game_resets_the_opponent():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "new"})
    assert session.view()["opponent"] == "human"
    with pytest.raises(ValueError):
        session.dispatch({"action": "new", "opponent": "robot"})
