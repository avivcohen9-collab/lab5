"""Checks for the lab's undo and save/load features, and how they combine.

Expected results come only from the README's lab requirements:

* Undo restores captured pieces and the side to move. Undo at the beginning does nothing.
* Move notation describes the currently played continuation.
* Save/load restores the game in a fresh instance, including whether the opponent is a
  person or the computer, and keeps enough information to undo moves made before saving.
* New game clears the previous game.

Not covered here until the team decides: what undo does against the computer, undo after
the game has ended, loading into a game in progress, and bad saved data.
"""

import json

import pytest

from game import new_position
from session import Session


# --- API adapters ---------------------------------------------------------------------
# Assumed API, to be confirmed with the partner implementing save/load. If the agreed API
# differs, change only these three functions.

def undo(session):
    """Undo one move. Assumed: an "undo" action that returns the view."""
    return session.dispatch({"action": "undo"})


def save(session):
    """Save the game. Assumed: a "save" action whose view carries the data in "saved"."""
    data = session.dispatch({"action": "save"})["saved"]
    # Assumed: saved data is JSON, so it can outlive the process. The round trip also
    # keeps the loaded game from sharing objects with the saved one.
    return json.loads(json.dumps(data))


def load_fresh(data):
    """Load saved data into a fresh instance, as after a server restart.

    Assumed: a "load" action that takes the data in "saved".
    """
    session = Session()
    session.dispatch({"action": "load", "saved": data})
    return session


# --- Helpers --------------------------------------------------------------------------

def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def state(session):
    """The game as a player sees it."""
    view = session.view()
    return {"board": dict(view["board"]), "turn": view["turn"],
            "moves": list(view["moves"]), "opponent": view["opponent"],
            "status": view["status"], "winner": view["winner"]}


def play_recording(session, moves):
    """Play moves and return the state before each one, oldest first."""
    history = []
    for step in moves:
        history.append(state(session))
        play(session, step)
    return history


def assert_at_start(session, opponent="human"):
    view = session.view()
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["opponent"] == opponent


# Both sides capture: e4xd5 (white takes a pawn), d8xd5 (black takes a pawn),
# d5xa2 (black takes a pawn). The last position is not check.
TWO_SIDED_CAPTURES = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"),
                      ("b1", "c3"), ("d5", "a2")]


# --- Undo -----------------------------------------------------------------------------

def test_undo_takes_back_only_the_last_move():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    before = state(session)
    play(session, ("g1", "f3"))

    view = undo(session)
    assert state(session) == before
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "e7-e5"]
    assert view["board"]["g1"] == "wN"
    assert "f3" not in view["board"]


def test_undo_at_the_start_does_nothing():
    session = Session()
    for _ in range(3):
        undo(session)
        assert_at_start(session)


@pytest.mark.parametrize("moves,capturer,restored", [
    # White's e4 pawn takes black's d5 pawn.
    ([("e2", "e4"), ("d7", "d5"), ("e4", "d5")], ("e4", "wP"), ("d5", "bP")),
    # Black's d5 pawn takes white's e4 pawn.
    ([("e2", "e4"), ("d7", "d5"), ("a2", "a3"), ("d5", "e4")], ("d5", "bP"), ("e4", "wP")),
], ids=["white-captures", "black-captures"])
def test_undo_restores_the_captured_piece(moves, capturer, restored):
    session = Session()
    play(session, *moves[:-1])
    before = state(session)
    play(session, moves[-1])
    assert len(session.view()["board"]) == 31

    view = undo(session)
    assert view["board"][capturer[0]] == capturer[1]
    assert view["board"][restored[0]] == restored[1]
    assert len(view["board"]) == 32
    assert view["turn"] == before["turn"]
    assert state(session) == before


def test_repeated_undo_walks_back_to_the_start():
    session = Session()
    history = play_recording(session, TWO_SIDED_CAPTURES)
    assert len(session.view()["board"]) == 29

    for expected in reversed(history):
        undo(session)
        assert state(session) == expected
    undo(session)
    assert_at_start(session)


def test_move_after_undo_replaces_the_continuation():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    undo(session)
    play(session, ("d7", "d5"))

    view = session.view()
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert view["board"]["e7"] == "bP"
    assert view["board"]["d5"] == "bP"
    assert "e5" not in view["board"]
    assert "d7" not in view["board"]
    assert view["turn"] == "w"


def test_new_game_clears_undo_history():
    session = Session()
    play(session, *TWO_SIDED_CAPTURES[:3])
    session.dispatch({"action": "new"})
    undo(session)
    assert_at_start(session)


# --- Save and load --------------------------------------------------------------------

def test_load_restores_the_full_game_state():
    # Mid-game after captures by both sides, ending in check: d5-e5+ along the open e-file.
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"),
         ("b1", "c3"), ("d5", "e5"))
    saved = state(session)
    assert saved["status"] == "check"

    restored = load_fresh(save(session))
    assert state(restored) == saved
    assert restored.view()["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5",
                                        "b1-c3", "d5-e5+"]
    assert restored.view()["turn"] == "w"
    assert len(restored.view()["board"]) == 30


@pytest.mark.parametrize("opponent", ["human", "computer"])
def test_load_restores_the_opponent(opponent):
    session = Session()
    session.dispatch({"action": "new", "opponent": opponent})
    play(session, ("e2", "e4"))

    restored = load_fresh(save(session))
    assert restored.view()["opponent"] == opponent
    assert restored.view()["moves"] == ["e2-e4"]
    if opponent == "computer":
        with pytest.raises(ValueError):
            play(restored, ("e7", "e5"))
        view = restored.dispatch({"action": "computer-move"})
        assert view["turn"] == "w"
        assert len(view["moves"]) == 2
    else:
        with pytest.raises(ValueError):
            restored.dispatch({"action": "computer-move"})
        play(restored, ("e7", "e5"))
        assert restored.view()["moves"] == ["e2-e4", "e7-e5"]


# --- Save/load combined with undo -----------------------------------------------------

def test_undo_after_load_takes_back_a_capture_made_before_saving():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"))
    before_capture = state(session)
    play(session, ("e4", "d5"))

    restored = load_fresh(save(session))
    view = undo(restored)
    assert state(restored) == before_capture
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e4"] == "wP"
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5"]


def test_repeated_undo_after_load_reaches_the_start():
    session = Session()
    history = play_recording(session, TWO_SIDED_CAPTURES)

    restored = load_fresh(save(session))
    for expected in reversed(history):
        undo(restored)
        assert state(restored) == expected
    undo(restored)
    assert_at_start(restored)


def test_undo_spans_moves_before_and_after_load():
    session = Session()
    history = play_recording(session, [("e2", "e4"), ("e7", "e5")])
    restored = load_fresh(save(session))
    history += play_recording(restored, [("g1", "f3")])

    for expected in reversed(history):
        undo(restored)
        assert state(restored) == expected
    assert_at_start(restored)


def test_save_after_undo_saves_the_undone_position_and_its_history():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    undo(session)
    after_undo = state(session)

    restored = load_fresh(save(session))
    assert state(restored) == after_undo
    assert restored.view()["moves"] == ["e2-e4", "e7-e5"]
    undo(restored)
    assert restored.view()["moves"] == ["e2-e4"]
    assert restored.view()["turn"] == "b"


def test_new_game_after_load_clears_undo_history():
    session = Session()
    play(session, *TWO_SIDED_CAPTURES[:3])

    restored = load_fresh(save(session))
    restored.dispatch({"action": "new"})
    undo(restored)
    assert_at_start(restored)
