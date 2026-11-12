"""Checks for the lab's undo and save/load features, and how they combine.

Expected results come only from the README's lab requirements:

* Undo restores captured pieces and the side to move. Undo at the beginning does nothing.
* Move notation describes the currently played continuation.
* Save/load restores the game in a fresh instance, including whether the opponent is a
  person or the computer, and keeps enough information to undo moves made before saving.
* New game clears the previous game.

And from the team decisions:

* Undo against the computer removes moves until it is the player's turn again, and
  always at least one of the player's moves (section 3).
* A missing or invalid save file shows an error and the current game doesn't change;
  the file holds {"opponent", "moves", "redo"} (section 6).
* Load replaces everything with the file, including the redo list; new game clears
  moves and redo (section 7).
"""

import json
from pathlib import Path
from typing import Any

import pytest

from game import new_position
from session import Session

# --- API adapters ---------------------------------------------------------------------
# Agreed API (team design and feature/save-load): "save" writes the game to
# game.save.json in the current directory and "load" reads it back; neither takes or
# returns the data through dispatch. If the API changes, change only these functions.

SAVE_FILE = Path("game.save.json")


@pytest.fixture(autouse=True)
def isolated_save_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run each test in its own empty directory so a real saved game is never touched."""
    monkeypatch.chdir(tmp_path)


def undo(session):
    """Undo one move. Assumed: an "undo" action that returns the view."""
    return session.dispatch({"action": "undo"})


def save(session: Session) -> Any:
    """Save the game with the "save" action and return what was written to the file."""
    session.dispatch({"action": "save"})
    # The saved game is JSON, so it can outlive the process.
    return json.loads(SAVE_FILE.read_text())


def load_fresh(data: Any) -> Session:
    """Load saved data into a fresh instance, as after a server restart.

    The data is written to the save file and read back with the "load" action.
    """
    SAVE_FILE.write_text(json.dumps(data))
    session = Session()
    session.dispatch({"action": "load"})
    return session


# --- Helpers --------------------------------------------------------------------------


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def state(session):
    """The game as a player sees it."""
    view = session.view()
    return {
        "board": dict(view["board"]),
        "turn": view["turn"],
        "moves": list(view["moves"]),
        "opponent": view["opponent"],
        "status": view["status"],
        "winner": view["winner"],
    }


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
TWO_SIDED_CAPTURES = [
    ("e2", "e4"),
    ("d7", "d5"),
    ("e4", "d5"),
    ("d8", "d5"),
    ("b1", "c3"),
    ("d5", "a2"),
]


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


@pytest.mark.parametrize(
    "moves,capturer,restored",
    [
        # White's e4 pawn takes black's d5 pawn.
        ([("e2", "e4"), ("d7", "d5"), ("e4", "d5")], ("e4", "wP"), ("d5", "bP")),
        # Black's d5 pawn takes white's e4 pawn.
        (
            [("e2", "e4"), ("d7", "d5"), ("a2", "a3"), ("d5", "e4")],
            ("d5", "bP"),
            ("e4", "wP"),
        ),
    ],
    ids=["white-captures", "black-captures"],
)
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
    play(
        session,
        ("e2", "e4"),
        ("d7", "d5"),
        ("e4", "d5"),
        ("d8", "d5"),
        ("b1", "c3"),
        ("d5", "e5"),
    )
    saved = state(session)
    assert saved["status"] == "check"

    restored = load_fresh(save(session))
    assert state(restored) == saved
    assert restored.view()["moves"] == [
        "e2-e4",
        "d7-d5",
        "e4xd5",
        "d8xd5",
        "b1-c3",
        "d5-e5+",
    ]
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


# --- Undo against the computer (team decision, section 3) -----------------------------

# Scholar's mate: White (the player) mates with d1xf7, so the computer has no reply.
SCHOLARS_MATE = [
    ["e2", "e4", None],
    ["e7", "e5", None],
    ["f1", "c4", None],
    ["b8", "c6", None],
    ["d1", "h5", None],
    ["g8", "f6", None],
    ["h5", "f7", None],
]


def test_undo_against_the_computer_removes_the_reply_and_the_player_move():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 2

    undo(session)
    assert_at_start(session, opponent="computer")


def test_undo_against_the_computer_returns_to_the_player_turn():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    after_first_reply = state(session)
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})

    view = undo(session)
    assert state(session) == after_first_reply
    assert view["turn"] == "w"
    # The player can move again; the computer is not to move.
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})


def test_undo_after_the_player_mates_the_computer_removes_one_move():
    session = load_fresh({"opponent": "computer", "moves": SCHOLARS_MATE, "redo": []})
    assert session.view()["status"] == "checkmate"

    view = undo(session)
    assert view["status"] is None
    assert view["turn"] == "w"
    assert len(view["moves"]) == 6
    assert view["board"]["h5"] == "wQ"
    assert view["board"]["f7"] == "bP"


def test_undo_while_the_computer_is_to_move_removes_the_player_move():
    # Saved right after the player's move, before the computer replied.
    session = load_fresh(
        {"opponent": "computer", "moves": [["e2", "e4", None]], "redo": []}
    )
    undo(session)
    assert_at_start(session, opponent="computer")


def test_undo_at_the_start_against_the_computer_does_nothing():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    undo(session)
    assert_at_start(session, opponent="computer")


# --- Bad save files (team decision, section 6) ----------------------------------------


def test_load_without_a_save_file_is_an_error_and_keeps_the_game():
    session = Session()
    play(session, ("e2", "e4"))
    before = state(session)

    with pytest.raises(ValueError):
        session.dispatch({"action": "load"})
    assert state(session) == before


@pytest.mark.parametrize(
    "content",
    [
        "not json {",
        "[]",
        json.dumps({"moves": [], "redo": []}),
        json.dumps({"opponent": "robot", "moves": [], "redo": []}),
        json.dumps({"opponent": "human", "moves": "e2e4", "redo": []}),
        json.dumps({"opponent": "human", "moves": [["e2", "e4"]], "redo": []}),
        json.dumps({"opponent": "human", "moves": [["e2", "e5", None]], "redo": []}),
        json.dumps({"opponent": "human", "moves": [["z9", "e4", None]], "redo": []}),
        # White moves twice in a row.
        json.dumps(
            {
                "opponent": "human",
                "moves": [["e2", "e4", None], ["d2", "d4", None]],
                "redo": [],
            }
        ),
    ],
    ids=[
        "not-json",
        "not-an-object",
        "no-opponent",
        "unknown-opponent",
        "moves-not-a-list",
        "move-too-short",
        "illegal-move",
        "off-the-board",
        "wrong-side-to-move",
    ],
)
def test_invalid_save_file_is_an_error_and_keeps_the_game(content):
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    before = state(session)
    SAVE_FILE.write_text(content)

    with pytest.raises(ValueError):
        session.dispatch({"action": "load"})
    assert state(session) == before
    # The game goes on as before the failed load.
    assert session.dispatch({"action": "computer-move"})["turn"] == "w"
    undo(session)
    assert_at_start(session, opponent="computer")


def test_save_file_holds_the_opponent_moves_and_redo():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))

    saved = save(session)
    assert saved == {
        "opponent": "computer",
        "moves": [["e2", "e4", None]],
        "redo": [],
    }


# --- Redo list in the save file (team decision, section 7) ----------------------------

REDO = [["e7", "e5", None], ["g1", "f3", None]]


def test_load_restores_the_saved_redo_list():
    session = load_fresh(
        {"opponent": "human", "moves": [["e2", "e4", None]], "redo": REDO}
    )
    assert save(session)["redo"] == REDO


def test_load_replaces_a_game_in_progress():
    SAVE_FILE.write_text(
        json.dumps({"opponent": "human", "moves": [["e2", "e4", None]], "redo": REDO})
    )
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})

    session.dispatch({"action": "load"})
    assert session.view()["opponent"] == "human"
    assert session.view()["moves"] == ["e2-e4"]
    assert save(session)["redo"] == REDO


def test_new_game_clears_moves_and_redo():
    session = load_fresh(
        {"opponent": "human", "moves": [["e2", "e4", None]], "redo": REDO}
    )
    session.dispatch({"action": "new"})
    saved = save(session)
    assert saved["moves"] == []
    assert saved["redo"] == []
